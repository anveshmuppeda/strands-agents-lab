# AgentCore Runtime Invoker (Part 5)

## *Test Any Deployed Agent from AWS — No Local Setup Needed*

A reusable Lambda function that invokes any AgentCore Runtime agent by sending prompts
and returning responses. Use it to test agents after deployment without running anything locally.

> **Works with all agents:** Weather Agent, Network Agent, Gateway Agent — any agent
> deployed to AgentCore Runtime. Just pass the Runtime ARN.

---

## Why This Exists

After deploying an agent to AgentCore Runtime, you need a way to test it. The options are:

| Method | Requires | Good For |
|--------|----------|----------|
| `agentcore invoke` (CLI) | Local machine with CLI installed | Quick local testing |
| AWS Console | Browser access | Manual one-off tests |
| **This Lambda** | Nothing — runs in AWS | CI/CD testing, automated tests, no local setup |

This Lambda is especially useful when:
- You deploy via CI/CD and want to verify the agent works
- You want to test from AWS without any local tools
- You want to integrate agent invocation into other AWS services (Step Functions, EventBridge, API Gateway)

---

## Architecture

```
You (or CI/CD pipeline)
    │
    │ aws lambda invoke --function-name agentcore-runtime-invoker \
    │   --payload '{"prompt": "What is the weather in NYC?"}'
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  Lambda: agentcore-runtime-invoker                    │
│                                                       │
│  1. Reads AGENT_RUNTIME_ARN from env (or event body) │
│  2. Calls bedrock-agentcore:InvokeAgentRuntime       │
│  3. Reads streaming response                          │
│  4. Returns the full response as JSON                 │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  AgentCore Runtime (any deployed agent)               │
│                                                       │
│  Weather Agent / Network Agent / Gateway Agent        │
│  Processes the prompt, calls tools, returns response  │
└──────────────────────────────────────────────────────┘
```

---

## Project Structure

```
05-runtime-invoker/
│
├── lambda/
│   └── lambda_function.py          # Invoker Lambda code
│
├── cdk/
│   ├── app.py                      # CDK app
│   ├── cdk.json
│   ├── requirements.txt
│   └── stacks/
│       └── invoker_stack.py        # Lambda + IAM permissions
│
└── README.md
```

---

## Deploy

### Step 1: Deploy the Lambda

```bash
cd agents/05-runtime-invoker/cdk

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Deploy with a default Runtime ARN (optional)
cdk deploy -c runtime_arn=arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT:runtime/YOUR_RUNTIME_ID

# Or deploy without a default (pass runtime_arn per invocation)
cdk deploy
```

### Step 2: Test Any Agent

**Test the Weather Agent:**

```bash
aws lambda invoke \
  --function-name agentcore-runtime-invoker \
  --payload '{"prompt": "What is the weather in Chicago?"}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json | python3 -m json.tool
```

**Test the Network Agent:**

```bash
aws lambda invoke \
  --function-name agentcore-runtime-invoker \
  --payload '{"prompt": "Is subnet subnet-0abc123 public or private?"}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json | python3 -m json.tool
```

**Test the Gateway Agent:**

```bash
aws lambda invoke \
  --function-name agentcore-runtime-invoker \
  --payload '{"prompt": "Does VPC vpc-0abc123 have internet access?"}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json | python3 -m json.tool
```

**Override the Runtime ARN per invocation** (test a different agent without redeploying):

```bash
aws lambda invoke \
  --function-name agentcore-runtime-invoker \
  --payload '{"prompt": "Hello", "runtime_arn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/OTHER_AGENT"}' \
  --cli-binary-format raw-in-base64-out \
  response.json
```

---

## How It Works

The Lambda does three things:

1. **Reads the prompt** from the event body and the Runtime ARN from the environment variable (or event body override)

2. **Calls `InvokeAgentRuntime`** via boto3:
   ```python
   client = boto3.client("bedrock-agentcore")
   response = client.invoke_agent_runtime(
       agentRuntimeArn=runtime_arn,
       qualifier="DEFAULT",
       payload=json.dumps({"prompt": prompt}).encode("utf-8"),
       contentType="application/json",
       accept="application/json",
   )
   ```

3. **Reads the streaming response** and assembles it into a single string:
   ```python
   for event_data in response["body"]:
       if "chunk" in event_data:
           result_chunks.append(event_data["chunk"]["bytes"].decode("utf-8"))
   ```

---

## Event Format

**Input:**

```json
{
  "prompt": "What's the weather in New York?",
  "runtime_arn": "arn:aws:bedrock-agentcore:...:runtime/xxx",
  "qualifier": "DEFAULT"
}
```

Only `prompt` is required. `runtime_arn` falls back to the `AGENT_RUNTIME_ARN` env var.
`qualifier` defaults to `"DEFAULT"`.

**Output:**

```json
{
  "statusCode": 200,
  "body": {
    "prompt": "What's the weather in New York?",
    "response": "The weather in New York is 47°F with rain showers tonight...",
    "runtime_arn": "arn:aws:bedrock-agentcore:...:runtime/xxx"
  }
}
```

---

## IAM Permissions

The Lambda needs `bedrock-agentcore:InvokeAgentRuntime` on all runtimes in the account:

```json
{
  "Effect": "Allow",
  "Action": "bedrock-agentcore:InvokeAgentRuntime",
  "Resource": "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/*"
}
```

The CDK stack sets this up automatically.

---

## Using with Other Agents

| Agent | Runtime ARN Source | Example Prompt |
|-------|--------------------|----------------|
| 01-weather-agent | `agentcore status` output | `"What's the weather in Seattle?"` |
| 02-network-agent | `agentcore status` output | `"Check security group sg-0abc123"` |
| 03-network-agent-cdk | CDK output `AgentRuntimeArn` | `"Does VPC vpc-abc have internet?"` |
| 04-gateway-agent | CDK output `AgentRuntimeArn` | `"Can role X do s3:PutObject on bucket Y?"` |

Get the Runtime ARN from any deployed agent:

```bash
# From AgentCore CLI
agentcore status

# From CDK output
aws cloudformation describe-stacks \
  --stack-name STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeArn`].OutputValue' \
  --output text
```

---

## Clean Up

```bash
cd agents/05-runtime-invoker/cdk
cdk destroy
```
