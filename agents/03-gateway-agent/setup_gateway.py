"""
Setup script — Creates AgentCore Gateway and attaches Lambda targets.

Usage:
  1. Deploy the 3 Lambda functions first (weather-tools, network-tools, iam-tools)
  2. Set environment variables for Lambda ARNs
  3. Run: python setup_gateway.py

Environment variables:
  AWS_REGION                  — AWS region (default: us-east-1)
  WEATHER_LAMBDA_ARN          — ARN of the weather-tools Lambda
  NETWORK_LAMBDA_ARN          — ARN of the network-tools Lambda
  IAM_LAMBDA_ARN              — ARN of the iam-tools Lambda
"""

import os
import json
import time
import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
WEATHER_LAMBDA_ARN = os.environ.get("WEATHER_LAMBDA_ARN", "")
NETWORK_LAMBDA_ARN = os.environ.get("NETWORK_LAMBDA_ARN", "")
IAM_LAMBDA_ARN = os.environ.get("IAM_LAMBDA_ARN", "")

client = boto3.client("bedrock-agentcore", region_name=REGION)


# --- Tool Schemas ---
# These define what the LLM sees via MCP — name, description, parameters.

WEATHER_TOOLS = [
    {
        "name": "get_weather_forecast",
        "description": "Get the weather forecast for a US city using the National Weather Service API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Name of a US city (e.g., 'New York', 'Chicago')"}
            },
            "required": ["city"],
        },
    }
]

NETWORK_TOOLS = [
    {
        "name": "check_subnet_details",
        "description": "Get details about an AWS subnet — CIDR, AZ, public/private, available IPs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subnet_id": {"type": "string", "description": "AWS Subnet ID (e.g., 'subnet-0abc123')"}
            },
            "required": ["subnet_id"],
        },
    },
    {
        "name": "check_vpc_routes",
        "description": "Analyze route tables for a VPC or subnet. Shows IGW, NAT, peering, TGW routes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vpc_id": {"type": "string", "description": "AWS VPC ID"},
                "subnet_id": {"type": "string", "description": "Subnet ID (optional)"},
            },
            "required": ["vpc_id"],
        },
    },
    {
        "name": "check_nacl_rules",
        "description": "Check Network ACL inbound and outbound rules for a subnet.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subnet_id": {"type": "string", "description": "AWS Subnet ID"}
            },
            "required": ["subnet_id"],
        },
    },
    {
        "name": "check_security_group",
        "description": "Check security group inbound and outbound rules with port labels.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "security_group_id": {"type": "string", "description": "AWS Security Group ID (e.g., 'sg-0abc123')"}
            },
            "required": ["security_group_id"],
        },
    },
    {
        "name": "check_vpc_endpoints",
        "description": "List VPC endpoints (S3, DynamoDB, interface endpoints) in a VPC.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vpc_id": {"type": "string", "description": "AWS VPC ID"}
            },
            "required": ["vpc_id"],
        },
    },
]

IAM_TOOLS = [
    {
        "name": "verify_iam_access",
        "description": "Check if an IAM role or user can perform a specific action on a resource using the IAM Policy Simulator.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "principal_arn": {"type": "string", "description": "ARN of the IAM role or user"},
                "action": {"type": "string", "description": "AWS action (e.g., 's3:PutObject')"},
                "resource_arn": {"type": "string", "description": "ARN of the resource"},
            },
            "required": ["principal_arn", "action", "resource_arn"],
        },
    },
    {
        "name": "list_principal_policies",
        "description": "List all policies attached to an IAM role or user (inline, managed, group).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "principal_arn": {"type": "string", "description": "ARN of the IAM role or user"}
            },
            "required": ["principal_arn"],
        },
    },
    {
        "name": "get_policy_document",
        "description": "Get the full JSON policy document for a managed IAM policy.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy_arn": {"type": "string", "description": "ARN of the IAM policy"}
            },
            "required": ["policy_arn"],
        },
    },
]


def create_gateway():
    """Create the AgentCore Gateway."""
    print("Creating Gateway...")
    resp = client.create_gateway(
        name="tools-gateway",
        protocolType="MCP",
        description="Centralized tools gateway for weather, network, and IAM tools",
    )
    gateway_id = resp["gatewayId"]
    print(f"  Gateway created: {gateway_id}")

    # Wait for Gateway to be ready
    print("  Waiting for Gateway to be ACTIVE...", end="", flush=True)
    for _ in range(30):
        status = client.get_gateway(gatewayId=gateway_id)
        if status.get("status") == "ACTIVE":
            print(" ACTIVE")
            break
        print(".", end="", flush=True)
        time.sleep(5)
    else:
        print(" TIMEOUT — check console")

    return gateway_id


def create_target(gateway_id, name, lambda_arn, tools):
    """Attach a Lambda function as a Gateway target with tool definitions."""
    if not lambda_arn:
        print(f"  SKIPPING {name} — no Lambda ARN provided")
        return

    print(f"  Attaching target: {name} ({lambda_arn})")
    resp = client.create_gateway_target(
        gatewayId=gateway_id,
        name=name,
        targetConfiguration={
            "lambdaTargetConfiguration": {
                "lambdaArn": lambda_arn,
            }
        },
        toolSchema={
            "inlinePayload": tools,
        },
        description=f"{name} tools via Lambda",
    )
    target_id = resp["targetId"]
    print(f"    Target created: {target_id}")

    # Wait for target to be ready
    for _ in range(20):
        status = client.get_gateway_target(gatewayId=gateway_id, targetId=target_id)
        if status.get("status") in ["ACTIVE", "READY"]:
            print(f"    Status: READY")
            break
        time.sleep(3)

    return target_id


def main():
    print("=" * 60)
    print("  AgentCore Gateway Setup")
    print("=" * 60)
    print()

    # Validate Lambda ARNs
    if not any([WEATHER_LAMBDA_ARN, NETWORK_LAMBDA_ARN, IAM_LAMBDA_ARN]):
        print("ERROR: No Lambda ARNs provided. Set environment variables:")
        print("  export WEATHER_LAMBDA_ARN=arn:aws:lambda:...")
        print("  export NETWORK_LAMBDA_ARN=arn:aws:lambda:...")
        print("  export IAM_LAMBDA_ARN=arn:aws:lambda:...")
        return

    # Step 1: Create Gateway
    gateway_id = create_gateway()
    print()

    # Step 2: Attach targets
    print("Attaching Lambda targets...")
    create_target(gateway_id, "weather-tools", WEATHER_LAMBDA_ARN, WEATHER_TOOLS)
    create_target(gateway_id, "network-tools", NETWORK_LAMBDA_ARN, NETWORK_TOOLS)
    create_target(gateway_id, "iam-tools", IAM_LAMBDA_ARN, IAM_TOOLS)
    print()

    # Step 3: Print summary
    print("=" * 60)
    print("  Setup Complete!")
    print("=" * 60)
    print(f"  Gateway ID: {gateway_id}")
    print(f"  Region: {REGION}")
    print()
    print("  To connect your agent, use this Gateway ID in your MCP client config.")
    print(f"  Gateway MCP endpoint: https://gateway.bedrock-agentcore.{REGION}.amazonaws.com/{gateway_id}/mcp")
    print()
    print("  Save this Gateway ID — you'll need it for the agent-code/main.py")


if __name__ == "__main__":
    main()
