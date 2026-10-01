"""อ่านค่าจาก .env — notebook และ service ใช้ไฟล์เดียวกัน เปลี่ยนเครื่องแค่แก้ .env"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
# override=True: ค่าใน .env ชนะตัวแปรที่ export ค้างไว้ใน shell (เช่น STUDENT=00 จาก .env ของคนอื่น)
load_dotenv(ROOT / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8000/v1")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "EMPTY")
    # off = ปิดโหมดคิดก่อนตอบของ Qwen3 บน vLLM (ตอบเร็วขึ้น) · ใช้กับ vLLM เท่านั้น API อื่นอาจไม่รู้จัก field นี้
    llm_thinking: str = os.getenv("LLM_THINKING", "on")
    embed_base_url: str = os.getenv("EMBED_BASE_URL", "http://127.0.0.1:8001/v1")
    embed_model: str = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
    embed_api_key: str = os.getenv("EMBED_API_KEY", "EMPTY")
    embed_dim: int = int(os.getenv("EMBED_DIM", "1024"))
    qdrant_url: str = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    qdrant_api_key: str | None = os.getenv("QDRANT_API_KEY") or None
    group: str = os.getenv("GROUP", "g00")
    data_dir: Path = ROOT / os.getenv("DATA_DIR", "data/raw")

    @property
    def llm_extra_body(self) -> dict | None:
        return {"chat_template_kwargs": {"enable_thinking": False}} if self.llm_thinking == "off" else None

    @property
    def collection(self) -> str:
        return os.getenv("COLLECTION") or f"cdd_docs_{self.group}"


settings = Settings()
