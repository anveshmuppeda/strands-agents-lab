"""
Stack 2: AgentCore Runtime for Gateway Agent

Deploys the gateway agent to AgentCore Runtime. This agent has NO tool code —
it connects to the Gateway (deployed by gateway_stack.py) via MCP to discover tools.

Receives ECR repo and Gateway ID from Stack 1.

Usage:
  cdk deploy GatewayAgent-Runtime -c image_tag=abc123
"""

from aws_cdk import (
    Stack,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_bedrockagentcore as bedrockagentcore,
    CfnOutput,
)
from constructs import Construct


class RuntimeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        gateway_id: str,
        ecr_repository: ecr.Repository,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        image_tag = self.node.try_get_context("image_tag") or "latest"

        # --- AgentCore Execution Role ---

        agent_role = iam.Role(
            self,
            "AgentCoreRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            inline_policies={
                "AgentCorePolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            sid="ECRImageAccess",
                            actions=[
                                "ecr:BatchGetImage",
                                "ecr:GetDownloadUrlForLayer",
                                "ecr:BatchCheckLayerAvailability",
                            ],
                            resources=[ecr_repository.repository_arn],
                        ),
                        iam.PolicyStatement(
                            sid="ECRTokenAccess",
                            actions=["ecr:GetAuthorizationToken"],
                            resources=["*"],
                        ),
                        iam.PolicyStatement(
                            sid="CloudWatchLogs",
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                                "logs:DescribeLogGroups",
                                "logs:DescribeLogStreams",
                            ],
                            resources=[
                                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*"
                            ],
                        ),
                        iam.PolicyStatement(
                            sid="XRayTracing",
                            actions=[
                                "xray:PutTraceSegments",
                                "xray:PutTelemetryRecords",
                                "xray:GetSamplingRules",
                                "xray:GetSamplingTargets",
                            ],
                            resources=["*"],
                        ),
                        iam.PolicyStatement(
                            sid="CloudWatchMetrics",
                            actions=["cloudwatch:PutMetricData"],
                            resources=["*"],
                            conditions={
                                "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}
                            },
                        ),
                        iam.PolicyStatement(
                            sid="WorkloadIdentity",
                            actions=[
                                "bedrock-agentcore:GetWorkloadAccessToken",
                                "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                                "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                            ],
                            resources=[
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default",
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default/workload-identity/*",
                            ],
                        ),
                        iam.PolicyStatement(
                            sid="BedrockModelInvocation",
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                            ],
                            resources=[
                                "arn:aws:bedrock:*::foundation-model/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:*",
                            ],
                        ),
                        # Gateway invocation — agent calls Gateway via MCP
                        iam.PolicyStatement(
                            sid="InvokeGateway",
                            actions=["bedrock-agentcore:InvokeGateway"],
                            resources=[
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/*"
                            ],
                        ),
                    ]
                )
            },
        )

        # --- Construct Gateway URL from Gateway ID ---

        gateway_url = f"https://{gateway_id}.gateway.bedrock-agentcore.{self.region}.amazonaws.com/mcp"

        # --- AgentCore Runtime ---

        agent_runtime = bedrockagentcore.CfnRuntime(
            self,
            "AgentRuntime",
            agent_runtime_name="GatewayAgent",
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
            description=f"Gateway Agent — connects to Gateway for tools (image: {image_tag})",
            environment_variables={
                "AWS_DEFAULT_REGION": self.region,
                "GATEWAY_URL": gateway_url,
            },
        )

        # --- Outputs ---

        CfnOutput(self, "AgentRuntimeId",
                   description="AgentCore Runtime ID",
                   value=agent_runtime.attr_agent_runtime_id)

        CfnOutput(self, "AgentRuntimeArn",
                   description="AgentCore Runtime ARN",
                   value=agent_runtime.attr_agent_runtime_arn)

        CfnOutput(self, "GatewayURL",
                   description="Gateway MCP endpoint URL (injected as env var)",
                   value=gateway_url)

        CfnOutput(self, "ContainerImage",
                   description="Container image used",
                   value=f"{ecr_repository.repository_uri}:{image_tag}")
