"""
AgentCore Runtime Invoker Lambda

A reusable Lambda function that invokes any AgentCore Runtime agent.
Pass the prompt in the event body and the Runtime ARN as an environment variable.

Environment variables:
  AGENT_RUNTIME_ARN — ARN of the AgentCore Runtime to invoke

Event format:
  {"prompt": "What's the weather in New York?"}

Response format:
  {"statusCode": 200, "body": "The weather in New York is..."}
"""

import os
import json
import boto3
import base64

AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")


def handler(event, context):
    """Invoke an AgentCore Runtime agent and return the response."""

    # Parse prompt from event
    if isinstance(event, str):
        event = json.loads(event)

    # Support both direct event and API Gateway format
    body = event
    if "body" in event:
        body = json.loads(event["body"]) if isinstance(event.get("body"), str) else event.get("body", {})

    prompt = body.get("prompt", "")
    runtime_arn = body.get("runtime_arn", AGENT_RUNTIME_ARN)
    qualifier = body.get("qualifier", "DEFAULT")

    if not prompt:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing 'prompt' in request body"}),
        }

    if not runtime_arn:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing AGENT_RUNTIME_ARN env var or 'runtime_arn' in request body"}),
        }

    print(f"Invoking: {runtime_arn} (qualifier: {qualifier})")
    print(f"Prompt: {prompt}")

    try:
        client = boto3.client("bedrock-agentcore")

        # Build the payload
        payload = json.dumps({"prompt": prompt}).encode("utf-8")

        # Invoke the agent runtime
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            qualifier=qualifier,
            payload=payload,
            contentType="application/json",
            accept="application/json",
        )

        # Read the streaming response
        result_chunks = []
        event_stream = response.get("body", response.get("responseStream", None))

        if event_stream:
            for event_data in event_stream:
                if "chunk" in event_data:
                    chunk = event_data["chunk"]
                    if "bytes" in chunk:
                        decoded = chunk["bytes"].decode("utf-8")
                        result_chunks.append(decoded)
                elif "bytes" in event_data:
                    decoded = event_data["bytes"].decode("utf-8")
                    result_chunks.append(decoded)

        full_response = "".join(result_chunks)

        if not full_response:
            # Try reading response as a simple body
            full_response = str(response.get("body", "No response received"))

        print(f"Response length: {len(full_response)} chars")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "prompt": prompt,
                "response": full_response,
                "runtime_arn": runtime_arn,
            }),
        }

    except Exception as e:
        print(f"Error invoking runtime: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "runtime_arn": runtime_arn,
                "prompt": prompt,
            }),
        }
