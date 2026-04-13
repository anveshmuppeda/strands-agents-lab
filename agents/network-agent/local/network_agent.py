"""
AWS Network Agent — Strands Agents SDK

Diagnoses AWS networking issues using AWS APIs. All checks are done by reading
AWS resource configurations — no local socket/ping calls.

Tools:
1. check_vpc_routes — Analyze route tables for internet/NAT/peering routes
2. check_nacl_rules — Check Network ACL inbound/outbound rules for a subnet
3. check_security_group — Check security group inbound/outbound rules
4. check_vpc_endpoints — List VPC endpoints (S3, DynamoDB, etc.)
5. check_subnet_details — Get subnet info (public/private, AZ, CIDR, available IPs)
6. check_reachability — Use VPC Reachability Analyzer to test path between two resources

Prerequisites:
  pip install -r requirements.txt
  aws configure
  Enable Claude model access in Amazon Bedrock console
"""

import os
import json
import time
import boto3
from strands import Agent, tool
from strands.models.bedrock import BedrockModel


# --- Model ---

model = BedrockModel(
    model_id="amazon.nova-pro-v1:0",
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    max_tokens=4096,
)


# --- Tools ---

@tool
def check_subnet_details(subnet_id: str) -> str:
    """Get details about a subnet — CIDR, availability zone, public/private, available IPs.

    Args:
        subnet_id: AWS Subnet ID (e.g., "subnet-0abc123def456")
    """
    try:
        ec2 = boto3.client("ec2")
        resp = ec2.describe_subnets(SubnetIds=[subnet_id])
        subnets = resp.get("Subnets", [])
        if not subnets:
            return f"❌ Subnet {subnet_id} not found"

        s = subnets[0]
        name = ""
        for tag in s.get("Tags", []):
            if tag["Key"] == "Name":
                name = tag["Value"]

        auto_public_ip = s.get("MapPublicIpOnLaunch", False)

        results = [
            f"Subnet: {subnet_id}",
            f"  Name: {name or '(no name tag)'}",
            f"  VPC: {s['VpcId']}",
            f"  CIDR: {s['CidrBlock']}",
            f"  Availability Zone: {s['AvailabilityZone']}",
            f"  Available IPs: {s['AvailableIpAddressCount']}",
            f"  Auto-assign public IP: {'Yes' if auto_public_ip else 'No'}",
            f"  State: {s['State']}",
        ]

        if auto_public_ip:
            results.append("  → This looks like a PUBLIC subnet (auto-assigns public IPs)")
        else:
            results.append("  → This looks like a PRIVATE subnet (no auto public IP)")

        return "\n".join(results)
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def check_vpc_routes(vpc_id: str, subnet_id: str = "") -> str:
    """Analyze route tables for a VPC or specific subnet. Shows internet gateway,
    NAT gateway, VPC peering, and transit gateway routes.

    Args:
        vpc_id: AWS VPC ID (e.g., "vpc-0abc123def456")
        subnet_id: Specific subnet to check (optional — if omitted, shows all route tables in the VPC)
    """
    try:
        ec2 = boto3.client("ec2")
        filters = [{"Name": "vpc-id", "Values": [vpc_id]}]
        if subnet_id:
            filters.append({"Name": "association.subnet-id", "Values": [subnet_id]})

        resp = ec2.describe_route_tables(Filters=filters)
        route_tables = resp.get("RouteTables", [])

        if not route_tables:
            # If subnet-specific filter returned nothing, try the main route table
            if subnet_id:
                resp = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
                route_tables = [rt for rt in resp.get("RouteTables", [])
                                if any(a.get("Main", False) for a in rt.get("Associations", []))]
                if route_tables:
                    return _format_route_tables(route_tables, f"(using main route table for VPC {vpc_id})")
            return f"❌ No route tables found for VPC {vpc_id}" + (f" subnet {subnet_id}" if subnet_id else "")

        return _format_route_tables(route_tables, "")
    except Exception as e:
        return f"❌ Error: {str(e)}"


def _format_route_tables(route_tables, note):
    results = []
    if note:
        results.append(note)
        results.append("")

    has_igw = False
    has_nat = False

    for rt in route_tables:
        rt_id = rt["RouteTableId"]
        rt_name = ""
        for tag in rt.get("Tags", []):
            if tag["Key"] == "Name":
                rt_name = tag["Value"]

        is_main = any(a.get("Main", False) for a in rt.get("Associations", []))
        label = f"{rt_id} ({rt_name})" if rt_name else rt_id
        if is_main:
            label += " [MAIN]"

        results.append(f"Route Table: {label}")

        for route in rt.get("Routes", []):
            dest = route.get("DestinationCidrBlock", route.get("DestinationPrefixListId", ""))
            state = route.get("State", "active")
            target = (
                route.get("GatewayId", "") or
                route.get("NatGatewayId", "") or
                route.get("VpcPeeringConnectionId", "") or
                route.get("TransitGatewayId", "") or
                route.get("NetworkInterfaceId", "") or
                "local"
            )

            icon = "✅" if state == "active" else "❌"

            if target.startswith("igw-"):
                has_igw = True
                results.append(f"  {icon} {dest} → Internet Gateway ({target})")
            elif target.startswith("nat-"):
                has_nat = True
                results.append(f"  {icon} {dest} → NAT Gateway ({target})")
            elif target.startswith("pcx-"):
                results.append(f"  {icon} {dest} → VPC Peering ({target})")
            elif target.startswith("tgw-"):
                results.append(f"  {icon} {dest} → Transit Gateway ({target})")
            elif target == "local":
                results.append(f"  {icon} {dest} → local (within VPC)")
            else:
                results.append(f"  {icon} {dest} → {target}")

        results.append("")

    results.append("--- Internet Access Summary ---")
    if has_igw:
        results.append("✅ Internet Gateway route found → PUBLIC subnet (direct internet access)")
    if has_nat:
        results.append("✅ NAT Gateway route found → PRIVATE subnet with outbound internet")
    if not has_igw and not has_nat:
        results.append("❌ No internet route → ISOLATED subnet (no internet access)")

    return "\n".join(results)


@tool
def check_nacl_rules(subnet_id: str) -> str:
    """Check Network ACL rules for a subnet. Shows inbound and outbound rules.

    Args:
        subnet_id: AWS Subnet ID (e.g., "subnet-0abc123def456")
    """
    try:
        ec2 = boto3.client("ec2")
        resp = ec2.describe_network_acls(
            Filters=[{"Name": "association.subnet-id", "Values": [subnet_id]}]
        )
        nacls = resp.get("NetworkAcls", [])
        if not nacls:
            return f"❌ No Network ACL found for subnet {subnet_id}"

        results = []
        for nacl in nacls:
            nacl_id = nacl["NetworkAclId"]
            is_default = nacl.get("IsDefault", False)
            results.append(f"Network ACL: {nacl_id}" + (" [DEFAULT]" if is_default else ""))
            results.append("")

            inbound = [e for e in nacl["Entries"] if not e["Egress"]]
            outbound = [e for e in nacl["Entries"] if e["Egress"]]

            results.append("INBOUND Rules:")
            for entry in sorted(inbound, key=lambda x: x["RuleNumber"]):
                results.append(_format_nacl_entry(entry))

            results.append("")
            results.append("OUTBOUND Rules:")
            for entry in sorted(outbound, key=lambda x: x["RuleNumber"]):
                results.append(_format_nacl_entry(entry))

        return "\n".join(results)
    except Exception as e:
        return f"❌ Error: {str(e)}"


def _format_nacl_entry(entry):
    rule = entry["RuleNumber"]
    action = entry["RuleAction"].upper()
    cidr = entry.get("CidrBlock", entry.get("Ipv6CidrBlock", "N/A"))
    protocol = entry.get("Protocol", "-1")

    proto_map = {"-1": "ALL", "6": "TCP", "17": "UDP", "1": "ICMP"}
    proto_name = proto_map.get(protocol, protocol)

    port_range = entry.get("PortRange", {})
    if port_range:
        from_port = port_range.get("From", "*")
        to_port = port_range.get("To", "*")
        ports = f"{from_port}" if from_port == to_port else f"{from_port}-{to_port}"
    else:
        ports = "ALL"

    icon = "✅" if action == "ALLOW" else "🚫"
    if rule == 32767:
        return f"  {icon} Rule *: {action} {proto_name} ports={ports} from {cidr} (default deny)"
    return f"  {icon} Rule {rule}: {action} {proto_name} ports={ports} from {cidr}"


@tool
def check_security_group(security_group_id: str) -> str:
    """Check security group inbound and outbound rules.

    Args:
        security_group_id: AWS Security Group ID (e.g., "sg-0abc123def456")
    """
    try:
        ec2 = boto3.client("ec2")
        resp = ec2.describe_security_groups(GroupIds=[security_group_id])
        sgs = resp.get("SecurityGroups", [])
        if not sgs:
            return f"❌ Security group {security_group_id} not found"

        sg = sgs[0]
        sg_name = sg.get("GroupName", "")
        vpc_id = sg.get("VpcId", "")

        results = [
            f"Security Group: {security_group_id}",
            f"  Name: {sg_name}",
            f"  VPC: {vpc_id}",
            f"  Description: {sg.get('Description', '')}",
            "",
        ]

        # Inbound rules
        results.append("INBOUND Rules:")
        if sg.get("IpPermissions"):
            for rule in sg["IpPermissions"]:
                results.extend(_format_sg_rule(rule, "inbound"))
        else:
            results.append("  (none — all inbound traffic is blocked)")

        results.append("")

        # Outbound rules
        results.append("OUTBOUND Rules:")
        if sg.get("IpPermissionsEgress"):
            for rule in sg["IpPermissionsEgress"]:
                results.extend(_format_sg_rule(rule, "outbound"))
        else:
            results.append("  (none — all outbound traffic is blocked)")

        return "\n".join(results)
    except Exception as e:
        return f"❌ Error: {str(e)}"


def _format_sg_rule(rule, direction):
    lines = []
    protocol = rule.get("IpProtocol", "-1")
    proto_name = "ALL" if protocol == "-1" else protocol.upper()

    from_port = rule.get("FromPort", "*")
    to_port = rule.get("ToPort", "*")
    if protocol == "-1":
        ports = "ALL"
    elif from_port == to_port:
        ports = str(from_port)
    else:
        ports = f"{from_port}-{to_port}"

    # Common port names
    port_label = ""
    common_ports = {22: "SSH", 80: "HTTP", 443: "HTTPS", 3306: "MySQL",
                    5432: "PostgreSQL", 6379: "Redis", 27017: "MongoDB",
                    8080: "HTTP-Alt", 3389: "RDP"}
    if from_port == to_port and from_port in common_ports:
        port_label = f" ({common_ports[from_port]})"

    # IP ranges
    for ip_range in rule.get("IpRanges", []):
        cidr = ip_range.get("CidrIp", "")
        desc = ip_range.get("Description", "")
        source = f"{cidr}" + (f" — {desc}" if desc else "")
        lines.append(f"  ✅ {proto_name} port {ports}{port_label} from {source}")

    # IPv6 ranges
    for ip_range in rule.get("Ipv6Ranges", []):
        cidr = ip_range.get("CidrIpv6", "")
        lines.append(f"  ✅ {proto_name} port {ports}{port_label} from {cidr}")

    # Security group references
    for sg_ref in rule.get("UserIdGroupPairs", []):
        ref_id = sg_ref.get("GroupId", "")
        desc = sg_ref.get("Description", "")
        source = f"{ref_id}" + (f" — {desc}" if desc else "")
        lines.append(f"  ✅ {proto_name} port {ports}{port_label} from SG {source}")

    # Prefix lists
    for pl in rule.get("PrefixListIds", []):
        lines.append(f"  ✅ {proto_name} port {ports}{port_label} from prefix-list {pl.get('PrefixListId', '')}")

    if not lines:
        lines.append(f"  ✅ {proto_name} port {ports}{port_label} from (all sources)")

    return lines


@tool
def check_vpc_endpoints(vpc_id: str) -> str:
    """List VPC endpoints in a VPC. VPC endpoints allow private access to AWS services
    (S3, DynamoDB, etc.) without going through the internet.

    Args:
        vpc_id: AWS VPC ID (e.g., "vpc-0abc123def456")
    """
    try:
        ec2 = boto3.client("ec2")
        resp = ec2.describe_vpc_endpoints(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )
        endpoints = resp.get("VpcEndpoints", [])

        if not endpoints:
            return (
                f"No VPC endpoints found in {vpc_id}\n"
                f"This means all AWS service traffic goes through the internet/NAT.\n"
                f"Consider adding Gateway endpoints for S3 and DynamoDB (free) to reduce NAT costs."
            )

        results = [f"VPC Endpoints in {vpc_id}:", ""]
        for ep in endpoints:
            ep_id = ep["VpcEndpointId"]
            service = ep["ServiceName"]
            ep_type = ep["VpcEndpointType"]
            state = ep["State"]

            icon = "✅" if state == "available" else "⚠️"
            results.append(f"{icon} {ep_id}")
            results.append(f"   Service: {service}")
            results.append(f"   Type: {ep_type}")
            results.append(f"   State: {state}")

            if ep_type == "Gateway":
                route_tables = ep.get("RouteTableIds", [])
                results.append(f"   Route tables: {', '.join(route_tables) if route_tables else 'none'}")
            elif ep_type == "Interface":
                subnets = ep.get("SubnetIds", [])
                results.append(f"   Subnets: {', '.join(subnets) if subnets else 'none'}")
                sgs = [g["GroupId"] for g in ep.get("Groups", [])]
                results.append(f"   Security groups: {', '.join(sgs) if sgs else 'none'}")

            results.append("")

        return "\n".join(results)
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def check_reachability(
    source_type: str,
    source_id: str,
    destination_type: str,
    destination_id: str,
    destination_port: int = 443,
    protocol: str = "tcp",
) -> str:
    """Use VPC Reachability Analyzer to test if network path exists between two AWS resources.
    This creates a Network Insights Path and runs an analysis.

    Args:
        source_type: Source resource type — "instance", "network-interface", "internet-gateway", "vpn-gateway", "transit-gateway"
        source_id: Source resource ID (e.g., "i-0abc123", "igw-0abc123", "eni-0abc123")
        destination_type: Destination resource type — same options as source_type
        destination_id: Destination resource ID
        destination_port: Destination port to test (default: 443)
        protocol: Protocol to test — "tcp" or "udp" (default: "tcp")
    """
    try:
        ec2 = boto3.client("ec2")

        # Create Network Insights Path
        path_resp = ec2.create_network_insights_path(
            Source=source_id,
            Destination=destination_id,
            Protocol=protocol,
            DestinationPort=destination_port,
            TagSpecifications=[{
                "ResourceType": "network-insights-path",
                "Tags": [{"Key": "Name", "Value": "agent-reachability-check"}]
            }]
        )
        path_id = path_resp["NetworkInsightsPath"]["NetworkInsightsPathId"]

        # Start analysis
        analysis_resp = ec2.start_network_insights_analysis(
            NetworkInsightsPathId=path_id
        )
        analysis_id = analysis_resp["NetworkInsightsAnalysis"]["NetworkInsightsAnalysisId"]

        # Wait for analysis to complete (max 60 seconds)
        for _ in range(12):
            time.sleep(5)
            status_resp = ec2.describe_network_insights_analyses(
                NetworkInsightsAnalysisIds=[analysis_id]
            )
            analysis = status_resp["NetworkInsightsAnalyses"][0]
            status = analysis["Status"]

            if status == "succeeded":
                break
            elif status == "failed":
                # Clean up
                ec2.delete_network_insights_path(NetworkInsightsPathId=path_id)
                return f"❌ Reachability analysis failed: {analysis.get('StatusMessage', 'unknown error')}"

        reachable = analysis.get("NetworkPathFound", False)

        results = [
            f"Reachability Analysis: {source_id} → {destination_id}:{destination_port}/{protocol}",
            "",
        ]

        if reachable:
            results.append(f"✅ PATH EXISTS — {source_id} CAN reach {destination_id} on port {destination_port}")
        else:
            results.append(f"❌ PATH BLOCKED — {source_id} CANNOT reach {destination_id} on port {destination_port}")

            # Show explanations
            explanations = analysis.get("Explanations", [])
            if explanations:
                results.append("")
                results.append("Blocking reasons:")
                for exp in explanations:
                    component = exp.get("Component", {})
                    comp_id = component.get("Id", "unknown")
                    reason = exp.get("ExplanationCode", "unknown")
                    results.append(f"  ❌ {comp_id}: {reason}")

        # Show the path
        forward_path = analysis.get("ForwardPathComponents", [])
        if forward_path:
            results.append("")
            results.append("Network path:")
            for i, comp in enumerate(forward_path):
                comp_id = comp.get("Component", {}).get("Id", "?")
                comp_name = comp.get("Component", {}).get("Name", "")
                label = f"{comp_id} ({comp_name})" if comp_name else comp_id
                results.append(f"  {i+1}. {label}")

        # Clean up the path resource
        try:
            ec2.delete_network_insights_path(NetworkInsightsPathId=path_id)
        except Exception:
            pass

        return "\n".join(results)
    except Exception as e:
        return f"❌ Error: {str(e)}"


# --- System Prompt ---

SYSTEM_PROMPT = """You are an AWS network diagnostics agent. All checks use AWS APIs — you
analyze AWS resource configurations to diagnose networking issues.

You have six tools:

1. **check_subnet_details** — Get subnet info (CIDR, AZ, public/private, available IPs)
2. **check_vpc_routes** — Analyze route tables for internet, NAT, peering, transit gateway routes
3. **check_nacl_rules** — Check Network ACL inbound/outbound rules for a subnet
4. **check_security_group** — Check security group inbound/outbound rules
5. **check_vpc_endpoints** — List VPC endpoints (S3, DynamoDB, etc.)
6. **check_reachability** — Use VPC Reachability Analyzer to test path between two resources

When diagnosing connectivity issues, follow this order:
1. Start with check_subnet_details to understand if it's public or private
2. Check check_vpc_routes to see if there's an internet/NAT route
3. Check check_nacl_rules for any blocking rules
4. Check check_security_group for the relevant security group
5. Use check_reachability for definitive path analysis between two resources

Explain results clearly:
- If a subnet has no internet route → suggest adding IGW (public) or NAT Gateway (private)
- If a NACL is blocking → identify the specific rule and suggest a fix
- If a security group is missing a rule → suggest the exact rule to add
- If there's no VPC endpoint → suggest adding one for cost savings (S3/DynamoDB endpoints are free)
- Always mention which specific resource (route table, NACL, SG) is causing the issue
"""


# --- Agent ---

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[
        check_subnet_details,
        check_vpc_routes,
        check_nacl_rules,
        check_security_group,
        check_vpc_endpoints,
        check_reachability,
    ],
)


# --- Run ---

if __name__ == "__main__":
    print("AWS Network Agent (type 'quit' to exit)")
    print("-" * 45)

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if not user_input:
            continue

        print("\nAgent: ", end="")
        response = agent(user_input)
        print()
