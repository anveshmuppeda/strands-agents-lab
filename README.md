# Strands Agents Lab

Learning and building AI agents with [Strands Agents SDK](https://strandsagents.com) and [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) — from basics to production deployment.

## What's Inside

### Agents

| # | Agent | Description | Deployment |
|---|-------|-------------|------------|
| 01 | [Weather Agent](agents/01-weather-agent/) | Live weather forecasts using NWS API | Local + AgentCore CLI |
| 02 | [Network Agent](agents/02-network-agent/) | AWS network diagnostics — subnets, routes, NACLs, SGs | Local + AgentCore CLI |
| 03 | [Network Agent CDK](agents/03-network-agent-cdk/) | Network agent deployed via Python CDK + CI/CD | Python CDK (2 stacks) |
| 04 | [Gateway Agent](agents/04-gateway-agent/) | Single agent accessing 9 tools via AgentCore Gateway | CDK (2 stacks) + Lambda |
| 05 | [Memory Agent](agents/05-memory-agent/) | Weather agent with short-term memory — remembers conversations | Local (AgentCore Memory) |
| 06 | [Long-Term Memory Agent](agents/06-longterm-memory-agent/) | Gateway agent with long-term memory — extracts facts and preferences permanently | CDK (2 stacks) + Strategies |

### Recommended Learning Order

1. **Weather Agent** — Start here. Learn Strands basics, `@tool` decorator, BedrockModel, deploy with AgentCore CLI
2. **Network Agent** — Build a real AWS diagnostics agent with multiple tools, deploy to AgentCore
3. **Network Agent CDK** — Learn Python CDK deployment with split stacks (base infra + runtime) and CI/CD
4. **Gateway Agent** — Centralize tools as Lambda functions behind AgentCore Gateway, connect via MCP
5. **Memory Agent** — Add short-term memory so your agent remembers conversations across sessions
6. **Long-Term Memory Agent** — Add memory strategies that extract facts and preferences permanently

### Documentation

| Doc | What's Covered |
|-----|----------------|
| [Terminology](docs/01-terminology.md) | Agent, LLM, Bedrock, AgentCore, Tools, MCP — all defined with examples |
| [Core Patterns](docs/02-core-patterns.md) | 15 Strands patterns from basic agent to multi-agent swarm |
| [Learning Path](docs/03-learning-path.md) | Phase progression, tool scaling, and key resources |

### CI/CD Workflows

| Workflow | Trigger | What It Does |
|----------|---------|-------------|
| [deploy.yml](.github/workflows/deploy.yml) | Push to `agents/03-network-agent-cdk/` | Deploy Network Agent via CDK |
| [deploy-gateway-agent.yml](.github/workflows/deploy-gateway-agent.yml) | Manual only | Deploy Gateway + Lambdas + Agent Runtime |

### Utilities

| Utility | Description | Folder |
|---------|-------------|--------|
| [Runtime Invoker](utils/runtime-invoker/) | Lambda to test any deployed agent from AWS — no local setup | `utils/runtime-invoker/` |

## Quick Start

```bash
# Clone the repo
git clone https://github.com/anveshmuppeda/strands-agents-lab.git
cd strands-agents-lab

# Run the weather agent locally
cd agents/01-weather-agent/local
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 weather_agent.py
```

## Prerequisites

- Python 3.10+
- AWS account with [Bedrock model access](https://console.aws.amazon.com/bedrock/home#/modelaccess) enabled
- AWS CLI configured (`aws configure`)
- For CDK agents: AWS CDK CLI (`npm install -g aws-cdk@latest`)
- For Gateway agent: `aws-cdk-lib >= 2.238.0`

## Tech Stack

- [Strands Agents SDK](https://strandsagents.com) — model-driven agent framework (open source, by AWS)
- [Amazon Bedrock](https://aws.amazon.com/bedrock/) — LLM provider (Claude, Nova, Llama via IAM credentials)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) — production runtime, memory, gateway, observability
- [AgentCore CLI](https://github.com/aws/agentcore-cli) — `agentcore create / dev / deploy / invoke`
- [AWS CDK (Python)](https://docs.aws.amazon.com/cdk/v2/guide/work-with-cdk-python.html) — infrastructure as code

## License

[MIT](./LICENSE)
