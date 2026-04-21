"""
Network Agent — Deployed on Amazon Bedrock AgentCore Runtime via Python CDK.

Diagnoses AWS networking issues using AWS APIs.
"""

import json
import boto3
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands.models.bedrock import BedrockModel

app = BedrockAgentCoreApp()
log = app.logger

model = BedrockModel(model_id="us.amazon.nova-pro-v1:0")

@tool
def check_subnet_details(subnet_id: str) -> str:
    """Get details about an AWS subnet — CIDR, AZ, public/private, available IPs.

    Args:
        subnet_id: AWS Subnet ID (e.g., "subnet-0abc123def456")
    """
    ec2 = boto3.client("ec2")
    resp = ec2.describe_subnets(SubnetIds=[subnet_id])
    subnets = resp.get("Subnets", [])
    if not subnets:
        return f"Subnet {subnet_id} not found"
    s = subnets[0]
    name = next((t["Value"] for t in s.get("Tags", []) if t["Key"] == "Name"), "(no name)")
    auto_pub = s.get("MapPublicIpOnLaunch", False)
    return "\n".join([
        f"Subnet: {subnet_id}", f"  Name: {name}", f"  VPC: {s['VpcId']}",
        f"  CIDR: {s['CidrBlock']}", f"  AZ: {s['AvailabilityZone']}",
        f"  Available IPs: {s['AvailableIpAddressCount']}",
        f"  Auto-assign public IP: {'Yes' if auto_pub else 'No'}",
        f"  Type: {'PUBLIC' if auto_pub else 'PRIVATE'}",
    ])


@tool
def check_vpc_routes(vpc_id: str, subnet_id: str = "") -> str:
    """Analyze route tables for a VPC or subnet. Shows IGW, NAT, peering, TGW routes.

    Args:
        vpc_id: AWS VPC ID (e.g., "vpc-0abc123def456")
        subnet_id: Specific subnet to check (optional)
    """
    ec2 = boto3.client("ec2")
    filters = [{"Name": "vpc-id", "Values": [vpc_id]}]
    if subnet_id:
        filters.append({"Name": "association.subnet-id", "Values": [subnet_id]})
    resp = ec2.describe_route_tables(Filters=filters)
    rts = resp.get("RouteTables", [])
    if not rts and subnet_id:
        resp = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
        rts = [rt for rt in resp.get("RouteTables", []) if any(a.get("Main") for a in rt.get("Associations", []))]
    if not rts:
        return f"No route tables found for VPC {vpc_id}"
    results, has_igw, has_nat = [], False, False
    for rt in rts:
        results.append(f"Route Table: {rt['RouteTableId']}")
        for r in rt.get("Routes", []):
            dest = r.get("DestinationCidrBlock", r.get("DestinationPrefixListId", ""))
            tgt = r.get("GatewayId", "") or r.get("NatGatewayId", "") or r.get("VpcPeeringConnectionId", "") or r.get("TransitGatewayId", "") or "local"
            if tgt.startswith("igw-"): has_igw = True
            if tgt.startswith("nat-"): has_nat = True
            results.append(f"  {dest} → {tgt}")
        results.append("")
    if has_igw: results.append("Internet Gateway route → PUBLIC subnet")
    elif has_nat: results.append("NAT Gateway route → PRIVATE with outbound internet")
    else: results.append("No internet route → ISOLATED subnet")
    return "\n".join(results)


@tool
def check_security_group(security_group_id: str) -> str:
    """Check security group inbound and outbound rules.

    Args:
        security_group_id: AWS Security Group ID (e.g., "sg-0abc123def456")
    """
    ec2 = boto3.client("ec2")
    resp = ec2.describe_security_groups(GroupIds=[security_group_id])
    sgs = resp.get("SecurityGroups", [])
    if not sgs:
        return f"Security group {security_group_id} not found"
    sg = sgs[0]
    common = {22: "SSH", 80: "HTTP", 443: "HTTPS", 3306: "MySQL", 5432: "PostgreSQL", 6379: "Redis"}
    results = [f"SG: {security_group_id} ({sg.get('GroupName', '')})", f"VPC: {sg.get('VpcId', '')}", ""]
    for direction, key in [("INBOUND", "IpPermissions"), ("OUTBOUND", "IpPermissionsEgress")]:
        results.append(f"{direction}:")
        for rule in sg.get(key, []):
            proto = "ALL" if rule.get("IpProtocol") == "-1" else rule.get("IpProtocol", "?").upper()
            fp, tp = rule.get("FromPort", "*"), rule.get("ToPort", "*")
            ports = "ALL" if proto == "ALL" else (str(fp) if fp == tp else f"{fp}-{tp}")
            label = f" ({common[fp]})" if fp == tp and fp in common else ""
            for r in rule.get("IpRanges", []):
                results.append(f"  {proto} {ports}{label} from {r.get('CidrIp', '?')}")
            for r in rule.get("UserIdGroupPairs", []):
                results.append(f"  {proto} {ports}{label} from SG {r.get('GroupId', '?')}")
        results.append("")
    return "\n".join(results)


SYSTEM_PROMPT = """You are an AWS network diagnostics agent.

Tools:
1. check_subnet_details — Subnet info (CIDR, AZ, public/private)
2. check_vpc_routes — Route table analysis (IGW, NAT, peering)
3. check_security_group — Security group inbound/outbound rules

When diagnosing: start with subnet details, then routes, then security groups.
Explain results clearly and suggest fixes."""

_agent = None

def get_or_create_agent():
    global _agent
    if _agent is None:
        _agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=[check_subnet_details, check_vpc_routes, check_security_group],
        )
    return _agent


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Network Agent...")
    agent = get_or_create_agent()
    stream = agent.stream_async(payload.get("prompt"))
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
