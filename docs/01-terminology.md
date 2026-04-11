# Terminology & Definitions

Before writing a single line of code, let's get crystal clear on what everything means.

---

## What is an AI Agent?

An AI agent is a program that uses a Large Language Model (LLM) to **decide what to do next**.

Unlike a regular chatbot that just generates text, an agent can:
- **Think** about what the user needs
- **Use tools** (call APIs, read files, query databases)
- **Observe** the results of those tool calls
- **Decide** if it needs to do more work or if it's done
- **Respond** with a final answer

The key difference: a chatbot follows a script. An agent **reasons and acts autonomously**.

```
Regular Chatbot:
  User asks question → Model generates text → Done

AI Agent:
  User asks question → Model thinks → Calls tool A → Reads result →
  Thinks again → Calls tool B → Reads result → Generates final answer
```

---

## What is an LLM (Large Language Model)?

The "brain" of the agent. Models like Claude, GPT, Nova, or Llama that understand natural
language and can generate text, reason about problems, and decide which tools to use.

In Strands, you configure which LLM your agent uses:
- **Claude** (via Anthropic API or Amazon Bedrock)
- **Amazon Nova** (via Amazon Bedrock)
- **GPT** (via OpenAI)
- **Llama** (via Bedrock, Ollama, or other providers)

---

## What is Amazon Bedrock?

Amazon Bedrock is an AWS service that gives you access to multiple LLMs (Claude, Nova, Llama,
Mistral, etc.) through a single API. Instead of managing API keys for each model provider,
you use your AWS credentials to call any supported model.

Why it matters for agents:
- No API key management (uses IAM credentials)
- Pay-per-use pricing
- Access to multiple models through one interface
- Required for AgentCore deployment

---

## What is Strands Agents?

Strands Agents is an **open-source Python/TypeScript SDK** for building AI agents. It was
created by AWS and is the recommended framework for building agents that deploy to AgentCore.

The core philosophy is **model-driven**: you give the agent a prompt and tools, and the LLM
decides what to do. You don't write workflow logic like "step 1, step 2, step 3." The model
figures out the steps on its own.

A minimal Strands agent is just 3 lines:

```python
from strands import Agent

agent = Agent()
agent("What is 2 + 2?")
```

That's it. The SDK handles the entire agent loop internally.

---

## What is the Agent Loop?

The agent loop is the core execution cycle that makes an agent "agentic." It's the repeating
process of: **think → act → observe → repeat**.

Here's exactly what happens when you call `agent("What's the weather in NYC?")`:

```
Step 1: THINK
  The model receives your message + system prompt + available tools
  It decides: "I need to call the weather tool"

Step 2: ACT
  The SDK executes the tool the model requested
  e.g., calls the weather API and gets back data

Step 3: OBSERVE
  The tool result is sent back to the model
  The model reads the result

Step 4: DECIDE
  Does the model need more information? → Go back to Step 1
  Is it satisfied? → Generate final response to the user

Step 5: RESPOND
  The model produces the final text answer
```

This loop can repeat multiple times. For example:
1. Model calls `get_product_info("PROD-002")` → gets back "Smart Watch, electronics category"
2. Model calls `get_return_policy("electronics")` → gets back "30 day return window"
3. Model combines both results into a helpful answer

The model drives the entire process. You never write code that says "call tool A then tool B."

---

## What is a Tool?

A tool is a **Python function that the LLM can call**. Tools are how agents interact with
the real world — they can call APIs, read files, query databases, run calculations, or
anything else you can write in Python.

The model reads the tool's **name**, **description**, and **parameter types** to decide
when and how to use it. That's why good docstrings are critical.

```python
from strands import tool
import json, urllib.request

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: Name of the city (e.g., "New York", "London")
    """
    # This is where YOUR code runs — call a real API, query a database, anything
    url = f"https://api.weather.gov/points/40.7128,-74.0060"  # example for NYC
    req = urllib.request.Request(url, headers={"User-Agent": "Agent/1.0"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data["properties"]["forecast"]
```

The model sees (from the decorator + docstring):
- Tool name: `get_weather`
- Description: "Get the current weather for a city"
- Parameters: `city` (string) — "Name of the city"

The model does NOT see the function body. It only reads the name, description, and
parameters to decide *when* to call the tool. Whatever your Python code returns (real
API data, database results, calculations) is what the model receives as the tool result.

If you wrote `return "72°F and sunny"` it would always return that fixed string.
If you wrote a real API call (like above), it returns live data. The tool is just a
Python function — it does whatever code you put inside it.

---

## What is a System Prompt?

A system prompt is the **instruction set** you give to the agent that defines its personality,
behavior, and rules. It's the first thing the model reads before any user message.

Think of it as the agent's "job description":

```python
SYSTEM_PROMPT = """You are a customer support agent for an e-commerce company.

Rules:
- Always be polite and professional
- Use tools to look up information, never guess
- If you don't know something, say so honestly
"""

agent = Agent(system_prompt=SYSTEM_PROMPT, tools=[...])
```

A good system prompt tells the agent:
- **Who it is** (role/persona)
- **What it can do** (available tools and when to use them)
- **How to behave** (tone, rules, constraints)
- **What NOT to do** (guardrails)

---

## What is a Model Provider?

A model provider is the service that hosts and serves the LLM. In Strands, you configure
which provider to use:

| Provider | Class | How It Authenticates |
|----------|-------|---------------------|
| Amazon Bedrock | `BedrockModel` | AWS credentials (IAM) |
| Anthropic (direct) | `AnthropicModel` | API key |
| OpenAI | `OpenAIModel` | API key |
| Ollama (local) | `OllamaModel` | None (runs locally) |
| LiteLLM | `LiteLLMModel` | Varies |

For production, **BedrockModel is recommended** because it uses IAM credentials (no API keys
to manage) and is required for AgentCore deployment.

---

## What is Amazon Bedrock AgentCore?

AgentCore is the **production infrastructure layer** for AI agents on AWS. It's what takes
your agent from "runs on my laptop" to "runs securely at scale in the cloud."

AgentCore is **framework-agnostic** (works with Strands, LangGraph, CrewAI, etc.) and
**model-agnostic** (works with any LLM).

It has several components:

| Component | What It Does | Analogy |
|-----------|-------------|---------|
| **Runtime** | Runs your agent code in a managed container | Like AWS Lambda, but for agents |
| **Memory** | Stores conversation history across sessions | Like a database for agent memory |
| **Gateway** | Turns APIs/Lambdas into tools agents can use | Like API Gateway, but for agent tools |
| **Identity** | Handles authentication for agents and users | Like Cognito/IAM for agents |
| **Observability** | Traces and monitors agent behavior | Like CloudWatch for agents |
| **Evaluations** | Tests agent quality automatically | Like unit tests for agent responses |
| **Tools** | Built-in Code Interpreter and Browser | Pre-built capabilities |

You don't need all of these to start. The learning path is:
1. First: Runtime (deploy your agent)
2. Then: Memory (remember conversations)
3. Then: Gateway (connect to external tools)
4. Later: Identity, Observability, Evaluations

---

## What is the AgentCore CLI?

A command-line tool that simplifies creating, developing, and deploying agents to AgentCore:

```bash
agentcore create    # Scaffold a new agent project
agentcore dev       # Run locally for testing
agentcore deploy    # Deploy to AWS
agentcore invoke    # Test your deployed agent
agentcore logs      # View agent logs
```

---

## What is MCP (Model Context Protocol)?

MCP is an **open standard** for connecting AI agents to tools and data sources. Think of it
as a universal plug for agent tools — any MCP-compatible tool works with any MCP-compatible
agent.

AgentCore Gateway uses MCP to expose tools to your agents. This means:
- Lambda functions can become MCP tools
- REST APIs can become MCP tools
- Your agent connects to Gateway and discovers available tools automatically

---

## What is A2A (Agent-to-Agent)?

A2A is a protocol that lets agents communicate with each other. Instead of one big agent
doing everything, you can have specialized agents that collaborate:

```
User → Supervisor Agent → Research Agent (does web research)
                        → Code Agent (writes code)
                        → Analysis Agent (analyzes data)
```

This is an advanced pattern you'll learn later.

---

## What is a Session?

A session represents a single conversation between a user and an agent. It tracks:
- The conversation history (all messages back and forth)
- Any state the agent needs to remember within that conversation
- Tool call results

When you use AgentCore Memory, sessions can persist across multiple interactions.

---

## What is Conversation History?

The list of all messages exchanged between the user and agent in a session. Each message
includes:
- **User messages**: What the user said
- **Assistant messages**: What the agent said
- **Tool calls**: Which tools the agent used and their results

The model reads the full conversation history on every turn, which is how it maintains
context. This is why token management matters for long conversations.

---

## Quick Reference: How Everything Connects

```
┌─────────────────────────────────────────────────────────────┐
│                     YOUR APPLICATION                         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Strands Agent                            │   │
│  │                                                       │   │
│  │  System Prompt: "You are a helpful assistant..."      │   │
│  │                                                       │   │
│  │  Model: BedrockModel (Claude on Amazon Bedrock)       │   │
│  │                                                       │   │
│  │  Tools: [get_weather, search_docs, send_email]        │   │
│  │                                                       │   │
│  │  ┌─────────────────────────────────────────────┐      │   │
│  │  │           Agent Loop                         │      │   │
│  │  │  Think → Act → Observe → Decide → Respond   │      │   │
│  │  └─────────────────────────────────────────────┘      │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│              Deployed on AgentCore Runtime                    │
│              Memory stored in AgentCore Memory               │
│              Tools served via AgentCore Gateway               │
└─────────────────────────────────────────────────────────────┘
```

---

## Simple Analogy: The Restaurant Kitchen

Before jumping into code, here's the easiest way to understand how all the pieces fit together.

Think of it like a restaurant:

| Term | Restaurant Analogy |
|------|-------------------|
| **Agent** | The chef — reads the order, thinks about what to do, picks the right tools, assembles the final dish |
| **Tool** | A kitchen appliance (oven, blender, knife) — does ONE specific thing when the chef decides to use it. The oven doesn't decide when to turn on — the chef does |
| **LLM (Model)** | The chef's brain — the ability to reason, plan, and make decisions |
| **System Prompt** | The chef's training and recipe book — "You're a French chef. Always use butter. Never serve raw meat." |
| **Agent Loop** | The cooking process — read order → pick tool → use it → taste result → need more work? → repeat or plate the dish |
| **Session** | One customer's visit — the chef remembers what they ordered across courses |
| **Conversation History** | The running list of everything ordered and served so far |
| **Model Provider** | The culinary school that trained the chef (Bedrock = Le Cordon Bleu, Anthropic = CIA, OpenAI = another school) |

```
Customer: "I want a steak, medium-rare, with a side salad."

Chef (Agent) THINKS → "I need to grill the steak and prepare a salad"
Chef USES the grill (Tool 1) → Steak is cooking
Chef USES the knife (Tool 2) → Vegetables are chopped
Chef CHECKS the steak → "Needs 2 more minutes"
Chef WAITS, then CHECKS again → "Perfect medium-rare"
Chef PLATES everything → Delivers the final dish (Response)
```

The chef (agent) makes all the decisions. The grill and knife (tools) just do what
they're told. Without the chef, the grill just sits there. Without the grill, the
chef can talk about steak but can't actually cook one.

That's agents + tools in a nutshell. Now let's see it with real code.

---

## Real-World Example: DevOps Incident Response Agent

Let's tie every term together with a real scenario that companies actually use in production.

**The scenario:** It's 2 AM. An alarm fires — your website is slow. Instead of a human
waking up and manually checking 5 different AWS dashboards, an agent handles it.

### The Code

```python
import json
import boto3
import urllib.request
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

# ─── MODEL (the brain) ───
# This is the LLM that powers the agent's reasoning.
# It runs on Amazon Bedrock — no API keys, uses your AWS credentials.
model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="us-east-1",
)

# ─── TOOLS (each does ONE specific job) ───

@tool
def check_cloudwatch_alarms(region: str = "us-east-1") -> str:
    """Check for active CloudWatch alarms in a region.

    Args:
        region: AWS region to check (e.g., "us-east-1")
    """
    cw = boto3.client("cloudwatch", region_name=region)
    response = cw.describe_alarms(StateValue="ALARM")
    alarms = response.get("MetricAlarms", [])
    if not alarms:
        return "No active alarms. All clear."
    result = []
    for a in alarms:
        result.append(f"🔴 {a['AlarmName']}: {a['MetricName']} in {a['Namespace']}")
    return "\n".join(result)

@tool
def check_ec2_health(instance_id: str) -> str:
    """Check the health status of a specific EC2 instance.

    Args:
        instance_id: The EC2 instance ID (e.g., "i-0abc123def456")
    """
    ec2 = boto3.client("ec2")
    response = ec2.describe_instance_status(InstanceIds=[instance_id])
    statuses = response.get("InstanceStatuses", [])
    if not statuses:
        return f"Instance {instance_id} not found or not running."
    s = statuses[0]
    return (
        f"Instance {instance_id}: State={s['InstanceState']['Name']}, "
        f"System={s['SystemStatus']['Status']}, Instance={s['InstanceStatus']['Status']}"
    )

@tool
def check_website_status(url: str) -> str:
    """Check if a website is responding and measure response time.

    Args:
        url: The URL to check (e.g., "https://myapp.example.com/health")
    """
    import time
    try:
        start = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": "IncidentAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed = time.time() - start
            return f"URL {url}: HTTP {resp.status}, Response time: {elapsed:.2f}s"
    except urllib.error.HTTPError as e:
        return f"URL {url}: HTTP ERROR {e.code} — {e.reason}"
    except Exception as e:
        return f"URL {url}: UNREACHABLE — {str(e)}"

@tool
def send_slack_alert(channel: str, message: str) -> str:
    """Send an alert message to a Slack channel.

    Args:
        channel: Slack channel name (e.g., "#incidents")
        message: The alert message to send
    """
    # In production, this would call the Slack API with a webhook URL
    # slack_webhook = os.environ["SLACK_WEBHOOK_URL"]
    # urllib.request.urlopen(slack_webhook, data=json.dumps({"text": message}).encode())
    return f"Alert sent to {channel}: {message}"

# ─── SYSTEM PROMPT (the agent's training/rules) ───
SYSTEM_PROMPT = """You are an on-call DevOps incident response agent.

When an incident is reported:
1. First check CloudWatch alarms to understand what's firing
2. Check the website health endpoint to confirm the issue
3. If specific instances are mentioned, check their EC2 health
4. Summarize your findings clearly
5. Send a Slack alert to #incidents with your diagnosis

Be concise and factual. Prioritize identifying the root cause.
Always recommend a next step for the human on-call engineer."""

# ─── AGENT (the decision-maker that uses tools) ───
incident_agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[check_cloudwatch_alarms, check_ec2_health, check_website_status, send_slack_alert],
)

# ─── WHAT HAPPENS WHEN THE AGENT RUNS ───
incident_agent("We're getting reports that the website is slow. Investigate and alert the team.")
```

### What the Agent Loop Does

```
User: "Website is slow. Investigate and alert the team."

THINK → "I should check alarms first to see what's going on"
ACT   → Calls check_cloudwatch_alarms("us-east-1")
RESULT: "🔴 HighCPU-WebServer: CPUUtilization in AWS/EC2"

THINK → "CPU alarm on the web server. Let me check the website directly"
ACT   → Calls check_website_status("https://myapp.example.com/health")
RESULT: "HTTP 200, Response time: 4.82s"  (normally 0.2s — way too slow)

THINK → "Confirmed slow. The alarm mentions EC2. Let me check that instance"
ACT   → Calls check_ec2_health("i-0abc123def456")
RESULT: "State=running, System=ok, Instance=impaired"

THINK → "Instance is impaired with high CPU. I have my diagnosis. Time to alert."
ACT   → Calls send_slack_alert("#incidents", "🔴 Website slow — root cause:
         EC2 i-0abc123 has impaired status with high CPU. Response time 4.8s
         (normal: 0.2s). Recommend: restart instance or scale out ASG.")

RESPOND → "Here's what I found:
           - CloudWatch alarm: High CPU on web server instance
           - Website response time: 4.82s (normally ~0.2s)
           - EC2 instance i-0abc123 status: impaired
           - Root cause: CPU saturation on the web server
           - I've sent an alert to #incidents
           - Recommended action: restart the instance or trigger ASG scale-out"
```

### How Every Term Maps to This Example

| Term | In This Example |
|------|----------------|
| **Agent** | `incident_agent` — the decision-maker that investigates the incident |
| **LLM / Model** | Claude on Bedrock — the brain that reasons about what to check next |
| **Tool** | `check_cloudwatch_alarms`, `check_ec2_health`, `check_website_status`, `send_slack_alert` — each does one specific job |
| **System Prompt** | The incident response instructions — "check alarms first, then website, then summarize" |
| **Agent Loop** | The think → act → observe cycle that ran 4 times above |
| **Model Provider** | Amazon Bedrock — hosts Claude, authenticated via AWS credentials |
| **Session** | This single incident investigation conversation |
| **Conversation History** | All the messages + tool results the model accumulated during the investigation |

### The Key Difference: Agent vs Tool

If you only had the **tools** without an agent, you'd have to write code like:

```python
# Without an agent — YOU write the logic
alarms = check_cloudwatch_alarms("us-east-1")
if "HighCPU" in alarms:
    health = check_ec2_health("i-0abc123")
    if "impaired" in health:
        send_slack_alert("#incidents", "CPU issue on web server")
```

You'd have to anticipate every possible scenario and write if/else branches for each one.

With an **agent**, you just say "investigate" and the LLM figures out:
- Which tools to call
- In what order
- What to do with the results
- When to stop
- How to summarize

That's the power of agents — they handle the decision-making so you don't have to
hardcode every workflow path.

---

## Where Agents Are Used in Production (Real-World Use Cases)

| Use Case | What the Agent Does | Tools It Uses |
|----------|-------------------|---------------|
| **Customer Support** | Answers questions, looks up orders, processes returns | Order database, shipping API, refund system |
| **DevOps / Incident Response** | Investigates alerts, diagnoses issues, notifies teams | CloudWatch, EC2, Slack, PagerDuty |
| **Code Review** | Reviews PRs, checks for bugs, suggests fixes | GitHub API, linter, test runner |
| **Data Analysis** | Queries databases, generates charts, writes reports | SQL database, Code Interpreter, S3 |
| **Sales Assistant** | Looks up CRM data, drafts emails, schedules meetings | Salesforce API, Gmail, Calendar |
| **Security Monitoring** | Analyzes logs, detects anomalies, blocks threats | CloudTrail, GuardDuty, WAF, SNS |
| **Research Assistant** | Searches papers, summarizes findings, compiles reports | Web search, ArXiv API, document store |
| **Infrastructure Management** | Provisions resources, scales services, optimizes costs | AWS APIs (EC2, RDS, Lambda, Cost Explorer) |

The common pattern: anywhere a human currently switches between multiple dashboards/tools
and makes decisions based on what they see — that's a good fit for an agent.
