#!/usr/bin/env python3
"""
scripts/eval_retrieval.py

Benchmark retrieval quality (Hit@5, Hit@10, MRR, latency) across evaluation datasets.
Records embedding model, reranker status, retrieval mode, and chunk configuration.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure backend can be imported
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

# Configure quiet logging for dependencies
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

from config import settings
import services
from services import run_retrieval_agent
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import VectorStoreIndex, StorageContext
from rank_bm25 import BM25Okapi


def load_cached_repo_bundle(collection_name: str, cache_dir_name: str) -> Dict[str, Any]:
    """Load cached repo sources and vector index into an engine bundle."""
    cache_path = REPO_ROOT / "backend" / ".cache" / cache_dir_name
    sources_file = cache_path / "sources.json"
    
    if not sources_file.exists():
        raise FileNotFoundError(f"Missing sources file at {sources_file}")

    with open(sources_file, "r", encoding="utf-8") as f:
        sources = json.load(f)

    chroma_path = str(REPO_ROOT / "backend" / "chroma_db")
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    vector_index = VectorStoreIndex.from_vector_store(
        vector_store, storage_context=storage_context
    )

    bm25_corpus, bm25_nodes = [], []
    for fp, src in sources.items():
        tokens = re.findall(r"[a-zA-Z_]\w*", src)
        bm25_corpus.append(tokens)
        bm25_nodes.append({"file_path": fp, "text": src[:4000]})

    bm25 = BM25Okapi(bm25_corpus) if bm25_corpus else None

    return {
        "vector_index": vector_index,
        "bm25": bm25,
        "bm25_nodes": bm25_nodes,
        "sources": sources,
    }


def evaluate_dataset(
    cases: List[Dict[str, Any]],
    bundles: Dict[str, Dict[str, Any]],
    reranker_enabled: bool = True,
    mode: str = "hybrid",
) -> Dict[str, Any]:
    """Run retrieval on cases and compute Hit@5, Hit@10, MRR, and latency."""
    hits_5 = 0
    hits_10 = 0
    mrr_total = 0.0
    latencies = []
    per_case_results = []

    # If reranker disabled, monkeypatch/divert reranker
    orig_rerank = None
    if not reranker_enabled:
        import reranker
        orig_rerank = reranker.rerank
        # simple pass-through rerank mock
        def no_rerank(candidates, **kwargs):
            sorted_cands = sorted(candidates.items(), key=lambda x: x[1][0], reverse=True)
            return {
                "results": [
                    {
                        "file_path": fp,
                        "rerank_score": score,
                        "signals": {},
                        "reasons": [],
                        "retrieval_method": method,
                        "penalty_applied": False,
                    }
                    for fp, (score, method) in sorted_cands[:kwargs.get("top_k", 6)]
                ],
                "top_tier": "MEDIUM",
                "anchor_file": None,
                "low_confidence": False,
                "confidence_score": 0.5,
                "explanation": "Reranker disabled",
            }
        reranker.rerank = no_rerank

    try:
        for case in cases:
            repo = case["repo"]
            bundle = bundles.get(repo)
            if not bundle:
                continue

            # Query text
            if "query" in case:
                query_text = case["query"]
            else:
                title = case.get("title", "")
                body = case.get("body", "")
                query_text = f"{title}\n{body}".strip()

            expected_files = set(case.get("expected_files", []))

            t0 = time.perf_counter()
            retrieval_result = run_retrieval_agent(bundle, query_text)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed_ms)

            retrieved_files = [
                f.get("path")
                for f in retrieval_result.get("relevant_files", [])
                if f.get("path")
            ]

            # Check hit@5 and hit@10
            top5 = set(retrieved_files[:5])
            top10 = set(retrieved_files[:10])

            hit5 = bool(expected_files & top5)
            hit10 = bool(expected_files & top10)

            if hit5:
                hits_5 += 1
            if hit10:
                hits_10 += 1

            # Reciprocal rank (first matching file position, 1-indexed)
            rr = 0.0
            for rank, r_file in enumerate(retrieved_files, start=1):
                if r_file in expected_files:
                    rr = 1.0 / rank
                    break
            mrr_total += rr

            per_case_results.append({
                "id": case["id"],
                "query": query_text[:60] + "...",
                "expected": list(expected_files),
                "top3_retrieved": retrieved_files[:3],
                "hit5": hit5,
                "hit10": hit10,
                "reciprocal_rank": round(rr, 3),
                "latency_ms": round(elapsed_ms, 1),
            })

    finally:
        if orig_rerank:
            import reranker
            reranker.rerank = orig_rerank

    total = len(cases)
    return {
        "total_cases": total,
        "hit_at_5": hits_5 / total if total else 0.0,
        "hit_at_10": hits_10 / total if total else 0.0,
        "mrr": mrr_total / total if total else 0.0,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
        "p95_latency_ms": sorted(latencies)[int(0.95 * len(latencies))] if latencies else 0.0,
        "cases": per_case_results,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate Contrib Retrieval Pipeline")
    parser.add_argument("--cases", default=str(REPO_ROOT / "data" / "eval_cases.json"))
    parser.add_argument("--reranker", action="store_true", default=True, help="Enable reranker")
    parser.add_argument("--no-reranker", action="store_false", dest="reranker")
    parser.add_argument("--runs", type=int, default=2, help="Number of evaluation runs to test variance")
    args = parser.parse_args()

    with open(args.cases, "r", encoding="utf-8") as f:
        data = json.load(f)

    retrieval_cases = data.get("retrieval", [])
    qa_cases = data.get("qa", [])

    print("=" * 70)
    print("CONTRIB RETRIEVAL EVALUATION")
    print("=" * 70)

    # Configuration metadata
    embed_model_name = getattr(services.Settings.embed_model, "model_name", settings.embed_model)
    device = getattr(services.Settings.embed_model, "device", "unknown")
    print(f"Embedding Model:   {embed_model_name} (device={device})")
    print(f"Reranker:          {'Enabled' if args.reranker else 'Disabled'}")
    print(f"Chunk Config:      chunk_size={settings.chunk_size}, chunk_overlap={settings.chunk_overlap}")
    print(f"Chroma Directory:  {REPO_ROOT / 'backend' / 'chroma_db'}")
    print(f"Retrieval Cases:   {len(retrieval_cases)}")
    print(f"QA Cases:          {len(qa_cases)}")
    print("=" * 70)

    print("\nLoading repository index bundles...")
    bundles = {
        "sherlock-project/sherlock": load_cached_repo_bundle("idx_4686cca7a29cf9ca", "idx_4686cca7a29cf9ca"),
        "htr-tech/zphisher": load_cached_repo_bundle("idx_6728de19778ed9be", "idx_6728de19778ed9be"),
    }
    print("Repository bundles loaded successfully.\n")

    run_results = []
    for r in range(1, args.runs + 1):
        print(f"--- RUN {r}/{args.runs} ---")
        ret_metrics = evaluate_dataset(retrieval_cases, bundles, reranker_enabled=args.reranker)
        qa_metrics = evaluate_dataset(qa_cases, bundles, reranker_enabled=args.reranker)
        run_results.append({"run": r, "retrieval": ret_metrics, "qa": qa_metrics})
        
        print(f"Retrieval Hit@5:  {ret_metrics['hit_at_5'] * 100:.1f}% ({int(ret_metrics['hit_at_5'] * len(retrieval_cases))}/{len(retrieval_cases)})")
        print(f"Retrieval Hit@10: {ret_metrics['hit_at_10'] * 100:.1f}% ({int(ret_metrics['hit_at_10'] * len(retrieval_cases))}/{len(retrieval_cases)})")
        print(f"Retrieval MRR:    {ret_metrics['mrr']:.3f}")
        print(f"Retrieval Latency:{ret_metrics['avg_latency_ms']:.1f} ms")
        print(f"QA Hit@5:         {qa_metrics['hit_at_5'] * 100:.1f}% ({int(qa_metrics['hit_at_5'] * len(qa_cases))}/{len(qa_cases)})")
        print(f"QA Hit@10:        {qa_metrics['hit_at_10'] * 100:.1f}% ({int(qa_metrics['hit_at_10'] * len(qa_cases))}/{len(qa_cases)})")
        print(f"QA MRR:           {qa_metrics['mrr']:.3f}\n")

    # Print summary table
    print("=" * 70)
    print("EVALUATION SUMMARY TABLE")
    print("=" * 70)
    print("| Metric | Run 1 | Run 2 | Variance | Target |")
    print("| :--- | :--- | :--- | :--- | :--- |")
    r1_ret = run_results[0]["retrieval"]
    r2_ret = run_results[1]["retrieval"] if len(run_results) > 1 else r1_ret
    r1_qa = run_results[0]["qa"]
    r2_qa = run_results[1]["qa"] if len(run_results) > 1 else r1_qa

    print(f"| Retrieval Hit@5 | {r1_ret['hit_at_5']*100:.1f}% | {r2_ret['hit_at_5']*100:.1f}% | {abs(r1_ret['hit_at_5'] - r2_ret['hit_at_5'])*100:.1f}% | >= 80% |")
    print(f"| Retrieval Hit@10 | {r1_ret['hit_at_10']*100:.1f}% | {r2_ret['hit_at_10']*100:.1f}% | {abs(r1_ret['hit_at_10'] - r2_ret['hit_at_10'])*100:.1f}% | >= 90% |")
    print(f"| Retrieval MRR | {r1_ret['mrr']:.3f} | {r2_ret['mrr']:.3f} | {abs(r1_ret['mrr'] - r2_ret['mrr']):.3f} | >= 0.70 |")
    print(f"| Retrieval Latency | {r1_ret['avg_latency_ms']:.1f}ms | {r2_ret['avg_latency_ms']:.1f}ms | {abs(r1_ret['avg_latency_ms'] - r2_ret['avg_latency_ms']):.1f}ms | < 200ms |")
    print(f"| QA Hit@5 | {r1_qa['hit_at_5']*100:.1f}% | {r2_qa['hit_at_5']*100:.1f}% | {abs(r1_qa['hit_at_5'] - r2_qa['hit_at_5'])*100:.1f}% | >= 80% |")
    print(f"| QA Hit@10 | {r1_qa['hit_at_10']*100:.1f}% | {r2_qa['hit_at_10']*100:.1f}% | {abs(r1_qa['hit_at_10'] - r2_qa['hit_at_10'])*100:.1f}% | >= 90% |")
    print(f"| QA MRR | {r1_qa['mrr']:.3f} | {r2_qa['mrr']:.3f} | {abs(r1_qa['mrr'] - r2_qa['mrr']):.3f} | >= 0.70 |")
    print("=" * 70)


if __name__ == "__main__":
    main()
