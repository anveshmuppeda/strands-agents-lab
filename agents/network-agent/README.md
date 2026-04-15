# AWS Network Agent — Built with Strands Agents SDK and Amazon Bedrock AgentCore

An AI agent that diagnoses AWS networking issues by reading AWS resource configurations — route tables, Network ACLs, security groups, VPC endpoints, and VPC Reachability Analyzer. No local socket or ping calls — everything is done through AWS APIs.

This agent covers the full lifecycle — from a Python script running on your laptop to a managed, scalable serverless endpoint on AWS — with the same core agent code throughout.

---

## What Is This?

Traditional network debugging means logging into the AWS Console, clicking through five different services, and manually correlating what you find. This agent does all of that for you — you describe the problem in plain English, and the LLM decides which AWS APIs to call, in what order, and how to interpret the results.

| Traditional Debugging | Network Agent |
|-----------------------|---------------|
| Open Console → EC2 → Subnets → find subnet | `"Is subnet-0abc123 public or private?"` |
| Open Route Tables → filter by VPC → read routes | `"Does VPC vpc-0def456 have internet access?"` |
| Open Security Groups → find SG → read rules | `"What ports are open on sg-0abc123?"` |
| Open Network ACLs → find NACL → read rules | `"Are there any NACL rules blocking port 443?"` |
| Open Reachability Analyzer → create path → run analysis | `"Can instance i-abc reach i-def on port 5432?"` |

---

## Architecture

![Network Agent Architecture](./assets/architecture.png)

> Place your architectural diagram at `agents/network-agent/assets/architecture.png`

```
User Query
    │
    ▼
Strands Agent
    ├── System Prompt  →  defines diagnostic workflow and rules
    ├── BedrockModel   →  LLM reasoning engine (Amazon Bedrock)
    └── Tools (6)      →  all call AWS EC2 APIs via boto3
         │
         ├── check_subnet_details   → ec2:DescribeSubnets
         ├── check_vpc_routes       → ec2:DescribeRouteTables
         ├── check_nacl_rules       → ec2:DescribeNetworkAcls
         ├── check_security_group   → ec2:DescribeSecurityGroups
         ├── check_vpc_endpoints    → ec2:DescribeVpcEndpoints
         └── check_reachability     → ec2:CreateNetworkInsightsPath
                                       ec2:StartNetworkInsightsAnalysis
                                       ec2:DescribeNetworkInsightsAnalyses
                                       ec2:DeleteNetworkInsightsPath
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | [Strands Agents SDK](https://strandsagents.com) (open source, by AWS) |
| LLM | Amazon Nova Pro via [Amazon Bedrock](https://aws.amazon.com/bedrock/) |
| Authentication | AWS IAM credentials — no API keys |
| AWS APIs | EC2 APIs via [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) |
| Production Runtime | [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) |
| Infrastructure | AWS CDK (managed by AgentCore CLI) |

---

## Tools

| Tool | AWS API | What It Checks |
|------|---------|----------------|
| `check_subnet_details` | `ec2:DescribeSubnets` | CIDR, AZ, public/private, available IPs |
| `check_vpc_routes` | `ec2:DescribeRouteTables` | IGW, NAT, VPC peering, transit gateway routes |
| `check_nacl_rules` | `ec2:DescribeNetworkAcls` | Inbound/outbound NACL rules with rule numbers |
| `check_security_group` | `ec2:DescribeSecurityGroups` | Inbound/outbound SG rules with port labels |
| `check_vpc_endpoints` | `ec2:DescribeVpcEndpoints` | Gateway and interface endpoints (S3, DynamoDB, etc.) |
| `check_reachability` | `ec2:NetworkInsights*` | Actual path analysis between two AWS resources |

---

## How the Agent Loop Works

When you ask "My EC2 instance can't reach the internet", here is exactly what happens:

```
You:    "My EC2 instance i-0abc123 in subnet subnet-xyz can't reach
         the internet. It's in VPC vpc-abc. Diagnose the issue."

THINK   "I should start with subnet details to understand the topology"

ACT     check_subnet_details("subnet-xyz")
RESULT  "PRIVATE subnet — no auto-assign public IP, VPC vpc-abc"

THINK   "Private subnet. Let me check if there's a NAT Gateway route"

ACT     check_vpc_routes("vpc-abc", "subnet-xyz")
RESULT  "❌ No internet route → ISOLATED subnet (no internet access)"

THINK   "No NAT route. That's the root cause. Let me also check the NACL
         to see if there's anything else blocking"

ACT     check_nacl_rules("subnet-xyz")
RESULT  "✅ Rule 100: ALLOW ALL from 0.0.0.0/0 (inbound)
         ✅ Rule 100: ALLOW ALL to 0.0.0.0/0 (outbound)"

DECIDE  "Root cause confirmed: missing NAT Gateway route. NACL is fine."

RESPOND "Your instance i-0abc123 is in a private subnet (subnet-xyz) with
         no outbound internet route. The NACL rules are open, so that's
         not the issue. To fix this:
         1. Create a NAT Gateway in a public subnet of vpc-abc
         2. Add a route in subnet-xyz's route table: 0.0.0.0/0 → nat-xxxxx"
```

---

## Diagnostic Workflow

The system prompt instructs the agent to follow this order for connectivity issues:

```
1. check_subnet_details   → Is it public or private?
2. check_vpc_routes       → Is there an internet/NAT route?
3. check_nacl_rules       → Is a NACL rule blocking traffic?
4. check_security_group   → Is a SG rule missing?
5. check_reachability     → Definitive path analysis (use when you have two specific resource IDs)
```

---

## Implementations

| Version | How It Runs | Entry Point | Use Case |
|---------|-------------|-------------|----------|
| [Local](./local/) | `python3 network_agent.py` | `if __name__ == "__main__"` loop | Development, learning, testing |
| [AgentCore](./agentcore/) | Managed container on AWS | `@app.entrypoint` async generator | Production, scalable deployment |

---

## Version 1: Local

### Setup & Run

```bash
cd agents/network-agent/local

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 network_agent.py
```

### Prerequisites

- Python 3.10+
- AWS CLI configured: `aws configure`
- Bedrock model access enabled in [AWS Console](https://console.aws.amazon.com/bedrock/home#/modelaccess)
- IAM permissions (see [IAM Permissions](#iam-permissions) below)

### Sample Queries

**Subnet & VPC analysis:**
```
Is subnet subnet-0abc123 public or private?
Does VPC vpc-0def456 have internet access?
Show me the route table for subnet subnet-0abc123 in vpc-0def456
Does VPC vpc-0def456 have a NAT gateway route?
```

**Security group checks:**
```
What are the inbound rules for security group sg-0abc123?
Is port 443 allowed inbound on sg-0abc123?
Does sg-0abc123 allow SSH (port 22) from anywhere?
```

**Network ACL checks:**
```
What are the NACL rules for subnet subnet-0abc123?
Are there any deny rules in the NACL for subnet subnet-0abc123?
Is outbound traffic on port 443 allowed by the NACL on subnet subnet-0abc123?
```

**VPC endpoints:**
```
What VPC endpoints exist in vpc-0abc123?
Does vpc-0abc123 have an S3 endpoint?
```

**Reachability analysis:**
```
Can instance i-0abc123 reach instance i-0def456 on port 443?
Can traffic from ENI eni-0abc123 reach ENI eni-0def456 on port 5432?
Test if internet gateway igw-0abc123 can reach instance i-0def456 on port 80
```

**Full troubleshooting scenarios:**
```
My EC2 instance i-0abc123 in subnet subnet-xyz can't reach the internet. It's in VPC vpc-abc. Diagnose the issue.
My RDS in subnet subnet-0abc123 isn't accessible from my EC2 instance i-0def456 on port 5432. Check security groups and NACLs.
My Lambda in VPC vpc-abc subnet subnet-xyz can't reach S3. Check if there's a VPC endpoint or NAT route.
ECS tasks in subnet subnet-0abc123 can't pull Docker images. Check if the subnet has outbound internet access.
I set up VPC peering but traffic isn't flowing between vpc-abc and vpc-def. Check the route tables.
```

---

## Version 2: Amazon Bedrock AgentCore

### What Changes

| Aspect | Local | AgentCore |
|--------|-------|-----------|
| Entry point | `if __name__ == "__main__"` loop | `@app.entrypoint` async generator |
| Invocation | `python3 network_agent.py` | HTTP POST to `/invocations` |
| Scaling | Single process on your machine | Auto-scales on demand |
| Auth | Local `aws configure` credentials | IAM role auto-provisioned by CLI |
| Monitoring | Print statements | OpenTelemetry traces → CloudWatch |

The agent logic — all 6 tools, the system prompt, the model — stays identical.

### Prerequisites

- Node.js 20.x or later
- Python 3.10+ with `uv` ([install](https://docs.astral.sh/uv/getting-started/installation/))
- AWS CLI configured with Bedrock + CloudFormation permissions
- AgentCore CLI:

```bash
npm install -g @aws/agentcore --prefix ~/.npm-global
agentcore --version
```

### Step 1 — Test Locally with `agentcore dev`

```bash
cd agents/network-agent/agentcore/networkagent
agentcore dev
```

```
Dev Server

  Agent: networkagent
  Server: http://localhost:8080/invocations
  Status: running

  > Is subnet subnet-0abc123 public or private?

  Subnet subnet-0abc123 is a PRIVATE subnet. It has no auto-assign public IP
  and is in VPC vpc-0def456, AZ us-east-1a, CIDR 10.0.1.0/24 with 251 available IPs.
```

### Step 2 — Deploy to AWS

```bash
agentcore deploy
```

Check status:

```bash
agentcore status
```

```
AgentCore Status (target: default, us-east-1)

Agents
  networkagent: Deployed - Runtime: READY (arn:aws:bedrock-agentcore:...)
```

### Step 3 — Invoke the Deployed Agent

```bash
agentcore invoke "Does VPC vpc-0abc123 have internet access?" --stream
```

### Step 4 — View Logs and Traces

```bash
agentcore logs
agentcore traces list --limit 10
```

### Clean Up

```bash
agentcore remove all
agentcore deploy
```

---

## IAM Permissions

The agent requires these EC2 read permissions, plus the Network Insights permissions for `check_reachability`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
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
      ],
      "Resource": "*"
    }
  ]
}
```

> Note: `check_reachability` creates and deletes a Network Insights Path resource. This incurs a small AWS cost per analysis (~$0.10 per analysis). All other tools are read-only and free.

---

## Resources

| Resource | Link |
|----------|------|
| Strands Agents SDK | https://strandsagents.com/latest/ |
| Amazon Bedrock | https://aws.amazon.com/bedrock/ |
| Amazon Bedrock AgentCore | https://aws.amazon.com/bedrock/agentcore/ |
| AgentCore Docs | https://docs.aws.amazon.com/bedrock-agentcore/ |
| AgentCore CLI | https://github.com/aws/agentcore-cli |
| VPC Reachability Analyzer | https://docs.aws.amazon.com/vpc/latest/reachability/what-is-reachability-analyzer.html |
| boto3 EC2 Docs | https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html |
