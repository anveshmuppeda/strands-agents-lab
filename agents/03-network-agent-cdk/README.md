# Productionizing AI Agents with AWS CDK, Bedrock AgentCore & CI/CD (Part 3)  
## *End-to-end IaC, Docker, and GitHub Actions CI/CD for production-ready Bedrock agents*

Deploy the [Network Agent](../02-network-agent/) to Amazon Bedrock AgentCore using **Python CDK**
instead of the AgentCore CLI. This gives you full control over the infrastructure, split stacks
for independent lifecycle management, and a GitHub Actions CI/CD pipeline.

> **Prerequisite:** Complete [01-weather-agent](../01-weather-agent/) and [02-network-agent](../02-network-agent/) first.
> This guide assumes you understand Strands agents, `@tool`, and AgentCore Runtime.

---

## Why Python CDK Instead of the AgentCore CLI?

The AgentCore CLI (`agentcore deploy`) is great for getting started — it handles everything
with one command. But it generates TypeScript CDK under the hood, and you can't customize it.

Python CDK gives you:

| AgentCore CLI | Python CDK (this project) |
|---------------|---------------------------|
| One command: `agentcore deploy` | You write the CDK stack in Python |
| TypeScript CDK auto-generated | Python CDK you control |
| Single stack (everything together) | Split stacks (base infra + runtime) |
| No CI/CD built in | GitHub Actions pipeline included |
| ECR repo destroyed with stack | ECR repo persists independently |
| Image always tagged `latest` | Image tagged with git SHA (traceable) |
| Good for learning | Good for production |

---

## Architecture

```
┌─ Stack 1: NetworkAgent-BaseInfra (deploy once) ────────────────┐
│                                                                  │
│  ECR Repository: network-agent                                   │
│  IAM Role: AgentCore execution role                              │
│    ├── Bedrock model invocation                                  │
│    ├── ECR image pull                                            │
│    ├── CloudWatch Logs + X-Ray                                   │
│    └── EC2 Describe* (for network tools)                         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                         │
                         │ ECR URI + Role ARN
                         ▼
┌─ GitHub Actions Pipeline ────────────────────────────────────────┐
│                                                                   │
│  docker build agent-code/ → docker push ECR (tag: git SHA)       │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
                         │
                         │ image tag
                         ▼
┌─ Stack 2: NetworkAgent-AgentCore (updates per deploy) ──────────┐
│                                                                  │
│  AgentCore CfnRuntime: NetworkAgent                              │
│    container_uri: {ECR_URI}:{image_tag}                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
03-network-agent-cdk/
│
├── app.py                              # CDK app — wires both stacks together
├── cdk.json                            # CDK configuration
├── requirements.txt                    # CDK Python dependencies
│
├── stacks/
│   ├── __init__.py
│   ├── base_infra_stack.py             # Stack 1: ECR repo + IAM role
│   └── agentcore_stack.py              # Stack 2: AgentCore Runtime
│
└── agent-code/                         # Agent source (gets containerized)
    ├── network_agent.py                # Strands agent with @app.entrypoint
    ├── requirements.txt                # Agent Python dependencies
    └── Dockerfile                      # Container definition
```

---

## What Each File Does

### `app.py` — CDK Entry Point

Wires the two stacks together with a dependency:

```python
base = BaseInfraStack(app, "NetworkAgent-BaseInfra")

agentcore = AgentCoreStack(
    app, "NetworkAgent-AgentCore",
    ecr_repository=base.ecr_repository,  # Pass ECR repo from Stack 1
    agent_role=base.agent_role,          # Pass IAM role from Stack 1
)
agentcore.add_dependency(base)  # Stack 2 deploys after Stack 1
```

### `stacks/base_infra_stack.py` — Stack 1: Base Infrastructure

Created once, rarely changes. Contains:

| Resource | Purpose |
| -------- | ------- |
| ECR Repository (`network-agent`) | Stores Docker images. Lifecycle rule keeps last 10 images. |
| IAM Role | AgentCore execution role with Bedrock, ECR, CloudWatch, X-Ray, and **EC2 Describe** permissions |

The EC2 permissions are what makes this different from the weather agent CDK — the network
agent needs `ec2:DescribeSubnets`, `ec2:DescribeRouteTables`, etc. to run its tools.

### `stacks/agentcore_stack.py` — Stack 2: AgentCore Runtime

Updated on every deploy. Takes the image tag as a CDK context variable:

```bash
cdk deploy NetworkAgent-AgentCore -c image_tag=abc123
```

### `agent-code/network_agent.py` — The Agent

Same network diagnostics tools from [02-network-agent](../02-network-agent/), wrapped with
`BedrockAgentCoreApp` for AgentCore Runtime:

| Tool | What It Checks |
| ---- | -------------- |
| `check_subnet_details` | Subnet CIDR, AZ, public/private, available IPs |
| `check_vpc_routes` | Route tables — IGW, NAT, peering, transit gateway |
| `check_security_group` | SG inbound/outbound rules with port labels |

### `agent-code/Dockerfile` — Container

```dockerfile
FROM python:3.11-slim
# ... install deps, create non-root user
CMD ["opentelemetry-instrument", "python", "-m", "network_agent"]
```

---

## Deploy

### Prerequisites

- Python 3.10+
- AWS CDK CLI (`npm install -g aws-cdk@latest`)
- AWS CLI configured (`aws configure`)
- Claude/Nova model access in Bedrock console
- CDK bootstrapped: `cdk bootstrap aws://ACCOUNT_ID/REGION`

### Step 1: Deploy Base Infrastructure

```bash
cd agents/03-network-agent-cdk

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cdk deploy NetworkAgent-BaseInfra
```

This creates the ECR repo and IAM role. Save the `ECRRepositoryUri` from the output.

### Step 2: Build and Push Docker Image

```bash
ECR_URI=$(aws cloudformation describe-stacks \
  --stack-name NetworkAgent-BaseInfra \
  --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
  --output text)

aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URI

cd agent-code
docker build -t $ECR_URI:latest .
docker push $ECR_URI:latest
cd ..
```

### Step 3: Deploy AgentCore Runtime

```bash
cdk deploy NetworkAgent-AgentCore -c image_tag=latest
```

### Step 4: Test

```bash
# Get the Runtime ARN
RUNTIME_ARN=$(aws cloudformation describe-stacks \
  --stack-name NetworkAgent-AgentCore \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeArn`].OutputValue' \
  --output text)

# Invoke
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn $RUNTIME_ARN \
  --qualifier DEFAULT \
  --payload $(echo '{"prompt": "Is subnet subnet-0abc123 public or private?"}' | base64) \
  response.json

cat response.json
```

### Clean Up

```bash
cdk destroy NetworkAgent-AgentCore
cdk destroy NetworkAgent-BaseInfra
```

---

## CI/CD with GitHub Actions

The `.github/workflows/deploy.yml` pipeline automates the full flow:

```
Push to main → Deploy Base Infra → Build & Push Image → Deploy AgentCore
```

See [01-weather-agent README](../01-weather-agent/) for GitHub OIDC setup instructions.

---

## What's Next

After deploying individual agents with CDK, the next step is [04-gateway-agent](../04-gateway-agent/) —
centralizing all your tools behind AgentCore Gateway so a single agent can access weather,
network, and IAM tools through MCP without any tool code baked in.
