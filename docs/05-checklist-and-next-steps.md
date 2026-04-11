# Phase 1 Checklist & Next Steps

## What You've Learned

After working through the Phase 1 docs, you should understand:

- [ ] What an AI agent is and how it differs from a chatbot
- [ ] The agent loop: think → act → observe → decide → respond
- [ ] What Strands Agents SDK is and why it's model-driven
- [ ] What Amazon Bedrock is and why BedrockModel is preferred
- [ ] What AgentCore is and its components (Runtime, Memory, Gateway, Identity)
- [ ] How to create custom tools with `@tool` decorator
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

## Phase 1 → Phase 2 Bridge

Once you're comfortable with everything above, you're ready for Phase 2:
**deploying to AgentCore**.

The key transition is wrapping your agent with `BedrockAgentCoreApp`:

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

That's the bridge from "runs on my laptop" to "runs on AgentCore Runtime."
The agent code stays the same — you just wrap it with the runtime entrypoint.

Next step: `agentcore create` → `agentcore dev` → `agentcore deploy`

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
| AgentCore Samples Repo | https://github.com/awslabs/amazon-bedrock-agentcore-samples |
| Build Production Agent (Video) | https://www.youtube.com/watch?v=wzIQDPFQx30 |
| Getting Started Workshop | https://catalog.us-east-1.prod.workshops.aws/workshops/850fcd5c-fd1f-48d7-932c-ad9babede979 |
| Deep Dive Workshop | https://catalog.workshops.aws/agentcore-deep-dive |
