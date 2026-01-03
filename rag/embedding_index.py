"""
Embedding Index Module for Coach AI RAG System

Creates semantic embeddings for KB documents using sentence-transformers.
Uses the SAME chunking logic as TF-IDF indexing for consistency.
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict

# Try to import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("sentence-transformers not installed. Run: pip install sentence-transformers")


def load_markdown_files(kb_dir: str = "kb") -> List[Dict[str, str]]:
    """
    Load all markdown files from KB directory.
    
    Returns:
        List of dicts with 'filename', 'title', and 'content' keys
    """
    import re
    
    documents = []
    kb_path = Path(kb_dir)
    
    if not kb_path.exists():
        print(f"Warning: KB directory {kb_dir} not found")
        return documents
    
    for md_file in kb_path.glob("*.md"):
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract title from first # heading
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else md_file.stem.replace('_', ' ').title()
            
            documents.append({
                'filename': md_file.name,
                'title': title,
                'content': content
            })
        except Exception as e:
            print(f"Error loading {md_file}: {e}")
    
    print(f"Loaded {len(documents)} KB documents")
    return documents


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """
    Split text into overlapping chunks (SAME as TF-IDF chunking).
    
    Args:
        text: Input text
        chunk_size: Target chunk size in tokens (approximate)
        overlap: Overlap between chunks in tokens
        
    Returns:
        List of text chunks
    """
    words = text.split()
    chunks = []
    
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunk = ' '.join(chunk_words)
        chunks.append(chunk)
        i += chunk_size - overlap
    
    return chunks


def chunk_documents(documents: List[Dict[str, str]], 
                    chunk_size: int = 500,
                    overlap: int = 100) -> List[Dict[str, str]]:
    """
    Chunk documents into smaller pieces (SAME as TF-IDF chunking).
    
    Returns:
        List of dicts with 'filename', 'title', 'chunk_id', and 'text' keys
    """
    chunked_docs = []
    
    for doc in documents:
        chunks = chunk_text(doc['content'], chunk_size, overlap)
        
        for i, chunk in enumerate(chunks):
            # Skip very small chunks
            if len(chunk.split()) < 20:
                continue
                
            chunked_docs.append({
                'filename': doc['filename'],
                'title': doc['title'],
                'chunk_id': i,
                'text': chunk
            })
    
    print(f"Created {len(chunked_docs)} chunks from {len(documents)} documents")
    return chunked_docs


def create_embedding_index(
    chunked_docs: List[Dict[str, str]],
    model_name: str = "all-MiniLM-L6-v2",
    output_dir: str = "rag"
) -> bool:
    """
    Create embedding index from chunked documents.
    
    Args:
        chunked_docs: List of chunked documents
        model_name: SentenceTransformer model name
        output_dir: Directory to save index files
        
    Returns:
        True if successful, False otherwise
    """
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        print("[ERROR] sentence-transformers not installed")
        print("Run: pip install sentence-transformers")
        return False
    
    print(f"Loading embedding model: {model_name}")
    print("This may download ~90MB on first run...")
    
    try:
        model = SentenceTransformer(model_name)
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        return False
    
    # Extract texts for embedding
    texts = [doc['text'] for doc in chunked_docs]
    
    print(f"Computing embeddings for {len(texts)} chunks...")
    try:
        embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    except Exception as e:
        print(f"[ERROR] Failed to compute embeddings: {e}")
        return False
    
    # Save embeddings
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Save embeddings as compressed numpy array
    np.savez_compressed(
        output_path / "embedding_index.npz",
        embeddings=embeddings
    )
    
    # Save metadata (for retrieval)
    with open(output_path / "embedding_meta.json", 'w', encoding='utf-8') as f:
        json.dump(chunked_docs, f, indent=2, ensure_ascii=False)
    
    # Save index info
    index_info = {
        'model_name': model_name,
        'num_chunks': len(chunked_docs),
        'embedding_dim': embeddings.shape[1],
        'index_path': str(output_path)
    }
    
    with open(output_path / "embedding_index_info.json", 'w') as f:
        json.dump(index_info, f, indent=2)
    
    print(f"[OK] Embedding index created: {len(chunked_docs)} chunks, {embeddings.shape[1]}-dim embeddings")
    print(f"[OK] Saved to: {output_path}/")
    
    return True


def build_embedding_index(
    kb_dir: str = "kb",
    output_dir: str = "rag",
    model_name: str = "all-MiniLM-L6-v2",
    chunk_size: int = 500,
    overlap: int = 100
) -> bool:
    """
    Main function to build the complete embedding index.
    
    Args:
        kb_dir: Knowledge base directory
        output_dir: Output directory for index
        model_name: SentenceTransformer model name
        chunk_size: Target chunk size
        overlap: Chunk overlap
        
    Returns:
        True if successful, False otherwise
    """
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        print("=" * 60)
        print("Embedding Index NOT Available")
        print("=" * 60)
        print()
        print("sentence-transformers is not installed.")
        print()
        print("To enable semantic embeddings:")
        print("  pip install sentence-transformers")
        print()
        print("TF-IDF retrieval will still work without embeddings.")
        print("=" * 60)
        return False
    
    print("=" * 60)
    print("Coach AI - Embedding Index Creation")
    print("=" * 60)
    
    # Load documents
    documents = load_markdown_files(kb_dir)
    
    if not documents:
        print("[ERROR] No documents found. Please add markdown files to kb/")
        return False
    
    # Chunk documents (SAME as TF-IDF)
    chunked_docs = chunk_documents(documents, chunk_size, overlap)
    
    if not chunked_docs:
        print("[ERROR] No valid chunks created")
        return False
    
    # Create embedding index
    success = create_embedding_index(chunked_docs, model_name, output_dir)
    
    if success:
        print("=" * 60)
        print("[OK] Embedding indexing complete!")
        print("=" * 60)
    else:
        print("=" * 60)
        print("[ERROR] Embedding indexing failed")
        print("=" * 60)
    
    return success


if __name__ == "__main__":
    # Build embedding index when run directly
    success = build_embedding_index()
    
    # Exit with appropriate code
    exit(0 if success else 1)

