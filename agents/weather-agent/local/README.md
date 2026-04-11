# Weather Agent — Strands Agents SDK

A weather assistant agent built with [Strands Agents SDK](https://strandsagents.com) and
[Amazon Bedrock](https://aws.amazon.com/bedrock/). It fetches live weather forecasts from
the National Weather Service API, checks the current time in any timezone, and can interact
with your AWS account.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    User Query                        │
│  "What's the weather in New York?"                   │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                  Strands Agent                       │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  Model: Claude Sonnet (via Amazon Bedrock)     │  │
│  │  Auth: AWS credentials (IAM) — no API keys     │  │
│  └──────────────────┬─────────────────────────────┘  │
│                     │                                │
│          ┌──────────┼──────────┐                     │
│          ▼          ▼          ▼                     │
│  ┌─────────────┐ ┌────────┐ ┌─────────┐             │
│  │ get_weather  │ │current │ │ use_aws │             │
│  │ _forecast   │ │ _time  │ │         │             │
│  │ (custom)    │ │(built) │ │ (built) │             │
│  └──────┬──────┘ └───┬────┘ └────┬────┘             │
└─────────┼────────────┼───────────┼──────────────────┘
          │            │           │
          ▼            ▼           ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ NWS API  │ │ Timezone │ │ AWS APIs │
    │(weather) │ │  Data    │ │  (S3..)  │
    └──────────┘ └──────────┘ └──────────┘
```

## How It Works

The agent follows a **model-driven loop** (the agent loop):

1. You send a natural language query
2. The LLM (Claude Sonnet on Bedrock) reads the query + system prompt + available tools
3. The model decides which tools to call and in what order
4. Each tool executes and returns results back to the model
5. The model reasons over the results, decides if more tool calls are needed
6. Once satisfied, the model produces a final human-readable response

**Example flow:**

```
You: "What's the weather in Chicago and what time is it there?"

Agent THINKS → "I need weather and time for Chicago"
Agent CALLS  → get_weather_forecast("Chicago")
Agent CALLS  → current_time("America/Chicago")
Agent READS  → Weather: 72°F, Sunny | Time: 2:30 PM CDT
Agent RESPONDS → "It's currently 2:30 PM in Chicago. The weather is 72°F
                  and sunny with light winds from the southwest..."
```

## Under the Hood: How the LLM Knows About Your Tools

When you write a tool with `@tool`, you're not just writing a Python function — you're
creating a **contract** that the LLM reads to decide when and how to call it.

### What the `@tool` Decorator Does

The decorator reads your function and converts it into a JSON schema:

```python
# You write this:
@tool
def get_weather_forecast(city: str) -> str:
    """Get the weather forecast for a US city.

    Args:
        city: Name of a US city (e.g., "New York", "Chicago")
    """
```

```json
// Strands generates this JSON schema:
{
  "name": "get_weather_forecast",
  "description": "Get the weather forecast for a US city.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "city": {
        "type": "string",
        "description": "Name of a US city (e.g., \"New York\", \"Chicago\")"
      }
    },
    "required": ["city"]
  }
}
```

- Function name → `"name"`
- Docstring first line → `"description"`
- Type hints → parameter `"type"`
- Args section → parameter `"description"`

### What Gets Sent to the LLM on Every Call

When you call `agent("What's the weather in Chicago?")`, the Strands SDK sends this
to the LLM (Claude on Bedrock):

```json
{
  "system": "You are a helpful assistant...",

  "tools": [
    {
      "name": "get_weather_forecast",
      "description": "Get the weather forecast for a US city.",
      "inputSchema": { "properties": { "city": { "type": "string" } } }
    },
    {
      "name": "current_time",
      "description": "Get current time in a timezone.",
      "inputSchema": { "properties": { "timezone": { "type": "string" } } }
    },
    {
      "name": "use_aws",
      "description": "Interact with AWS services.",
      "inputSchema": { "..." : "..." }
    }
  ],

  "messages": [
    { "role": "user", "content": "What's the weather in Chicago?" }
  ]
}
```

**All 3 tool schemas are sent on every request.** The LLM reads them all and picks
the right one.

### How the LLM Responds

The LLM doesn't return text — it returns a **tool call**:

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "tool_use",
      "name": "get_weather_forecast",
      "input": { "city": "Chicago" }
    }
  ]
}
```

The LLM extracted `"Chicago"` from your natural language sentence and mapped it to the
`city` parameter. It knew to do this because it read the tool's name, description, and
parameter schema.

### The Full Request/Response Cycle

```
YOUR CODE                    STRANDS SDK                   LLM (Claude on Bedrock)
─────────                    ───────────                   ───────────────────────

@tool decorator          ──► Converts to JSON schema
                              {name, description,
                               inputSchema}

agent("weather in        ──► Sends API request:        ──► Receives:
 Chicago?")                   system prompt                 - system prompt
                              + 3 tool schemas              - 3 tool JSON schemas
                              + user message                - "weather in Chicago?"

                                                            THINKS: "I should call
                                                            get_weather_forecast
                                                            with city='Chicago'"

                         ◄── Receives response:        ◄── {tool_use:
                              tool_use request               get_weather_forecast,
                                                             input: {city: "Chicago"}}

                         ──► Calls YOUR Python function:
                              get_weather_forecast("Chicago")
                              → returns "72°F, Sunny..."

                         ──► Sends tool result back:    ──► Receives weather data

                                                            THINKS: "I have the data,
                                                            let me write a response"

                         ◄── Receives final text:       ◄── "The weather in Chicago
                                                             is 72°F and sunny..."

print(response)          ◄──
```

**Key insight:** The LLM never sees your Python code. It only sees the JSON schema
(name + description + parameters). Your code runs on your machine (or AgentCore Runtime),
not inside the LLM. The LLM just decides *when* to call the tool and *what arguments*
to pass.

For more on what happens when you have 10, 50, or 100+ tools, see
[Tool Scaling & Progressive Disclosure](../docs/06-tool-scaling.md).

---

## Components

### Model

| Setting | Value |
| ------- | ----- |
| Provider | Amazon Bedrock (uses AWS credentials, no API keys) |
| Model ID | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| Max Tokens | 4096 |

### Tools

| Tool | Type | What It Does |
| ---- | ---- | ------------ |
| `get_weather_forecast` | Custom `@tool` | Calls the NWS API for live weather forecasts in 8 US cities |
| `current_time` | Pre-built (`strands-agents-tools`) | Gets the current time in any timezone |
| `use_aws` | Pre-built (`strands-agents-tools`) | Interacts with AWS services (S3, EC2, etc.) |

### Supported Cities

New York, Chicago, San Francisco, Miami, Seattle, Los Angeles, Denver, Boston

---

## Local Development

### Prerequisites

- Python 3.10+
- AWS credentials configured (`aws configure`)
- Claude model access enabled in [Amazon Bedrock console](https://console.aws.amazon.com/bedrock/)

### Setup & Run

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the agent
python3 weather_agent_v2.py
```

### Sample Queries

```
You: What's the weather in New York?
You: What time is it in Tokyo?
You: List my S3 buckets
You: What's the weather in Miami and what time is it there?
```

Type `quit` to exit.

### macOS SSL Note

If you see an SSL certificate error, Python on macOS is missing root certificates. The agent
handles this automatically with a fallback. For a permanent fix:

```bash
# Option 1: Install certificates for your Python version
open /Applications/Python\ 3.14/Install\ Certificates.command

# Option 2: Install certifi
pip install certifi
```

---

## Deploy to Amazon Bedrock AgentCore

AgentCore takes this agent from "runs on your laptop" to "runs securely at scale in the cloud."
The agent code stays almost the same — you wrap it with `BedrockAgentCoreApp`.

### What Changes for AgentCore

| Aspect | Local (current) | AgentCore |
| ------ | --------------- | --------- |
| How it runs | `python3 weather_agent_v2.py` | Managed container on AWS |
| Entry point | `if __name__ == "__main__"` loop | `@app.entrypoint` async function |
| Scaling | Single process on your machine | Auto-scales based on demand |
| Auth | Your local AWS credentials | IAM role attached to the runtime |
| Memory | Lost when you close the terminal | Persistent via AgentCore Memory (optional) |
| Monitoring | Print statements | OpenTelemetry traces in CloudWatch |

### Step 1: Install the AgentCore CLI

```bash
npm install -g @aws/agentcore --prefix ~/.npm-global
agentcore --version
```

### Step 2: Create an AgentCore Project

```bash
agentcore create \
  --name weatheragent \
  --framework Strands \
  --model-provider Bedrock \
  --defaults
```

This scaffolds:

```
weatheragent/
├── agentcore/
│   ├── agentcore.json          # Project config (agents, memories, etc.)
│   ├── aws-targets.json        # Deployment targets (region, account)
│   └── cdk/                    # CDK infrastructure (auto-managed)
└── app/
    └── weatheragent/
        ├── main.py             # ← Your agent code goes here
        ├── model/load.py       # Model configuration
        └── pyproject.toml      # Python dependencies
```

### Step 3: Replace main.py with Your Agent

Copy your weather agent code into the AgentCore project, wrapped with the runtime entrypoint.

Replace `weatheragent/app/weatheragent/main.py` with:

```python
"""Weather Agent — deployed on Amazon Bedrock AgentCore Runtime."""

import json
import ssl
import urllib.request
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model

app = BedrockAgentCoreApp()
log = app.logger

# SSL context for NWS API
try:
    _ssl_context = ssl.create_default_context()
except Exception:
    _ssl_context = ssl._create_unverified_context()


# --- Tools (same as local version) ---

@tool
def get_weather_forecast(city: str) -> str:
    """Get the weather forecast for a US city using the National Weather Service API.

    Args:
        city: Name of a US city (e.g., "New York", "Chicago", "San Francisco")
    """
    city_coords = {
        "new york": (40.7128, -74.0060),
        "chicago": (41.8781, -87.6298),
        "san francisco": (37.7749, -122.4194),
        "miami": (25.7617, -80.1918),
        "seattle": (47.6062, -122.3321),
        "los angeles": (34.0522, -118.2437),
        "denver": (39.7392, -104.9903),
        "boston": (42.3601, -71.0589),
    }

    coords = city_coords.get(city.lower())
    if not coords:
        return f"City '{city}' not found. Supported: {', '.join(city_coords.keys())}"

    try:
        point_url = f"https://api.weather.gov/points/{coords[0]},{coords[1]}"
        req = urllib.request.Request(point_url, headers={"User-Agent": "weatheragent/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context) as resp:
            point_data = json.loads(resp.read())

        forecast_url = point_data["properties"]["forecast"]
        req = urllib.request.Request(forecast_url, headers={"User-Agent": "weatheragent/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context) as resp:
            forecast_data = json.loads(resp.read())

        periods = forecast_data["properties"]["periods"][:4]
        result = []
        for p in periods:
            result.append(
                f"  {p['name']}: {p['temperature']}°{p['temperatureUnit']}, "
                f"{p['shortForecast']}, Wind: {p['windSpeed']} {p['windDirection']}"
            )
        return f"Weather forecast for {city}:\n" + "\n".join(result)
    except Exception as e:
        return f"Error fetching weather: {str(e)}"


# --- System Prompt ---

SYSTEM_PROMPT = """You are a helpful weather assistant.

Use get_weather_forecast to check weather for US cities.
Always use the tool to get real data — never make up weather information.
Format responses clearly with temperature, conditions, and wind."""


# --- Agent ---

_agent = None

def get_or_create_agent():
    global _agent
    if _agent is None:
        _agent = Agent(
            model=load_model(),
            system_prompt=SYSTEM_PROMPT,
            tools=[get_weather_forecast],
        )
    return _agent


# --- AgentCore Runtime Entrypoint ---

@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Weather Agent...")
    agent = get_or_create_agent()
    stream = agent.stream_async(payload.get("prompt"))
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
```

**Key differences from the local version:**

| Change | Why |
| ------ | --- |
| `BedrockAgentCoreApp()` wraps the agent | Provides the runtime entrypoint AgentCore needs |
| `@app.entrypoint` async function | Defines how AgentCore invokes your agent |
| `agent.stream_async()` with `yield` | Streams responses back to the caller |
| `load_model()` instead of inline `BedrockModel` | Uses the CLI-managed model config |
| `get_or_create_agent()` singleton | Reuses the agent across invocations (warm start) |

### Step 4: Test Locally

```bash
cd weatheragent
agentcore dev
```

This starts an interactive chat in your terminal. Try:

```
What's the weather in Seattle?
```

Press `Esc` to exit.

You can also test non-interactively:

```bash
# In one terminal:
agentcore dev --logs

# In another terminal:
agentcore dev "What's the weather in Denver?" --stream
```

### Step 5: Deploy to AWS

```bash
agentcore deploy
```

This packages your code, provisions IAM roles, and deploys to a managed serverless endpoint.

Check status:

```bash
agentcore status
```

You should see:

```
AgentCore Status (target: default, us-east-1)

Agents
  weatheragent: Deployed - Runtime: READY (arn:aws:bedrock-agentcore:...)
```

### Step 6: Invoke the Deployed Agent

```bash
agentcore invoke "What's the weather in New York?" --stream
```

Your agent is now running in the cloud.

### Step 7: View Logs and Traces

```bash
# Stream live logs
agentcore logs

# View recent traces
agentcore traces list --limit 10
```

---

## Next Steps: Add AgentCore Features

Once deployed, you can incrementally add production capabilities:

### Add Memory (remember conversations across sessions)

```bash
agentcore add memory \
  --name WeatherMemory \
  --strategies SEMANTIC,SUMMARIZATION \
  --expiry 30

agentcore deploy
```

### Add Evaluations (monitor agent quality)

```bash
agentcore add online-eval \
  --name QualityMonitor \
  --agent weatheragent \
  --evaluator Builtin.GoalSuccessRate \
  --sampling-rate 100 \
  --enable-on-create

agentcore deploy
```

### Add Gateway (share tools across agents via MCP)

```bash
agentcore add gateway \
  --name weather-gateway \
  --runtimes weatheragent

agentcore deploy
```

---

## Clean Up

Remove all deployed resources:

```bash
cd weatheragent
agentcore remove all
agentcore deploy
```

---

## Project Structure

```
agents/weather-agent/
├── weather_agent_v2.py    # Local agent (run directly with Python)
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Resources

| Resource | Link |
| -------- | ---- |
| Strands Agents Docs | https://strandsagents.com/latest/ |
| AgentCore Docs | https://docs.aws.amazon.com/bedrock-agentcore/ |
| AgentCore CLI | https://github.com/aws/agentcore-cli |
| AgentCore Python SDK | https://github.com/aws/bedrock-agentcore-sdk-python |
| Getting Started Workshop | https://catalog.us-east-1.prod.workshops.aws/workshops/850fcd5c-fd1f-48d7-932c-ad9babede979 |
