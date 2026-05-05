"""
Stack 2: AgentCore Runtime with Memory

Deploys:
- AgentCore Memory resource (short-term, 7-day expiry)
- IAM Role with Bedrock + ECR + Gateway + Memory permissions
- AgentCore Runtime with GATEWAY_URL + MEMORY_ID env vars

Receives ECR repo and Gateway ID from Stack 1 (gateway_stack.py).

Usage:
  cdk deploy --all
  cdk deploy MemoryGatewayAgent-Runtime -c image_tag=abc123
"""

from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_bedrockagentcore as bedrockagentcore,
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
        model_id = self.node.try_get_context("model_id") or "us.meta.llama3-3-70b-instruct-v1:0"

        # --- AgentCore Memory (NEW — not in Guide 04) ---

        memory = bedrockagentcore.CfnMemory(
            self,
            "AgentMemory",
            name="MemoryGatewayAgentMemory",
            description="Short-term memory for gateway agent — remembers conversations across sessions",
            event_expiry_duration=7,  # Auto-delete after 7 days
        )

        # --- IAM Role (same as Guide 04 + Memory permissions) ---

        agent_role = iam.Role(
            self,
            "AgentCoreRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            inline_policies={
                "AgentCorePolicy": iam.PolicyDocument(
                    statements=[
                        # ECR — pull container images
                        iam.PolicyStatement(
                            sid="ECRAccess",
                            actions=[
                                "ecr:BatchGetImage",
                                "ecr:GetDownloadUrlForLayer",
                                "ecr:BatchCheckLayerAvailability",
                            ],
                            resources=[ecr_repository.repository_arn],
                        ),
                        iam.PolicyStatement(
                            sid="ECRToken",
                            actions=["ecr:GetAuthorizationToken"],
                            resources=["*"],
                        ),
                        # CloudWatch Logs
                        iam.PolicyStatement(
                            sid="Logs",
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
                        # X-Ray
                        iam.PolicyStatement(
                            sid="XRay",
                            actions=[
                                "xray:PutTraceSegments",
                                "xray:PutTelemetryRecords",
                                "xray:GetSamplingRules",
                                "xray:GetSamplingTargets",
                            ],
                            resources=["*"],
                        ),
                        # CloudWatch metrics
                        iam.PolicyStatement(
                            sid="Metrics",
                            actions=["cloudwatch:PutMetricData"],
                            resources=["*"],
                            conditions={
                                "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}
                            },
                        ),
                        # Workload identity
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
                        # Bedrock model invocation
                        iam.PolicyStatement(
                            sid="Bedrock",
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                            ],
                            resources=[
                                "arn:aws:bedrock:*::foundation-model/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:*",
                            ],
                        ),
                        # Gateway invocation (same as Guide 04)
                        iam.PolicyStatement(
                            sid="Gateway",
                            actions=["bedrock-agentcore:InvokeGateway"],
                            resources=[
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/*"
                            ],
                        ),
                        # Memory operations (NEW — not in Guide 04)
                        iam.PolicyStatement(
                            sid="Memory",
                            actions=[
                                "bedrock-agentcore:CreateEvent",
                                "bedrock-agentcore:GetLastKTurns",
                                "bedrock-agentcore:GetMemory",
                                "bedrock-agentcore:ListMemories",
                                "bedrock-agentcore:ListEvents",
                            ],
                            resources=[
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:memory/*"
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
            agent_runtime_name="MemoryGatewayAgent",
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
            description=f"Gateway Agent with Memory (image: {image_tag})",
            environment_variables={
                "AWS_DEFAULT_REGION": self.region,
                "MODEL_ID": model_id,
                "GATEWAY_URL": gateway_url,
                "MEMORY_ID": memory.attr_memory_id,  # ← Memory ID injected automatically
            },
        )
        agent_runtime.add_dependency(memory)

        # --- Outputs ---

        CfnOutput(self, "AgentRuntimeId",
                   description="AgentCore Runtime ID",
                   value=agent_runtime.attr_agent_runtime_id)

        CfnOutput(self, "AgentRuntimeArn",
                   description="AgentCore Runtime ARN",
                   value=agent_runtime.attr_agent_runtime_arn)

        CfnOutput(self, "MemoryId",
                   description="AgentCore Memory ID",
                   value=memory.attr_memory_id)

        CfnOutput(self, "GatewayURL",
                   description="Gateway MCP endpoint URL",
                   value=gateway_url)

        CfnOutput(self, "ECRRepositoryUri",
                   description="ECR Repository URI",
                   value=ecr_repository.repository_uri)

        CfnOutput(self, "ContainerImage",
                   description="Container image used",
                   value=f"{ecr_repository.repository_uri}:{image_tag}")
