"""
Weather Tools Lambda — Gateway Target

Exposes: get_weather_forecast

Gateway calls this Lambda with the tool name in context.client_context.custom
and the tool parameters in the event body.
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
    """Lambda handler — Gateway sends MCP JSON-RPC tools/call requests."""
    body = event if isinstance(event, dict) else json.loads(event)

    # MCP JSON-RPC format: {"method": "tools/call", "params": {"name": "...", "arguments": {...}}}
    params = body.get("params", {})
    tool_name = params.get("name", "")
    tool_args = params.get("arguments", {})

    if tool_name == "get_weather_forecast":
        city = tool_args.get("city", "")
        result = get_weather_forecast(city)
        return {"content": [{"type": "text", "text": result}]}

    return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}


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
        result = []
        for p in periods:
            result.append(
                f"  {p['name']}: {p['temperature']}°{p['temperatureUnit']}, "
                f"{p['shortForecast']}, Wind: {p['windSpeed']} {p['windDirection']}"
            )
        return f"Weather forecast for {city}:\n" + "\n".join(result)
    except Exception as e:
        return f"Error fetching weather: {str(e)}"
