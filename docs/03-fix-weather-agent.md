# Fix Your Current Weather Agent

Let's apply what you've learned. Here's your current `weather_agent.py` rewritten
with best practices.

## Problems with the Current Version

1. ❌ Hardcoded API key (security risk)
2. ❌ Uses Anthropic direct API (not compatible with AgentCore)
3. ❌ No custom tools (relies entirely on pre-built tools)
4. ❌ No error handling
5. ❌ Runs as a script with no structure

## What Changed

- `BedrockModel` instead of `AnthropicModel` — uses AWS credentials
- Custom `get_weather_forecast` tool with proper error handling
- Better system prompt that lists tools and guidelines
- Interactive loop so you can have a conversation
- Environment variable for region (not hardcoded)

## Improved Version

See: [`strands/weather_agent_v2.py`](../strands/weather_agent_v2.py)

## How to Run

```bash
cd strands
pip install -r requirements.txt
aws configure  # if not already done
python weather_agent_v2.py
```

## Before vs After Comparison

### Model Configuration

**Before:**
```python
from strands.models.anthropic import AnthropicModel

model = AnthropicModel(
    client_args={"api_key": "<Your API Key>"},  # Hardcoded key = security risk
    model_id="claude-3-7-sonnet-20250219",
    max_tokens=1000
)
```

**After:**
```python
from strands.models.bedrock import BedrockModel

model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    max_tokens=4096,
)
```

### Tools

**Before:** Only pre-built tools, no custom logic
```python
from strands_tools import current_time, http_request, use_aws
tools = [current_time, http_request, use_aws]
```

**After:** Custom tool with error handling + pre-built tools
```python
from strands import tool
from strands_tools import current_time, use_aws

@tool
def get_weather_forecast(city: str) -> str:
    """Get the weather forecast for a US city using the National Weather Service API.

    Args:
        city: Name of a US city (e.g., "New York", "Chicago", "San Francisco")
    """
    try:
        # ... API call with proper error handling
    except urllib.error.HTTPError as e:
        return f"Weather API error (HTTP {e.code}): {e.reason}"

tools = [get_weather_forecast, current_time, use_aws]
```

### Execution

**Before:** One-shot script, no conversation
```python
response = subject_expert(query)
```

**After:** Interactive conversation loop
```python
while True:
    user_input = input("\nYou: ").strip()
    if user_input.lower() in ("quit", "exit", "q"):
        break
    response = agent(user_input)
```
