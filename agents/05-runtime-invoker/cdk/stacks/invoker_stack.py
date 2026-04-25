"""
CDK Stack: AgentCore Runtime Invoker Lambda

Deploys a Lambda function that can invoke any AgentCore Runtime agent.
The Runtime ARN is passed as a CDK context variable or can be overridden
per invocation via the event body.

Usage:
  cdk deploy -c runtime_arn=arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/xxx
"""

from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_iam as iam,
    aws_lambda as lambda_,
)
from constructs import Construct


class InvokerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Runtime ARN — pass via: cdk deploy -c runtime_arn=arn:aws:...
        runtime_arn = self.node.try_get_context("runtime_arn") or ""

        # --- Lambda Function ---

        invoker_lambda = lambda_.Function(
            self,
            "InvokerLambda",
            function_name="agentcore-runtime-invoker",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_function.handler",
            code=lambda_.Code.from_asset("../lambda"),
            timeout=Duration.minutes(5),
            memory_size=256,
            description="Invokes any AgentCore Runtime agent with a prompt",
            environment={
                "AGENT_RUNTIME_ARN": runtime_arn,
            },
        )

        # --- IAM Permissions ---

        # Allow invoking any AgentCore Runtime in this account
        invoker_lambda.add_to_role_policy(
            iam.PolicyStatement(
                sid="InvokeAgentCoreRuntime",
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/*"
                ],
            )
        )

        # --- Outputs ---

        CfnOutput(self, "InvokerLambdaArn",
                   description="Invoker Lambda ARN",
                   value=invoker_lambda.function_arn)

        CfnOutput(self, "InvokerLambdaName",
                   description="Invoker Lambda function name",
                   value=invoker_lambda.function_name)

        if runtime_arn:
            CfnOutput(self, "DefaultRuntimeArn",
                       description="Default AgentCore Runtime ARN",
                       value=runtime_arn)
