import re

with open("backend/services.py", "r") as f:
    services_code = f.read()

# Replace vector_index usage in run_retrieval_agent
services_code = re.sub(r'vector_index: VectorStoreIndex = engine_bundle\["vector_index"\](.*?)def build_retrieval_plan', '''vector_index = engine_bundle.get("vector_index")
  bm25 = engine_bundle.get("bm25")
  bm25_nodes = engine_bundle.get("bm25_nodes", [])
  sources = engine_bundle.get("sources", {})

  def build_retrieval_plan''', services_code, flags=re.DOTALL)

with open("backend/services.py", "w") as f:
    f.write(services_code)
