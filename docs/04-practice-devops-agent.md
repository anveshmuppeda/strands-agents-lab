# Practice Project: DevOps Assistant Agent

A multi-tool agent that helps with AWS infrastructure tasks. This project exercises
multiple Strands patterns: custom tools, pre-built tools, error handling, system prompts,
and multi-tool chaining.

## What It Does

- Check EC2 instance status across regions
- List S3 buckets in your account
- Check CloudWatch alarms for active issues
- Get AWS account identity info
- Generate formatted infrastructure reports

## How to Run

```bash
cd strands
pip install -r requirements.txt
aws configure  # if not already done
python devops_agent.py
```

## Source Code

See: [`strands/devops_agent.py`](../strands/devops_agent.py)

## Try These Queries

```
You: What AWS account am I using?
You: List all my EC2 instances and S3 buckets
You: Check if there are any active alarms
You: Generate a full infrastructure report for my account
```

The agent will chain multiple tool calls together to build comprehensive answers.

## Patterns Used

| Pattern | Where It's Used |
|---------|----------------|
| Custom `@tool` | All 5 infrastructure tools |
| Pre-built tools | `current_time`, `shell` from strands-agents-tools |
| Error handling | Every tool has try/except with meaningful error messages |
| System prompt | Lists all tools and defines behavior guidelines |
| Multi-tool chaining | Agent calls multiple tools per query and combines results |
| Type hints + docstrings | Every tool has proper signatures for the model to read |

## Architecture

```
User Query: "Generate a full infrastructure report"
    │
    ▼
┌─────────────────────────────────────────┐
│           DevOps Agent                   │
│                                          │
│  1. Calls get_aws_account_info()        │
│  2. Calls list_ec2_instances()          │
│  3. Calls list_s3_buckets()             │
│  4. Calls check_cloudwatch_alarms()     │
│  5. Calls generate_report() with all    │
│     findings combined                    │
│  6. Returns formatted report to user     │
└─────────────────────────────────────────┘
    │           │           │           │
    ▼           ▼           ▼           ▼
  AWS STS    AWS EC2     AWS S3    CloudWatch
```

## Extending This Agent

Ideas for adding more tools:
- `check_lambda_functions()` — list Lambda functions and their last invocation
- `estimate_monthly_cost()` — use AWS Cost Explorer to estimate costs
- `check_security_groups()` — audit security groups for open ports
- `check_iam_users()` — list IAM users and their last activity
