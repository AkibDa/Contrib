import asyncio
import time
import os
import sys

# Load backend imports
sys.path.append(os.path.abspath("."))
from config import settings
from services import Settings, _chroma_client, _rich_metadata
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter

async def main():
    import tempfile
    
    # fake small docs
    texts = ["This is a test document to measure embedding speed. It should be long enough to be a chunk."] * 1000
    
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    
    for batch_size in [16, 32, 64]:
        print(f"--- BATCH SIZE {batch_size} ---")
        Settings.embed_model = HuggingFaceEmbedding(
            model_name="BAAI/bge-base-en-v1.5",
            device="mps",
            embed_batch_size=batch_size,
        )
        
        t0 = time.time()
        embeds = Settings.embed_model.get_text_embedding_batch(texts)
        t_embed = time.time() - t0
        
        print(f"Batch Size {batch_size}: {len(texts)} chunks embedded in {t_embed:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
