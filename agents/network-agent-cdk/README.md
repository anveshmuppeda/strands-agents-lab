# Weather Agent — Python CDK + GitHub Actions CI/CD

Deploy the weather agent to Amazon Bedrock AgentCore using **Python CDK** with a
**GitHub Actions CI/CD pipeline** for automated builds and deployments.

## Architecture

```
Developer pushes code to main
        │
        ▼
┌─ GitHub Actions Pipeline ──────────────────────────────────────┐
│                                                                 │
│  Job 1: Deploy Base Infra                                       │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  cdk deploy WeatherAgent-BaseInfra                     │     │
│  │  Creates: ECR Repository + IAM Role                    │     │
│  │  (idempotent — skips if already exists)                │     │
│  └──────────────────────┬─────────────────────────────────┘     │
│                         │ outputs: ECR URI                      │
│                         ▼                                       │
│  Job 2: Build & Push Docker Image                               │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  docker build agent-code/                              │     │
│  │  docker push → ECR (tagged with git SHA)               │     │
│  └──────────────────────┬─────────────────────────────────┘     │
│                         │ outputs: image tag (git SHA)          │
│                         ▼                                       │
│  Job 3: Deploy AgentCore Runtime                                │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  cdk deploy WeatherAgent-AgentCore -c image_tag=abc123 │     │
│  │  Creates/Updates: AgentCore Runtime with new image     │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
weather-agent-cdk-py/
│
├── app.py                              # CDK app — wires both stacks together
├── cdk.json                            # CDK config
├── requirements.txt                    # CDK Python dependencies
│
├── stacks/
│   ├── base_infra_stack.py             # Stack 1: ECR repo + IAM role
│   └── agentcore_stack.py              # Stack 2: AgentCore Runtime
│
├── agent-code/                         # Agent source (gets containerized)
│   ├── weather_agent.py                # Strands agent with @app.entrypoint
│   ├── requirements.txt                # Agent Python dependencies
│   └── Dockerfile                      # Container definition
│
└── .github/workflows/
    └── deploy.yml                      # CI/CD pipeline (3 jobs)
```

## Stack Breakdown

### Stack 1: Base Infrastructure (`WeatherAgent-BaseInfra`)

Deployed once, rarely changes.

| Resource | Purpose |
| -------- | ------- |
| ECR Repository | Stores Docker images for the agent |
| IAM Role | AgentCore execution role (Bedrock, ECR, CloudWatch, X-Ray) |

### Stack 2: AgentCore Runtime (`WeatherAgent-AgentCore`)

Updated on every code push.

| Resource | Purpose |
| -------- | ------- |
| AgentCore CfnRuntime | Runs the weather agent container |

The image tag is passed via CDK context: `cdk deploy -c image_tag=abc123`

## Prerequisites

- Python 3.10+
- AWS CDK v2 (`npm install -g aws-cdk`)
- AWS CLI configured (`aws configure`)
- Claude model access enabled in Bedrock console
- GitHub repo with AWS OIDC configured (for CI/CD)

## Manual Deploy (without CI/CD)

```bash
cd agents/weather-agent-cdk-py

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy base infra
cdk deploy WeatherAgent-BaseInfra

# Build and push image manually
ECR_URI=$(aws cloudformation describe-stacks \
  --stack-name WeatherAgent-BaseInfra \
  --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
  --output text)

aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URI

cd agent-code
docker build -t $ECR_URI:latest .
docker push $ECR_URI:latest
cd ..

# Deploy AgentCore
cdk deploy WeatherAgent-AgentCore -c image_tag=latest
```

## CI/CD Setup (GitHub Actions)

### 1. Configure AWS OIDC for GitHub Actions

Create an IAM OIDC identity provider and role for GitHub Actions:

```bash
# Create OIDC provider (one-time)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create role for GitHub Actions (replace YOUR_GITHUB_ORG/YOUR_REPO)
aws iam create-role \
  --role-name GitHubActions-WeatherAgent \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_ORG/YOUR_REPO:*"
        }
      }
    }]
  }'

# Attach required policies
aws iam attach-role-policy \
  --role-name GitHubActions-WeatherAgent \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

aws iam attach-role-policy \
  --role-name GitHubActions-WeatherAgent \
  --policy-arn arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess

# Also needs: CloudFormation, IAM (for CDK), S3 (for CDK assets)
```

### 2. Add GitHub Secret

Go to your repo → Settings → Secrets → Actions → New secret:

- Name: `AWS_ROLE_ARN`
- Value: `arn:aws:iam::YOUR_ACCOUNT_ID:role/GitHubActions-WeatherAgent`

### 3. Push and Deploy

```bash
git push origin main
```

The pipeline triggers automatically on pushes to `agents/weather-agent-cdk-py/`.

## Clean Up

```bash
# Destroy both stacks
cdk destroy WeatherAgent-AgentCore
cdk destroy WeatherAgent-BaseInfra
```

## Comparison: Single Stack vs Split Stacks

| Aspect | Single stack (before) | Split stacks (now) |
| ------ | --------------------- | ------------------ |
| Image build | CodeBuild custom resource (fragile) | GitHub Actions (proper CI/CD) |
| Deploy time | 8-12 min (CodeBuild runs every time) | ~3 min (only CDK update) |
| ECR repo | Recreated on stack destroy | Persists independently |
| IAM role | Recreated on stack destroy | Persists independently |
| Image tagging | Always "latest" | Git SHA (traceable) |
| Rollback | Redeploy entire stack | Just change image_tag |
