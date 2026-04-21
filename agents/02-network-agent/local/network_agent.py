"""
AWS Network Agent — Strands Agents SDK

Diagnoses AWS networking issues using AWS APIs. All checks are done by reading
AWS resource configurations — no local socket/ping calls.

Tools:
1. check_vpc_routes      — Analyze route tables for internet/NAT/peering routes
2. check_nacl_rules      — Check Network ACL inbound/outbound rules for a subnet
3. check_security_group  — Check security group inbound/outbound rules
4. check_vpc_endpoints   — List VPC endpoints (S3, DynamoDB, etc.)
5. check_subnet_details  — Get subnet info (public/private, AZ, CIDR, available IPs)
6. check_reachability    — Use VPC Reachability Analyzer to test path between two resources

Prerequisites:
  pip install -r requirements.txt
  aws configure
  Enable model access in Amazon Bedrock console
"""

import os
import json
import time
import logging
import boto3
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# --- Model ---

model = BedrockModel(
    model_id="amazon.nova-pro-v1:0",
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    max_tokens=4096,
)


# --- Helper functions ---

def _get_name_tag(tags: list) -> str:
    return next((t["Value"] for t in tags if t["Key"] == "Name"), "")


def _resolve_route_target(route: dict) -> str:
    return (
        route.get("GatewayId") or
        route.get("NatGatewayId") or
        route.get("VpcPeeringConnectionId") or
        route.get("TransitGatewayId") or
        route.get("NetworkInterfaceId") or
        "local"
    )


def _format_nacl_entry(entry: dict) -> str:
    rule = entry["RuleNumber"]
    action = entry["RuleAction"].upper()
    cidr = entry.get("CidrBlock", entry.get("Ipv6CidrBlock", "N/A"))
    protocol = entry.get("Protocol", "-1")
    proto_name = {"-1": "ALL", "6": "TCP", "17": "UDP", "1": "ICMP"}.get(protocol, protocol)

    port_range = entry.get("PortRange", {})
    if port_range:
        from_port = port_range.get("From", "*")
        to_port = port_range.get("To", "*")
        ports = str(from_port) if from_port == to_port else f"{from_port}-{to_port}"
    else:
        ports = "ALL"

    icon = "✅" if action == "ALLOW" else "🚫"
    if rule == 32767:
        return f"  {icon} Rule *: {action} {proto_name} ports={ports} from {cidr} (default deny)"
    return f"  {icon} Rule {rule}: {action} {proto_name} ports={ports} from {cidr}"


def _format_sg_rule(rule: dict) -> list:
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

    common_ports = {
        22: "SSH", 80: "HTTP", 443: "HTTPS", 3306: "MySQL",
        5432: "PostgreSQL", 6379: "Redis", 27017: "MongoDB",
        8080: "HTTP-Alt", 3389: "RDP",
    }
    port_label = f" ({common_ports[from_port]})" if from_port == to_port and from_port in common_ports else ""

    for ip_range in rule.get("IpRanges", []):
        cidr = ip_range.get("CidrIp", "")
        desc = ip_range.get("Description", "")
        source = f"{cidr}" + (f" — {desc}" if desc else "")
        lines.append(f"  ✅ {proto_name} port {ports}{port_label} from {source}")

    for ip_range in rule.get("Ipv6Ranges", []):
        lines.append(f"  ✅ {proto_name} port {ports}{port_label} from {ip_range.get('CidrIpv6', '')}")

    for sg_ref in rule.get("UserIdGroupPairs", []):
        ref_id = sg_ref.get("GroupId", "")
        desc = sg_ref.get("Description", "")
        source = f"{ref_id}" + (f" — {desc}" if desc else "")
        lines.append(f"  ✅ {proto_name} port {ports}{port_label} from SG {source}")

    for pl in rule.get("PrefixListIds", []):
        lines.append(f"  ✅ {proto_name} port {ports}{port_label} from prefix-list {pl.get('PrefixListId', '')}")

    if not lines:
        lines.append(f"  ✅ {proto_name} port {ports}{port_label} from (all sources)")

    return lines


def _format_route_table(rt: dict) -> tuple[list, bool, bool]:
    """Format a single route table. Returns (lines, has_igw, has_nat)."""
    lines = []
    has_igw = False
    has_nat = False

    rt_id = rt["RouteTableId"]
    rt_name = _get_name_tag(rt.get("Tags", []))
    is_main = any(a.get("Main", False) for a in rt.get("Associations", []))
    label = f"{rt_id} ({rt_name})" if rt_name else rt_id
    if is_main:
        label += " [MAIN]"

    lines.append(f"Route Table: {label}")

    for route in rt.get("Routes", []):
        dest = route.get("DestinationCidrBlock", route.get("DestinationPrefixListId", ""))
        state = route.get("State", "active")
        target = _resolve_route_target(route)
        icon = "✅" if state == "active" else "❌"

        if target.startswith("igw-"):
            has_igw = True
            lines.append(f"  {icon} {dest} → Internet Gateway ({target})")
        elif target.startswith("nat-"):
            has_nat = True
            lines.append(f"  {icon} {dest} → NAT Gateway ({target})")
        elif target.startswith("pcx-"):
            lines.append(f"  {icon} {dest} → VPC Peering ({target})")
        elif target.startswith("tgw-"):
            lines.append(f"  {icon} {dest} → Transit Gateway ({target})")
        elif target == "local":
            lines.append(f"  {icon} {dest} → local (within VPC)")
        else:
            lines.append(f"  {icon} {dest} → {target}")

    lines.append("")
    return lines, has_igw, has_nat


# --- Tools ---

@tool
def check_subnet_details(subnet_id: str) -> str:
    """Get details about a subnet — CIDR, availability zone, public/private, available IPs.

    Args:
        subnet_id: AWS Subnet ID (e.g., "subnet-0abc123def456")
    """
    try:
        ec2 = boto3.client("ec2", region_name=AWS_REGION)
        resp = ec2.describe_subnets(SubnetIds=[subnet_id])
        subnets = resp.get("Subnets", [])
        if not subnets:
            return f"❌ Subnet {subnet_id} not found"

        s = subnets[0]
        auto_public_ip = s.get("MapPublicIpOnLaunch", False)
        lines = [
            f"Subnet: {subnet_id}",
            f"  Name: {_get_name_tag(s.get('Tags', [])) or '(no name tag)'}",
            f"  VPC: {s['VpcId']}",
            f"  CIDR: {s['CidrBlock']}",
            f"  Availability Zone: {s['AvailabilityZone']}",
            f"  Available IPs: {s['AvailableIpAddressCount']}",
            f"  Auto-assign public IP: {'Yes' if auto_public_ip else 'No'}",
            f"  State: {s['State']}",
            f"  → {'PUBLIC subnet (auto-assigns public IPs)' if auto_public_ip else 'PRIVATE subnet (no auto public IP)'}",
        ]
        return "\n".join(lines)
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
        ec2 = boto3.client("ec2", region_name=AWS_REGION)
        filters = [{"Name": "vpc-id", "Values": [vpc_id]}]
        if subnet_id:
            filters.append({"Name": "association.subnet-id", "Values": [subnet_id]})

        resp = ec2.describe_route_tables(Filters=filters)
        route_tables = resp.get("RouteTables", [])

        if not route_tables and subnet_id:
            # Fall back to the main route table for the VPC
            resp = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
            route_tables = [
                rt for rt in resp.get("RouteTables", [])
                if any(a.get("Main", False) for a in rt.get("Associations", []))
            ]
            if not route_tables:
                return f"❌ No route tables found for VPC {vpc_id} subnet {subnet_id}"

        if not route_tables:
            return f"❌ No route tables found for VPC {vpc_id}"

        results = []
        all_has_igw = False
        all_has_nat = False

        for rt in route_tables:
            lines, has_igw, has_nat = _format_route_table(rt)
            results.extend(lines)
            all_has_igw = all_has_igw or has_igw
            all_has_nat = all_has_nat or has_nat

        results.append("--- Internet Access Summary ---")
        if all_has_igw:
            results.append("✅ Internet Gateway route found → PUBLIC subnet (direct internet access)")
        if all_has_nat:
            results.append("✅ NAT Gateway route found → PRIVATE subnet with outbound internet")
        if not all_has_igw and not all_has_nat:
            results.append("❌ No internet route → ISOLATED subnet (no internet access)")

        return "\n".join(results)
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def check_nacl_rules(subnet_id: str) -> str:
    """Check Network ACL rules for a subnet. Shows inbound and outbound rules.

    Args:
        subnet_id: AWS Subnet ID (e.g., "subnet-0abc123def456")
    """
    try:
        ec2 = boto3.client("ec2", region_name=AWS_REGION)
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
            results.extend(_format_nacl_entry(e) for e in sorted(inbound, key=lambda x: x["RuleNumber"]))
            results.append("")
            results.append("OUTBOUND Rules:")
            results.extend(_format_nacl_entry(e) for e in sorted(outbound, key=lambda x: x["RuleNumber"]))

        return "\n".join(results)
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def check_security_group(security_group_id: str) -> str:
    """Check security group inbound and outbound rules.

    Args:
        security_group_id: AWS Security Group ID (e.g., "sg-0abc123def456")
    """
    try:
        ec2 = boto3.client("ec2", region_name=AWS_REGION)
        resp = ec2.describe_security_groups(GroupIds=[security_group_id])
        sgs = resp.get("SecurityGroups", [])
        if not sgs:
            return f"❌ Security group {security_group_id} not found"

        sg = sgs[0]
        results = [
            f"Security Group: {security_group_id}",
            f"  Name: {sg.get('GroupName', '')}",
            f"  VPC: {sg.get('VpcId', '')}",
            f"  Description: {sg.get('Description', '')}",
            "",
            "INBOUND Rules:",
        ]

        if sg.get("IpPermissions"):
            results.extend(line for rule in sg["IpPermissions"] for line in _format_sg_rule(rule))
        else:
            results.append("  (none — all inbound traffic is blocked)")

        results.extend(["", "OUTBOUND Rules:"])

        if sg.get("IpPermissionsEgress"):
            results.extend(line for rule in sg["IpPermissionsEgress"] for line in _format_sg_rule(rule))
        else:
            results.append("  (none — all outbound traffic is blocked)")

        return "\n".join(results)
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def check_vpc_endpoints(vpc_id: str) -> str:
    """List VPC endpoints in a VPC. VPC endpoints allow private access to AWS services
    (S3, DynamoDB, etc.) without going through the internet.

    Args:
        vpc_id: AWS VPC ID (e.g., "vpc-0abc123def456")
    """
    try:
        ec2 = boto3.client("ec2", region_name=AWS_REGION)
        resp = ec2.describe_vpc_endpoints(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )
        endpoints = resp.get("VpcEndpoints", [])

        if not endpoints:
            return (
                f"No VPC endpoints found in {vpc_id}\n"
                f"All AWS service traffic goes through the internet/NAT.\n"
                f"Consider adding Gateway endpoints for S3 and DynamoDB (free) to reduce NAT costs."
            )

        results = [f"VPC Endpoints in {vpc_id}:", ""]
        for ep in endpoints:
            icon = "✅" if ep["State"] == "available" else "⚠️"
            results.append(f"{icon} {ep['VpcEndpointId']}")
            results.append(f"   Service: {ep['ServiceName']}")
            results.append(f"   Type: {ep['VpcEndpointType']}")
            results.append(f"   State: {ep['State']}")

            if ep["VpcEndpointType"] == "Gateway":
                rts = ep.get("RouteTableIds", [])
                results.append(f"   Route tables: {', '.join(rts) if rts else 'none'}")
            elif ep["VpcEndpointType"] == "Interface":
                subnets = ep.get("SubnetIds", [])
                sgs = [g["GroupId"] for g in ep.get("Groups", [])]
                results.append(f"   Subnets: {', '.join(subnets) if subnets else 'none'}")
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
    """Use VPC Reachability Analyzer to test if a network path exists between two AWS resources.
    Creates a Network Insights Path and runs an analysis. Note: this incurs a small AWS cost per analysis.

    Args:
        source_type: Source resource type — "instance", "network-interface", "internet-gateway", "vpn-gateway", "transit-gateway"
        source_id: Source resource ID (e.g., "i-0abc123", "igw-0abc123", "eni-0abc123")
        destination_type: Destination resource type — same options as source_type
        destination_id: Destination resource ID
        destination_port: Destination port to test (default: 443)
        protocol: Protocol to test — "tcp" or "udp" (default: "tcp")
    """
    ec2 = boto3.client("ec2", region_name=AWS_REGION)
    path_id = None
    try:
        path_resp = ec2.create_network_insights_path(
            Source=source_id,
            Destination=destination_id,
            Protocol=protocol,
            DestinationPort=destination_port,
            TagSpecifications=[{
                "ResourceType": "network-insights-path",
                "Tags": [{"Key": "Name", "Value": "agent-reachability-check"}],
            }],
        )
        path_id = path_resp["NetworkInsightsPath"]["NetworkInsightsPathId"]

        analysis_resp = ec2.start_network_insights_analysis(NetworkInsightsPathId=path_id)
        analysis_id = analysis_resp["NetworkInsightsAnalysis"]["NetworkInsightsAnalysisId"]

        # Poll until complete (max 60 seconds)
        analysis = {}
        for _ in range(12):
            time.sleep(5)
            status_resp = ec2.describe_network_insights_analyses(
                NetworkInsightsAnalysisIds=[analysis_id]
            )
            analysis = status_resp["NetworkInsightsAnalyses"][0]
            if analysis["Status"] == "succeeded":
                break
            if analysis["Status"] == "failed":
                return f"❌ Reachability analysis failed: {analysis.get('StatusMessage', 'unknown error')}"

        reachable = analysis.get("NetworkPathFound", False)
        results = [
            f"Reachability Analysis: {source_id} → {destination_id}:{destination_port}/{protocol}",
            "",
            f"{'✅ PATH EXISTS' if reachable else '❌ PATH BLOCKED'} — "
            f"{source_id} {'CAN' if reachable else 'CANNOT'} reach {destination_id} on port {destination_port}",
        ]

        if not reachable:
            explanations = analysis.get("Explanations", [])
            if explanations:
                results.extend(["", "Blocking reasons:"])
                results.extend(
                    f"  ❌ {exp.get('Component', {}).get('Id', 'unknown')}: {exp.get('ExplanationCode', 'unknown')}"
                    for exp in explanations
                )

        forward_path = analysis.get("ForwardPathComponents", [])
        if forward_path:
            results.extend(["", "Network path:"])
            results.extend(
                f"  {i+1}. {comp.get('Component', {}).get('Id', '?')}"
                + (f" ({comp.get('Component', {}).get('Name', '')})" if comp.get("Component", {}).get("Name") else "")
                for i, comp in enumerate(forward_path)
            )

        return "\n".join(results)

    except Exception as e:
        return f"❌ Error: {str(e)}"
    finally:
        if path_id:
            try:
                ec2.delete_network_insights_path(NetworkInsightsPathId=path_id)
            except Exception as cleanup_err:
                logger.warning("Failed to delete network insights path %s: %s", path_id, cleanup_err)


# --- System Prompt ---

SYSTEM_PROMPT = """You are an AWS network diagnostics agent. All checks use AWS APIs —
you analyze AWS resource configurations to diagnose networking issues.

You have six tools:

1. check_subnet_details  — Get subnet info (CIDR, AZ, public/private, available IPs)
2. check_vpc_routes      — Analyze route tables for internet, NAT, peering, transit gateway routes
3. check_nacl_rules      — Check Network ACL inbound/outbound rules for a subnet
4. check_security_group  — Check security group inbound/outbound rules
5. check_vpc_endpoints   — List VPC endpoints (S3, DynamoDB, etc.)
6. check_reachability    — Use VPC Reachability Analyzer to test path between two resources

When diagnosing connectivity issues, follow this order:
1. check_subnet_details — understand if it's public or private
2. check_vpc_routes — confirm internet/NAT route exists
3. check_nacl_rules — check for blocking NACL rules
4. check_security_group — check for missing SG rules
5. check_reachability — definitive path analysis between two specific resources

Explain results clearly:
- No internet route → suggest adding IGW (public) or NAT Gateway (private)
- NACL blocking → identify the specific rule number and suggest a fix
- SG missing rule → suggest the exact rule to add (protocol, port, source)
- No VPC endpoint → suggest adding one for cost savings (S3/DynamoDB endpoints are free)
- Always name the specific resource (route table ID, NACL ID, SG ID) causing the issue
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
        agent(user_input)
        print()
