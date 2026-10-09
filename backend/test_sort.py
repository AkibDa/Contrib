from llama_index.embeddings.huggingface import HuggingFaceEmbedding

def setup_sorting():
    original_get = HuggingFaceEmbedding._get_text_embeddings
    
    def sorted_get(self, texts):
        # pair with indices
        indexed = list(enumerate(texts))
        # sort by length
        indexed.sort(key=lambda x: len(x[1]))
        
        sorted_texts = [x[1] for x in indexed]
        
        # get embeddings
        sorted_embeds = original_get(self, sorted_texts)
        
        # restore order
        restored = [None] * len(texts)
        for i, (orig_idx, _) in enumerate(indexed):
            restored[orig_idx] = sorted_embeds[i]
            
        return restored
        
    HuggingFaceEmbedding._get_text_embeddings = sorted_get

setup_sorting()
