"""
Embedding Retrieval Module for Coach AI RAG System

Performs semantic search using sentence-transformer embeddings.
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple

# Try to import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class EmbeddingRetriever:
    """Retrieves relevant KB chunks using semantic embeddings."""
    
    def __init__(self, index_dir: str = "rag", model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize retriever by loading embedding index.
        
        Args:
            index_dir: Directory containing index files
            model_name: SentenceTransformer model name
        """
        self.index_dir = Path(index_dir)
        self.model_name = model_name
        self.model = None
        self.embeddings = None
        self.doc_metadata = None
        self.loaded = False
        
        self._load_index()
    
    def _load_index(self):
        """Load embedding index from disk."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            print("Warning: sentence-transformers not installed")
            self.loaded = False
            return
        
        try:
            # Load embeddings
            embeddings_file = self.index_dir / "embedding_index.npz"
            if not embeddings_file.exists():
                print(f"Warning: Embedding index not found at {embeddings_file}")
                self.loaded = False
                return
            
            data = np.load(embeddings_file)
            self.embeddings = data['embeddings']
            
            # Load metadata
            meta_file = self.index_dir / "embedding_meta.json"
            with open(meta_file, 'r', encoding='utf-8') as f:
                self.doc_metadata = json.load(f)
            
            # Load model for query encoding
            print(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            
            self.loaded = True
            print(f"[OK] Embedding index loaded: {len(self.doc_metadata)} chunks")
            
        except FileNotFoundError as e:
            print(f"Warning: Embedding index files not found in {self.index_dir}/")
            print("Run 'python rag/embedding_index.py' to create embedding index")
            self.loaded = False
        except Exception as e:
            print(f"Error loading embedding index: {e}")
            self.loaded = False
    
    def retrieve(self, 
                query: str, 
                top_k: int = 5,
                min_score: float = 0.0) -> List[Dict]:
        """
        Retrieve top-k most relevant chunks for a query using embeddings.
        
        Args:
            query: User question
            top_k: Number of chunks to retrieve
            min_score: Minimum similarity score threshold
            
        Returns:
            List of dicts with 'text', 'title', 'filename', 'score', 'chunk_id'
        """
        if not self.loaded:
            return []
        
        try:
            # Encode query
            query_embedding = self.model.encode(query, convert_to_numpy=True)
            
            # Compute cosine similarity
            # Normalize embeddings
            query_norm = query_embedding / np.linalg.norm(query_embedding)
            doc_norms = self.embeddings / np.linalg.norm(self.embeddings, axis=1, keepdims=True)
            
            similarities = np.dot(doc_norms, query_norm)
            
            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            # Filter by minimum score and build results
            results = []
            for idx in top_indices:
                score = float(similarities[idx])
                
                if score < min_score:
                    continue
                
                doc = self.doc_metadata[idx]
                results.append({
                    'text': doc['text'],
                    'title': doc['title'],
                    'filename': doc['filename'],
                    'chunk_id': doc['chunk_id'],
                    'score': score  # Cosine similarity (0..1)
                })
            
            return results
            
        except Exception as e:
            print(f"Error during embedding retrieval: {e}")
            return []


def retrieve_with_embeddings(query: str, 
                             top_k: int = 5,
                             index_dir: str = "rag",
                             model_name: str = "all-MiniLM-L6-v2") -> List[Dict]:
    """
    Convenience function to retrieve using embeddings.
    
    Args:
        query: User question
        top_k: Number of chunks to retrieve
        index_dir: Index directory
        model_name: SentenceTransformer model name
        
    Returns:
        List of retrieved chunks with scores, or empty list if unavailable
    """
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        return []
    
    retriever = EmbeddingRetriever(index_dir, model_name)
    
    if not retriever.loaded:
        return []
    
    return retriever.retrieve(query, top_k)


if __name__ == "__main__":
    # Test embedding retrieval
    print("=" * 60)
    print("Testing Embedding Retrieval")
    print("=" * 60)
    
    test_queries = [
        "What causes balance drift?",
        "Why is my recovery time important?",
        "How do I improve my split step?",
        "What is hip rotation?"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 60)
        
        results = retrieve_with_embeddings(query, top_k=3)
        
        if results:
            print(f"Retrieved {len(results)} chunks:")
            for i, result in enumerate(results, 1):
                print(f"  {i}. {result['title']} (score: {result['score']:.3f})")
                print(f"     {result['text'][:100]}...")
        else:
            print("No results (embedding index not available)")

