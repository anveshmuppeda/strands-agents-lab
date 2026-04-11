# Tool Scaling & Progressive Disclosure

What happens when your agent has 10, 50, or 100+ tools — and how production systems handle it.

---

## The Problem: Every Tool Gets Sent on Every Call

When you create an agent with tools, **all tool schemas are sent to the LLM on every
single API call**. The LLM reads them all to decide which one(s) to use.

```python
agent = Agent(
    model=model,
    tools=[tool_1, tool_2, tool_3, tool_4, tool_5]
)

# This sends ALL 5 tool schemas to the LLM
agent("What's the weather?")
```

The API request to the LLM looks like:

```json
{
  "system": "You are a helpful assistant...",
  "tools": [
    { "name": "tool_1", "description": "...", "inputSchema": {...} },
    { "name": "tool_2", "description": "...", "inputSchema": {...} },
    { "name": "tool_3", "description": "...", "inputSchema": {...} },
    { "name": "tool_4", "description": "...", "inputSchema": {...} },
    { "name": "tool_5", "description": "...", "inputSchema": {...} }
  ],
  "messages": [
    { "role": "user", "content": "What's the weather?" }
  ]
}
```

With 5 tools, this is fine. But what happens as you add more?

---

## How It Scales (and Where It Breaks)

| # of Tools | Performance | Cost | Accuracy | Verdict |
| ---------- | ----------- | ---- | -------- | ------- |
| 3-10 | Fast | Low | Excellent — LLM picks the right tool reliably | ✅ No problem |
| 10-20 | Slightly slower | Moderate — tool schemas consume input tokens | Good — occasional wrong picks | ⚠️ Watch it |
| 20-50 | Noticeably slower | High — hundreds of extra tokens per request | Degrades — LLM gets confused between similar tools | ❌ Needs a solution |
| 50-100+ | Slow | Very high | Poor — LLM frequently picks wrong tools or hallucinates parameters | ❌ Broken without a strategy |

**Why it gets expensive:** You pay for input tokens. Each tool schema is roughly 50-200
tokens. With 50 tools, that's 2,500-10,000 extra tokens on *every single request*, even
if the user just says "hello."

**Why accuracy drops:** When the LLM sees 50+ tool descriptions, it struggles to
distinguish between similar tools. For example, if you have `search_google`,
`search_wikipedia`, `search_arxiv`, `search_tavily`, and `search_docs`, the model
may pick the wrong search tool.

---

## Solution 1: Group Tools into Skill Categories

Instead of one agent with 50 tools, organize tools into **skills** — logical groups
that get loaded on demand.

```
❌ Bad: One agent, 50 tools sent every time

agent = Agent(tools=[
    get_weather, get_forecast, get_alerts,           # weather
    search_google, search_wikipedia, search_arxiv,   # search
    read_gmail, send_gmail, delete_gmail,             # email
    get_stock_price, get_financials, get_news,        # finance
    create_chart, create_poster, create_infographic,  # visualization
    ... 35 more tools
])
```

```
✅ Good: Skills loaded only when needed

skills/
├── weather/          # 3 tools
├── search/           # 4 tools
├── gmail/            # 3 tools
├── finance/          # 4 tools
├── visualization/    # 3 tools
└── ...
```

### How Progressive Disclosure Works

The `sample-strands-agent-with-agentcore` project in this workspace uses a 3-level system:

```
Level 1: CATALOG (always in system prompt — tiny, ~200 tokens)
  The agent sees a list of skill names and one-line descriptions:
  "weather: Check weather forecasts for US cities"
  "finance: Stock prices, financial data, market news"
  "gmail: Read, search, and manage Gmail"

Level 2: INSTRUCTIONS (loaded on demand — ~500 tokens per skill)
  User asks about weather → Agent calls skill_dispatcher("weather")
  → Full SKILL.md instructions for the weather skill are loaded
  → Agent now sees the 3 weather tool schemas

Level 3: EXECUTION (tool calls)
  Agent calls get_weather_forecast("Chicago")
  → Tool runs, returns data
```

**The result:** Instead of 50 tool schemas on every request, the LLM sees:
- Always: A small catalog (~200 tokens)
- On demand: Only the relevant skill's tools (~200 tokens)
- Total: ~400 tokens instead of ~5,000 tokens

### Code Example

```python
from strands import Agent, tool

# --- Skill Catalog (always loaded) ---
SKILL_CATALOG = """
Available skills:
- weather: Check weather forecasts for US cities
- finance: Stock prices, financial data, market news
- search: Search Google, Wikipedia, ArXiv
- email: Read and send Gmail messages

To use a skill, call load_skill with the skill name.
"""

# --- Skill Loader Tool ---
# This is the ONLY tool always available to the agent.
# It loads other tools on demand.

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
        # Dynamically add tools to the agent
        for t in SKILL_TOOLS[skill_name]:
            agent.tool_registry.register_tool(t)
        tool_names = [t.__name__ for t in SKILL_TOOLS[skill_name]]
        return f"Loaded {skill_name} skill. Available tools: {', '.join(tool_names)}"
    return f"Unknown skill: {skill_name}. Available: {', '.join(SKILL_TOOLS.keys())}"

# Agent starts with ONLY the skill loader
agent = Agent(
    model=model,
    system_prompt=f"You are a helpful assistant.\n\n{SKILL_CATALOG}",
    tools=[load_skill]  # Only 1 tool schema sent initially!
)
```

**Flow:**

```
User: "What's the stock price of Apple?"

LLM sees: 1 tool (load_skill) + skill catalog
LLM THINKS: "This is a finance question. I need to load the finance skill."
LLM CALLS: load_skill("finance")
→ 3 finance tools are now registered

LLM sees: 4 tools (load_skill + 3 finance tools)
LLM CALLS: get_stock_price("AAPL")
→ Returns "$198.50"

LLM RESPONDS: "Apple (AAPL) is currently trading at $198.50."
```

---

## Solution 2: AgentCore Gateway with Semantic Tool Selection

AgentCore Gateway takes a different approach — it sits between your agent and the tools,
and uses **semantic search** to pick the most relevant tools before sending them to the LLM.

```
Without Gateway:
  Agent → LLM sees ALL 50 tool schemas → picks one

With Gateway:
  Agent → Gateway receives the user query
       → Gateway semantically searches 50 tools
       → Gateway returns only the 3 most relevant tool schemas
       → LLM sees 3 tools → picks one
```

This is configured at the infrastructure level, not in your code:

```bash
agentcore add gateway \
  --name my-gateway \
  --runtimes MyAgent

agentcore deploy
```

The Gateway handles:
- Registering all your tools (Lambda functions, APIs, MCP servers)
- Semantic search to find relevant tools per query
- SigV4 authentication for secure tool access
- Centralized API key management via Secrets Manager

---

## Solution 3: Multi-Agent Architecture

Instead of one agent with many tools, use **specialized agents** that each have a few tools:

```
❌ One agent, 50 tools:

SuperAgent (50 tools) → LLM confused

✅ Multiple specialized agents, few tools each:

Supervisor Agent (3 tools: delegate_to_weather, delegate_to_finance, delegate_to_email)
    │
    ├── Weather Agent (3 tools: forecast, alerts, hourly)
    ├── Finance Agent (4 tools: stock_price, financials, news, charts)
    └── Email Agent (3 tools: read, send, search)
```

```python
from strands import Agent, tool

# Specialist agents — each has only a few tools
weather_agent = Agent(
    model=model,
    system_prompt="You are a weather specialist.",
    tools=[get_weather_forecast, get_alerts, get_hourly]
)

finance_agent = Agent(
    model=model,
    system_prompt="You are a finance specialist.",
    tools=[get_stock_price, get_financials, get_news]
)

# Wrap specialists as tools for the supervisor
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

# Supervisor only sees 2 tools, not 6
supervisor = Agent(
    model=model,
    system_prompt="Route questions to the right specialist.",
    tools=[ask_weather_agent, ask_finance_agent]
)
```

Each LLM call only sees 2-4 tool schemas, keeping accuracy high and costs low.

---

## Comparison: When to Use What

| Approach | Best For | Complexity | Example |
| -------- | -------- | ---------- | ------- |
| **All tools on one agent** | 3-15 tools | Simple | Your weather agent (3 tools) |
| **Skill-based progressive disclosure** | 15-100+ tools, single agent | Medium | `sample-strands-agent-with-agentcore` chatbot |
| **AgentCore Gateway** | Enterprise, shared tools across agents | Medium (infra) | Lambda functions as MCP tools |
| **Multi-agent (agent-as-tool)** | Distinct domains, clear boundaries | Medium | Weather agent + Finance agent + Email agent |
| **Multi-agent (Swarm)** | Conversational handoffs between specialists | Advanced | Sales → Support → Billing |
| **Multi-agent (A2A)** | Agents on separate runtimes/services | Advanced | Research agent on separate AgentCore Runtime |

---

## Key Takeaway

For your weather agent with 3 tools — don't worry about any of this. Just put all tools
on the agent and it works great.

When you grow to 15+ tools, start thinking about skill groups or multi-agent patterns.

When you hit 50+ tools, you need one of the solutions above — progressive disclosure,
Gateway semantic selection, or multi-agent architecture. The `sample-strands-agent-with-agentcore`
project in your workspace is a production example of how to handle 100+ tools.
