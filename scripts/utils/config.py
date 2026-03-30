#!/usr/bin/env python3
"""Shared constants for the Hanna Grants Agent scripts.

All embedding consumers MUST import EMBEDDING_DIMS from this module.
Do NOT hardcode dimension values elsewhere.
"""

# Bedrock Titan Text Embeddings V2 output dimensions.
# Used by: embeddings.py, init_db.py (schema DDL), ingest_documents.py, generate_hyde.py
# Changing this value requires: (1) update DB schema vector columns, (2) re-embed all documents
EMBEDDING_DIMS = 1024

# Bedrock model ID for embeddings
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"

# AWS region
AWS_REGION = "us-west-2"

# OpenAI model for HyDE generation
# Using OpenRouter model name format; change to "gpt-5.4-2026-03-05" for direct OpenAI
HYDE_MODEL = "openai/gpt-4.1"
