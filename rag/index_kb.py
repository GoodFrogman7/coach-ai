"""
Knowledge Base Indexing for Coach AI RAG System

This module loads markdown files from kb/, chunks them, and creates a searchable index
using TF-IDF vectorization for semantic retrieval.
"""

import json
import re
from pathlib import Path
from typing import List, Dict

try:
    from rag.kb_metadata import parse_front_matter
except ImportError:  # run as a script from rag/ (python rag/index_kb.py)
    from kb_metadata import parse_front_matter
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer


def load_markdown_files(kb_dir: str = "kb") -> List[Dict[str, str]]:
    """
    Load all markdown files from the knowledge base directory.
    
    Returns:
        List of dicts with 'filename', 'title', and 'content' keys
    """
    documents = []
    kb_path = Path(kb_dir)
    
    if not kb_path.exists():
        print(f"Warning: KB directory {kb_dir} not found")
        return documents
    
    for md_file in kb_path.glob("*.md"):
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Optional front matter (strokes: [...]) is stripped from the text
            # and carried as metadata on every chunk.
            meta, content = parse_front_matter(content)

            # Extract title from first # heading
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else md_file.stem.replace('_', ' ').title()
            
            documents.append({
                'filename': md_file.name,
                'title': title,
                'content': content,
                'strokes': meta.get('strokes', []),
            })
        except Exception as e:
            print(f"Error loading {md_file}: {e}")
    
    print(f"Loaded {len(documents)} KB documents")
    return documents


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """
    Split text into overlapping chunks by tokens (approximate).
    
    Args:
        text: Input text
        chunk_size: Target chunk size in tokens (approximate)
        overlap: Overlap between chunks in tokens
        
    Returns:
        List of text chunks
    """
    # Simple word-based chunking (approximates tokens)
    words = text.split()
    chunks = []
    
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunk = ' '.join(chunk_words)
        chunks.append(chunk)
        i += chunk_size - overlap  # Overlap for context continuity
    
    return chunks


def chunk_documents(documents: List[Dict[str, str]], 
                    chunk_size: int = 500,
                    overlap: int = 100) -> List[Dict[str, str]]:
    """
    Chunk documents into smaller pieces for retrieval.
    
    Returns:
        List of dicts with 'filename', 'title', 'chunk_id', and 'text' keys
    """
    chunked_docs = []
    
    for doc in documents:
        chunks = chunk_text(doc['content'], chunk_size, overlap)
        
        for i, chunk in enumerate(chunks):
            # Skip very small chunks (likely incomplete)
            if len(chunk.split()) < 20:
                continue
                
            chunked_docs.append({
                'filename': doc['filename'],
                'title': doc['title'],
                'chunk_id': i,
                'text': chunk,
                'strokes': doc.get('strokes', []),
            })
    
    print(f"Created {len(chunked_docs)} chunks from {len(documents)} documents")
    return chunked_docs


def create_index(chunked_docs: List[Dict[str, str]], 
                output_dir: str = "rag") -> Dict:
    """
    Create TF-IDF index from chunked documents.
    
    Args:
        chunked_docs: List of chunked documents
        output_dir: Directory to save index files
        
    Returns:
        Index metadata dict
    """
    # Extract text for vectorization
    texts = [doc['text'] for doc in chunked_docs]
    
    # Create TF-IDF vectorizer
    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words='english',
        ngram_range=(1, 2),  # Unigrams and bigrams
        min_df=1,
        max_df=0.8
    )
    
    # Fit and transform
    print("Creating TF-IDF index...")
    tfidf_matrix = vectorizer.fit_transform(texts)
    
    # Save index components
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Save vectorizer
    with open(output_path / "vectorizer.pkl", 'wb') as f:
        pickle.dump(vectorizer, f)
    
    # Save TF-IDF matrix
    with open(output_path / "tfidf_matrix.pkl", 'wb') as f:
        pickle.dump(tfidf_matrix, f)
    
    # Save document metadata (for retrieval)
    with open(output_path / "doc_metadata.json", 'w', encoding='utf-8') as f:
        json.dump(chunked_docs, f, indent=2, ensure_ascii=False)
    
    # Count unique documents
    unique_docs = len(set(doc['filename'] for doc in chunked_docs))
    
    # Save index metadata
    index_meta = {
        'num_documents': unique_docs,
        'num_chunks': len(chunked_docs),
        'vocab_size': len(vectorizer.vocabulary_),
        'index_path': str(output_path)
    }
    
    with open(output_path / "index_meta.json", 'w') as f:
        json.dump(index_meta, f, indent=2)
    
    print(f"[OK] Index created: {len(chunked_docs)} chunks, {len(vectorizer.vocabulary_)} vocabulary terms")
    print(f"[OK] Saved to: {output_path}/")
    
    return index_meta


def build_index(kb_dir: str = "kb", 
                output_dir: str = "rag",
                chunk_size: int = 500,
                overlap: int = 100) -> Dict:
    """
    Main function to build the complete RAG index.
    
    Args:
        kb_dir: Knowledge base directory
        output_dir: Output directory for index
        chunk_size: Target chunk size
        overlap: Chunk overlap
        
    Returns:
        Index metadata
    """
    print("=" * 60)
    print("Coach AI - Knowledge Base Indexing")
    print("=" * 60)
    
    # Load documents
    documents = load_markdown_files(kb_dir)
    
    if not documents:
        print("Error: No documents found. Please add markdown files to kb/")
        return {}
    
    # Chunk documents
    chunked_docs = chunk_documents(documents, chunk_size, overlap)
    
    if not chunked_docs:
        print("Error: No valid chunks created")
        return {}
    
    # Create index
    index_meta = create_index(chunked_docs, output_dir)
    
    print("=" * 60)
    print("[OK] Indexing complete!")
    print("=" * 60)
    
    return index_meta


if __name__ == "__main__":
    # Build index when run directly
    build_index()

