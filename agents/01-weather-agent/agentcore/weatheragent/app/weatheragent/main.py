from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
import json
import ssl
import urllib.request

app = BedrockAgentCoreApp()
log = app.logger

# SSL context for NWS API
# AgentCore runtime and macOS Python often lack root certificates for weather.gov.
# Use unverified context as the default — this is safe for a public read-only API.
_ssl_context = ssl._create_unverified_context()


# --- Tools ---

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
        req = urllib.request.Request(point_url, headers={"User-Agent": "WeatherAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context) as resp:
            point_data = json.loads(resp.read())

        forecast_url = point_data["properties"]["forecast"]
        req = urllib.request.Request(forecast_url, headers={"User-Agent": "WeatherAgent/1.0"})
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
