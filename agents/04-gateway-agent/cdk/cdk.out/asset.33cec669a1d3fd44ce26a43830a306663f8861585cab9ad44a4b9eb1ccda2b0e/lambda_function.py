"""
Network Tools Lambda — Gateway Target

Exposes: check_subnet_details, check_vpc_routes, check_nacl_rules,
         check_security_group, check_vpc_endpoints

(check_reachability excluded — it takes 60s+ which exceeds Lambda timeout for Gateway)
"""

import json
import boto3


def handler(event, context):
    """Lambda handler — Gateway sends MCP JSON-RPC tools/call requests."""
    body = event if isinstance(event, dict) else json.loads(event)

    params = body.get("params", {})
    tool_name = params.get("name", "")
    tool_args = params.get("arguments", {})

    tools = {
        "check_subnet_details": check_subnet_details,
        "check_vpc_routes": check_vpc_routes,
        "check_nacl_rules": check_nacl_rules,
        "check_security_group": check_security_group,
        "check_vpc_endpoints": check_vpc_endpoints,
    }

    if tool_name in tools:
        try:
            result = tools[tool_name](**tool_args)
            return {"content": [{"type": "text", "text": result}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}

    return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}


# --- Tool Implementations ---

def check_subnet_details(subnet_id: str, **kwargs) -> str:
    ec2 = boto3.client("ec2")
    resp = ec2.describe_subnets(SubnetIds=[subnet_id])
    subnets = resp.get("Subnets", [])
    if not subnets:
        return f"Subnet {subnet_id} not found"

    s = subnets[0]
    name = next((t["Value"] for t in s.get("Tags", []) if t["Key"] == "Name"), "(no name)")
    auto_pub = s.get("MapPublicIpOnLaunch", False)

    return "\n".join([
        f"Subnet: {subnet_id}",
        f"  Name: {name}",
        f"  VPC: {s['VpcId']}",
        f"  CIDR: {s['CidrBlock']}",
        f"  AZ: {s['AvailabilityZone']}",
        f"  Available IPs: {s['AvailableIpAddressCount']}",
        f"  Auto-assign public IP: {'Yes' if auto_pub else 'No'}",
        f"  Type: {'PUBLIC' if auto_pub else 'PRIVATE'}",
    ])


def check_vpc_routes(vpc_id: str, subnet_id: str = "", **kwargs) -> str:
    ec2 = boto3.client("ec2")
    filters = [{"Name": "vpc-id", "Values": [vpc_id]}]
    if subnet_id:
        filters.append({"Name": "association.subnet-id", "Values": [subnet_id]})

    resp = ec2.describe_route_tables(Filters=filters)
    route_tables = resp.get("RouteTables", [])

    if not route_tables and subnet_id:
        resp = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
        route_tables = [rt for rt in resp.get("RouteTables", [])
                        if any(a.get("Main", False) for a in rt.get("Associations", []))]

    if not route_tables:
        return f"No route tables found for VPC {vpc_id}"

    results = []
    has_igw = has_nat = False

    for rt in route_tables:
        rt_id = rt["RouteTableId"]
        results.append(f"Route Table: {rt_id}")
        for route in rt.get("Routes", []):
            dest = route.get("DestinationCidrBlock", route.get("DestinationPrefixListId", ""))
            target = (route.get("GatewayId", "") or route.get("NatGatewayId", "") or
                      route.get("VpcPeeringConnectionId", "") or route.get("TransitGatewayId", "") or "local")
            if target.startswith("igw-"):
                has_igw = True
            if target.startswith("nat-"):
                has_nat = True
            results.append(f"  {dest} → {target}")
        results.append("")

    if has_igw:
        results.append("Internet Gateway route found → PUBLIC subnet")
    elif has_nat:
        results.append("NAT Gateway route found → PRIVATE with outbound internet")
    else:
        results.append("No internet route → ISOLATED subnet")

    return "\n".join(results)


def check_nacl_rules(subnet_id: str, **kwargs) -> str:
    ec2 = boto3.client("ec2")
    resp = ec2.describe_network_acls(
        Filters=[{"Name": "association.subnet-id", "Values": [subnet_id]}]
    )
    nacls = resp.get("NetworkAcls", [])
    if not nacls:
        return f"No NACL found for subnet {subnet_id}"

    results = []
    proto_map = {"-1": "ALL", "6": "TCP", "17": "UDP", "1": "ICMP"}

    for nacl in nacls:
        results.append(f"NACL: {nacl['NetworkAclId']}")
        for direction in ["INBOUND", "OUTBOUND"]:
            entries = [e for e in nacl["Entries"] if e["Egress"] == (direction == "OUTBOUND")]
            results.append(f"  {direction}:")
            for e in sorted(entries, key=lambda x: x["RuleNumber"]):
                if e["RuleNumber"] == 32767:
                    continue
                proto = proto_map.get(e.get("Protocol", "-1"), e.get("Protocol", "?"))
                cidr = e.get("CidrBlock", "N/A")
                pr = e.get("PortRange", {})
                ports = f"{pr.get('From', '*')}-{pr.get('To', '*')}" if pr else "ALL"
                results.append(f"    Rule {e['RuleNumber']}: {e['RuleAction'].upper()} {proto} {ports} {cidr}")

    return "\n".join(results)


def check_security_group(security_group_id: str, **kwargs) -> str:
    ec2 = boto3.client("ec2")
    resp = ec2.describe_security_groups(GroupIds=[security_group_id])
    sgs = resp.get("SecurityGroups", [])
    if not sgs:
        return f"Security group {security_group_id} not found"

    sg = sgs[0]
    common_ports = {22: "SSH", 80: "HTTP", 443: "HTTPS", 3306: "MySQL",
                    5432: "PostgreSQL", 6379: "Redis", 8080: "HTTP-Alt", 3389: "RDP"}

    results = [f"SG: {security_group_id} ({sg.get('GroupName', '')})", f"VPC: {sg.get('VpcId', '')}", ""]

    for direction, rules_key in [("INBOUND", "IpPermissions"), ("OUTBOUND", "IpPermissionsEgress")]:
        results.append(f"{direction}:")
        rules = sg.get(rules_key, [])
        if not rules:
            results.append("  (none)")
            continue
        for rule in rules:
            proto = "ALL" if rule.get("IpProtocol") == "-1" else rule.get("IpProtocol", "?").upper()
            fp, tp = rule.get("FromPort", "*"), rule.get("ToPort", "*")
            ports = "ALL" if proto == "ALL" else (str(fp) if fp == tp else f"{fp}-{tp}")
            label = f" ({common_ports[fp]})" if fp == tp and fp in common_ports else ""
            for r in rule.get("IpRanges", []):
                results.append(f"  {proto} {ports}{label} from {r.get('CidrIp', '?')}")
            for r in rule.get("UserIdGroupPairs", []):
                results.append(f"  {proto} {ports}{label} from SG {r.get('GroupId', '?')}")
        results.append("")

    return "\n".join(results)


def check_vpc_endpoints(vpc_id: str, **kwargs) -> str:
    ec2 = boto3.client("ec2")
    resp = ec2.describe_vpc_endpoints(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
    endpoints = resp.get("VpcEndpoints", [])

    if not endpoints:
        return f"No VPC endpoints in {vpc_id}. Consider adding S3/DynamoDB Gateway endpoints (free)."

    results = [f"VPC Endpoints in {vpc_id}:", ""]
    for ep in endpoints:
        results.append(f"  {ep['VpcEndpointId']}: {ep['ServiceName']} ({ep['VpcEndpointType']}) — {ep['State']}")

    return "\n".join(results)
