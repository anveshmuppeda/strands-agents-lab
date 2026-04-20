"""
Stack 2: AgentCore Runtime

Deploys the weather agent to Amazon Bedrock AgentCore Runtime.
Depends on the base infra stack for ECR repository and IAM role.

The image tag is passed as a CDK context variable:
  cdk deploy WeatherAgent-AgentCore -c image_tag=abc123
"""

from aws_cdk import (
    Stack,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_bedrockagentcore as bedrockagentcore,
    CfnOutput,
)
from constructs import Construct


class AgentCoreStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        ecr_repository: ecr.Repository,
        agent_role: iam.Role,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Image tag — passed from CI/CD pipeline via CDK context
        # Usage: cdk deploy -c image_tag=abc123
        # Falls back to "latest" for manual deploys
        image_tag = self.node.try_get_context("image_tag") or "latest"

        # --- AgentCore Runtime ---

        agent_runtime = bedrockagentcore.CfnRuntime(
            self,
            "AgentRuntime",
            agent_runtime_name="WeatherAgent",
            agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=bedrockagentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=f"{ecr_repository.repository_uri}:{image_tag}"
                )
            ),
            network_configuration=bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC"
            ),
            protocol_configuration="HTTP",
            role_arn=agent_role.role_arn,
            description=f"Weather Agent (image: {image_tag})",
            environment_variables={
                "AWS_DEFAULT_REGION": self.region,
            },
        )

        # --- Outputs ---

        CfnOutput(self, "AgentRuntimeId",
                   description="AgentCore Runtime ID",
                   value=agent_runtime.attr_agent_runtime_id)

        CfnOutput(self, "AgentRuntimeArn",
                   description="AgentCore Runtime ARN",
                   value=agent_runtime.attr_agent_runtime_arn)

        CfnOutput(self, "ContainerImage",
                   description="Container image used",
                   value=f"{ecr_repository.repository_uri}:{image_tag}")
