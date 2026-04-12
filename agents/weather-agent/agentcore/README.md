# Weather Agent — Amazon Bedrock AgentCore

The weather agent deployed to [Amazon Bedrock AgentCore Runtime](https://aws.amazon.com/bedrock/agentcore/). This takes the local agent from "runs on my laptop" to a managed, scalable serverless endpoint on AWS.

## Purpose

Demonstrates how to:

- Wrap a Strands agent with `BedrockAgentCoreApp` for AgentCore Runtime
- Use the AgentCore CLI (`agentcore dev` / `agentcore deploy`) for the full development workflow
- Structure an AgentCore project (config, CDK infrastructure, app code)
- Stream responses from a deployed agent

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Amazon Bedrock AgentCore                       │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   AgentCore Runtime                          │ │
│  │                                                              │ │
│  │   BedrockAgentCoreApp                                        │ │
│  │   └── @app.entrypoint  ←── HTTP POST /invocations           │ │
│  │       └── Strands Agent                                      │ │
│  │           ├── BedrockModel (amazon.nova-pro-v1:0)            │ │
│  │           └── get_weather_forecast tool → NWS API            │ │
│  │                                                              │ │
│  │   IAM Role (auto-provisioned by AgentCore CLI)               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Infrastructure provisioned via AWS CDK (managed by CLI)          │
└─────────────────────────────────────────────────────────────────┘
         ▲
         │  agentcore invoke / agentcore dev
         │
    Developer / Client
```

## Project Structure

```
agentcore/
└── weatheragent/
    ├── AGENTS.md                   # AI coding assistant context for this project
    ├── README.md                   # AgentCore CLI-generated readme
    ├── agentcore/                  # AgentCore configuration (source of truth)
    │   ├── agentcore.json          # Project spec: agents, memories, credentials
    │   ├── aws-targets.json        # Deployment targets (account, region)
    │   ├── .env.local              # Local env vars (gitignored)
    │   ├── .llm-context/           # TypeScript type definitions for the JSON schemas
    │   └── cdk/                    # AWS CDK project (auto-managed by CLI)
    └── app/
        └── weatheragent/
            ├── main.py             # Agent code with @app.entrypoint
            ├── model/
            │   └── load.py         # BedrockModel configuration
            ├── mcp_client/         # MCP client (scaffolded by CLI)
            └── pyproject.toml      # Python dependencies
```

## Key Differences from Local Version

| Aspect | Local | AgentCore |
|--------|-------|-----------|
| Entry point | `if __name__ == "__main__"` loop | `@app.entrypoint` async generator |
| Invocation | `python3 weather_agent.py` | HTTP POST to `/invocations` |
| Scaling | Single process | Auto-scales on demand |
| Auth | Local `aws configure` credentials | IAM role attached to the runtime |
| Monitoring | Print statements | OpenTelemetry traces → CloudWatch |
| Memory | Lost on exit | Persistent via AgentCore Memory (optional) |

## Implementation Details

### Entry Point (`main.py`)

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from model.load import load_model

app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload, context):
    agent = get_or_create_agent()
    stream = agent.stream_async(payload.get("prompt"))
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]

if __name__ == "__main__":
    app.run()
```

- `BedrockAgentCoreApp` provides the HTTP server and runtime lifecycle
- `@app.entrypoint` is the handler AgentCore calls on each invocation
- `agent.stream_async()` + `yield` streams tokens back to the caller as they're generated
- `get_or_create_agent()` singleton reuses the agent across invocations (warm start)

### Model Configuration (`model/load.py`)

```python
from strands.models.bedrock import BedrockModel

def load_model() -> BedrockModel:
    return BedrockModel(model_id="amazon.nova-pro-v1:0")
```

The model ID is managed separately so it can be changed without touching the agent logic.

### AgentCore Configuration (`agentcore/agentcore.json`)

The JSON config is the source of truth for all AgentCore resources. The CLI reads this file to provision infrastructure via CDK:

```json
{
  "name": "weatheragent",
  "runtimes": [],
  "memories": [],
  "credentials": [],
  "evaluators": [],
  "onlineEvalConfigs": [],
  "agentCoreGateways": []
}
```

Resources are added with `agentcore add` commands and reflected in this file.

## Prerequisites

- Node.js 20.x or later (for AgentCore CLI)
- Python 3.10+ with `uv` ([install](https://docs.astral.sh/uv/getting-started/installation/))
- AWS CLI configured with credentials that have Bedrock and CloudFormation permissions
- AgentCore CLI installed:

```bash
npm install -g @aws/agentcore --prefix ~/.npm-global
agentcore --version
```

## Development Workflow

### 1. Local Testing with `agentcore dev`

```bash
cd agentcore/weatheragent
agentcore dev
```

This starts a local HTTP server at `http://localhost:8080/invocations` and opens an interactive chat. The agent runs exactly as it would in production.

To test non-interactively:

```bash
# Terminal 1
agentcore dev --logs

# Terminal 2
agentcore dev "What's the weather in Seattle?" --stream
```

### 2. Deploy to AWS

```bash
agentcore deploy
```

This:
1. Packages your agent code as a zip artifact
2. Runs CDK to provision IAM roles, the AgentCore Runtime endpoint, and supporting resources
3. Uploads the artifact and activates the runtime

Check deployment status:

```bash
agentcore status
```

Expected output:

```
AgentCore Status (target: default, us-east-1)

Agents
  weatheragent: Deployed - Runtime: READY (arn:aws:bedrock-agentcore:...)
```

### 3. Invoke the Deployed Agent

```bash
agentcore invoke "What's the weather in Denver?" --stream
```

### 4. View Logs and Traces

```bash
agentcore logs
agentcore traces list --limit 10
```

## Adding AgentCore Features

### Memory — Persist conversations across sessions

```bash
agentcore add memory \
  --name WeatherMemory \
  --strategies SEMANTIC,SUMMARIZATION \
  --expiry 30

agentcore deploy
```

### Evaluations — Monitor agent quality automatically

```bash
agentcore add online-eval \
  --name QualityMonitor \
  --agent weatheragent \
  --evaluator Builtin.GoalSuccessRate \
  --sampling-rate 100 \
  --enable-on-create

agentcore deploy
```

### Gateway — Expose tools via MCP to other agents

```bash
agentcore add gateway \
  --name weather-gateway \
  --runtimes weatheragent

agentcore deploy
```

## Clean Up

Remove all deployed AWS resources:

```bash
agentcore remove all
agentcore deploy
```

## Troubleshooting

**`AccessDeniedException` — Model access denied / INVALID_PAYMENT_INSTRUMENT**

The model requires a valid payment method and Bedrock model access enabled. Go to [Bedrock Console → Model Access](https://console.aws.amazon.com/bedrock/home#/modelaccess) and ensure the model is enabled. Alternatively, switch to `amazon.nova-pro-v1:0` in `model/load.py` which doesn't require a marketplace subscription.

**`ValidationException` — on-demand throughput not supported**

The model ID requires a cross-region inference profile (prefixed with `us.`) or use a model that supports on-demand throughput like `amazon.nova-pro-v1:0`.

**SSL errors calling NWS API**

The agent uses `ssl._create_unverified_context()` as a fallback for environments without root certificates. This is safe for the public read-only NWS API.

## Resources

| Resource | Link |
|----------|------|
| AgentCore Docs | https://docs.aws.amazon.com/bedrock-agentcore/ |
| AgentCore CLI | https://github.com/aws/agentcore-cli |
| AgentCore Python SDK | https://github.com/aws/bedrock-agentcore-sdk-python |
| Strands Agents Docs | https://strandsagents.com/latest/ |
| Getting Started Workshop | https://catalog.us-east-1.prod.workshops.aws/workshops/850fcd5c-fd1f-48d7-932c-ad9babede979 |
| AgentCore Deep Dive Workshop | https://catalog.workshops.aws/agentcore-deep-dive |
