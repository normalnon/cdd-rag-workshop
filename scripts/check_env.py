"""รันก่อนเริ่ม lab: uv run python scripts/check_env.py — ต้องเขียวทั้ง 3 บรรทัด"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openai import OpenAI  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402

from cdd_rag.config import ROOT, settings  # noqa: E402

# Qdrant เปิดเฉพาะ 127.0.0.1 ของ server → ส่ง key ผ่าน http ได้ ไม่ต้องเตือน
warnings.filterwarnings("ignore", message="Api key is used with an insecure connection")

OK, FAIL, SKIP = "\033[32m✔\033[0m", "\033[31m✘\033[0m", "\033[33m–\033[0m"
failed = False

env_file = ROOT / ".env"
if not env_file.exists():
    sys.exit(f"{FAIL} ยังไม่มี .env — cp .env.example .env แล้วแก้ XX เป็นเลขประจำตัว")
left = [line.split("=")[0] for line in env_file.read_text(encoding="utf-8").splitlines() if "XX" in line and not line.startswith("#")]
if left:
    sys.exit(f"{FAIL} .env ยังมี XX ที่ยังไม่ได้แก้: {', '.join(left)}")


def check(label, fn):
    global failed
    try:
        print(f"{OK} {label}: {fn()}")
    except Exception as e:  # noqa: BLE001
        failed = True
        print(f"{FAIL} {label}: {type(e).__name__}: {e}")


def _embed():
    c = OpenAI(base_url=settings.embed_base_url, api_key=settings.embed_api_key)
    v = c.embeddings.create(model=settings.embed_model, input=["ทดสอบ"]).data[0].embedding
    assert len(v) == settings.embed_dim, f"dim={len(v)} แต่ EMBED_DIM={settings.embed_dim}"
    return f"{settings.embed_model} dim={len(v)}"


def _llm():
    if not settings.llm_model:
        raise ValueError("ยังไม่ได้ตั้ง LLM_MODEL ใน .env")
    c = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
    r = c.chat.completions.create(
        model=settings.llm_model, messages=[{"role": "user", "content": "ตอบคำเดียว: สวัสดี"}], max_tokens=10,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},  # ทดสอบแค่ต่อได้ไหม: Qwen3 ถ้าคิดก่อน 10 token จะหมดตอนคิด
    )
    return f"{settings.llm_model} → {r.choices[0].message.content!r}"


def _qdrant():
    q = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    names = [c.name for c in q.get_collections().collections]
    return f"{settings.qdrant_url} collection ของเรา={settings.collection} ({'มีแล้ว' if settings.collection in names else 'ยังไม่มี'})"


check("Embedding", _embed)
if settings.llm_model:
    check("LLM", _llm)
else:
    print(f"{SKIP} LLM: ข้าม (ยังไม่ได้ตั้ง LLM_MODEL — ช่วง retrieval ยังไม่ต้องใช้)")
check("Qdrant", _qdrant)
sys.exit(1 if failed else 0)
