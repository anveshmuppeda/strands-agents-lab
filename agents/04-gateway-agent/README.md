# AgentCore Gateway Agent (Part 4)

## *From Tools-in-Code to Tools-as-a-Service: Centralizing Agent Tools with MCP*

A single agent that accesses weather, network, and IAM tools through **AgentCore Gateway**
instead of having tools baked into the agent code. The agent has zero tool implementations —
it discovers all 9 tools at runtime via MCP.

> **Prerequisite:** Complete [01-weather-agent](../01-weather-agent/), [02-network-agent](../02-network-agent/),
> and [03-network-agent-cdk](../03-network-agent-cdk/) first. This guide assumes you understand
> Strands agents, `@tool`, AgentCore Runtime, and Python CDK.

---

## Why Gateway?

In the previous agents, tools lived inside the agent code:

```python
# 01-weather-agent and 02-network-agent: tools baked in
agent = Agent(tools=[get_weather_forecast, check_subnet_details, ...])
```

This works for one agent. But when you have multiple agents sharing tools, or 50+ tools
that need independent scaling, you need to separate tools from agents.

| Tools in Agent (before) | Tools in Gateway (this project) |
|-------------------------|----------------------------------|
| Tool code lives in the agent container | Tool code lives in Lambda functions |
| Change a tool → redeploy the agent | Change a tool → redeploy only the Lambda |
| Each agent carries its own tools | All agents connect to the same Gateway |
| API keys in agent code/env vars | API keys in Secrets Manager via Gateway |
| Tools scale with the agent | Tools scale independently (Lambda) |
| Agent discovers tools at build time | Agent discovers tools at runtime via MCP |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  AgentCore Runtime                                                │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Gateway Agent (agent-code/main.py)                         │  │
│  │                                                              │  │
│  │  This agent has ZERO tool code.                              │  │
│  │  It connects to Gateway via MCP and discovers 9 tools.      │  │
│  │                                                              │  │
│  │  tools = [mcp_client]  ← single MCP connection              │  │
│  └──────────────┬──────────────────────────────────────────────┘  │
└─────────────────┼─────────────────────────────────────────────────┘
                  │ MCP protocol (SigV4 authenticated)
                  ▼
┌──────────────────────────────────────────────────────────────────┐
│  AgentCore Gateway (tools-gateway)                                │
│  A managed MCP server — created by CDK                            │
│                                                                   │
│  Receives MCP tool calls from the agent,                          │
│  routes them to the correct Lambda, returns results.              │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Weather      │  │ Network      │  │ IAM          │           │
│  │ Target       │  │ Target       │  │ Target       │           │
│  │ (1 tool)     │  │ (5 tools)    │  │ (3 tools)    │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
└─────────┼─────────────────┼─────────────────┼────────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ weather-tools│  │ network-tools│  │ iam-tools    │
  │ Lambda       │  │ Lambda       │  │ Lambda       │
  │              │  │              │  │              │
  │ NWS API      │  │ EC2 APIs     │  │ IAM APIs     │
  └──────────────┘  └──────────────┘  └──────────────┘
```

---

## How It Works Step by Step

```
User: "Does subnet-abc have internet access?"

1. Agent receives the question
2. Agent's MCP client calls Gateway's listTools → gets 9 tool schemas
3. LLM reads all 9 schemas, decides: "I need check_subnet_details and check_vpc_routes"
4. Agent sends MCP tool call to Gateway: check_subnet_details(subnet_id="subnet-abc")
5. Gateway looks up which target owns "check_subnet_details" → network-tools
6. Gateway invokes network-tools Lambda with:
   - event = {"subnet_id": "subnet-abc"}
   - context.client_context.custom = {"bedrockAgentCoreToolName": "network-tools___check_subnet_details"}
7. Lambda strips the prefix, calls check_subnet_details("subnet-abc")
8. Lambda returns: {"statusCode": 200, "body": "Subnet: subnet-abc\n  Type: PRIVATE\n  ..."}
9. Gateway passes result back to agent via MCP
10. LLM reads result, calls check_vpc_routes next, then responds to user
```

---

## Project Structure

```
04-gateway-agent/
│
├── cdk/                                    # Infrastructure (one `cdk deploy`)
│   ├── app.py                              # CDK app entry point
│   ├── cdk.json                            # CDK config
│   ├── requirements.txt                    # aws-cdk-lib >= 2.238.0
│   └── stacks/
│       └── gateway_stack.py                # Lambdas + Gateway + Targets
│
├── lambdas/                                # Tool implementations (Lambda functions)
│   ├── weather-tools/
│   │   └── lambda_function.py              # get_weather_forecast
│   ├── network-tools/
│   │   └── lambda_function.py              # 5 network diagnostic tools
│   └── iam-tools/
│       └── lambda_function.py              # 3 IAM access tools
│
├── agent-code/                             # Agent for AgentCore Runtime
│   ├── main.py                             # Connects to Gateway via MCP
│   ├── requirements.txt                    # Agent dependencies
│   └── Dockerfile                          # Container definition
│
├── gatewayagent/                           # AgentCore CLI project (alternative deploy)
│
├── setup_gateway.py                        # Alternative: manual setup via boto3
└── README.md                               # This file
```

---

## What CDK Deploys

One `cdk deploy` creates everything:

### IAM Roles

| Role | Trusted By | Permissions | Why |
| ---- | ---------- | ----------- | --- |
| Lambda Execution Role | `lambda.amazonaws.com` | CloudWatch Logs, EC2 Describe*, IAM Simulate/List/Get | Lambdas need these to run the tools |
| Gateway Role | `bedrock-agentcore.amazonaws.com` | `lambda:InvokeFunction` on the 3 Lambdas | Gateway invokes Lambdas on tool calls |

### Lambda Functions

| Lambda | Tools | What It Calls |
| ------ | ----- | ------------- |
| `weather-tools` | `get_weather_forecast` | NWS Weather API |
| `network-tools` | `check_subnet_details`, `check_vpc_routes`, `check_nacl_rules`, `check_security_group`, `check_vpc_endpoints` | EC2 APIs via boto3 |
| `iam-tools` | `verify_iam_access`, `list_principal_policies`, `get_policy_document` | IAM APIs via boto3 |

### AgentCore Gateway + Targets

| Resource | Details |
| -------- | ------- |
| Gateway | `tools-gateway`, MCP protocol, AWS IAM auth |
| Weather Target | Attaches weather-tools Lambda with 1 tool schema |
| Network Target | Attaches network-tools Lambda with 5 tool schemas |
| IAM Target | Attaches iam-tools Lambda with 3 tool schemas |

---

## How Lambda Functions Work with Gateway

Gateway sends the tool name in `context.client_context.custom["bedrockAgentCoreToolName"]`
with the target name prepended: `network-tools___check_subnet_details`.

Each Lambda strips the prefix and routes to the right function:

```python
def handler(event, context):
    # Gateway sends: "network-tools___check_subnet_details"
    tool_name = context.client_context.custom.get("bedrockAgentCoreToolName", "")

    # Strip prefix → "check_subnet_details"
    if "___" in tool_name:
        tool_name = tool_name.split("___", 1)[1]

    # Tool parameters come directly in event (not event["body"])
    if tool_name == "check_subnet_details":
        result = check_subnet_details(event["subnet_id"])
        return {"statusCode": 200, "body": result}  # body is a plain string
```

Key details:
- Context key is **camelCase**: `bedrockAgentCoreToolName` (not `bedrockagentcoreToolName`)
- Tool name has **target prefix**: `weather-tools___get_weather_forecast`
- Parameters are in **`event` directly** (not `event["body"]`)
- Response body is a **plain string** (not JSON-wrapped)

---

## How the Agent Connects to Gateway

The agent (`agent-code/main.py`) uses `MCPClient` with SigV4 authentication:

```python
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

auth = get_sigv4_auth()  # Signs requests with AWS credentials

mcp_client = MCPClient(
    lambda: streamablehttp_client(GATEWAY_URL, auth=auth)
)

agent = Agent(
    system_prompt=SYSTEM_PROMPT,
    tools=[mcp_client],  # All 9 tools via one MCP connection
)
```

The `GATEWAY_URL` is the Gateway's MCP endpoint:

```
https://<GATEWAY_ID>.gateway.bedrock-agentcore.<REGION>.amazonaws.com/mcp
```

---

## Deploy

### Prerequisites

- Python 3.10+
- AWS CDK CLI >= 2.1118.2 (`npm install -g aws-cdk@latest`)
- AWS CLI configured (`aws configure`)
- Claude/Nova model access in Bedrock console
- `aws-cdk-lib >= 2.238.0` (for `CfnGateway` support)
- If your account is in an AWS Organization: SCP must allow `bedrock-agentcore:*`

### Step 1: Deploy Gateway + Lambdas

```bash
cd agents/04-gateway-agent/cdk

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1
cdk deploy
```

Takes ~3-5 minutes. Save the `GatewayId` from the output.

### Step 2: Get the Gateway URL

```bash
GATEWAY_ID=$(aws cloudformation describe-stacks \
  --stack-name ToolsGateway \
  --query 'Stacks[0].Outputs[?OutputKey==`GatewayId`].OutputValue' \
  --output text)

echo "GATEWAY_URL=https://${GATEWAY_ID}.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
```

### Step 3: Deploy the Agent

Create an AgentCore project and set the `GATEWAY_URL` environment variable:

```bash
agentcore create --name GatewayAgent --framework Strands --model-provider Bedrock --defaults
cd GatewayAgent

# Copy the agent code
cp /path/to/agents/04-gateway-agent/agent-code/main.py app/GatewayAgent/main.py
```

Add `GATEWAY_URL` to `agentcore/agentcore.json` under the runtime's environment variables,
then deploy:

```bash
agentcore dev    # test locally first
agentcore deploy # deploy to AWS
```

### Step 4: Test

```bash
agentcore invoke "What's the weather in Chicago?" --stream
agentcore invoke "Is subnet subnet-0abc123 public or private?" --stream
agentcore invoke "Can arn:aws:iam::123456789012:role/MyRole do s3:PutObject on arn:aws:s3:::my-bucket/*?" --stream
```

### Clean Up

```bash
# Destroy the Gateway + Lambdas
cd agents/04-gateway-agent/cdk
cdk destroy

# Destroy the agent runtime
cd GatewayAgent
agentcore remove all
agentcore deploy
```

---

## Troubleshooting

### SCP Error: "no service control policy allows bedrock-agentcore:CreateGateway"

Your AWS account is in an Organization with an SCP that doesn't allow AgentCore actions.
Fix: add `bedrock-agentcore:*` to the SCP, or use a different account.

### CDK CLI Version Mismatch

```bash
npm install -g aws-cdk@latest --prefix ~/.npm-global
```

### CfnGateway Not Found

Your `aws-cdk-lib` is too old. Need `>= 2.238.0`:

```bash
pip install "aws-cdk-lib>=2.238.0" --upgrade
```

### Lambda Invoked but Agent Hangs (No Response)

Check these common issues:
1. **Tool name prefix not stripped** — Lambda must handle `target-name___tool_name` format
2. **Context key case** — Must be `bedrockAgentCoreToolName` (camelCase)
3. **Event parsing** — Parameters are in `event` directly, not `event["body"]`
4. **Response format** — Must be `{"statusCode": 200, "body": "plain string"}`

Check Lambda logs: `aws logs tail /aws/lambda/weather-tools --follow`

---

## Tools Reference (9 total)

### Weather (1 tool)

| Tool | Parameters | Description |
| ---- | ---------- | ----------- |
| `get_weather_forecast` | `city` (required) | Live weather from NWS API for 8 US cities |

### Network (5 tools)

| Tool | Parameters | Description |
| ---- | ---------- | ----------- |
| `check_subnet_details` | `subnet_id` (required) | Subnet CIDR, AZ, public/private, available IPs |
| `check_vpc_routes` | `vpc_id` (required), `subnet_id` (optional) | Route table analysis — IGW, NAT, peering, TGW |
| `check_nacl_rules` | `subnet_id` (required) | Network ACL inbound/outbound rules |
| `check_security_group` | `security_group_id` (required) | SG rules with port labels (SSH, HTTPS, etc.) |
| `check_vpc_endpoints` | `vpc_id` (required) | VPC endpoints — S3, DynamoDB, interface |

### IAM (3 tools)

| Tool | Parameters | Description |
| ---- | ---------- | ----------- |
| `verify_iam_access` | `principal_arn`, `action`, `resource_arn` (all required) | IAM Policy Simulator — allow/deny decision |
| `list_principal_policies` | `principal_arn` (required) | List inline, managed, and group policies |
| `get_policy_document` | `policy_arn` (required) | Full JSON policy document |

---

## What's Next

With Gateway, you've centralized tools as a service. Next steps to explore:

- **AgentCore Memory** — Add conversation persistence across sessions
- **Gateway Semantic Search** — Let Gateway auto-select relevant tools from 50+ tools
- **Multi-Agent (A2A)** — Have specialized agents communicate with each other
- **AgentCore Observability** — OpenTelemetry traces for debugging agent behavior

See the [agentcore-samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples) repo for tutorials on each.
