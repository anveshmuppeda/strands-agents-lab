# GitHub Repository Setup Guide

How to organize and publish your Strands Agents & AgentCore projects as an open-source repo.

---

## Repo Name

```
strands-agents-lab
```

Why this name:
- `strands-agents` — makes it clear what framework you're using
- `lab` — signals it's a learning/experimentation repo that will grow over time
- Easy to find, easy to remember

Alternative names if that's taken: `strands-agents-playground`, `aws-agents-lab`, `agentcore-agents`

---

## Repo Description (for GitHub)

```
Learning and building AI agents with Strands Agents SDK and Amazon Bedrock AgentCore — from basics to production deployment.
```

## Topics/Tags (for GitHub discoverability)

```
strands-agents, amazon-bedrock, agentcore, ai-agents, aws, python, llm, mcp, agent-tools
```

---

## Folder Structure

```
strands-agents-lab/
│
├── README.md                          # Repo overview, what's inside, how to get started
├── LICENSE                            # MIT or Apache-2.0
├── .gitignore                         # Python + Node + macOS ignores
│
├── docs/                              # Learning documentation
│   ├── README.md                      # Docs index
│   ├── 01-terminology.md              # Definitions: Agent, LLM, Bedrock, AgentCore, etc.
│   ├── 02-core-patterns.md            # 15 Strands patterns with code examples
│   ├── 03-fix-weather-agent.md        # Before/after: Anthropic → Bedrock migration
│   ├── 04-practice-devops-agent.md    # DevOps agent practice project guide
│   ├── 05-checklist-and-next-steps.md # Phase 1 checklist + Phase 2 bridge
│   ├── 06-tool-scaling.md             # Tool scaling & progressive disclosure
│   └── 07-github-repo-setup.md        # This file
│
├── agents/                            # All agent projects
│   │
│   ├── weather-agent/                 # Local Strands agent (Phase 1)
│   │   ├── README.md                  # Setup, run, deploy to AgentCore guide
│   │   ├── requirements.txt
│   │   └── weather_agent_v2.py
│   │
│   ├── devops-agent/                  # Local Strands agent (Phase 1)
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   └── devops_agent.py
│   │
│   └── weather-agent-agentcore/       # AgentCore deployed version (Phase 2)
│       ├── README.md
│       ├── AGENTS.md
│       ├── agentcore/                 # AgentCore CLI config + CDK
│       │   ├── agentcore.json
│       │   ├── aws-targets.json
│       │   └── cdk/
│       └── app/
│           └── WeatherAgent/
│               ├── main.py            # Agent code with @app.entrypoint
│               ├── model/
│               │   └── load.py
│               └── pyproject.toml
│
└── archive/                           # Your original first agent (for reference)
    └── weather_agent_v1.py            # The Anthropic API version you started with
```

### Why This Structure?

| Folder | Purpose |
| ------ | ------- |
| `docs/` | Learning docs — anyone can read these to understand agents from scratch |
| `agents/` | Each agent is a self-contained project with its own README, requirements, and code |
| `agents/weather-agent/` | Local-only agent (run with `python`) |
| `agents/weather-agent-agentcore/` | Same agent wrapped for AgentCore deployment |
| `archive/` | Your original v1 code — shows your learning progression |

As you build more agents, just add new folders under `agents/`:

```
agents/
├── weather-agent/
├── devops-agent/
├── customer-support-agent/        # future
├── research-agent/                # future
├── multi-agent-swarm/             # future
└── weather-agent-agentcore/
```

---

## Files to Create

### 1. Root README.md

This is the first thing people see on your GitHub repo.

```markdown
# Strands Agents Lab

Learning and building AI agents with [Strands Agents SDK](https://strandsagents.com)
and [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/).

## What's Inside

### Agents

| Agent | Description | Status |
|-------|-------------|--------|
| [Weather Agent](agents/weather-agent/) | Live weather forecasts using NWS API | ✅ Working |
| [DevOps Agent](agents/devops-agent/) | AWS infrastructure monitoring & reporting | ✅ Working |
| [Weather Agent (AgentCore)](agents/weather-agent-agentcore/) | Weather agent deployed to AgentCore Runtime | ✅ Deployed |

### Documentation

| Doc | What You'll Learn |
|-----|-------------------|
| [Terminology](docs/01-terminology.md) | Agent, LLM, Bedrock, AgentCore, Tools, MCP — all defined |
| [Core Patterns](docs/02-core-patterns.md) | 15 Strands patterns from basic to multi-agent |
| [Tool Scaling](docs/06-tool-scaling.md) | What happens with 10, 50, 100+ tools |
| [All Docs →](docs/) | Full learning path |

## Quick Start

```bash
# Clone the repo
git clone https://github.com/<your-username>/strands-agents-lab.git
cd strands-agents-lab

# Run the weather agent
cd agents/weather-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 weather_agent_v2.py
```

## Prerequisites

- Python 3.10+
- AWS account with Bedrock access ([setup guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-modify.html))
- AWS CLI configured (`aws configure`)

## Tech Stack

- [Strands Agents SDK](https://strandsagents.com) — Agent framework
- [Amazon Bedrock](https://aws.amazon.com/bedrock/) — LLM provider (Claude Sonnet)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) — Production deployment
- [AgentCore CLI](https://github.com/aws/agentcore-cli) — Create, dev, deploy agents

## License

MIT
```

### 2. .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.venv/
venv/
env/
*.egg-info/
dist/
build/
.eggs/

# Environment
.env
.env.local
*.env

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# macOS
.DS_Store
.AppleDouble
.LSOverride

# Node (for AgentCore CDK)
node_modules/
*.tgz

# AgentCore
agentcore/.cli/logs/
agentcore/.cli/deployed-state.json

# Jupyter
.ipynb_checkpoints/

# uv
uv.lock
```

### 3. LICENSE (MIT)

```
MIT License

Copyright (c) 2026 Anvesh Muppeda

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Step-by-Step: Create the GitHub Repo

### Step 1: Create the repo on GitHub

```bash
# Using GitHub CLI (install: brew install gh)
gh repo create strands-agents-lab --public --description "Learning and building AI agents with Strands Agents SDK and Amazon Bedrock AgentCore"

# Or create it manually at https://github.com/new
```

### Step 2: Initialize your local repo

From your current workspace, restructure and initialize:

```bash
# Create a fresh directory for the repo
mkdir ~/strands-agents-lab
cd ~/strands-agents-lab
git init

# Copy your work into the new structure
# (adjust source paths to match your workspace location)

# Docs
cp -r /path/to/workspace/docs/ ./docs/

# Weather agent (local)
mkdir -p agents/weather-agent
cp /path/to/workspace/agents/weather-agent/weather_agent_v2.py agents/weather-agent/
cp /path/to/workspace/agents/weather-agent/requirements.txt agents/weather-agent/
cp /path/to/workspace/agents/weather-agent/README.md agents/weather-agent/

# DevOps agent
mkdir -p agents/devops-agent
cp /path/to/workspace/agents/devops-agent/devops_agent.py agents/devops-agent/
# Create a requirements.txt and README.md for it too

# Weather agent AgentCore version
mkdir -p agents/weather-agent-agentcore
cp -r /path/to/workspace/agents/WeatherAgent/* agents/weather-agent-agentcore/
# Remove the .git subfolder (it has its own git from agentcore create)
rm -rf agents/weather-agent-agentcore/.git

# Archive your original v1
mkdir -p archive
cp /path/to/workspace/strands/weather_agent.py archive/weather_agent_v1.py

# Create root files (README.md, .gitignore, LICENSE)
# Use the templates from this doc
```

### Step 3: Clean up sensitive data

Before committing, make sure there are NO:

```bash
# Check for API keys, secrets, credentials
grep -r "api_key" --include="*.py" .
grep -r "secret" --include="*.py" .
grep -r "password" --include="*.py" .
grep -r "sk-" --include="*.py" .

# Check for .env files
find . -name ".env*" -not -name ".env.example"

# Check for AWS account IDs
grep -r "[0-9]\{12\}" --include="*.py" .
grep -r "[0-9]\{12\}" --include="*.json" .
```

Remove or replace any real credentials with placeholders.

### Step 4: First commit and push

```bash
git add .
git commit -m "Initial commit: weather agent, devops agent, learning docs"

git remote add origin https://github.com/<your-username>/strands-agents-lab.git
git branch -M main
git push -u origin main
```

### Step 5: Add a good GitHub description

Go to your repo settings and add:
- **Description:** "Learning and building AI agents with Strands Agents SDK and Amazon Bedrock AgentCore"
- **Website:** (leave blank or link to your blog if you have one)
- **Topics:** `strands-agents`, `amazon-bedrock`, `agentcore`, `ai-agents`, `aws`, `python`

---

## What NOT to Commit

| File/Folder | Why |
| ----------- | --- |
| `.env`, `.env.local` | Contains API keys or AWS config |
| `agentcore/.cli/logs/` | Local dev server logs |
| `agentcore/.cli/deployed-state.json` | Contains your AWS account-specific deployment state |
| `.venv/`, `node_modules/` | Dependencies — install from requirements.txt/package.json |
| `__pycache__/` | Python bytecode cache |
| `uv.lock` | Environment-specific lock file |
| `aws-targets.json` | Contains your AWS account ID and region — replace with example |

### Handle aws-targets.json

This file contains your AWS account ID. Create an example version instead:

```bash
# Rename the real one
mv agents/weather-agent-agentcore/agentcore/aws-targets.json agents/weather-agent-agentcore/agentcore/aws-targets.json.example
```

Edit the example to replace your account ID:

```json
{
  "targets": {
    "default": {
      "accountId": "123456789012",
      "region": "us-east-1"
    }
  }
}
```

Add the real one to `.gitignore`:

```
agentcore/aws-targets.json
```

---

## Ongoing: Adding New Agents

Every time you build a new agent:

1. Create a new folder under `agents/`:
   ```
   agents/my-new-agent/
   ├── README.md           # What it does, how to run, architecture
   ├── requirements.txt    # Python dependencies
   └── my_agent.py         # Agent code
   ```

2. Update the root `README.md` table with the new agent

3. Commit and push:
   ```bash
   git add agents/my-new-agent/
   git commit -m "Add my-new-agent: description of what it does"
   git push
   ```

---

## Optional: GitHub Extras

### Add a GitHub Actions CI (optional)

Create `.github/workflows/lint.yml` to lint Python on every push:

```yaml
name: Lint

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install ruff
      - run: ruff check agents/ --select E,F,W
```

### Add a CONTRIBUTING.md (optional)

If others want to contribute:

```markdown
# Contributing

1. Fork the repo
2. Create a branch: `git checkout -b my-new-agent`
3. Add your agent under `agents/`
4. Include a README.md with setup instructions
5. Open a pull request
```
