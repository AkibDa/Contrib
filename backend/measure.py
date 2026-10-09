import asyncio
import time
import os
import sys

# Load backend imports
sys.path.append(os.path.abspath("."))
from api import ingest_async
from services import build_query_engine_async
from config import settings

async def main():
    repo_url = "https://github.com/htr-tech/zphisher"
    import subprocess, tempfile
    
    for batch_size in [16, 32, 64]:
        print(f"--- BATCH SIZE {batch_size} ---")
        settings.embed_batch_size = batch_size
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = os.path.join(tmp_dir, "cloned_repo")
            
            t_clone_start = time.perf_counter()
            process = await asyncio.to_thread(
              subprocess.run,
              ["git", "clone", "--depth=1", repo_url, repo_path],
              capture_output=True,
              text=True,
            )
            t_clone = time.perf_counter() - t_clone_start
            
            sha_process = await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            commit_sha = sha_process.stdout.strip()
            
            t_ingest_start = time.perf_counter()
            summary, tree, content = await ingest_async(repo_path)
            t_ingest = time.perf_counter() - t_ingest_start
            
            # Clear chroma so it rebuilds
            import chromadb
            from services import _chroma_client
            for c in _chroma_client.list_collections():
                _chroma_client.delete_collection(c.name)
                
            await build_query_engine_async(content, "zphisher", commit_sha)
            
        print()

if __name__ == "__main__":
    asyncio.run(main())
