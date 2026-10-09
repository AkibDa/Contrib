import os
import re

with open("backend/services.py", "r") as f:
    services_code = f.read()

# We will just write a new function at the end of services.py

new_func = """
import asyncio

async def build_query_engine_progressive(content: str, repo_name: str, commit_sha: str = ""):
    embed_model_name = getattr(Settings.embed_model, "model_name", "default")
    config_str = f"{repo_name}_{commit_sha}_{embed_model_name}_{settings.chunk_size}_{settings.chunk_overlap}"
    repo_hash = hashlib.md5(config_str.encode()).hexdigest()[:16]
    safe_name = f"idx_{repo_hash}"

    collection = _chroma_client.get_or_create_collection(safe_name)
    metadata = collection.metadata or {}
    is_complete = metadata.get("status") == "complete"
    
    if not is_complete and collection.count() > 0:
        _chroma_client.delete_collection(safe_name)
        collection = _chroma_client.create_collection(safe_name)
        
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    t0 = time.perf_counter()
    files = await asyncio.to_thread(_split_repo_content, content)
    t_filter = time.perf_counter() - t0
    
    sources = {fp: src for fp, src in files}
    file_priorities = {fp: _file_priority(fp) for fp, _ in files}

    # BM25 build
    bm25_corpus, bm25_nodes = [], []
    for fp, src in files:
        tokens = re.findall(r"[a-zA-Z_]\\w*", src)
        bm25_corpus.append(tokens)
        bm25_nodes.append({"file_path": fp, "text": src[:4_000]})

    bm25 = BM25Okapi(bm25_corpus) if bm25_corpus else None
    
    bundle = {
        "vector_index": None,
        "bm25": bm25,
        "bm25_nodes": bm25_nodes,
        "sources": sources,
        "file_priorities": file_priorities,
        "is_embedding": not is_complete
    }
    
    yield {"status": "bm25_ready", "bundle": bundle}

    if is_complete and collection.count() > 0:
        logger.info(f"Reusing Chroma collection '{safe_name}'...")
        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        bundle["vector_index"] = index
        bundle["is_embedding"] = False
        yield {"status": "ready", "bundle": bundle}
        return

    # Background embedding
    logger.info(f"Building '{safe_name}'...")
    
    def _prepare_nodes():
        docs = []
        for fp, src in files:
            meta = _rich_metadata(fp, src)
            docs.append(Document(
                text=src,
                metadata=meta,
                excluded_embed_metadata_keys=["functions", "classes", "imports", "priority"],
                excluded_llm_metadata_keys=["functions", "classes", "imports", "priority"],
            ))
        small_docs = [d for d in docs if len(d.text) <= _LARGE_FILE_THRESHOLD]
        large_docs = [d for d in docs if len(d.text) > _LARGE_FILE_THRESHOLD]
        all_nodes = []
        if small_docs:
            small_splitter = SentenceSplitter(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
            all_nodes.extend(small_splitter.get_nodes_from_documents(small_docs))
        if large_docs:
            large_splitter = SentenceSplitter(chunk_size=settings.chunk_size // 2, chunk_overlap=settings.chunk_overlap // 2)
            all_nodes.extend(large_splitter.get_nodes_from_documents(large_docs))
        return all_nodes
        
    all_nodes = await asyncio.to_thread(_prepare_nodes)
    
    total = len(all_nodes)
    done = 0
    
    # We will embed in batches and yield progress
    batch_size = 32
    
    def _embed_batch(batch):
        # We can use index.insert_nodes which does embedding and writing
        # Wait, if we create an empty VectorStoreIndex:
        idx = VectorStoreIndex([], storage_context=storage_context)
        idx.insert_nodes(batch)
        return idx
        
    index = VectorStoreIndex([], storage_context=storage_context)
    
    start_time = time.time()
    for i in range(0, total, batch_size):
        batch = all_nodes[i:i+batch_size]
        await asyncio.to_thread(index.insert_nodes, batch)
        done += len(batch)
        percent = int(done * 100 / total)
        elapsed = time.time() - start_time
        eta = int((elapsed / done) * (total - done)) if done > 0 else 0
        yield {"status": "embedding_progress", "done": done, "total": total, "percent": percent, "eta_seconds": eta}
        
    collection.modify(metadata={**(collection.metadata or {}), "status": "complete"})
    bundle["vector_index"] = index
    bundle["is_embedding"] = False
    yield {"status": "ready", "bundle": bundle}

"""

with open("backend/services.py", "a") as f:
    f.write(new_func)
