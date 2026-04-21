# Strands Agents & Amazon Bedrock AgentCore — Learning Docs

A structured learning path from zero to production-ready AI agents on AWS.

## Documents

| # | Document | What's Covered |
|---|----------|----------------|
| 1 | [Terminology & Definitions](./01-terminology.md) | Agent, LLM, Bedrock, Strands, AgentCore, Tools, MCP, A2A, Sessions |
| 2 | [Core Strands Patterns](./02-core-patterns.md) | 15 code patterns from simplest agent to multi-agent swarm |
| 3 | [Learning Path, Checklist & Tool Scaling](./03-learning-path.md) | Phase progression, checklist, tool scaling strategies, key resources |

## Learning Path

```
Phase 1 — Foundations
  ├── Understand the concepts  →  01-terminology.md
  ├── Learn the code patterns  →  02-core-patterns.md
  └── Run an agent locally     →  agents/weather-agent/local/

Phase 2 — AgentCore Deployment
  ├── Wrap your agent with BedrockAgentCoreApp
  ├── Test locally with agentcore dev
  └── Deploy to AWS            →  agents/weather-agent/agentcore/

Phase 3 — AgentCore Features
  ├── Memory — persist conversations across sessions
  ├── Gateway — expose tools via MCP
  ├── Identity — authentication for agents and users
  └── Observability & Evaluations
```

## Key Concepts at a Glance

- **Strands Agents SDK** — open-source Python SDK for building model-driven agents
- **Amazon Bedrock** — AWS service providing access to LLMs (Claude, Nova, Llama, etc.) via IAM credentials
- **Amazon Bedrock AgentCore** — production infrastructure for running agents at scale (Runtime, Memory, Gateway, Identity, Observability)
- **AgentCore CLI** — `agentcore create / dev / deploy / invoke` — the developer workflow tool

## Agents in This Repo

| Agent | Description | Docs |
|-------|-------------|------|
| Weather Agent (Local) | Strands agent running locally with Python | [agents/weather-agent/local/](../agents/weather-agent/local/README.md) |
| Weather Agent (AgentCore) | Same agent deployed to AgentCore Runtime | [agents/weather-agent/agentcore/](../agents/weather-agent/agentcore/README.md) |
