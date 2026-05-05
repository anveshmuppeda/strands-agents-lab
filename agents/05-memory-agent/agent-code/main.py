"""
Gateway Agent with Memory — Part 5

Same Gateway agent from Guide 04, with AgentCore Memory added.
Remembers conversations across sessions using AgentCoreMemorySessionManager.

Environment variables:
  GATEWAY_URL — AgentCore Gateway MCP endpoint URL
  MEMORY_ID — AgentCore Memory resource ID
  MODEL_ID — Bedrock model ID (default: us.meta.llama3-3-70b-instruct-v1:0)
  AWS_DEFAULT_REGION — AWS region (default: us-east-1)
"""

import os
import logging
import boto3
import httpx
from botocore.auth import SigV4Auth as BotoSigV4Auth
from botocore.awsrequest import AWSRequest
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("memory-gateway-agent")

app = BedrockAgentCoreApp()

GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
MEMORY_ID = os.environ.get("MEMORY_ID", "")
MODEL_ID = os.environ.get("MODEL_ID", "us.meta.llama3-3-70b-instruct-v1:0")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

SYSTEM_PROMPT = """You are a helpful AWS operations assistant with memory.
You remember previous conversations in this session.

Available tool categories:
1. **Weather**: get_weather_forecast — live weather for US cities
2. **Network**: check_subnet_details, check_vpc_routes, check_nacl_rules,
   check_security_group, check_vpc_endpoints — AWS VPC diagnostics
3. **IAM**: verify_iam_access, list_principal_policies, get_policy_document — IAM access checks

Guidelines:
- Always use tools to get real data
- If the user refers to something from a previous conversation, use your memory context
- Explain results clearly and suggest fixes for any issues found
"""


def _make_sigv4_auth() -> httpx.Auth:
    """SigV4 auth for Gateway requests."""
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
_session_manager = None
_current_session_id = None


def get_or_create_agent(actor_id: str, session_id: str) -> Agent:
    """Create agent with Gateway tools + Memory session manager."""
    global _agent, _session_manager, _current_session_id

    if _agent is not None and _current_session_id == session_id:
        return _agent

    logger.info(f"Initializing agent for actor={actor_id}, session={session_id}")

    if not GATEWAY_URL:
        raise ValueError("GATEWAY_URL environment variable is not set")

    # Gateway MCP client (same as Guide 04)
    mcp_client = MCPClient(
        lambda: streamablehttp_client(GATEWAY_URL, auth=_make_sigv4_auth())
    )

    # Memory session manager (NEW in Guide 05)
    if MEMORY_ID:
        memory_config = AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
        )
        _session_manager = AgentCoreMemorySessionManager(memory_config, region_name=AWS_REGION)
        logger.info(f"Memory enabled: {MEMORY_ID}")
    else:
        _session_manager = None
        logger.warning("MEMORY_ID not set — running without memory")

    _agent = Agent(
        model=BedrockModel(model_id=MODEL_ID, streaming=False),
        system_prompt=SYSTEM_PROMPT,
        tools=[mcp_client],
        session_manager=_session_manager,
    )
    _current_session_id = session_id
    logger.info("Agent created with Gateway tools + Memory")
    return _agent


@app.entrypoint
def invoke(payload, context):
    """AgentCore Runtime entrypoint with session-aware memory."""
    logger.info(f"Payload: {payload}")
    logger.info(f"Session: {context.session_id}")

    prompt = payload.get("prompt", "")
    actor_id = payload.get("actor_id", "default_user")
    session_id = context.session_id

    if not prompt:
        return "Missing 'prompt' in payload"

    agent = get_or_create_agent(actor_id, session_id)
    response = agent(prompt)
    response_text = response.message["content"][0]["text"]

    logger.info(f"Response: {response_text[:100]}...")
    return response_text


if __name__ == "__main__":
    app.run()
