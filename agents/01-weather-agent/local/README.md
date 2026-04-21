# Weather Agent — Local

A Strands agent that runs locally with Python. Fetches live weather forecasts from the National Weather Service API using Amazon Bedrock as the model provider.

## Purpose

This is the local development version of the weather agent. It demonstrates:

- Creating a Strands agent with `BedrockModel` (IAM credentials, no API keys)
- Writing a custom `@tool` with proper docstrings and type hints
- Combining custom tools with pre-built tools from `strands-agents-tools`
- Running an interactive multi-turn conversation loop

## Architecture

```
weather_agent.py
│
├── BedrockModel
│   └── amazon.nova-pro-v1:0 (via AWS IAM credentials)
│
├── Tools
│   ├── get_weather_forecast  ← custom @tool → NWS API (weather.gov)
│   ├── current_time          ← strands-agents-tools → timezone data
│   └── use_aws               ← strands-agents-tools → AWS APIs
│
└── Agent Loop
    └── Think → Act → Observe → Decide → Respond
```

## Project Structure

```
local/
├── weather_agent.py    # Agent code
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Implementation Details

### Model

```python
from strands.models.bedrock import BedrockModel

model = BedrockModel(
    model_id="amazon.nova-pro-v1:0",
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    max_tokens=4096,
)
```

Uses AWS credentials from `aws configure` — no API keys required. The model ID can be any Bedrock-supported model you have access to.

### Custom Tool

```python
@tool
def get_weather_forecast(city: str) -> str:
    """Get the weather forecast for a US city using the National Weather Service API.

    Args:
        city: Name of a US city (e.g., "New York", "Chicago", "San Francisco")
    """
```

The `@tool` decorator converts the function into a JSON schema the LLM reads to decide when and how to call it:

- Function name → tool `name`
- Docstring first line → tool `description`
- Type hints → parameter `type`
- Args section → parameter `description`

The LLM never sees the function body — only the schema. Your Python code runs locally and returns results back to the model.

### Two-Step NWS API Call

The NWS API requires two requests to get a forecast:

```
Step 1: GET https://api.weather.gov/points/{lat},{lon}
        → Returns the forecast endpoint URL for those coordinates

Step 2: GET {forecast_url}
        → Returns the actual forecast periods
```

The tool handles both steps and returns the first 4 forecast periods formatted as plain text.

### System Prompt

```python
SYSTEM_PROMPT = """You are a helpful assistant with these capabilities:

1. Weather: Use get_weather_forecast to check weather for US cities
2. Time: Use current_time to get the current time in any timezone
3. AWS: Use use_aws to interact with AWS services

Guidelines:
- Always use tools to get real data — never make up weather or time information
- Format responses in a clear, readable way
- If a tool returns an error, explain the issue to the user
"""
```

The system prompt tells the model what tools are available and how to use them.

## Setup & Run

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the agent
python3 weather_agent.py
```

## Sample Queries

```
You: What's the weather in New York?
You: What time is it in Tokyo?
You: What's the weather in Miami and what time is it there?
You: List my S3 buckets
```

Type `quit` to exit.

## macOS SSL Note

If you see an SSL certificate error when calling the NWS API, Python on macOS may be missing root certificates. The agent handles this automatically with a fallback. For a permanent fix:

```bash
# Install certificates for your Python version
open /Applications/Python\ 3.x/Install\ Certificates.command

# Or install certifi
pip install certifi
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `strands-agents` | Core agent framework |
| `strands-agents-tools` | Pre-built tools (`current_time`, `use_aws`) |
| `boto3` | AWS SDK (used by `use_aws` tool) |

## Next Step: Deploy to AgentCore

Once you're comfortable running the agent locally, deploy it to Amazon Bedrock AgentCore Runtime for production use. See [agentcore/README.md](../agentcore/README.md).
