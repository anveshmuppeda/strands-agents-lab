# AWS Network Agent — Local

A Strands agent that diagnoses AWS networking issues by reading AWS resource configurations. Runs locally with Python using `aws configure` credentials.

## Purpose

Demonstrates:
- Building a multi-tool Strands agent with `BedrockModel` (IAM credentials, no API keys)
- Writing custom `@tool` functions that call AWS APIs via boto3
- Chaining multiple tool calls to diagnose a problem end-to-end
- Proper error handling and cleanup in tools (e.g., `finally` block in `check_reachability`)

## Project Structure

```
local/
├── network_agent.py    # Agent code with all 6 tools
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Tools

| Tool | What It Does |
|------|-------------|
| `check_subnet_details` | CIDR, AZ, public/private, available IPs |
| `check_vpc_routes` | Route tables — IGW, NAT, peering, transit gateway |
| `check_nacl_rules` | Network ACL inbound/outbound rules |
| `check_security_group` | Security group inbound/outbound rules |
| `check_vpc_endpoints` | VPC endpoints (S3, DynamoDB, interface endpoints) |
| `check_reachability` | VPC Reachability Analyzer — actual path between two resources |

## Setup & Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 network_agent.py
```

## Sample Queries

```
Is subnet subnet-0abc123 public or private?
Does VPC vpc-0def456 have internet access?
What are the inbound rules for sg-0abc123?
Can instance i-0abc123 reach instance i-0def456 on port 5432?
My Lambda in VPC vpc-abc can't reach S3. Check if there's a VPC endpoint or NAT route.
```

## IAM Permissions Required

```json
{
  "Action": [
    "ec2:DescribeSubnets",
    "ec2:DescribeRouteTables",
    "ec2:DescribeNetworkAcls",
    "ec2:DescribeSecurityGroups",
    "ec2:DescribeVpcEndpoints",
    "ec2:CreateNetworkInsightsPath",
    "ec2:StartNetworkInsightsAnalysis",
    "ec2:DescribeNetworkInsightsAnalyses",
    "ec2:DeleteNetworkInsightsPath"
  ]
}
```

> `check_reachability` creates/deletes a Network Insights Path (~$0.10 per analysis). All other tools are read-only and free.

## Next Step

Deploy to AgentCore Runtime: [agentcore/README.md](../agentcore/README.md)
