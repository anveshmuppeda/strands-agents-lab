#!/usr/bin/env python3
"""
CDK App — Two-stack deployment for Gateway Agent.

Stack 1: ToolsGateway         — ECR + Lambdas + Gateway + Targets (base infra)
Stack 2: GatewayAgent-Runtime — AgentCore Runtime (uses ECR + Gateway URL from Stack 1)
"""

import aws_cdk as cdk
from stacks.gateway_stack import GatewayStack
from stacks.runtime_stack import RuntimeStack

app = cdk.App()

# Stack 1: Base infra — ECR, Lambdas, Gateway, Targets
gateway = GatewayStack(app, "ToolsGateway")

# Stack 2: AgentCore Runtime — gets ECR repo + Gateway URL from Stack 1
runtime = RuntimeStack(
    app,
    "GatewayAgent-Runtime",
    gateway_id=gateway.gateway_id,
    ecr_repository=gateway.ecr_repository,
)
runtime.add_dependency(gateway)

app.synth()
