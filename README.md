# Strands Agents Lab

Learning and building AI agents with [Strands Agents SDK](https://strandsagents.com) and [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) — from basics to production deployment.

## What's Inside

### Agents

| Agent | Description | Local | AgentCore |
|-------|-------------|-------|-----------|
| [Weather Agent](agents/weather-agent/) | Live weather forecasts using NWS API | [local/](agents/weather-agent/local/) | [agentcore/](agents/weather-agent/agentcore/) |

### Documentation

| Doc | What's Covered |
|-----|----------------|
| [Terminology](docs/01-terminology.md) | Agent, LLM, Bedrock, AgentCore, Tools, MCP — all defined with examples |
| [Core Patterns](docs/02-core-patterns.md) | 15 Strands patterns from basic agent to multi-agent swarm |
| [Learning Checklist](docs/05-checklist-and-next-steps.md) | Phase progression and key resources |
| [Tool Scaling](docs/06-tool-scaling.md) | What happens with 10, 50, 100+ tools and how to handle it |

## Quick Start

```bash
# Run the weather agent locally
cd agents/weather-agent/local
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 weather_agent.py
```

## Prerequisites

- Python 3.10+
- AWS account with [Bedrock model access](https://console.aws.amazon.com/bedrock/home#/modelaccess) enabled
- AWS CLI configured (`aws configure`)

## Tech Stack

- [Strands Agents SDK](https://strandsagents.com) — model-driven agent framework (open source, by AWS)
- [Amazon Bedrock](https://aws.amazon.com/bedrock/) — LLM provider (Claude, Nova, Llama via IAM credentials)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) — production runtime, memory, gateway, observability
- [AgentCore CLI](https://github.com/aws/agentcore-cli) — `agentcore create / dev / deploy / invoke`

## License

[MIT](./LICENSE)
