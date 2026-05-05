"""
Weather Agent with AgentCore Memory (Short-Term) — Part 5

Same weather agent from Guide 01, but now it remembers conversations across sessions.
When you restart the agent, it loads the last 5 conversation turns from AgentCore Memory.

Prerequisites:
  pip install -r requirements.txt
  aws configure
  Enable Claude/Nova model access in Bedrock console

Environment variables:
  MEMORY_ID — AgentCore Memory ID (created by this script on first run)
  AWS_DEFAULT_REGION — AWS region (default: us-east-1)
"""

import os
import json
import ssl
import logging
import urllib.request
from datetime import datetime

from strands import Agent, tool
from strands.models.bedrock import BedrockModel
from strands.hooks import AgentInitializedEvent, HookProvider, HookRegistry, MessageAddedEvent
from bedrock_agentcore.memory import MemoryClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("memory-weather-agent")

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
ACTOR_ID = "user_local"
SESSION_ID = f"weather_session_{datetime.now().strftime('%Y%m%d')}"

_ssl_context = ssl._create_unverified_context()


# --- Model ---

model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name=REGION,
    max_tokens=4096,
)


# --- Tool (same as Guide 01) ---

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


@tool
def get_weather_forecast(city: str) -> str:
    """Get the weather forecast for a US city using the National Weather Service API.

    Args:
        city: Name of a US city (e.g., "New York", "Chicago", "San Francisco")
    """
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
        lines = [f"  {p['name']}: {p['temperature']}°{p['temperatureUnit']}, {p['shortForecast']}" for p in periods]
        return f"Weather forecast for {city}:\n" + "\n".join(lines)
    except Exception as e:
        return f"Error fetching weather: {str(e)}"


# --- Memory Hook ---

class MemoryHookProvider(HookProvider):
    """Automatically loads conversation history on agent start and saves new messages."""

    def __init__(self, memory_client: MemoryClient, memory_id: str):
        self.memory_client = memory_client
        self.memory_id = memory_id

    def on_agent_initialized(self, event: AgentInitializedEvent):
        """Load recent conversation history when agent starts."""
        try:
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")
            if not actor_id or not session_id:
                return

            recent_turns = self.memory_client.get_last_k_turns(
                memory_id=self.memory_id,
                actor_id=actor_id,
                session_id=session_id,
                k=5,
            )

            if recent_turns:
                context_messages = []
                for turn in recent_turns:
                    for message in turn:
                        role = message["role"]
                        content = message["content"]["text"]
                        context_messages.append(f"{role}: {content}")

                context = "\n".join(context_messages)
                event.agent.system_prompt += f"\n\nRecent conversation:\n{context}"
                logger.info(f"Loaded {len(recent_turns)} conversation turns from memory")
        except Exception as e:
            logger.error(f"Memory load error: {e}")

    def on_message_added(self, event: MessageAddedEvent):
        """Store new messages in memory."""
        messages = event.agent.messages
        try:
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")

            last_msg = messages[-1]
            if last_msg["content"][0].get("text"):
                self.memory_client.create_event(
                    memory_id=self.memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    messages=[(last_msg["content"][0]["text"], last_msg["role"])],
                )
        except Exception as e:
            logger.error(f"Memory save error: {e}")

    def register_hooks(self, registry: HookRegistry):
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        registry.add_callback(MessageAddedEvent, self.on_message_added)


# --- Create or Get Memory ---

def get_or_create_memory() -> str:
    """Create AgentCore Memory resource (or reuse existing one)."""
    client = MemoryClient(region_name=REGION)
    memory_name = "WeatherAgentMemory"

    # Check if MEMORY_ID is set
    memory_id = os.environ.get("MEMORY_ID", "")
    if memory_id:
        logger.info(f"Using existing memory: {memory_id}")
        return memory_id, client

    try:
        memory = client.create_memory_and_wait(
            name=memory_name,
            strategies=[],  # No strategies = short-term memory only
            description="Short-term memory for weather agent",
            event_expiry_days=7,
        )
        memory_id = memory["id"]
        logger.info(f"Created memory: {memory_id}")
        logger.info(f"Set MEMORY_ID={memory_id} to reuse this memory next time")
    except Exception as e:
        if "already exists" in str(e):
            memories = client.list_memories()
            memory_id = next((m["id"] for m in memories if memory_name in m.get("name", "")), None)
            logger.info(f"Memory already exists: {memory_id}")
        else:
            raise

    return memory_id, client


# --- Main ---

if __name__ == "__main__":
    memory_id, memory_client = get_or_create_memory()

    agent = Agent(
        name="WeatherAssistant",
        model=model,
        system_prompt=f"""You are a helpful weather assistant with memory.
You remember previous conversations in this session.

Use get_weather_forecast to check weather for US cities.
Always use the tool to get real data — never make up weather information.
Today's date: {datetime.today().strftime('%Y-%m-%d')}""",
        hooks=[MemoryHookProvider(memory_client, memory_id)],
        tools=[get_weather_forecast],
        state={"actor_id": ACTOR_ID, "session_id": SESSION_ID},
    )

    print(f"Weather Agent with Memory (session: {SESSION_ID})")
    print(f"Memory ID: {memory_id}")
    print("Type 'quit' to exit. Restart to test memory continuity.")
    print("-" * 50)

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
