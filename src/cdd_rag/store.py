"""Qdrant: สร้าง collection, ingest เอกสาร, ค้นหา (schema v2: docs/index-schema.md)"""
import uuid
import warnings
from pathlib import Path

from qdrant_client import QdrantClient, models

from .config import settings
from .embed import embed, embed_one
from .ingest import chunk_pdf, list_pdfs
from .schema import DENSE, PIPELINE_VERSION, SPARSE, ChunkPayload, Hit, embedding_text
from .sparse import sparse_doc, sparse_query

# ส่ง API key ผ่าน http ปลอดภัยในกรณีของเรา: Qdrant เปิดเฉพาะ 127.0.0.1 และเข้าจากนอกเครื่องผ่าน SSH เท่านั้น
# (ถ้าเปิด Qdrant ให้ network อื่นเข้าถึงได้ ต้องใช้ https และลบบรรทัดนี้)
warnings.filterwarnings("ignore", message="Api key is used with an insecure connection")

# QDRANT_URL=:memory: → Qdrant ในหน่วยความจำ ใช้ซ้อม/ทดสอบได้โดยไม่ต้องรัน server
client = (
    QdrantClient(":memory:")
    if settings.qdrant_url == ":memory:"
    else QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
)

# field ที่ใช้กรอง → ต้องมี payload index
PAYLOAD_INDEXES = {
    "doc_id": models.PayloadSchemaType.KEYWORD,
    "file_name": models.PayloadSchemaType.KEYWORD,
    "doc_type": models.PayloadSchemaType.KEYWORD,
    "issued_date": models.PayloadSchemaType.DATETIME,
    "page": models.PayloadSchemaType.INTEGER,
    "chunk_index": models.PayloadSchemaType.INTEGER,
}


def ensure_collection(name: str | None = None, recreate: bool = False) -> str:
    name = name or settings.collection
    if recreate and client.collection_exists(name):
        client.delete_collection(name)
    if not client.collection_exists(name):
        client.create_collection(
            name,
            vectors_config={DENSE: models.VectorParams(size=settings.embed_dim, distance=models.Distance.COSINE)},
            # BM25 (จับคำ) สำหรับ hybrid search — ให้ Qdrant คำนวณ IDF เอง · เพิ่มทีหลังไม่ได้ ต้องประกาศตอนสร้าง
            sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
        for field, schema in PAYLOAD_INDEXES.items():
            client.create_payload_index(name, field_name=field, field_schema=schema)
    return name


def point_id(chunk_id: str) -> str:
    # id คงที่จาก chunk_id → ingest ซ้ำไฟล์เดิมจะทับของเก่า ไม่เกิด chunk ซ้ำ
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def _match(key: str, value) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchValue(value=value))


def upsert_chunks(chunks: list[ChunkPayload], name: str | None = None, batch_size: int = 64) -> int:
    name = ensure_collection(name)
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [embedding_text(c) for c in batch]  # "หัวข้อ + เนื้อหา"
        vectors = embed(texts)
        client.upsert(
            name,
            points=[
                models.PointStruct(
                    id=point_id(c["chunk_id"]),
                    vector={DENSE: v, SPARSE: sparse_doc(t)},  # ความหมาย + คำ
                    payload=dict(c),
                )
                for c, v, t in zip(batch, vectors, texts)
            ],
        )
    return len(chunks)


def ingest_file(path: Path, name: str | None = None, chunk_size: int = 600, overlap: int = 120) -> str:
    """ingest ซ้ำได้ปลอดภัย:
    - ไฟล์เดิม (doc_id เดิม) + pipeline เดิม → ข้าม ไม่ embed ซ้ำ
    - ไฟล์ชื่อเดิมแต่เนื้อหาเปลี่ยน / เปลี่ยน pipeline → ลบ chunk เก่าของไฟล์นั้นทั้งหมด แล้วใส่ใหม่"""
    name = ensure_collection(name)
    chunks = chunk_pdf(path, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return "empty"
    doc_id, file_name, pipe = chunks[0]["doc_id"], chunks[0]["file_name"], chunks[0]["pipeline"]

    existing, _ = client.scroll(name, scroll_filter=models.Filter(must=[_match("doc_id", doc_id)]), limit=1)
    if existing and existing[0].payload.get("pipeline") == pipe and client.count(
        name, count_filter=models.Filter(must=[_match("doc_id", doc_id)])
    ).count == len(chunks):
        return "skipped"

    client.delete(name, points_selector=models.FilterSelector(filter=models.Filter(must=[_match("file_name", file_name)])))
    upsert_chunks(chunks, name)
    return f"indexed {len(chunks)} chunks"


def ingest_dir(data_dir: Path | None = None, name: str | None = None, **kw) -> dict[str, str]:
    data_dir = Path(data_dir or settings.data_dir)
    return {p.name: ingest_file(p, name, **kw) for p in list_pdfs(data_dir)}


def _to_hit(p) -> Hit:
    pl = p.payload
    return Hit(
        chunk_id=pl["chunk_id"],
        text=pl["text"],
        score=p.score if getattr(p, "score", None) is not None else 0.0,
        file_name=pl["file_name"],
        file_path=pl["file_path"],
        page=pl["page"],
        page_end=pl.get("page_end", pl["page"]),
        section=pl.get("section", ""),
        doc_type=pl.get("doc_type", ""),
    )


def search(
    query: str,
    top_k: int = 5,
    file_name: str | None = None,
    doc_type: str | None = None,
    date_from: str | None = None,
    mode: str = "hybrid",
    name: str | None = None,
) -> list[Hit]:
    """Contract เดียวกันทุกที่: notebook เรียกตรง, agent ห่อเป็น tool, MCP เปิดเป็น tool ชื่อเดิม

    mode: "dense"  = ค้นตามความหมาย (bge-m3)
          "sparse" = ค้นแบบจับคำ (BM25)
          "hybrid" = รวมทั้งสองด้วย RRF (อันดับ)"""
    must = []
    if file_name:
        must.append(_match("file_name", file_name))
    if doc_type:
        must.append(_match("doc_type", doc_type))
    if date_from:
        must.append(models.FieldCondition(key="issued_date", range=models.DatetimeRange(gte=date_from)))
    flt = models.Filter(must=must) if must else None
    name = name or settings.collection

    if mode == "dense":
        res = client.query_points(name, query=embed_one(query), using=DENSE, query_filter=flt, limit=top_k, with_payload=True)
    elif mode == "sparse":
        res = client.query_points(name, query=sparse_query(query), using=SPARSE, query_filter=flt, limit=top_k, with_payload=True)
    elif mode == "hybrid":
        candidates = max(top_k * 4, 20)  # ดึงผู้สมัครจากแต่ละแบบมากกว่า top_k แล้วค่อยรวม
        res = client.query_points(
            name,
            prefetch=[
                models.Prefetch(query=embed_one(query), using=DENSE, filter=flt, limit=candidates),
                models.Prefetch(query=sparse_query(query), using=SPARSE, filter=flt, limit=candidates),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
    else:
        raise ValueError(f"mode ต้องเป็น dense / sparse / hybrid ไม่ใช่ {mode!r}")
    return [_to_hit(p) for p in res.points]


def expand(hit: Hit, window: int = 1, name: str | None = None) -> list[Hit]:
    """ดึง chunk ข้างเคียง (chunk_index ±window) ของเอกสารเดียวกัน — ใช้เติมบริบทก่อนส่งให้ LLM"""
    doc_id, idx = hit["chunk_id"].rsplit("_c", 1)
    idx = int(idx)
    pts, _ = client.scroll(
        name or settings.collection,
        scroll_filter=models.Filter(
            must=[
                _match("doc_id", doc_id),
                models.FieldCondition(key="chunk_index", range=models.Range(gte=idx - window, lte=idx + window)),
            ]
        ),
        limit=2 * window + 1,
        with_payload=True,
    )
    return sorted((_to_hit(p) for p in pts), key=lambda h: h["chunk_id"])


__all__ = ["client", "ensure_collection", "upsert_chunks", "ingest_file", "ingest_dir", "search", "expand", "PIPELINE_VERSION"]
