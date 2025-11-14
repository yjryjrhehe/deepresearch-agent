import os
from typing import Optional
from openai import OpenAI
from langchain_openai import ChatOpenAI

from ...core.config import settings

preprocessing_chunk_client = ChatOpenAI(
    base_url=settings.PREPROCESSING_LLM_BASE_URL,
    api_key="xxx",
    model=settings.PREPROCESSING_LLM_MODEL,
    temperature=0
)


