# Strands Agents & Amazon Bedrock AgentCore — Learning Docs

A structured learning path from zero to production-ready AI agents on AWS.

## Documents

| # | Document | What's Covered |
|---|----------|----------------|
| 1 | [Terminology & Definitions](./01-terminology.md) | Agent, LLM, Bedrock, Strands, AgentCore, Tools, MCP, A2A, Sessions |
| 2 | [Core Strands Patterns](./02-core-patterns.md) | 15 code patterns from simplest agent to multi-agent swarm |
| 3 | [Learning Path & Tool Scaling](./03-learning-path.md) | Phase progression, checklist, tool scaling strategies, key resources |

## Agents in This Repo

| # | Agent | What You Learn | Folder |
|---|-------|---------------|--------|
| 01 | Weather Agent | Strands basics, `@tool`, BedrockModel, local + AgentCore CLI | [agents/01-weather-agent/](../agents/01-weather-agent/) |
| 02 | Network Agent | Multi-tool agent, AWS APIs, VPC diagnostics | [agents/02-network-agent/](../agents/02-network-agent/) |
| 03 | Network Agent CDK | Python CDK, split stacks, CI/CD pipeline | [agents/03-network-agent-cdk/](../agents/03-network-agent-cdk/) |
| 04 | Gateway Agent | AgentCore Gateway, Lambda tools, MCP, CDK runtime stack | [agents/04-gateway-agent/](../agents/04-gateway-agent/) |

## Learning Path

```
Phase 1 — Foundations
  ├── Understand the concepts       → 01-terminology.md
  ├── Learn the code patterns       → 02-core-patterns.md
  └── Run an agent locally          → agents/01-weather-agent/local/

Phase 2 — AgentCore Deployment
  ├── Deploy with AgentCore CLI     → agents/01-weather-agent/agentcore/
  ├── Deploy with Python CDK        → agents/03-network-agent-cdk/
  └── CI/CD with GitHub Actions     → .github/workflows/deploy.yml

Phase 3 — AgentCore Gateway
  ├── Move tools to Lambda          → agents/04-gateway-agent/lambdas/
  ├── Create Gateway + Targets      → agents/04-gateway-agent/cdk/ (Stack 1)
  ├── Deploy agent with GATEWAY_URL → agents/04-gateway-agent/cdk/ (Stack 2)
  └── Agent discovers tools via MCP → agents/04-gateway-agent/agent-code/

Phase 4 — Next Steps
  ├── AgentCore Memory — persist conversations
  ├── Gateway Semantic Search — auto-select tools
  ├── Multi-Agent (A2A) — agent-to-agent collaboration
  └── Observability — OpenTelemetry traces
```
