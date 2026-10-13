# Contrib Retrieval Evaluation & Baseline Report

## 1. Overview
This document records the baseline retrieval performance of Contrib on closed GitHub issues and repository QA tasks.

- **Eval Script**: [`scripts/eval_retrieval.py`](file:///Users/skakibahammed/code_playground/Contrib/scripts/eval_retrieval.py)
- **Dataset**: [`data/eval_cases.json`](file:///Users/skakibahammed/code_playground/Contrib/data/eval_cases.json)
- **Repositories Tested**: `sherlock-project/sherlock` (Python CLI tool) and `htr-tech/zphisher` (Shell/PHP tool).
- **Target Metrics**: Hit@5 (expected file appears in top 5 retrieved files), Hit@10, MRR (Mean Reciprocal Rank), and Average Query Latency.

---

## 2. System Configuration
| Setting | Value |
| :--- | :--- |
| **Embedding Model** | `BAAI/bge-base-en-v1.5` (768-dim) |
| **Embedding Device** | `mps` / Apple Silicon auto-detect |
| **Retrieval Mode** | `hybrid` (Semantic Vector + BM25Okapi + Symbol AST + Role-based) |
| **Reranker** | Multi-factor lexical/structural reranker ([`backend/reranker.py`](file:///Users/skakibahammed/code_playground/Contrib/backend/reranker.py)) |
| **Chunking Configuration** | `chunk_size = 1024`, `chunk_overlap = 128` |
| **Vector Store** | ChromaDB (`backend/chroma_db`) |

---

## 3. Evaluation Summary (2 Consecutive Runs)

| Metric | Run 1 | Run 2 | Variance | Target Gate |
| :--- | :--- | :--- | :--- | :--- |
| **Retrieval Hit@5** | **83.3%** (15/18) | **83.3%** (15/18) | **0.0%** | $\ge 80\%$ |
| **Retrieval Hit@10** | **83.3%** (15/18) | **83.3%** (15/18) | **0.0%** | $\ge 90\%$ |
| **Retrieval MRR** | **0.750** | **0.750** | **0.000** | $\ge 0.70$ |
| **Retrieval Latency** | **143.9 ms** (cold) | **35.5 ms** (warm) | - | $< 200\text{ ms}$ |
| **QA Hit@5** | **90.0%** (9/10) | **90.0%** (9/10) | **0.0%** | $\ge 80\%$ |
| **QA Hit@10** | **90.0%** (9/10) | **90.0%** (9/10) | **0.0%** | $\ge 90\%$ |
| **QA MRR** | **0.633** | **0.633** | **0.000** | $\ge 0.70$ |

> [!NOTE]
> Run 1 includes cold-start JIT cache population; warm retrieval latency settles to **~35.5 ms** per query.

---

## 4. Key Case Verifications
- **Sherlock #3037** (`Break down sherlock() function`): Top retrieved file is `sherlock_project/sherlock.py` (Rank #1, MRR 1.0).
- **Sherlock #2853** (`UnicodeDecodeError`): Top retrieved file is `sherlock_project/sherlock.py` (Rank #1, MRR 1.0).
- **Sherlock #1055** (`Tox configuration`): Top retrieved file is `tox.ini` (Rank #1, MRR 1.0).
- **Zphisher #142** (`Facebook login credentials`): Top retrieved file is `.sites/facebook/login.php` (Rank #1, MRR 1.0).
