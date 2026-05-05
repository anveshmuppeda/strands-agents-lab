# AgentCore Memory Agent (Part 5)

## *Making Agents Remember: Conversations That Persist Across Sessions*

Add **AgentCore Memory** to the Gateway Agent from Guide 04 so it remembers conversations.
When a user returns, the agent knows their name, what they asked before, and can continue
where it left off.

> **Prerequisite:** Complete [01-weather-agent](../01-weather-agent/) and
> [04-gateway-agent](../04-gateway-agent/) first.

---

## The Problem

Without memory, every agent session starts fresh:

```
Session 1:
  You: "My name is Alex. Check subnet-abc for me."
  Agent: "Hi Alex! Subnet-abc is a private subnet in vpc-123..."

Session 2 (new session):
  You: "What subnet did I ask about?"
  Agent: "I don't have any context about previous conversations."  ← forgot
```

With AgentCore Memory:

```
Session 1:
  You: "My name is Alex. Check subnet-abc for me."
  Agent: "Hi Alex! Subnet-abc is a private subnet..."
  → Memory saves the conversation automatically

Session 2 (new session):
  You: "What subnet did I ask about?"
  Agent: "You asked about subnet-abc — it's a private subnet in vpc-123."  ← remembers!
```

---

## What is AgentCore Memory?

A managed AWS service that stores and retrieves conversation history for agents.

| Type | What It Stores | How Long | Use Case |
|------|---------------|----------|----------|
| **Short-term** | Raw conversation turns (last K messages) | Configurable (1-365 days) | Continue conversations after session expires |
| **Long-term** | Extracted facts, preferences, summaries | Permanent | "Remember my name is Alex" across all sessions |

This guide uses **short-term memory** — the simplest starting point.

---

## How Memory Works

There are two ways to add memory to a Strands agent:

### Approach 1: Hooks (local version)

You write two hook functions that Strands calls automatically:

```python
class MemoryHookProvider(HookProvider):
    def on_agent_initialized(self, event):
        # Load last 5 turns from memory → append to system prompt
        recent = memory_client.get_last_k_turns(memory_id, actor_id, session_id, k=5)
        event.agent.system_prompt += f"\nRecent conversation:\n{context}"

    def on_message_added(self, event):
        # Save every new message to memory
        memory_client.create_event(memory_id, actor_id, session_id, messages=[...])

agent = Agent(hooks=[MemoryHookProvider(client, memory_id)], ...)
```

### Approach 2: SessionManager (AgentCore version — recommended)

Use the built-in `AgentCoreMemorySessionManager` which handles everything:

```python
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

config = AgentCoreMemoryConfig(
    memory_id=MEMORY_ID,
    session_id=session_id,
    actor_id=actor_id,
)
session_manager = AgentCoreMemorySessionManager(config, region_name=REGION)

agent = Agent(
    model=model,
    tools=[mcp_client],
    session_manager=session_manager,  # ← one line adds memory
)
```

The SessionManager automatically:
- Loads conversation history when the agent starts
- Saves every message as it happens
- Handles session tracking and cleanup

---

## What Changed from Guide 04

| Aspect | 04-gateway-agent | 05-memory-agent |
|--------|-----------------|-----------------|
| Memory | None — forgets on session end | AgentCore Memory — remembers across sessions |
| New env var | — | `MEMORY_ID` |
| New import | — | `AgentCoreMemoryConfig`, `AgentCoreMemorySessionManager` |
| Agent creation | `Agent(model, tools)` | `Agent(model, tools, session_manager=...)` |
| Session handling | Stateless | Reinitializes when session_id changes |

The Gateway connection, SigV4 auth, MCP client — all stay exactly the same.

---

## Project Structure

```
05-memory-agent/
├── local/
│   ├── memory_weather_agent.py     # Simple weather agent with memory hooks
│   └── requirements.txt
│
├── agentcore/
│   ├── main.py                     # Gateway agent + memory (for AgentCore Runtime)
│   └── requirements.txt
│
└── README.md
```

---

## Version 1: Local (Simple Weather Agent with Memory)

### Setup & Run

```bash
cd agents/05-memory-agent/local

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 memory_weather_agent.py
```

First run creates a Memory resource. Save the `MEMORY_ID` from the output.

### Test Memory

```bash
# Session 1
You: My name is Alex. Weather in NYC?
Agent: Hi Alex! NYC is 72°F...
You: quit

# Session 2 (restart with same MEMORY_ID)
export MEMORY_ID=WeatherAgentMemory-xxxxx
python3 memory_weather_agent.py

You: What's my name?
Agent: Your name is Alex!  ← remembered
```

---

## Version 2: AgentCore (Gateway Agent with Memory)

This is the full Gateway agent from Guide 04 with memory added.

### Prerequisites

- Gateway deployed from Guide 04 (you need `GATEWAY_URL`)
- AgentCore Memory resource created (see Step 1 below)

### Step 1: Create Memory Resource

```bash
# Using the AgentCore CLI
agentcore add memory \
  --name GatewayAgentMemory \
  --strategies SEMANTIC,SUMMARIZATION \
  --expiry 30

agentcore deploy
```

Or create via boto3:

```python
from bedrock_agentcore.memory import MemoryClient

client = MemoryClient(region_name="us-east-1")
memory = client.create_memory_and_wait(
    name="GatewayAgentMemory",
    strategies=[],
    description="Short-term memory for gateway agent",
    event_expiry_days=7,
)
print(f"MEMORY_ID={memory['id']}")
```

### Step 2: Deploy with AgentCore CLI

```bash
agentcore create --name MemoryGatewayAgent --framework Strands --model-provider Bedrock --defaults
cd MemoryGatewayAgent

# Copy the agent code
cp /path/to/agents/05-memory-agent/agentcore/main.py app/MemoryGatewayAgent/main.py
```

Add environment variables to `agentcore/agentcore.json`:

```json
{
  "runtimes": [{
    "name": "MemoryGatewayAgent",
    "environmentVariables": {
      "GATEWAY_URL": "https://your-gateway.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
      "MEMORY_ID": "GatewayAgentMemory-xxxxx",
      "MODEL_ID": "us.meta.llama3-3-70b-instruct-v1:0"
    }
  }]
}
```

```bash
agentcore dev    # test locally
agentcore deploy # deploy to AWS
```

### Step 3: Test Memory Across Sessions

```bash
# Session 1
agentcore invoke '{"prompt": "My name is Alex. Check subnet subnet-abc."}' --stream

# Session 2 (new invocation — same session_id maintained by Runtime)
agentcore invoke '{"prompt": "What subnet did I ask about?"}' --stream
# → "You asked about subnet-abc..."
```

---

## Key Concepts

### Memory ID

A unique identifier for your memory resource. Created once, set as `MEMORY_ID` env var.
All conversations for this agent are stored under this ID.

### Actor ID

Identifies who is talking. In a multi-user app, each user gets a different actor ID.
Passed in the payload: `{"prompt": "...", "actor_id": "user_123"}`.

### Session ID

Groups conversation turns together. On AgentCore Runtime, `context.session_id` is
provided automatically by the runtime. Locally, you set it yourself.

### SessionManager vs Hooks

| | SessionManager | Hooks |
|---|---------------|-------|
| Code | One line: `session_manager=...` | ~40 lines of hook code |
| Auto save/load | Yes | You write it |
| Works with Runtime | Yes (uses `context.session_id`) | Manual session tracking |
| Recommended for | AgentCore Runtime deployment | Local development, custom logic |

---

## IAM Permissions for Memory

The agent's IAM role needs these additional permissions:

```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock-agentcore:CreateEvent",
    "bedrock-agentcore:GetLastKTurns",
    "bedrock-agentcore:GetMemory",
    "bedrock-agentcore:ListMemories"
  ],
  "Resource": "arn:aws:bedrock-agentcore:*:*:memory/*"
}
```

If deploying via CDK, add this to the agent's IAM role in `runtime_stack.py`.

---

## Resources

| Resource | Link |
|----------|------|
| AgentCore Memory Docs | https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html |
| Short-term Memory Tutorial | `agentcore-samples/01-tutorials/04-AgentCore-memory/01-short-term-memory/` |
| Memory + Runtime Tutorial | `agentcore-samples/01-tutorials/04-AgentCore-memory/03-advanced-patterns/02-memory-runtime-integration/` |
| Strands SessionManager | https://strandsagents.com/latest/user-guide/concepts/agents/session-manager/ |
