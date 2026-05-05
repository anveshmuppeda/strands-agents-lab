"""
IAM Tools Lambda — Gateway Target
Exposes: verify_iam_access, list_principal_policies, get_policy_document
"""

import json
import boto3


def handler(event, context):
    tool_name = context.client_context.custom.get("bedrockAgentCoreToolName", "")
    if "___" in tool_name:
        tool_name = tool_name.split("___", 1)[1]

    print(f"Tool: {tool_name}, Event: {json.dumps(event)}")

    tools = {
        "verify_iam_access": verify_iam_access,
        "list_principal_policies": list_principal_policies,
        "get_policy_document": get_policy_document,
    }

    if tool_name in tools:
        try:
            result = tools[tool_name](**event)
            return {"statusCode": 200, "body": result}
        except Exception as e:
            return {"statusCode": 500, "body": f"Error in {tool_name}: {str(e)}"}

    return {"statusCode": 400, "body": f"Unknown tool: {tool_name}"}


def verify_iam_access(principal_arn: str, action: str, resource_arn: str, **kwargs) -> str:
    iam = boto3.client("iam")
    if ":role/" in principal_arn:
        name = principal_arn.split(":role/")[-1]
    elif ":user/" in principal_arn:
        name = principal_arn.split(":user/")[-1]
    else:
        return f"Cannot parse ARN: {principal_arn}"
    results = [f"IAM Access Check", f"  Principal: {principal_arn}", f"  Action: {action}", f"  Resource: {resource_arn}", ""]
    try:
        sim = iam.simulate_principal_policy(PolicySourceArn=principal_arn, ActionNames=[action], ResourceArns=[resource_arn])
        for er in sim.get("EvaluationResults", []):
            d = er["EvalDecision"]
            if d == "allowed": results.append(f"ALLOWED — {name} CAN perform {action}")
            elif d == "explicitDeny": results.append(f"EXPLICITLY DENIED — a deny policy blocks {action}")
            else: results.append(f"IMPLICITLY DENIED — no policy grants {action}")
            for s in er.get("MatchedStatements", []):
                results.append(f"  Matched: {s.get('SourcePolicyId', 'unknown')}")
    except Exception as e:
        results.append(f"Error: {str(e)}")
    return "\n".join(results)


def list_principal_policies(principal_arn: str, **kwargs) -> str:
    iam = boto3.client("iam")
    results = [f"Policies for: {principal_arn}", ""]
    try:
        if ":role/" in principal_arn:
            n = principal_arn.split(":role/")[-1]
            for p in iam.list_role_policies(RoleName=n).get("PolicyNames", []):
                results.append(f"  Inline: {p}")
            for p in iam.list_attached_role_policies(RoleName=n).get("AttachedPolicies", []):
                results.append(f"  Managed: {p['PolicyName']} ({p['PolicyArn']})")
        elif ":user/" in principal_arn:
            n = principal_arn.split(":user/")[-1]
            for p in iam.list_user_policies(UserName=n).get("PolicyNames", []):
                results.append(f"  Inline: {p}")
            for p in iam.list_attached_user_policies(UserName=n).get("AttachedPolicies", []):
                results.append(f"  Managed: {p['PolicyName']} ({p['PolicyArn']})")
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
        ver = iam.get_policy_version(PolicyArn=policy_arn, VersionId=policy["Policy"]["DefaultVersionId"])
        return f"Policy: {policy['Policy']['PolicyName']}\n\n{json.dumps(ver['PolicyVersion']['Document'], indent=2)}"
    except Exception as e:
        return f"Error: {str(e)}"
