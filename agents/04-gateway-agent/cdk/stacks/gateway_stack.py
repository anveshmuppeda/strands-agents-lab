"""
CDK Stack: AgentCore Gateway + Lambda Targets

Deploys everything in one `cdk deploy`:
1. IAM roles (Gateway role, Lambda execution role)
2. Three Lambda functions (weather, network, IAM tools)
3. AgentCore Gateway (MCP endpoint with IAM auth)
4. Three Gateway Targets (one per Lambda, with tool schemas)

No manual setup_gateway.py needed — CDK handles it all.
"""

from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_bedrockagentcore as bedrockagentcore,
)
from constructs import Construct


class GatewayStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ─── Lambda Execution Role ───────────────────────────────────

        lambda_role = iam.Role(
            self,
            "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
            inline_policies={
                "ToolPermissions": iam.PolicyDocument(
                    statements=[
                        # Network tools need EC2 describe permissions
                        iam.PolicyStatement(
                            sid="EC2ReadOnly",
                            actions=[
                                "ec2:DescribeSubnets",
                                "ec2:DescribeRouteTables",
                                "ec2:DescribeNetworkAcls",
                                "ec2:DescribeSecurityGroups",
                                "ec2:DescribeVpcEndpoints",
                            ],
                            resources=["*"],
                        ),
                        # IAM tools need policy simulator + list permissions
                        iam.PolicyStatement(
                            sid="IAMReadOnly",
                            actions=[
                                "iam:SimulatePrincipalPolicy",
                                "iam:ListRolePolicies",
                                "iam:ListAttachedRolePolicies",
                                "iam:ListUserPolicies",
                                "iam:ListAttachedUserPolicies",
                                "iam:ListGroupsForUser",
                                "iam:ListAttachedGroupPolicies",
                                "iam:GetPolicy",
                                "iam:GetPolicyVersion",
                            ],
                            resources=["*"],
                        ),
                    ]
                )
            },
        )

        # ─── Lambda Functions ────────────────────────────────────────

        weather_lambda = lambda_.Function(
            self,
            "WeatherToolsLambda",
            function_name="weather-tools",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_function.handler",
            code=lambda_.Code.from_asset("../lambdas/weather-tools"),
            timeout=Duration.seconds(30),
            role=lambda_role,
            description="Weather tools for AgentCore Gateway",
        )

        network_lambda = lambda_.Function(
            self,
            "NetworkToolsLambda",
            function_name="network-tools",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_function.handler",
            code=lambda_.Code.from_asset("../lambdas/network-tools"),
            timeout=Duration.seconds(30),
            role=lambda_role,
            description="AWS network diagnostics tools for AgentCore Gateway",
        )

        iam_lambda = lambda_.Function(
            self,
            "IAMToolsLambda",
            function_name="iam-tools",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_function.handler",
            code=lambda_.Code.from_asset("../lambdas/iam-tools"),
            timeout=Duration.seconds(30),
            role=lambda_role,
            description="IAM access verification tools for AgentCore Gateway",
        )

        # ─── Gateway IAM Role ───────────────────────────────────────

        gateway_role = iam.Role(
            self,
            "GatewayRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            inline_policies={
                "GatewayPolicy": iam.PolicyDocument(
                    statements=[
                        # Gateway needs to invoke the Lambda functions
                        iam.PolicyStatement(
                            sid="InvokeLambdas",
                            actions=["lambda:InvokeFunction"],
                            resources=[
                                weather_lambda.function_arn,
                                network_lambda.function_arn,
                                iam_lambda.function_arn,
                            ],
                        ),
                    ]
                )
            },
        )

        # ─── AgentCore Gateway ───────────────────────────────────────

        gateway = bedrockagentcore.CfnGateway(
            self,
            "ToolsGateway",
            name="tools-gateway",
            protocol_type="MCP",
            authorizer_type="AWS_IAM",
            role_arn=gateway_role.role_arn,
            description="Centralized MCP gateway for weather, network, and IAM tools",
        )

        # ─── Helper: Create a tool definition for CDK ────────────────

        def tool_def(name, description, properties, required):
            """Build a CfnGatewayTarget.ToolDefinitionProperty."""
            schema_props = {}
            for prop_name, prop_desc in properties.items():
                schema_props[prop_name] = bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                    type="string",
                    description=prop_desc,
                )
            return bedrockagentcore.CfnGatewayTarget.ToolDefinitionProperty(
                name=name,
                description=description,
                input_schema=bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                    type="object",
                    properties=schema_props,
                    required=required,
                ),
            )

        # ─── Gateway Targets ────────────────────────────────────────

        # Weather target (1 tool)
        weather_target = bedrockagentcore.CfnGatewayTarget(
            self,
            "WeatherTarget",
            name="weather-tools",
            gateway_identifier=gateway.ref,
            description="Weather forecast tools",
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=weather_lambda.function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=[
                                tool_def(
                                    "get_weather_forecast",
                                    "Get the weather forecast for a US city using the National Weather Service API.",
                                    {"city": "Name of a US city (e.g., 'New York', 'Chicago')"},
                                    ["city"],
                                ),
                            ]
                        ),
                    )
                )
            ),
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE",
                )
            ],
        )
        weather_target.add_dependency(gateway)

        # Network target (5 tools)
        network_target = bedrockagentcore.CfnGatewayTarget(
            self,
            "NetworkTarget",
            name="network-tools",
            gateway_identifier=gateway.ref,
            description="AWS network diagnostics tools",
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=network_lambda.function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=[
                                tool_def(
                                    "check_subnet_details",
                                    "Get details about an AWS subnet — CIDR, AZ, public/private, available IPs.",
                                    {"subnet_id": "AWS Subnet ID (e.g., 'subnet-0abc123')"},
                                    ["subnet_id"],
                                ),
                                tool_def(
                                    "check_vpc_routes",
                                    "Analyze route tables for a VPC or subnet. Shows IGW, NAT, peering, TGW routes.",
                                    {"vpc_id": "AWS VPC ID", "subnet_id": "Subnet ID (optional)"},
                                    ["vpc_id"],
                                ),
                                tool_def(
                                    "check_nacl_rules",
                                    "Check Network ACL inbound and outbound rules for a subnet.",
                                    {"subnet_id": "AWS Subnet ID"},
                                    ["subnet_id"],
                                ),
                                tool_def(
                                    "check_security_group",
                                    "Check security group inbound and outbound rules with port labels.",
                                    {"security_group_id": "AWS Security Group ID (e.g., 'sg-0abc123')"},
                                    ["security_group_id"],
                                ),
                                tool_def(
                                    "check_vpc_endpoints",
                                    "List VPC endpoints (S3, DynamoDB, interface endpoints) in a VPC.",
                                    {"vpc_id": "AWS VPC ID"},
                                    ["vpc_id"],
                                ),
                            ]
                        ),
                    )
                )
            ),
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE",
                )
            ],
        )
        network_target.add_dependency(gateway)

        # IAM target (3 tools)
        iam_target = bedrockagentcore.CfnGatewayTarget(
            self,
            "IAMTarget",
            name="iam-tools",
            gateway_identifier=gateway.ref,
            description="IAM access verification tools",
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=iam_lambda.function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=[
                                tool_def(
                                    "verify_iam_access",
                                    "Check if an IAM role or user can perform a specific action on a resource using the IAM Policy Simulator.",
                                    {
                                        "principal_arn": "ARN of the IAM role or user",
                                        "action": "AWS action (e.g., 's3:PutObject')",
                                        "resource_arn": "ARN of the resource",
                                    },
                                    ["principal_arn", "action", "resource_arn"],
                                ),
                                tool_def(
                                    "list_principal_policies",
                                    "List all policies attached to an IAM role or user (inline, managed, group).",
                                    {"principal_arn": "ARN of the IAM role or user"},
                                    ["principal_arn"],
                                ),
                                tool_def(
                                    "get_policy_document",
                                    "Get the full JSON policy document for a managed IAM policy.",
                                    {"policy_arn": "ARN of the IAM policy"},
                                    ["policy_arn"],
                                ),
                            ]
                        ),
                    )
                )
            ),
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE",
                )
            ],
        )
        iam_target.add_dependency(gateway)

        # ─── Outputs ────────────────────────────────────────────────

        CfnOutput(self, "GatewayId",
                   description="AgentCore Gateway ID",
                   value=gateway.ref)

        CfnOutput(self, "GatewayArn",
                   description="AgentCore Gateway ARN",
                   value=gateway.attr_gateway_arn)

        CfnOutput(self, "WeatherLambdaArn",
                   description="Weather tools Lambda ARN",
                   value=weather_lambda.function_arn)

        CfnOutput(self, "NetworkLambdaArn",
                   description="Network tools Lambda ARN",
                   value=network_lambda.function_arn)

        CfnOutput(self, "IAMLambdaArn",
                   description="IAM tools Lambda ARN",
                   value=iam_lambda.function_arn)
