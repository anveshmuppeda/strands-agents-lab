# Learning Path, Checklist & Tool Scaling

A complete guide covering what to learn, how to progress through phases, and how to handle tool scaling in production.

---

## Phase 1: Foundations Checklist

After working through [Terminology](./01-terminology.md) and [Core Patterns](./02-core-patterns.md), you should understand:

- [ ] What an AI agent is and how it differs from a chatbot
- [ ] The agent loop: think → act → observe → decide → respond
- [ ] What Strands Agents SDK is and why it's model-driven
- [ ] What Amazon Bedrock is and why `BedrockModel` is preferred
- [ ] What AgentCore is and its components (Runtime, Memory, Gateway, Identity)
- [ ] How to create custom tools with the `@tool` decorator
- [ ] Why docstrings and type hints matter for tools
- [ ] How to use pre-built tools from `strands-agents-tools`
- [ ] How system prompts guide agent behavior
- [ ] Multi-turn conversations and conversation history
- [ ] Structured output with Pydantic models
- [ ] Class-based tools for shared state
- [ ] Tool context for per-request data
- [ ] Multi-agent patterns (agent-as-tool, swarm)
- [ ] Error handling in tools
- [ ] Async agents and streaming

---

## Phase 2: AgentCore Deployment

Once comfortable with Phase 1, deploy your agent to AgentCore Runtime.

The key change is wrapping your agent with `BedrockAgentCoreApp`:

```python
# Phase 1: Local agent
from strands import Agent
agent = Agent(model=model, tools=[...])
agent("Hello")

# Phase 2: AgentCore-deployable agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload, context):
    agent = Agent(model=model, tools=[...])
    stream = agent.stream_async(payload.get("prompt"))
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]

if __name__ == "__main__":
    app.run()
```

The agent code stays the same — you just wrap it with the runtime entrypoint.

Workflow: `agentcore create` → `agentcore dev` → `agentcore deploy`

See the full deployment walkthrough: [agents/weather-agent/agentcore/](../agents/weather-agent/agentcore/README.md)

---

## Phase 3: AgentCore Features

- [ ] Memory — persist conversations across sessions with `agentcore add memory`
- [ ] Gateway — expose Lambda/API tools via MCP with `agentcore add gateway`
- [ ] Identity — agent and user authentication
- [ ] Observability — OpenTelemetry traces in CloudWatch
- [ ] Evaluations — automated quality monitoring with `agentcore add online-eval`

---

## Tool Scaling & Progressive Disclosure

What happens when your agent has 10, 50, or 100+ tools — and how production systems handle it.

### The Problem: Every Tool Gets Sent on Every Call

When you create an agent with tools, all tool schemas are sent to the LLM on every single API call. The LLM reads them all to decide which one(s) to use.

```python
agent = Agent(model=model, tools=[tool_1, tool_2, tool_3, tool_4, tool_5])

# This sends ALL 5 tool schemas to the LLM on every request
agent("What's the weather?")
```

With 5 tools this is fine. With 50+ it breaks down.

### How It Scales

| # of Tools | Performance | Cost | Accuracy | Verdict |
|------------|-------------|------|----------|---------|
| 3–10 | Fast | Low | Excellent | ✅ No problem |
| 10–20 | Slightly slower | Moderate | Good — occasional wrong picks | ⚠️ Watch it |
| 20–50 | Noticeably slower | High | Degrades — LLM confused between similar tools | ❌ Needs a solution |
| 50–100+ | Slow | Very high | Poor — wrong tools, hallucinated parameters | ❌ Broken without a strategy |

**Why it gets expensive:** Each tool schema is ~50–200 tokens. With 50 tools, that's 2,500–10,000 extra input tokens on every request, even for a simple "hello."

**Why accuracy drops:** When the LLM sees 50+ tool descriptions, it struggles to distinguish between similar tools (e.g., `search_google` vs `search_wikipedia` vs `search_arxiv`).

### Solution 1: Skill-Based Progressive Disclosure

Organize tools into skill groups that load on demand. The agent starts with only a catalog tool, then loads the relevant skill when needed.

```python
from strands import Agent, tool

SKILL_CATALOG = """
Available skills:
- weather: Check weather forecasts for US cities
- finance: Stock prices, financial data, market news
- search: Search Google, Wikipedia, ArXiv
- email: Read and send Gmail messages

To use a skill, call load_skill with the skill name.
"""

SKILL_TOOLS = {
    "weather": [get_weather_forecast, get_weather_alerts, get_hourly_forecast],
    "finance": [get_stock_price, get_financials, get_market_news],
    "search":  [search_google, search_wikipedia, search_arxiv],
    "email":   [read_gmail, send_gmail, search_gmail],
}

@tool
def load_skill(skill_name: str) -> str:
    """Load a skill to access its tools. Call this before using skill-specific tools.

    Args:
        skill_name: Name of the skill to load (weather, finance, search, email)
    """
    if skill_name in SKILL_TOOLS:
        for t in SKILL_TOOLS[skill_name]:
            agent.tool_registry.register_tool(t)
        tool_names = [t.__name__ for t in SKILL_TOOLS[skill_name]]
        return f"Loaded {skill_name} skill. Available tools: {', '.join(tool_names)}"
    return f"Unknown skill: {skill_name}. Available: {', '.join(SKILL_TOOLS.keys())}"

# Agent starts with ONLY the skill loader — 1 tool schema sent initially
agent = Agent(
    model=model,
    system_prompt=f"You are a helpful assistant.\n\n{SKILL_CATALOG}",
    tools=[load_skill]
)
```

**Flow:**
```
User: "What's the stock price of Apple?"

LLM sees: 1 tool (load_skill) + skill catalog (~200 tokens total)
LLM CALLS: load_skill("finance")  → 3 finance tools registered

LLM sees: 4 tools
LLM CALLS: get_stock_price("AAPL")  → "$198.50"

LLM RESPONDS: "Apple (AAPL) is currently trading at $198.50."
```

Instead of 50 tool schemas (~5,000 tokens) on every request, the LLM sees ~400 tokens total.

### Solution 2: AgentCore Gateway with Semantic Tool Selection

AgentCore Gateway sits between your agent and the tools, using semantic search to pick the most relevant tools before sending them to the LLM.

```
Without Gateway:
  Agent → LLM sees ALL 50 tool schemas → picks one

With Gateway:
  Agent → Gateway receives the user query
       → Gateway semantically searches 50 tools
       → Gateway returns only the 3 most relevant schemas
       → LLM sees 3 tools → picks one
```

```bash
agentcore add gateway \
  --name my-gateway \
  --runtimes MyAgent

agentcore deploy
```

The Gateway handles tool registration, semantic search, SigV4 authentication, and centralized API key management via Secrets Manager.

### Solution 3: Multi-Agent Architecture

Use specialized agents that each have a few tools, with a supervisor that delegates:

```
Supervisor Agent (2 tools: ask_weather_agent, ask_finance_agent)
    ├── Weather Agent (3 tools: forecast, alerts, hourly)
    └── Finance Agent (4 tools: stock_price, financials, news, charts)
```

```python
from strands import Agent, tool

weather_agent = Agent(model=model, system_prompt="You are a weather specialist.",
                      tools=[get_weather_forecast, get_alerts, get_hourly])

finance_agent = Agent(model=model, system_prompt="You are a finance specialist.",
                      tools=[get_stock_price, get_financials, get_news])

@tool
def ask_weather_agent(question: str) -> str:
    """Ask the weather specialist a question about weather.

    Args:
        question: The weather-related question
    """
    return str(weather_agent(question))

@tool
def ask_finance_agent(question: str) -> str:
    """Ask the finance specialist a question about stocks or markets.

    Args:
        question: The finance-related question
    """
    return str(finance_agent(question))

supervisor = Agent(model=model,
                   system_prompt="Route questions to the right specialist.",
                   tools=[ask_weather_agent, ask_finance_agent])
```

Each LLM call only sees 2–4 tool schemas, keeping accuracy high and costs low.

### When to Use What

| Approach | Best For | Complexity |
|----------|----------|------------|
| All tools on one agent | 3–15 tools | Simple |
| Skill-based progressive disclosure | 15–100+ tools, single agent | Medium |
| AgentCore Gateway | Enterprise, shared tools across agents | Medium (infra) |
| Multi-agent (agent-as-tool) | Distinct domains, clear boundaries | Medium |
| Multi-agent (Swarm) | Conversational handoffs between specialists | Advanced |
| Multi-agent (A2A) | Agents on separate runtimes/services | Advanced |

For a weather agent with 3 tools — don't worry about any of this. When you grow to 15+ tools, start thinking about skill groups or multi-agent patterns. At 50+ tools, one of the solutions above is required.

---

## Key Resources

| Resource | Link |
|----------|------|
| Strands Agents Documentation | https://strandsagents.com/latest/ |
| Strands Quickstart (Python) | https://strandsagents.com/docs/user-guide/quickstart/python/ |
| Custom Tools Guide | https://strandsagents.com/docs/user-guide/concepts/tools/custom-tools/ |
| Multi-Agent Patterns | https://strandsagents.com/docs/user-guide/concepts/multi-agent/ |
| Amazon Bedrock AgentCore Docs | https://docs.aws.amazon.com/bedrock-agentcore/ |
| AgentCore CLI | https://github.com/aws/agentcore-cli |
| AgentCore Samples | https://github.com/awslabs/amazon-bedrock-agentcore-samples |
| Build Production Agent (Video) | https://www.youtube.com/watch?v=wzIQDPFQx30 |
| Getting Started Workshop | https://catalog.us-east-1.prod.workshops.aws/workshops/850fcd5c-fd1f-48d7-932c-ad9babede979 |
| Deep Dive Workshop | https://catalog.workshops.aws/agentcore-deep-dive |
