"""
Gateway Agent — Connects to AgentCore Gateway to access all tools via MCP.

This agent has NO tool code. It discovers tools from the Gateway at runtime.
All tools (weather, network, IAM) are Lambda functions behind the Gateway.

Environment variables:
  GATEWAY_URL — AgentCore Gateway MCP endpoint URL
  AWS_DEFAULT_REGION — AWS region (default: us-east-1)
"""

import os
import boto3
import httpx
from botocore.auth import SigV4Auth as BotoSigV4Auth
from botocore.awsrequest import AWSRequest
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model

app = BedrockAgentCoreApp()
log = app.logger

GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

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


def _make_sigv4_auth() -> httpx.Auth:
    """SigV4 auth for Gateway requests using current boto3 credentials."""
    session = boto3.Session()
    creds = session.get_credentials().get_frozen_credentials()

    class _GatewayAuth(httpx.Auth):
        def auth_flow(self, request):
            headers = dict(request.headers)
            headers.pop("connection", None)
            aws_req = AWSRequest(
                method=request.method,
                url=str(request.url),
                data=request.content,
                headers=headers,
            )
            BotoSigV4Auth(creds, "bedrock-agentcore", AWS_REGION).add_auth(aws_req)
            request.headers.update(dict(aws_req.headers))
            yield request

    return _GatewayAuth()


_agent = None


def get_or_create_agent() -> Agent:
    global _agent
    if _agent is None:
        if not GATEWAY_URL:
            raise ValueError("GATEWAY_URL environment variable is not set")

        mcp_client = MCPClient(
            lambda: streamablehttp_client(GATEWAY_URL, auth=_make_sigv4_auth())
        )

        _agent = Agent(
            model=load_model(),
            system_prompt=SYSTEM_PROMPT,
            tools=[mcp_client],
        )
        log.info("Agent created with Gateway tools from %s", GATEWAY_URL)
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
