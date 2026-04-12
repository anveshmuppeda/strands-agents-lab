# Core Strands Patterns (With Code Examples)

Now that you know the terminology, let's learn every core pattern in Strands Agents.
Each section builds on the previous one.

---

## Pattern 1: The Simplest Agent

The most basic agent — no tools, no system prompt. Just a model that answers questions.

```python
from strands import Agent

agent = Agent()
response = agent("Explain what an API is in one sentence.")
print(response)
```

What happens:
1. Strands creates an agent with the default model (Bedrock Claude)
2. Your message goes to the model
3. The model generates a response
4. The response is returned

This is essentially a chatbot. No tools, no agentic behavior.

---

## Pattern 2: Choosing Your Model

Your current `weather_agent.py` uses `AnthropicModel` with a hardcoded API key.
Here's how to switch to `BedrockModel`:

**Before (your current code — not recommended for production):**
```python
from strands.models.anthropic import AnthropicModel

model = AnthropicModel(
    client_args={"api_key": "<Your API Key>"},  # Hardcoded key = security risk
    model_id="claude-3-7-sonnet-20250219",
    max_tokens=1000
)
```

**After (recommended — uses AWS credentials):**
```python
from strands.models.bedrock import BedrockModel

model = BedrockModel(
    model_id="amazon.nova-pro-v1:0",
    region_name="us-east-1",
    max_tokens=4096
)
```

**Why BedrockModel is better:**
- Uses your AWS credentials (`aws configure`) — no API keys to leak
- Required for AgentCore deployment
- Access to multiple models (Claude, Nova, Llama) through one interface
- Pay-per-use through your AWS account

**Available model providers:**

```python
# Amazon Bedrock (recommended)
from strands.models.bedrock import BedrockModel
model = BedrockModel(model_id="amazon.nova-pro-v1:0")

# Anthropic direct
from strands.models.anthropic import AnthropicModel
model = AnthropicModel(client_args={"api_key": "..."}, model_id="claude-sonnet-4-20250514")

# OpenAI
from strands.models.openai import OpenAIModel
model = OpenAIModel(client_args={"api_key": "..."}, model_id="gpt-4o")

# Local model via Ollama
from strands.models.ollama import OllamaModel
model = OllamaModel(model_id="llama3.2")

# Pass to agent
agent = Agent(model=model)
```

---

## Pattern 3: System Prompts

The system prompt shapes everything about how your agent behaves.

```python
from strands import Agent
from strands.models.bedrock import BedrockModel

model = BedrockModel(model_id="amazon.nova-pro-v1:0")

# A focused, well-structured system prompt
SYSTEM_PROMPT = """You are a Python code reviewer.

Your job:
- Review code snippets the user provides
- Point out bugs, security issues, and style problems
- Suggest improvements with code examples
- Be concise and direct

Rules:
- Never write complete implementations, only suggest changes
- Always explain WHY something is a problem, not just WHAT
- Rate severity: 🔴 Critical, 🟡 Warning, 🟢 Suggestion
"""

agent = Agent(model=model, system_prompt=SYSTEM_PROMPT)
agent("Review this: password = input('Enter password:')")
```

**Tips for good system prompts:**
- Be specific about the agent's role
- List what tools are available and when to use them
- Define clear rules and constraints
- Keep it focused — don't try to make one agent do everything

---

## Pattern 4: Custom Tools with @tool

This is the most important pattern. Tools are how your agent interacts with the world.

**Basic tool:**
```python
from strands import Agent, tool

@tool
def calculate_bmi(weight_kg: float, height_m: float) -> str:
    """Calculate Body Mass Index.

    Args:
        weight_kg: Weight in kilograms
        height_m: Height in meters
    """
    bmi = weight_kg / (height_m ** 2)
    category = (
        "underweight" if bmi < 18.5
        else "normal" if bmi < 25
        else "overweight" if bmi < 30
        else "obese"
    )
    return f"BMI: {bmi:.1f} ({category})"

agent = Agent(tools=[calculate_bmi])
agent("I weigh 75kg and I'm 1.80m tall. What's my BMI?")
```

**What the model sees from your tool:**
- Name: `calculate_bmi`
- Description: "Calculate Body Mass Index" (from the docstring's first line)
- Parameters: `weight_kg` (float), `height_m` (float) (from type hints)
- Parameter descriptions: from the Args section of the docstring

**Critical rules for tools:**
1. Always use type hints (`weight_kg: float`, not just `weight_kg`)
2. Always write a clear docstring — the model reads it to decide when to use the tool
3. Always document Args — the model needs to know what each parameter means
4. Return strings for simple results, dicts for structured data

---

## Pattern 5: Multiple Tools

Agents become powerful when they have multiple tools and the model decides which to use.

```python
from strands import Agent, tool
from strands.models.bedrock import BedrockModel
import json

model = BedrockModel(model_id="amazon.nova-pro-v1:0")

@tool
def search_employees(query: str) -> str:
    """Search for employees by name or department.

    Args:
        query: Employee name or department name to search for
    """
    employees = {
        "alice": {"name": "Alice Smith", "dept": "Engineering", "salary": 120000},
        "bob": {"name": "Bob Jones", "dept": "Marketing", "salary": 95000},
        "carol": {"name": "Carol White", "dept": "Engineering", "salary": 130000},
    }
    results = [
        emp for key, emp in employees.items()
        if query.lower() in key or query.lower() in emp["dept"].lower()
    ]
    return json.dumps(results) if results else "No employees found."

@tool
def calculate_department_budget(department: str) -> str:
    """Calculate total salary budget for a department.

    Args:
        department: Department name (e.g., 'Engineering', 'Marketing')
    """
    budgets = {"Engineering": 250000, "Marketing": 95000, "Sales": 180000}
    budget = budgets.get(department)
    if budget:
        return f"{department} department budget: ${budget:,}"
    return f"No budget data for {department}"

@tool
def send_report(recipient: str, content: str) -> str:
    """Send a report to a specified email address.

    Args:
        recipient: Email address to send the report to
        content: The report content to send
    """
    # In production, this would actually send an email
    return f"Report sent to {recipient}"

agent = Agent(
    model=model,
    system_prompt="You are an HR assistant. Use your tools to help with employee queries.",
    tools=[search_employees, calculate_department_budget, send_report]
)

# The model will call search_employees, then calculate_department_budget
agent("How many engineers do we have and what's the engineering budget?")
```

The model decides the order and combination of tool calls based on the user's question.

---

## Pattern 6: Tools with External APIs

Real-world tools often call external services. Here's a pattern using HTTP requests:

```python
import os
import json
import urllib.request
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

model = BedrockModel(model_id="amazon.nova-pro-v1:0")

@tool
def get_weather(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location using the National Weather Service API.

    Args:
        latitude: Latitude of the location (e.g., 40.7128 for New York)
        longitude: Longitude of the location (e.g., -74.0060 for New York)
    """
    try:
        point_url = f"https://api.weather.gov/points/{latitude},{longitude}"
        req = urllib.request.Request(point_url, headers={"User-Agent": "WeatherAgent/1.0"})
        with urllib.request.urlopen(req) as resp:
            point_data = json.loads(resp.read())

        forecast_url = point_data["properties"]["forecast"]
        req = urllib.request.Request(forecast_url, headers={"User-Agent": "WeatherAgent/1.0"})
        with urllib.request.urlopen(req) as resp:
            forecast_data = json.loads(resp.read())

        periods = forecast_data["properties"]["periods"][:3]
        result = []
        for p in periods:
            result.append(f"{p['name']}: {p['temperature']}°{p['temperatureUnit']}, {p['shortForecast']}")
        return "\n".join(result)
    except Exception as e:
        return f"Error fetching weather: {str(e)}"

@tool
def geocode_city(city_name: str) -> str:
    """Convert a city name to latitude/longitude coordinates.

    Args:
        city_name: Name of the city (e.g., "New York", "San Francisco")
    """
    cities = {
        "new york": (40.7128, -74.0060),
        "san francisco": (37.7749, -122.4194),
        "chicago": (41.8781, -87.6298),
        "miami": (25.7617, -80.1918),
    }
    coords = cities.get(city_name.lower())
    if coords:
        return json.dumps({"city": city_name, "latitude": coords[0], "longitude": coords[1]})
    return f"Could not find coordinates for {city_name}"

agent = Agent(
    model=model,
    system_prompt="""You are a weather assistant. When asked about weather:
1. First use geocode_city to get coordinates
2. Then use get_weather with those coordinates
Always explain the forecast in a friendly, easy-to-understand way.""",
    tools=[geocode_city, get_weather]
)

agent("What's the weather like in Chicago?")
```

Notice how the system prompt guides the model to use tools in a specific order.
The model will:
1. Call `geocode_city("Chicago")` → gets coordinates
2. Call `get_weather(41.8781, -87.6298)` → gets forecast
3. Combine results into a friendly response

---

## Pattern 7: Conversation History (Multi-Turn)

By default, a Strands agent remembers the conversation within a session:

```python
from strands import Agent
from strands.models.bedrock import BedrockModel

model = BedrockModel(model_id="amazon.nova-pro-v1:0")

agent = Agent(
    model=model,
    system_prompt="You are a helpful coding tutor. Build on previous answers."
)

# Turn 1
agent("What is a Python list?")

# Turn 2 — the agent remembers Turn 1
agent("How do I sort one?")

# Turn 3 — the agent remembers Turns 1 and 2
agent("What about sorting in reverse?")
```

Each call to `agent()` adds to the conversation history. The model sees all previous
messages on every turn.

**To start a fresh conversation**, create a new agent instance or clear the messages.

---

## Pattern 8: Structured Output

Sometimes you need the agent to return data in a specific format (JSON, typed objects),
not just free text.

```python
from strands import Agent
from strands.models.bedrock import BedrockModel
from pydantic import BaseModel

model = BedrockModel(model_id="amazon.nova-pro-v1:0")

# Define the output structure
class MovieReview(BaseModel):
    title: str
    rating: float
    summary: str
    recommended: bool

agent = Agent(model=model)

# The agent returns a structured MovieReview object
result = agent.structured_output(
    MovieReview,
    "Review the movie 'Inception' by Christopher Nolan"
)

print(result.title)        # "Inception"
print(result.rating)       # 9.2
print(result.summary)      # "A mind-bending thriller..."
print(result.recommended)  # True
```

This is useful when your agent's output feeds into another system that expects structured data.

---

## Pattern 9: Async Agents

For web applications or when you need non-blocking execution:

```python
import asyncio
from strands import Agent
from strands.models.bedrock import BedrockModel

model = BedrockModel(model_id="amazon.nova-pro-v1:0")

async def main():
    agent = Agent(model=model, system_prompt="You are a helpful assistant.")

    # Async invocation
    result = await agent.invoke_async("What is the capital of France?")
    print(result)

    # Async streaming — get tokens as they're generated
    async for event in agent.stream_async("Write a haiku about coding"):
        if "data" in event and isinstance(event["data"], str):
            print(event["data"], end="", flush=True)

asyncio.run(main())
```

Streaming is especially important for chat UIs where you want to show the response
as it's being generated, not wait for the entire response.

---

## Pattern 10: Using Pre-Built Tools (strands-agents-tools)

The `strands-agents-tools` package provides ready-made tools. These are the ones you
used in your weather agent:

```python
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands_tools import (
    calculator,       # Math calculations
    current_time,     # Get current time in any timezone
    file_read,        # Read files
    file_write,       # Write files
    http_request,     # Make HTTP requests
    shell,            # Run shell commands
    use_aws,          # Interact with AWS services
    python_repl,      # Execute Python code
)

model = BedrockModel(model_id="amazon.nova-pro-v1:0")

agent = Agent(
    model=model,
    system_prompt="You are a DevOps assistant that can check systems and run commands.",
    tools=[current_time, http_request, shell, use_aws]
)

agent("What time is it in UTC and what's my AWS account ID?")
```

**Available tools in strands-agents-tools:**

| Tool | What It Does |
|------|-------------|
| `calculator` | Mathematical calculations |
| `current_time` | Get time in any timezone |
| `file_read` | Read file contents |
| `file_write` | Write/create files |
| `http_request` | Make HTTP GET/POST/PUT/DELETE requests |
| `shell` | Execute shell commands |
| `use_aws` | Call any AWS service via boto3 |
| `python_repl` | Execute Python code |
| `retrieve` | RAG retrieval from knowledge bases |

You can mix pre-built tools with your custom `@tool` functions:

```python
from strands import Agent, tool
from strands_tools import http_request, current_time

@tool
def format_report(data: str) -> str:
    """Format raw data into a clean report.

    Args:
        data: Raw data to format
    """
    return f"=== REPORT ===\n{data}\n=============="

agent = Agent(tools=[http_request, current_time, format_report])
```

---

## Pattern 11: Class-Based Tools (Stateful)

When tools need to share state (like a database connection), use class-based tools:

```python
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

class InventoryManager:
    def __init__(self):
        self.inventory = {
            "laptop": {"stock": 50, "price": 999.99},
            "mouse": {"stock": 200, "price": 29.99},
            "keyboard": {"stock": 150, "price": 79.99},
        }

    @tool
    def check_stock(self, product: str) -> str:
        """Check current stock level for a product.

        Args:
            product: Product name to check
        """
        item = self.inventory.get(product.lower())
        if item:
            return f"{product}: {item['stock']} units in stock at ${item['price']}"
        return f"Product '{product}' not found"

    @tool
    def update_stock(self, product: str, quantity: int) -> str:
        """Update stock quantity for a product.

        Args:
            product: Product name to update
            quantity: New stock quantity
        """
        if product.lower() in self.inventory:
            self.inventory[product.lower()]["stock"] = quantity
            return f"Updated {product} stock to {quantity} units"
        return f"Product '{product}' not found"

# Create instance — tools share the same inventory state
inventory = InventoryManager()

model = BedrockModel(model_id="amazon.nova-pro-v1:0")
agent = Agent(
    model=model,
    system_prompt="You are an inventory management assistant.",
    tools=[inventory.check_stock, inventory.update_stock]
)

agent("Check laptop stock, then reduce it by 5 units")
```

---

## Pattern 12: Tool Context

Tools can access information about the agent and the current invocation:

```python
from strands import Agent, tool, ToolContext
from strands.models.bedrock import BedrockModel

@tool(context=True)
def personalized_greeting(tool_context: ToolContext) -> str:
    """Generate a personalized greeting using the current user's info."""
    user_id = tool_context.invocation_state.get("user_id", "unknown")
    agent_name = tool_context.agent.name
    return f"Hello! I'm {agent_name}, and I see you're user {user_id}."

model = BedrockModel(model_id="amazon.nova-pro-v1:0")
agent = Agent(
    model=model,
    name="SupportBot",
    tools=[personalized_greeting]
)

# Pass state that tools can access
agent("Greet me", user_id="user-42")
```

Use `invocation_state` for data that changes per request (user IDs, session tokens).
Use class-based tools for data that stays the same (API keys, database connections).

---

## Pattern 13: Multi-Agent — Agent as a Tool

One agent can use another agent as a tool. The "outer" agent delegates tasks to
specialized "inner" agents:

```python
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

model = BedrockModel(model_id="amazon.nova-pro-v1:0")

# Specialist agents
code_reviewer = Agent(
    model=model,
    system_prompt="You are a code reviewer. Review code for bugs and style issues. Be concise."
)

doc_writer = Agent(
    model=model,
    system_prompt="You are a technical writer. Write clear, concise documentation."
)

# Wrap them as tools
@tool
def review_code(code: str) -> str:
    """Send code to the code review specialist for analysis.

    Args:
        code: The code snippet to review
    """
    result = code_reviewer(f"Review this code:\n{code}")
    return str(result)

@tool
def write_docs(description: str) -> str:
    """Send a description to the documentation specialist.

    Args:
        description: What to document
    """
    result = doc_writer(f"Write documentation for: {description}")
    return str(result)

# Supervisor agent that delegates
supervisor = Agent(
    model=model,
    system_prompt="""You are a tech lead. You have two specialists:
- review_code: For code review tasks
- write_docs: For documentation tasks
Delegate appropriately based on what the user needs.""",
    tools=[review_code, write_docs]
)

supervisor("Review this function and then write docs for it: def add(a, b): return a + b")
```

---

## Pattern 14: Swarm Pattern

The Swarm pattern allows agents to hand off conversations to each other. Each agent
is a specialist, and they transfer control based on the task:

```python
from strands import Agent, tool
from strands.models.bedrock import BedrockModel
from strands.multiagent.swarm import Swarm

model = BedrockModel(model_id="amazon.nova-pro-v1:0")

# Define specialist agents
sales_agent = Agent(
    model=model,
    system_prompt="""You are a sales specialist. Help with product recommendations
and pricing questions. If the customer has a technical issue, transfer to support.""",
    name="SalesAgent"
)

support_agent = Agent(
    model=model,
    system_prompt="""You are a technical support specialist. Help with troubleshooting
and technical issues. If the customer wants to buy something, transfer to sales.""",
    name="SupportAgent"
)

# Create a swarm — agents can hand off to each other
swarm = Swarm(
    agents=[sales_agent, support_agent],
    default_agent=sales_agent  # Start with sales
)

# The swarm routes to the right agent automatically
swarm("I'm interested in buying a laptop")       # → SalesAgent handles
swarm("Actually, my current laptop won't turn on") # → Transfers to SupportAgent
```

---

## Pattern 15: Error Handling in Tools

Production tools need proper error handling:

```python
from strands import Agent, tool
import json
import urllib.request

@tool
def fetch_api_data(endpoint: str) -> str:
    """Fetch data from an API endpoint.

    Args:
        endpoint: The API URL to fetch data from
    """
    try:
        req = urllib.request.Request(endpoint, headers={"User-Agent": "Agent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return json.dumps(data, indent=2)
    except urllib.error.HTTPError as e:
        return f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"Connection error: {str(e.reason)}"
    except json.JSONDecodeError:
        return "Error: Response was not valid JSON"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
```

The model reads error messages and can decide to retry, try a different approach,
or inform the user about the problem.
