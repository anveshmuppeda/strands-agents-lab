# AWS Network Agent — Amazon Bedrock AgentCore

The network agent deployed to [Amazon Bedrock AgentCore Runtime](https://aws.amazon.com/bedrock/agentcore/). Same 6 tools and system prompt as the local version, wrapped with `BedrockAgentCoreApp` for production deployment.

## Project Structure

```
agentcore/
└── networkagent/
    ├── agentcore/
    │   ├── agentcore.json      # Project config (source of truth)
    │   ├── aws-targets.json    # Deployment target (account, region)
    │   └── cdk/                # CDK infrastructure (auto-managed by CLI)
    └── app/
        └── networkagent/
            ├── main.py         # Agent code with @app.entrypoint
            ├── model/
            │   └── load.py     # BedrockModel configuration
            └── pyproject.toml  # Python dependencies (includes boto3)
```

## Key Code: Entry Point (`main.py`)

```python
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model

app = BedrockAgentCoreApp()

# ... all 6 tools (same as local version) ...

_agent = None

def get_or_create_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(
            model=load_model(),
            system_prompt=SYSTEM_PROMPT,
            tools=[check_subnet_details, check_vpc_routes, check_nacl_rules,
                   check_security_group, check_vpc_endpoints, check_reachability],
        )
    return _agent

@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Network Agent...")
    agent = get_or_create_agent()
    stream = agent.stream_async(payload.get("prompt"))
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]
```

## Development Workflow

### Test locally

```bash
cd agents/network-agent/agentcore/networkagent
agentcore dev
```

### Deploy to AWS

```bash
agentcore deploy
agentcore status
```

### Invoke

```bash
agentcore invoke "Does VPC vpc-0abc123 have internet access?" --stream
```

### Logs & traces

```bash
agentcore logs
agentcore traces list --limit 10
```

## IAM Role

The AgentCore CLI auto-provisions an IAM role for the runtime. You need to ensure it includes the EC2 permissions required by the tools:

```json
{
  "Action": [
    "ec2:DescribeSubnets",
    "ec2:DescribeRouteTables",
    "ec2:DescribeNetworkAcls",
    "ec2:DescribeSecurityGroups",
    "ec2:DescribeVpcEndpoints",
    "ec2:CreateNetworkInsightsPath",
    "ec2:StartNetworkInsightsAnalysis",
    "ec2:DescribeNetworkInsightsAnalyses",
    "ec2:DeleteNetworkInsightsPath"
  ]
}
```

## Clean Up

```bash
agentcore remove all
agentcore deploy
```

## Resources

| Resource | Link |
|----------|------|
| AgentCore Docs | https://docs.aws.amazon.com/bedrock-agentcore/ |
| AgentCore CLI | https://github.com/aws/agentcore-cli |
| VPC Reachability Analyzer | https://docs.aws.amazon.com/vpc/latest/reachability/what-is-reachability-analyzer.html |
