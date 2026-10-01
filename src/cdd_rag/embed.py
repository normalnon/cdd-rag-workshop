"""เรียก embedding bge-m3 ผ่าน OpenAI-compatible API (vLLM ตัวกลางบน server)"""
from openai import OpenAI

from .config import settings

_client = OpenAI(base_url=settings.embed_base_url, api_key=settings.embed_api_key)


def embed(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        resp = _client.embeddings.create(model=settings.embed_model, input=texts[i : i + batch_size])
        vectors.extend(d.embedding for d in resp.data)
    return vectors


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
