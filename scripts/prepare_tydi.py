"""เตรียมชุดข้อมูล Mr. TyDi (ภาษาไทย) สำหรับ Lab 02 — ผู้สอนรันครั้งเดียวก่อนเรียน

    uv run python scripts/prepare_tydi.py            # corpus ย่อย 10,000 passages
    uv run python scripts/prepare_tydi.py --size 5000

corpus เต็มมี ~570,000 passages — ใหญ่เกินจะ embed ในห้องเรียน จึงตัดเป็นชุดย่อย:
  1) passage ที่เป็นคำตอบ (positives) ทุกอัน
  2) passage อื่นจาก "บทความเดียวกัน" กับคำตอบ  → ตัวหลอกที่ยาก (hard negatives)
  3) สุ่ม passage อื่นจนครบขนาด                  → ตัวหลอกทั่วไป
ผลลัพธ์: data/tydi/{queries.tsv, qrels.tsv, corpus.jsonl}
"""
import argparse
import gzip
import json
import random
import re
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "tydi"
ZERO_WIDTH = re.compile(r"[​‌‍﻿]")


def article_of(docid: str) -> str:
    return docid.split("#")[0]


def main(size: int, seed: int) -> None:
    random.seed(seed)
    topics = hf_hub_download("castorini/mr-tydi", "mrtydi-v1.1-thai/ir-format-data/topics.test.txt", repo_type="dataset")
    qrels = hf_hub_download("castorini/mr-tydi", "mrtydi-v1.1-thai/ir-format-data/qrels.test.txt", repo_type="dataset")
    corpus = hf_hub_download("castorini/mr-tydi-corpus", "mrtydi-v1.1-thai/corpus.jsonl.gz", repo_type="dataset")

    queries = {}
    for line in open(topics, encoding="utf-8"):
        qid, query = line.rstrip("\n").split("\t", 1)
        queries[qid] = ZERO_WIDTH.sub("", query).strip()   # คำถามบางข้อมีอักขระล่องหน (zero-width space)

    rel = []
    for line in open(qrels, encoding="utf-8"):
        qid, _, docid, label = line.split()
        if int(label) > 0 and qid in queries:
            rel.append((qid, docid))
    positives = {d for _, d in rel}
    pos_articles = {article_of(d) for d in positives}

    pos_docs, same_article, reservoir, seen = {}, [], [], 0
    reservoir_size = size * 2
    with gzip.open(corpus, "rt", encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            d = {"docid": doc["docid"], "title": doc["title"], "text": doc["text"]}
            if d["docid"] in positives:
                pos_docs[d["docid"]] = d
            elif article_of(d["docid"]) in pos_articles:
                same_article.append(d)
            else:
                seen += 1
                if len(reservoir) < reservoir_size:
                    reservoir.append(d)
                elif (j := random.randrange(seen)) < reservoir_size:
                    reservoir[j] = d

    selected = list(pos_docs.values())
    random.shuffle(same_article)
    selected += same_article[: max(0, size // 2 - len(selected))]
    random.shuffle(reservoir)
    selected += reservoir[: max(0, size - len(selected))]
    random.shuffle(selected)

    kept_q = {q for q, d in rel if d in pos_docs}
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "corpus.jsonl", "w", encoding="utf-8") as f:
        for d in selected:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    with open(OUT / "queries.tsv", "w", encoding="utf-8") as f:
        for qid in sorted(kept_q, key=int):
            f.write(f"{qid}\t{queries[qid]}\n")
    with open(OUT / "qrels.tsv", "w", encoding="utf-8") as f:
        for qid, docid in rel:
            if docid in pos_docs:
                f.write(f"{qid}\t{docid}\n")

    n_same = sum(1 for d in selected if d["docid"] not in pos_docs and article_of(d["docid"]) in pos_articles)
    print(f"queries   : {len(kept_q)}")
    print(f"qrels     : {sum(1 for q, d in rel if d in pos_docs)}")
    print(f"corpus    : {len(selected)} (คำตอบ {len(pos_docs)} · ตัวหลอกบทความเดียวกัน {n_same} · สุ่ม {len(selected) - len(pos_docs) - n_same})")
    print(f"บันทึกที่  : {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    main(args.size, args.seed)
