"""Embedding server สำหรับเครื่อง dev ที่ไม่มี GPU (Mac) — API หน้าตาเหมือน vLLM /v1/embeddings
บน server จริงให้ใช้: vllm serve BAAI/bge-m3 --port 8001 แทน แล้วโค้ดอื่นไม่ต้องแก้

    uv run --with sentence-transformers --with fastapi --with uvicorn scripts/local_embed_server.py
"""
import os
import threading

import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
# Mac: ใช้ GPU (mps) + fp16 → ใช้ RAM ราวครึ่งหนึ่งของ fp32
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
model = SentenceTransformer(
    MODEL, device=DEVICE, model_kwargs={"torch_dtype": torch.float16 if DEVICE == "mps" else torch.float32}
)
model.max_seq_length = int(os.getenv("EMBED_MAX_LEN", "1024"))
print(f"loaded {MODEL} on {DEVICE}", flush=True)
app = FastAPI()
# MPS ไม่ thread-safe: FastAPI รัน request พร้อมกันหลาย thread → encode ทีละคำขอ (vLLM บน server ไม่มีปัญหานี้)
_lock = threading.Lock()


class EmbedRequest(BaseModel):
    model: str = MODEL
    input: str | list[str]


@app.post("/v1/embeddings")
def embeddings(req: EmbedRequest):
    texts = [req.input] if isinstance(req.input, str) else req.input
    with _lock:
        vecs = model.encode(texts, normalize_embeddings=True, batch_size=8)
    return {
        "object": "list",
        "model": req.model,
        "data": [{"object": "embedding", "index": i, "embedding": v.tolist()} for i, v in enumerate(vecs)],
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }


@app.get("/v1/models")
def models():
    return {"object": "list", "data": [{"id": MODEL, "object": "model"}]}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8001")))
