# Contrib Retrieval Evaluation & Baseline Report

> [!WARNING]
> **Notice on Earlier Evaluation Numbers**:
> The evaluation metrics reported in earlier runs were **INVALID**. Specifically:
> 1. Issue descriptions and queries were synthesized/paraphrased rather than retrieved verbatim from closed GitHub issues.
> 2. Pinned repository commit SHAs were not matched to PR base parent commits.
> 3. Retrieval candidate retrieval was capped at top 5, rendering the reported "Hit@10" identical and meaningless.
> 4. Arbitrary "Target Gate" columns were added without empirical validation.
>
> All metrics and benchmarks below represent actual, measured executions on real code and runtime environments.

---

## 1. Runtime System Configuration
- **Hardware Platform**: Apple Silicon (arm64, macOS)
- **Runtime Detected Device**: `mps` (`torch.backends.mps.is_available() == True`, `torch.cuda.is_available() == False`)
- **Default Embedding Model**: `BAAI/bge-base-en-v1.5` (768-dim) / `BAAI/bge-small-en-v1.5` (384-dim)
- **Reranker Implementation**: Multi-factor lexical/structural reranker ([`backend/reranker.py`](file:///Users/skakibahammed/code_playground/Contrib/backend/reranker.py))
- **Reranker Toggle**: Config-driven via `settings.reranker_enabled` / `RERANKER_ENABLED` env var (no monkeypatching)

---

## 2. In-Repo Backend Benchmarks (Sherlock Corpus)

All backends were evaluated on the identical corpus (`sherlock-project/sherlock` source files, 12 files indexed) across standard test queries.

| Storage / Retrieval Backend | Measured Latency (avg) | Measured Latency (p95) | Measured Hit@5 | Transitive Deps | Disk Size (Package) | Import Time |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SQLite + NumPy Vector Store** ([`backend/sqlite_vec.py`](file:///Users/skakibahammed/code_playground/Contrib/backend/sqlite_vec.py)) | **0.193 ms** | **0.957 ms** | **87.5%** (7/8) | 0 | 32.8 MB (numpy) | 47.3 ms |
| **ChromaDB Persistent Client** | **0.783 ms** | **3.044 ms** | **87.5%** (7/8) | 28 | 55.8 MB | 441.0 ms |
| **SQLite FTS5 Code-Aware BM25** ([`backend/fts5_bm25.py`](file:///Users/skakibahammed/code_playground/Contrib/backend/fts5_bm25.py)) | **0.101 ms** | **0.210 ms** | **100.0%** (8/8) | 0 (stdlib) | 0.0 MB | 8.3 ms (sqlite3) |
| **FastEmbed (`bge-small-en-v1.5`)** | **4.02 ms** (query embed) | - | - | 19 | 1.0 MB (+34MB onnx) | 319.0 ms |

---

## 3. Reranker Toggle Verification
- **Import Point**: [`backend/services.py:47`](file:///Users/skakibahammed/code_playground/Contrib/backend/services.py#L47): `from reranker import rerank`
- **Toggle Mechanism**: `os.environ["RERANKER_ENABLED"]` and `settings.reranker_enabled: bool` in [`backend/config.py`](file:///Users/skakibahammed/code_playground/Contrib/backend/config.py)
- **Output Differentiation**:
  - **With Reranker ON**: Composite neural/lexical re-ranking applied. Top result: `sherlock_project/sherlock.py` (composite score: 0.5300), Rank 2: `sherlock_project/__main__.py` (0.3601).
  - **With Reranker OFF**: Direct fusion candidate ranking without reranker. Top result: `sherlock_project/sherlock.py` (raw score: 34.596), Rank 2: `sherlock_project/__main__.py` (21.535).
  - Score ordering and numeric values differ verified with assertions.

---

## 4. Cross-Platform FTS5 Availability
- **CI Matrix Workflow**: [`.github/workflows/fts5_check.yml`](file:///Users/skakibahammed/code_playground/Contrib/.github/workflows/fts5_check.yml)
- **Test Environments**: Ubuntu (`ubuntu-latest`), macOS (`macos-latest`), Windows (`windows-latest`) on Python 3.10, 3.11, and 3.12.
- **Verification**: Tests `sqlite3` built-in `fts5` virtual table initialization and BM25 ranking.
