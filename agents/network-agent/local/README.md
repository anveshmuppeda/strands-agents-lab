# AWS Network Agent

Diagnoses AWS networking issues using AWS APIs. No local socket/ping calls — everything
is checked by reading AWS resource configurations (route tables, NACLs, security groups,
VPC endpoints, and Reachability Analyzer).

## Tools

| Tool | What It Checks |
| ---- | -------------- |
| `check_subnet_details` | Subnet CIDR, AZ, public/private, available IPs |
| `check_vpc_routes` | Route tables — IGW, NAT, peering, transit gateway routes |
| `check_nacl_rules` | Network ACL inbound/outbound rules |
| `check_security_group` | Security group inbound/outbound rules with port labels |
| `check_vpc_endpoints` | VPC endpoints (S3, DynamoDB, interface endpoints) |
| `check_reachability` | VPC Reachability Analyzer — tests actual path between two resources |

## Setup & Run

```bash
cd agents/network-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 network_agent.py
```

## Sample Queries

### Subnet & VPC Analysis

```
Tell me about subnet subnet-0abc123
Is subnet subnet-0abc123 public or private?
What routes does VPC vpc-0def456 have?
Does subnet subnet-0abc123 in vpc-0def456 have internet access?
Does VPC vpc-0def456 have a NAT gateway route?
Show me the route table for subnet subnet-0abc123 in vpc-0def456
```

### Security Group Checks

```
What are the inbound rules for security group sg-0abc123?
Is port 443 allowed inbound on sg-0abc123?
Does sg-0abc123 allow SSH (port 22) from anywhere?
Show me the outbound rules for sg-0def456
What ports are open on security group sg-0abc123?
```

### Network ACL Checks

```
What are the NACL rules for subnet subnet-0abc123?
Is outbound traffic on port 443 allowed by the NACL on subnet subnet-0abc123?
Show me the inbound NACL rules for subnet subnet-0def456
Are there any deny rules in the NACL for subnet subnet-0abc123?
```

### VPC Endpoints

```
What VPC endpoints exist in vpc-0abc123?
Does vpc-0abc123 have an S3 endpoint?
Are there any interface endpoints in vpc-0def456?
```

### Reachability Analysis (Path Between Two Resources)

```
Can instance i-0abc123 reach instance i-0def456 on port 443?
Test if internet gateway igw-0abc123 can reach instance i-0def456 on port 80
Can traffic from ENI eni-0abc123 reach ENI eni-0def456 on port 5432?
Is there a network path from instance i-0abc123 to the internet gateway igw-0def456?
```

### Troubleshooting Scenarios

```
My EC2 instance i-0abc123 in subnet subnet-xyz can't reach the internet. It's in VPC vpc-abc. Diagnose the issue.
My RDS in subnet subnet-0abc123 isn't accessible from my EC2 instance i-0def456 on port 5432. Check security groups and NACLs.
My Lambda in VPC vpc-abc subnet subnet-xyz can't reach S3. Check if there's a VPC endpoint or NAT route.
ECS tasks in subnet subnet-0abc123 can't pull Docker images. Check if the subnet has outbound internet access.
My application in subnet subnet-abc can't connect to an API on port 443. Check routes, NACLs, and security groups.
I set up VPC peering but traffic isn't flowing between vpc-abc and vpc-def. Check the route tables.
```

## How It Works

The agent chains tools based on your question. For example:

```
"My EC2 instance i-abc in subnet subnet-xyz can't reach the internet"

1. check_subnet_details("subnet-xyz")
   → Private subnet, VPC vpc-123, no auto-public IP

2. check_vpc_routes("vpc-123", "subnet-xyz")
   → No 0.0.0.0/0 route found
   → ❌ ISOLATED — no internet access

3. Agent responds:
   "Subnet subnet-xyz has no internet route. It's a private subnet
    with no NAT Gateway. To fix this:
    1. Create a NAT Gateway in a public subnet
    2. Add a route: 0.0.0.0/0 → nat-xxxxx in this subnet's route table"
```

```
"Can instance i-abc reach instance i-def on port 5432?"

1. check_reachability(
     source_type="instance", source_id="i-abc",
     destination_type="instance", destination_id="i-def",
     destination_port=5432
   )
   → ❌ PATH BLOCKED — sg-xyz: no inbound rule for port 5432

2. check_security_group("sg-xyz")
   → Inbound: only port 443 from 0.0.0.0/0
   → No rule for port 5432

3. Agent responds:
   "The path is blocked by security group sg-xyz on the destination instance.
    It only allows port 443 inbound. To fix:
    Add an inbound rule: TCP port 5432 from sg-abc (the source instance's SG)"
```

## Prerequisites

- Python 3.10+
- AWS credentials (`aws configure`)
- Claude model access in Bedrock console
- IAM permissions needed:
  - `ec2:DescribeSubnets`
  - `ec2:DescribeRouteTables`
  - `ec2:DescribeNetworkAcls`
  - `ec2:DescribeSecurityGroups`
  - `ec2:DescribeVpcEndpoints`
  - `ec2:CreateNetworkInsightsPath` (for reachability analysis)
  - `ec2:StartNetworkInsightsAnalysis`
  - `ec2:DescribeNetworkInsightsAnalyses`
  - `ec2:DeleteNetworkInsightsPath`
