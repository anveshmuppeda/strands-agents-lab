"""
Weather Agent — Using BedrockModel with custom + pre-built tools.

Prerequisites:
  pip install strands-agents strands-agents-tools
  aws configure  (set up your AWS credentials)
  Enable Claude model access in Amazon Bedrock console
"""

import os
import json
import ssl
import urllib.request
from strands import Agent, tool
from strands.models.bedrock import BedrockModel
from strands_tools import current_time, use_aws

# Fix for macOS SSL certificate issue with weather.gov
# macOS Python often ships without root certificates installed.
# Proper fix: run "Install Certificates.command" from your Python install folder,
# or run: pip install certifi
# This fallback uses an unverified context so the agent works immediately.
try:
    _ssl_context = ssl.create_default_context()
    # Test if certificates actually work
    urllib.request.urlopen("https://api.weather.gov", timeout=5, context=_ssl_context)
except Exception:
    _ssl_context = ssl._create_unverified_context()


# --- Model Configuration ---
# Uses AWS credentials from `aws configure` — no API keys needed
model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    max_tokens=4096,
)


# --- Custom Tools ---

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
        return f"City '{city}' not found. Supported cities: {', '.join(city_coords.keys())}"

    try:
        # Step 1: Get forecast endpoint for these coordinates
        point_url = f"https://api.weather.gov/points/{coords[0]},{coords[1]}"
        req = urllib.request.Request(point_url, headers={"User-Agent": "StrandsWeatherAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context) as resp:
            point_data = json.loads(resp.read())

        # Step 2: Fetch the actual forecast
        forecast_url = point_data["properties"]["forecast"]
        req = urllib.request.Request(forecast_url, headers={"User-Agent": "StrandsWeatherAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context) as resp:
            forecast_data = json.loads(resp.read())

        # Format the first 4 forecast periods
        periods = forecast_data["properties"]["periods"][:4]
        result = []
        for p in periods:
            result.append(
                f"  {p['name']}: {p['temperature']}°{p['temperatureUnit']}, "
                f"{p['shortForecast']}, Wind: {p['windSpeed']} {p['windDirection']}"
            )
        return f"Weather forecast for {city}:\n" + "\n".join(result)

    except urllib.error.HTTPError as e:
        return f"Weather API error (HTTP {e.code}): {e.reason}"
    except urllib.error.URLError as e:
        return f"Could not connect to weather service: {str(e.reason)}"
    except Exception as e:
        return f"Error fetching weather: {str(e)}"


# --- System Prompt ---

SYSTEM_PROMPT = """You are a helpful assistant with these capabilities:

1. **Weather**: Use get_weather_forecast to check weather for US cities
2. **Time**: Use current_time to get the current time in any timezone
3. **AWS**: Use use_aws to interact with AWS services (S3, EC2, etc.)

Guidelines:
- Always use tools to get real data — never make up weather or time information
- Format responses in a clear, readable way
- If a tool returns an error, explain the issue to the user
- For weather, mention temperature, conditions, and wind
"""


# --- Agent ---

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[get_weather_forecast, current_time, use_aws],
)


# --- Run ---

if __name__ == "__main__":
    print("Weather Agent (type 'quit' to exit)")
    print("-" * 40)

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if not user_input:
            continue

        print("\nAgent: ", end="")
        response = agent(user_input)
        print()
