"""
Weather Tools Lambda — Gateway Target
Exposes: get_weather_forecast
"""

import json
import ssl
import urllib.request

_ssl_context = ssl._create_unverified_context()

CITY_COORDS = {
    "new york": (40.7128, -74.0060),
    "chicago": (41.8781, -87.6298),
    "san francisco": (37.7749, -122.4194),
    "miami": (25.7617, -80.1918),
    "seattle": (47.6062, -122.3321),
    "los angeles": (34.0522, -118.2437),
    "denver": (39.7392, -104.9903),
    "boston": (42.3601, -71.0589),
}


def handler(event, context):
    # Get tool name — Gateway uses camelCase key
    tool_name = context.client_context.custom.get("bedrockAgentCoreToolName", "")

    # Gateway prepends target name: "weather-tools___get_weather_forecast"
    if "___" in tool_name:
        tool_name = tool_name.split("___", 1)[1]

    print(f"Tool: {tool_name}, Event: {json.dumps(event)}")

    # Gateway sends tool arguments directly in event (not in event["body"])
    if tool_name == "get_weather_forecast":
        city = event.get("city", "")
        result = get_weather_forecast(city)
        return {"statusCode": 200, "body": result}

    return {"statusCode": 400, "body": f"Unknown tool: {tool_name}"}


def get_weather_forecast(city: str) -> str:
    coords = CITY_COORDS.get(city.lower())
    if not coords:
        return f"City '{city}' not found. Supported: {', '.join(CITY_COORDS.keys())}"
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
        lines = [f"{p['name']}: {p['temperature']}°{p['temperatureUnit']}, {p['shortForecast']}" for p in periods]
        return f"Weather forecast for {city}:\n" + "\n".join(lines)
    except Exception as e:
        return f"Error fetching weather: {str(e)}"
