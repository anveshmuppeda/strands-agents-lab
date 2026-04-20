"""
Gateway Agent — Connects to AgentCore Gateway to access all tools via MCP.

This agent has NO tool code. It discovers tools from the Gateway at runtime.
All tools (weather, network, IAM) are Lambda functions behind the Gateway.

Environment variables:
  GATEWAY_ID — AgentCore Gateway ID (set after running setup_gateway.py)
"""

import os
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.gateway import GatewayClient

app = BedrockAgentCoreApp()
log = app.logger

GATEWAY_ID = os.environ.get("GATEWAY_ID", "")

SYSTEM_PROMPT = """You are a helpful AWS operations assistant with access to weather,
network diagnostics, and IAM security tools.

Available tool categories:
1. **Weather**: get_weather_forecast — live weather for US cities
2. **Network**: check_subnet_details, check_vpc_routes, check_nacl_rules,
   check_security_group, check_vpc_endpoints — AWS VPC diagnostics
3. **IAM**: verify_iam_access, list_principal_policies, get_policy_document — IAM access checks

Guidelines:
- Always use tools to get real data
- For network issues, start with subnet details, then routes, then NACLs/SGs
- For IAM, use verify_iam_access first, then list_principal_policies for context
- Explain results clearly and suggest fixes for any issues found
"""

_agent = None


def get_or_create_agent():
    global _agent
    if _agent is None:
        # Connect to Gateway as an MCP client
        # GatewayClient handles SigV4 auth automatically on AgentCore Runtime
        gateway_client = GatewayClient(gateway_id=GATEWAY_ID)
        mcp_client = MCPClient(gateway_client)

        _agent = Agent(
            system_prompt=SYSTEM_PROMPT,
            tools=[mcp_client],  # All Gateway tools available via MCP
        )
        log.info(f"Agent created with Gateway tools from {GATEWAY_ID}")
    return _agent


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Gateway Agent...")
    agent = get_or_create_agent()
    stream = agent.stream_async(payload.get("prompt"))
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
