# Weather Agent

A weather assistant built with [Strands Agents SDK](https://strandsagents.com) and [Amazon Bedrock](https://aws.amazon.com/bedrock/). It fetches live weather forecasts from the National Weather Service (NWS) API using a model-driven agent loop.

## Purpose

Demonstrates the full lifecycle of an AI agent — from local development to production deployment on Amazon Bedrock AgentCore:

- Building a Strands agent with custom tools and a system prompt
- Using Amazon Bedrock (IAM credentials, no API keys) as the model provider
- Deploying the same agent to AgentCore Runtime with minimal code changes

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        User Query                             │
│         "What's the weather in Chicago?"                      │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                     Strands Agent                             │
│                                                               │
│   Model: Amazon Bedrock (Claude / Nova)                       │
│   Auth:  AWS IAM credentials — no API keys                    │
│                                                               │
│   Agent Loop: Think → Act → Observe → Decide → Respond        │
│                                                               │
│   ┌─────────────────────┐   ┌────────────┐   ┌───────────┐   │
│   │ get_weather_forecast │   │current_time│   │  use_aws  │   │
│   │   (custom @tool)    │   │ (built-in) │   │ (built-in)│   │
│   └──────────┬──────────┘   └─────┬──────┘   └─────┬─────┘   │
└──────────────┼─────────────────────┼────────────────┼─────────┘
               │                     │                │
               ▼                     ▼                ▼
         NWS Weather API        Timezone Data      AWS APIs
```

## Implementations

| Version | Description | Docs |
|---------|-------------|------|
| [local/](./local/) | Runs directly with Python — for development and learning | [local/README.md](./local/README.md) |
| [agentcore/](./agentcore/) | Deployed to Amazon Bedrock AgentCore Runtime | [agentcore/README.md](./agentcore/README.md) |

## How the Agent Loop Works

```
You: "What's the weather in Chicago and what time is it there?"

THINK  → "I need weather data and the local time for Chicago"
ACT    → get_weather_forecast("Chicago")
RESULT → "72°F, Sunny, Wind: 10 mph SW"

THINK  → "Now I need the time"
ACT    → current_time("America/Chicago")
RESULT → "2:30 PM CDT"

RESPOND → "It's 2:30 PM in Chicago. The weather is 72°F and sunny
           with 10 mph winds from the southwest..."
```

The LLM drives all decisions — which tools to call, in what order, and when to stop.

## Supported Cities

New York, Chicago, San Francisco, Miami, Seattle, Los Angeles, Denver, Boston

## Prerequisites

- Python 3.10+
- AWS account with Bedrock model access enabled
- AWS CLI configured (`aws configure`)

## Resources

| Resource | Link |
|----------|------|
| Strands Agents Docs | https://strandsagents.com/latest/ |
| Amazon Bedrock AgentCore | https://docs.aws.amazon.com/bedrock-agentcore/ |
| AgentCore CLI | https://github.com/aws/agentcore-cli |
| NWS Weather API | https://www.weather.gov/documentation/services-web-api |
