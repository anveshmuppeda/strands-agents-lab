#!/usr/bin/env python3
"""
CDK App — Complete Memory Gateway Agent deployment.

Stack 1: MemoryToolsGateway       — ECR + Lambdas + Gateway + Targets (base infra)
Stack 2: MemoryGatewayAgent-Runtime — Memory + IAM + AgentCore Runtime

Everything deploys with: cdk deploy --all
"""

import aws_cdk as cdk
from stacks.gateway_stack import GatewayStack
from stacks.runtime_stack import RuntimeStack

app = cdk.App()

# Stack 1: Lambdas + Gateway + Targets + ECR
gateway = GatewayStack(app, "MemoryToolsGateway")

# Stack 2: Memory + Runtime (gets ECR + Gateway ID from Stack 1)
runtime = RuntimeStack(
    app,
    "MemoryGatewayAgent-Runtime",
    gateway_id=gateway.gateway_id,
    ecr_repository=gateway.ecr_repository,
)
runtime.add_dependency(gateway)

app.synth()
