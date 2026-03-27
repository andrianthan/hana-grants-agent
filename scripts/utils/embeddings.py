#!/usr/bin/env python3
"""Bedrock Titan Text Embeddings V2."""
import json
import boto3
from utils.config import EMBEDDING_DIMS, EMBEDDING_MODEL_ID, AWS_REGION

BEDROCK = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def get_embedding(text: str) -> list[float]:
    """Generate embedding via Amazon Bedrock Titan Text Embeddings V2.

    Returns a vector of EMBEDDING_DIMS dimensions (currently 1024).
    """
    response = BEDROCK.invoke_model(
        modelId=EMBEDDING_MODEL_ID,
        body=json.dumps({"inputText": text, "dimensions": EMBEDDING_DIMS, "normalize": True}),
    )
    return json.loads(response["body"].read())["embedding"]
