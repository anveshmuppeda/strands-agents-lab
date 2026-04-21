#!/usr/bin/env python3
"""
CDK App — Two-stack deployment for Network Agent on AgentCore.

Stack 1: BaseInfraStack  — ECR repo, IAM roles (deploy once)
Stack 2: AgentCoreStack  — AgentCore Runtime (updates on every deploy)
"""

import aws_cdk as cdk
from stacks.base_infra_stack import BaseInfraStack
from stacks.agentcore_stack import AgentCoreStack

app = cdk.App()

# Stack 1: Base infrastructure (ECR, IAM)
base = BaseInfraStack(app, "NetworkAgent-BaseInfra")

# Stack 2: AgentCore Runtime (depends on base)
agentcore = AgentCoreStack(
    app,
    "NetworkAgent-AgentCore",
    ecr_repository=base.ecr_repository,
    agent_role=base.agent_role,
)
agentcore.add_dependency(base)

app.synth()
