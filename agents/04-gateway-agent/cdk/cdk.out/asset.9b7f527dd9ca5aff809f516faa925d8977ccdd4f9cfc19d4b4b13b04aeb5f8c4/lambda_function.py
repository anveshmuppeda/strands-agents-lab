"""
IAM Tools Lambda — Gateway Target

Exposes: verify_iam_access, list_principal_policies, get_policy_document
"""

import json
import boto3


def handler(event, context):
    """Lambda handler — Gateway routes MCP tool calls here."""
    tool_name = ""
    if hasattr(context, "client_context") and context.client_context:
        tool_name = getattr(context.client_context, "custom", {}).get(
            "bedrockagentcoreToolName", ""
        )

    body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event.get("body", {})

    tools = {
        "verify_iam_access": verify_iam_access,
        "list_principal_policies": list_principal_policies,
        "get_policy_document": get_policy_document,
    }

    if tool_name in tools:
        try:
            result = tools[tool_name](**body)
            return {"statusCode": 200, "body": json.dumps({"result": result})}
        except Exception as e:
            return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    return {"statusCode": 400, "body": json.dumps({"error": f"Unknown tool: {tool_name}"})}


# --- Tool Implementations ---

def verify_iam_access(principal_arn: str, action: str, resource_arn: str, **kwargs) -> str:
    iam = boto3.client("iam")

    if ":role/" in principal_arn:
        principal_name = principal_arn.split(":role/")[-1]
    elif ":user/" in principal_arn:
        principal_name = principal_arn.split(":user/")[-1]
    else:
        return f"Cannot parse ARN: {principal_arn}"

    results = [f"IAM Access Check", f"  Principal: {principal_arn}", f"  Action: {action}", f"  Resource: {resource_arn}", ""]

    try:
        sim = iam.simulate_principal_policy(
            PolicySourceArn=principal_arn,
            ActionNames=[action],
            ResourceArns=[resource_arn],
        )
        for er in sim.get("EvaluationResults", []):
            decision = er["EvalDecision"]
            if decision == "allowed":
                results.append(f"ALLOWED — {principal_name} CAN perform {action}")
            elif decision == "explicitDeny":
                results.append(f"EXPLICITLY DENIED — a deny policy blocks {action}")
            else:
                results.append(f"IMPLICITLY DENIED — no policy grants {action}")

            for stmt in er.get("MatchedStatements", []):
                results.append(f"  Matched: {stmt.get('SourcePolicyId', 'unknown')}")

    except iam.exceptions.NoSuchEntityException:
        results.append(f"Principal not found: {principal_arn}")
    except Exception as e:
        results.append(f"Error: {str(e)}")

    return "\n".join(results)


def list_principal_policies(principal_arn: str, **kwargs) -> str:
    iam = boto3.client("iam")
    results = [f"Policies for: {principal_arn}", ""]

    try:
        if ":role/" in principal_arn:
            name = principal_arn.split(":role/")[-1]
            inline = iam.list_role_policies(RoleName=name)
            for p in inline.get("PolicyNames", []):
                results.append(f"  Inline: {p}")
            managed = iam.list_attached_role_policies(RoleName=name)
            for p in managed.get("AttachedPolicies", []):
                results.append(f"  Managed: {p['PolicyName']} ({p['PolicyArn']})")

        elif ":user/" in principal_arn:
            name = principal_arn.split(":user/")[-1]
            inline = iam.list_user_policies(UserName=name)
            for p in inline.get("PolicyNames", []):
                results.append(f"  Inline: {p}")
            managed = iam.list_attached_user_policies(UserName=name)
            for p in managed.get("AttachedPolicies", []):
                results.append(f"  Managed: {p['PolicyName']} ({p['PolicyArn']})")
            groups = iam.list_groups_for_user(UserName=name)
            for g in groups.get("Groups", []):
                results.append(f"  Group: {g['GroupName']}")
        else:
            return f"Cannot parse ARN: {principal_arn}"

    except Exception as e:
        results.append(f"Error: {str(e)}")

    if len(results) == 2:
        results.append("  (no policies attached)")

    return "\n".join(results)


def get_policy_document(policy_arn: str, **kwargs) -> str:
    iam = boto3.client("iam")
    try:
        policy = iam.get_policy(PolicyArn=policy_arn)
        version_id = policy["Policy"]["DefaultVersionId"]
        version = iam.get_policy_version(PolicyArn=policy_arn, VersionId=version_id)
        doc = version["PolicyVersion"]["Document"]
        return f"Policy: {policy['Policy']['PolicyName']}\n\n{json.dumps(doc, indent=2)}"
    except Exception as e:
        return f"Error: {str(e)}"
