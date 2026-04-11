# Strands Agents & Amazon Bedrock AgentCore — Learning Docs

A structured learning path from zero to production-ready AI agents on AWS.

## Phase 1: Foundations

| # | Document | What You'll Learn |
|---|----------|-------------------|
| 1 | [Terminology & Definitions](./01-terminology.md) | What is an Agent, LLM, Bedrock, Strands, AgentCore, Tools, MCP, A2A, and more |
| 2 | [Core Strands Patterns](./02-core-patterns.md) | 15 code patterns from simplest agent to multi-agent swarm |
| 3 | [Fix Your Weather Agent](./03-fix-weather-agent.md) | Rewrite your agent with best practices (BedrockModel, error handling) |
| 4 | [Practice Project: DevOps Agent](./04-practice-devops-agent.md) | Build a multi-tool AWS infrastructure assistant |
| 5 | [Phase 1 Checklist & Next Steps](./05-checklist-and-next-steps.md) | What you've learned + bridge to Phase 2 (AgentCore deployment) |
| 6 | [Tool Scaling & Progressive Disclosure](./06-tool-scaling.md) | What happens with 10, 50, 100+ tools and how production systems handle it |
| 7 | [GitHub Repo Setup](./07-github-repo-setup.md) | Repo name, folder structure, .gitignore, LICENSE, step-by-step publish guide |

## Phase 2: AgentCore Deployment (Coming Next)

Deploy your first agent to AgentCore Runtime using the CLI.

## Phase 3: AgentCore Features (Coming Next)

Memory, Gateway, Identity, Observability, Evaluations.

## Quick Start

```bash
cd strands
pip install -r requirements.txt
python weather_agent_v2.py
```
