#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.gateway_stack import GatewayStack

app = cdk.App()
GatewayStack(app, "ToolsGateway")

app.synth()
