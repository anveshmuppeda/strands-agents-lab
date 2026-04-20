from strands.models.bedrock import BedrockModel


def load_model() -> BedrockModel:
    """Get Bedrock model client using IAM credentials."""
    return BedrockModel(
        model_id="us.meta.llama3-3-70b-instruct-v1:0",
        streaming=False,
    )
