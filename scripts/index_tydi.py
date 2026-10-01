"""สร้าง collection ของ Mr. TyDi (dense bge-m3) สำหรับ Lab 02 ใน Qdrant ของเรา

ผู้สอน (ครั้งเดียว ก่อนวางไฟล์ให้ผู้เรียน):
    uv run python scripts/prepare_tydi.py            # ถ้ายังไม่มี data/tydi/
    uv run python scripts/index_tydi.py --export     # embed (GPU ~1–2 นาที) แล้วเก็บ snapshot → data/tydi/

ผู้เรียน (แต่ละคนมี Qdrant ของตัวเอง):
    uv run python scripts/index_tydi.py              # มี snapshot → upload เข้า Qdrant ของเรา ไม่ต้อง embed ใหม่

รันซ้ำได้: ข้าม passage ที่ index แล้ว (ต่อจากที่ค้างได้ถ้าถูกขัดจังหวะ)
"""
import json
import sys
import uuid
from pathlib import Path

import httpx
from qdrant_client import models
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cdd_rag.config import ROOT, settings  # noqa: E402
from cdd_rag.embed import embed  # noqa: E402
from cdd_rag.store import client  # noqa: E402

TYDI_COLLECTION = "tydi_th_bge_m3"
SNAPSHOT = ROOT / "data/tydi" / f"{TYDI_COLLECTION}.snapshot"
HEADERS = {"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else {}


def passage_text(d: dict) -> str:
    return f"{d['title']}\n{d['text']}"


def restore_snapshot() -> None:
    """upload snapshot ที่ผู้สอนเตรียมไว้ → Qdrant สร้าง collection ให้เลย (ไม่ใช้ GPU)"""
    with open(SNAPSHOT, "rb") as f:
        r = httpx.post(
            f"{settings.qdrant_url}/collections/{TYDI_COLLECTION}/snapshots/upload",
            params={"priority": "snapshot"},
            files={"snapshot": (SNAPSHOT.name, f)},
            headers=HEADERS,
            timeout=300,
        )
    r.raise_for_status()
    client.delete_snapshot(TYDI_COLLECTION, SNAPSHOT.name)   # ไฟล์ที่ upload ค้างใน storage ไม่ต้องเก็บ


def export_snapshot() -> None:
    snap = client.create_snapshot(TYDI_COLLECTION, wait=True)
    url = f"{settings.qdrant_url}/collections/{TYDI_COLLECTION}/snapshots/{snap.name}"
    with httpx.stream("GET", url, headers=HEADERS, timeout=300) as r, open(SNAPSHOT, "wb") as f:
        r.raise_for_status()
        for chunk in r.iter_bytes():
            f.write(chunk)
    client.delete_snapshot(TYDI_COLLECTION, snap.name)
    print(f"เก็บ snapshot แล้ว → {SNAPSHOT.relative_to(ROOT)} ({SNAPSHOT.stat().st_size / 1e6:.0f} MB)")


def main(batch_size: int = 64) -> None:
    if not client.collection_exists(TYDI_COLLECTION) and SNAPSHOT.exists():
        restore_snapshot()
        print(f"{TYDI_COLLECTION}: กู้จาก snapshot แล้ว", client.count(TYDI_COLLECTION).count, "points")
        return
    docs = [json.loads(l) for l in open(ROOT / "data/tydi/corpus.jsonl", encoding="utf-8")]
    if not client.collection_exists(TYDI_COLLECTION):
        client.create_collection(
            TYDI_COLLECTION,
            vectors_config={"dense": models.VectorParams(size=settings.embed_dim, distance=models.Distance.COSINE)},
        )
    done = set()
    offset = None
    while True:
        pts, offset = client.scroll(TYDI_COLLECTION, limit=1000, offset=offset, with_payload=["docid"])
        done.update(p.payload["docid"] for p in pts)
        if offset is None:
            break
    todo = [d for d in docs if d["docid"] not in done]
    print(f"{TYDI_COLLECTION}: มีแล้ว {len(done)} · ต้อง index {len(todo)}")
    for i in tqdm(range(0, len(todo), batch_size), unit="batch"):
        batch = todo[i : i + batch_size]
        vecs = embed([passage_text(d) for d in batch])
        client.upsert(
            TYDI_COLLECTION,
            points=[
                models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, d["docid"])), vector={"dense": v}, payload=d)
                for d, v in zip(batch, vecs)
            ],
        )
    print("รวม", client.count(TYDI_COLLECTION).count, "points")


if __name__ == "__main__":
    main()
    if "--export" in sys.argv:
        export_snapshot()
