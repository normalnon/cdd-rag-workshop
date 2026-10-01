"""BM25 แบบ sparse vector สำหรับ Qdrant (ค้นแบบจับคำ — ส่วน "keyword" ของ hybrid search)

แนวคิด: 1 คำ = 1 มิติ · เวกเตอร์มีค่าเฉพาะคำที่ปรากฏ (ที่เหลือเป็น 0 → เก็บแค่ index + value = "sparse")
- ฝั่งเอกสาร: ค่า = ความถี่ของคำ (ปรับแบบ BM25 ให้คำที่ซ้ำมาก ๆ ไม่ได้คะแนนเพิ่มไม่สิ้นสุด)
- ฝั่งคำถาม: ค่า = 1 ต่อคำ
- IDF (คำหายากมีน้ำหนักมากกว่า) → Qdrant คำนวณเองจากทั้ง collection (SparseVectorParams(modifier=IDF))
"""
import zlib
from collections import Counter

from pythainlp import word_tokenize
from qdrant_client import models

K1, B = 1.2, 0.75
AVG_LEN = 256  # ความยาวเอกสารเฉลี่ยโดยประมาณ (หน่วย: คำ) — ใช้ค่าคงที่เพื่อให้ ingest ทีละไฟล์ได้

# ใส่ใน payload.pipeline → ถ้าเปลี่ยนวิธีตัดคำ ingest_file จะรู้ว่าต้อง index ใหม่
SPARSE_PIPELINE = "bm25-newmm-v2"


_PUNCT = "()[]{}<>.,:;!?\"'`-–—/\\|*•·›"


def tokenize(text: str) -> list[str]:
    """ตัดคำไทยด้วย pythainlp (newmm) · ตัวพิมพ์เล็ก · ตัดเครื่องหมายวรรคตอนออก"""
    words = (w.strip().strip(_PUNCT) for w in word_tokenize(text.lower(), engine="newmm", keep_whitespace=False))
    return [w for w in words if w]


def token_id(token: str) -> int:
    """คำ → เลขมิติ (hash คงที่ ไม่ต้องเก็บพจนานุกรม)"""
    return zlib.crc32(token.encode("utf-8")) & 0x7FFFFFFF


def sparse_doc(text: str) -> models.SparseVector:
    tokens = tokenize(text)
    tf = Counter(token_id(t) for t in tokens)
    norm = K1 * (1 - B + B * len(tokens) / AVG_LEN)
    return models.SparseVector(indices=list(tf), values=[f * (K1 + 1) / (f + norm) for f in tf.values()])


def sparse_query(text: str) -> models.SparseVector:
    ids = sorted({token_id(t) for t in tokenize(text)})
    return models.SparseVector(indices=ids, values=[1.0] * len(ids))
