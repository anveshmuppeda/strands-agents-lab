#!/usr/bin/env python3
"""
CDK App — Runtime Invoker Lambda

Deploys a Lambda function that can invoke any AgentCore Runtime agent.
Pass the Runtime ARN as a CDK context variable.

Usage:
  cdk deploy -c runtime_arn=arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/xxx
"""

import aws_cdk as cdk
from stacks.invoker_stack import InvokerStack

app = cdk.App()
InvokerStack(app, "RuntimeInvoker")

app.synth()
