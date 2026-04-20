# AgentCore Gateway Agent

A single agent that accesses weather, network, and IAM tools through **AgentCore Gateway**
instead of having tools baked into the agent code. Everything deploys with `cdk deploy`.

---

## How It Works

### The Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│  AgentCore Runtime                                               │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Gateway Agent (agent-code/main.py)                        │  │
│  │                                                             │  │
│  │  This agent has ZERO tool code.                             │  │
│  │  It connects to Gateway via MCP and discovers 9 tools.     │  │
│  │                                                             │  │
│  │  tools = [mcp_client]  ← single MCP connection             │  │
│  └──────────────┬─────────────────────────────────────────────┘  │
└─────────────────┼────────────────────────────────────────────────┘
                  │ MCP protocol (SigV4 authenticated)
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  AgentCore Gateway (tools-gateway)                               │
│  A managed MCP server — created by CDK                           │
│                                                                  │
│  The Gateway receives MCP tool calls from the agent,             │
│  routes them to the correct Lambda, and returns results.         │
│                                                                  │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │  Weather Target  │ │ Network Target  │ │   IAM Target    │   │
│  │  (1 tool)        │ │ (5 tools)       │ │  (3 tools)      │   │
│  └────────┬─────────┘ └────────┬────────┘ └────────┬────────┘   │
└───────────┼────────────────────┼───────────────────┼────────────┘
            │                    │                   │
            ▼                    ▼                   ▼
   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
   │ weather-tools  │  │ network-tools  │  │  iam-tools     │
   │ Lambda         │  │ Lambda         │  │  Lambda        │
   │                │  │                │  │                │
   │ Calls NWS API  │  │ Calls EC2 APIs │  │ Calls IAM APIs │
   └────────────────┘  └────────────────┘  └────────────────┘
```

### What Happens When You Ask a Question

```
User: "Does subnet-abc have internet access?"

1. Agent receives the question
2. Agent sees 9 tools via MCP (discovered from Gateway)
3. LLM decides: "I need check_subnet_details and check_vpc_routes"
4. Agent sends MCP tool call → Gateway
5. Gateway routes to network-tools Lambda
6. Lambda calls ec2:DescribeSubnets, ec2:DescribeRouteTables
7. Lambda returns results → Gateway → Agent
8. LLM reads results and responds:
   "Subnet subnet-abc is a private subnet with no NAT gateway.
    It has no internet access. To fix this, add a NAT Gateway..."
```

---

## Project Structure

```
gateway-agent/
│
├── cdk/                                    # Infrastructure (deploy with `cdk deploy`)
│   ├── app.py                              # CDK app entry point
│   ├── cdk.json                            # CDK config
│   ├── requirements.txt                    # CDK dependencies (aws-cdk-lib >= 2.238.0)
│   └── stacks/
│       └── gateway_stack.py                # All resources: Lambdas + Gateway + Targets
│
├── lambdas/                                # Lambda function code (tool implementations)
│   ├── weather-tools/
│   │   └── lambda_function.py              # get_weather_forecast
│   ├── network-tools/
│   │   └── lambda_function.py              # 5 network diagnostic tools
│   └── iam-tools/
│       └── lambda_function.py              # 3 IAM access tools
│
├── agent-code/                             # Agent for AgentCore Runtime
│   ├── main.py                             # Connects to Gateway via MCP (no tool code)
│   ├── requirements.txt                    # Agent dependencies
│   └── Dockerfile                          # Container for AgentCore Runtime
│
├── setup_gateway.py                        # Alternative: manual setup via boto3
├── requirements.txt                        # Dependencies for manual setup
└── README.md                               # This file
```

---

## What CDK Deploys

The CDK stack (`cdk/stacks/gateway_stack.py`) creates all resources in one command:

### IAM Roles

| Role | Trusted By | Permissions | Why |
| ---- | ---------- | ----------- | --- |
| Lambda Execution Role | `lambda.amazonaws.com` | CloudWatch Logs, EC2 Describe*, IAM Simulate/List/Get | Lambdas need these to run the tools |
| Gateway Role | `bedrock-agentcore.amazonaws.com` | `lambda:InvokeFunction` on the 3 Lambdas | Gateway needs to call the Lambdas |

### Lambda Functions

| Lambda | Code Location | Tools | What It Calls |
| ------ | ------------- | ----- | ------------- |
| `weather-tools` | `lambdas/weather-tools/` | `get_weather_forecast` | NWS Weather API |
| `network-tools` | `lambdas/network-tools/` | `check_subnet_details`, `check_vpc_routes`, `check_nacl_rules`, `check_security_group`, `check_vpc_endpoints` | EC2 APIs via boto3 |
| `iam-tools` | `lambdas/iam-tools/` | `verify_iam_access`, `list_principal_policies`, `get_policy_document` | IAM APIs via boto3 |

### AgentCore Gateway

| Setting | Value |
| ------- | ----- |
| Name | `tools-gateway` |
| Protocol | MCP (Model Context Protocol) |
| Auth | AWS IAM (SigV4) |
| Targets | 3 Lambda targets with 9 tools total |

### Gateway Targets

Each target attaches a Lambda to the Gateway with **tool schemas** — the JSON definitions
that tell the LLM what each tool does and what parameters it accepts.

```
Gateway
├── Target: weather-tools → weather-tools Lambda (1 tool schema)
├── Target: network-tools → network-tools Lambda (5 tool schemas)
└── Target: iam-tools     → iam-tools Lambda (3 tool schemas)
```

---

## How Lambda Functions Work with Gateway

When Gateway receives an MCP tool call, it invokes the Lambda and passes the tool name
in `context.client_context.custom["bedrockagentcoreToolName"]`.

Each Lambda reads this to route to the right function:

```python
def handler(event, context):
    # Gateway tells us which tool was called
    tool_name = context.client_context.custom.get("bedrockagentcoreToolName", "")

    # Tool parameters come in the event body
    body = json.loads(event.get("body", "{}"))

    # Route to the right function
    if tool_name == "check_subnet_details":
        result = check_subnet_details(body["subnet_id"])
        return {"statusCode": 200, "body": json.dumps({"result": result})}
```

This is why one Lambda can serve multiple tools — it reads the tool name and dispatches.

---

## How the Agent Connects to Gateway

The agent (`agent-code/main.py`) has no tool code at all. It connects to Gateway via MCP:

```python
from bedrock_agentcore.gateway import GatewayClient
from strands.tools.mcp.mcp_client import MCPClient

# Connect to Gateway — discovers all 9 tools automatically
gateway_client = GatewayClient(gateway_id=GATEWAY_ID)
mcp_client = MCPClient(gateway_client)

agent = Agent(
    system_prompt=SYSTEM_PROMPT,
    tools=[mcp_client],  # All 9 tools available through this single connection
)
```

When the agent starts, the MCP client calls `listTools` on the Gateway and gets back
all 9 tool schemas. The LLM sees them and can call any of them.

---

## Deploy

### Prerequisites

- Python 3.10+
- AWS CDK CLI >= 2.1118.2 (`npm install -g aws-cdk@latest`)
- AWS CLI configured (`aws configure`)
- Claude model access in Bedrock console
- IAM permissions: `BedrockAgentCoreFullAccess` + standard CDK permissions
- If your account is in an AWS Organization: SCP must allow `bedrock-agentcore:*`

### Step 1: Deploy Gateway + Lambdas

```bash
cd agents/gateway-agent/cdk

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1

# Deploy
cdk deploy
```

Takes ~3-5 minutes. Save the `GatewayId` from the output.

### Step 2: Deploy the Agent

Set `GATEWAY_ID` as an environment variable in your AgentCore Runtime, then deploy
`agent-code/` using the AgentCore CLI or your CDK pipeline.

### Step 3: Test

```bash
agentcore invoke "What's the weather in Chicago?" --stream
agentcore invoke "Is subnet subnet-abc public or private?" --stream
agentcore invoke "Can arn:aws:iam::123456789012:role/MyRole do s3:PutObject on arn:aws:s3:::my-bucket/*?" --stream
```

### Clean Up

```bash
cd agents/gateway-agent/cdk
cdk destroy
```

---

## Troubleshooting

### SCP Error: "no service control policy allows bedrock-agentcore:CreateGateway"

Your AWS account is in an Organization with an SCP that doesn't allow AgentCore actions.
Fix: add `bedrock-agentcore:*` to the SCP, or use a different account.

### CDK CLI Version Mismatch

If you see "Cloud assembly schema version mismatch", upgrade the CDK CLI:

```bash
npm install -g aws-cdk@latest --prefix ~/.npm-global
```

### CfnGateway Not Found

If `aws_bedrockagentcore` doesn't have `CfnGateway`, your `aws-cdk-lib` is too old.
Need `>= 2.238.0`:

```bash
pip install "aws-cdk-lib>=2.238.0" --upgrade
```

---

## Tools Reference (9 total)

### Weather Tools (1)

| Tool | Parameters | Description |
| ---- | ---------- | ----------- |
| `get_weather_forecast` | `city` (string, required) | Live weather from NWS API for 8 US cities |

### Network Tools (5)

| Tool | Parameters | Description |
| ---- | ---------- | ----------- |
| `check_subnet_details` | `subnet_id` (required) | Subnet CIDR, AZ, public/private, available IPs |
| `check_vpc_routes` | `vpc_id` (required), `subnet_id` (optional) | Route table analysis — IGW, NAT, peering, TGW |
| `check_nacl_rules` | `subnet_id` (required) | Network ACL inbound/outbound rules |
| `check_security_group` | `security_group_id` (required) | SG rules with port labels (SSH, HTTPS, etc.) |
| `check_vpc_endpoints` | `vpc_id` (required) | VPC endpoints — S3, DynamoDB, interface |

### IAM Tools (3)

| Tool | Parameters | Description |
| ---- | ---------- | ----------- |
| `verify_iam_access` | `principal_arn`, `action`, `resource_arn` (all required) | IAM Policy Simulator — allow/deny decision |
| `list_principal_policies` | `principal_arn` (required) | List inline, managed, and group policies |
| `get_policy_document` | `policy_arn` (required) | Full JSON policy document |
