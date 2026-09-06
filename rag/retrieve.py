"""
Retrieval Module for Coach AI RAG System

This module loads the TF-IDF index and retrieves relevant knowledge base chunks
for user queries.
"""

import json
import pickle
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np


class KnowledgeRetriever:
    """Retrieves relevant KB chunks using TF-IDF similarity."""
    
    def __init__(self, index_dir: str = "rag"):
        """
        Initialize retriever by loading index components.
        
        Args:
            index_dir: Directory containing index files
        """
        self.index_dir = Path(index_dir)
        self.vectorizer = None
        self.tfidf_matrix = None
        self.doc_metadata = None
        self.loaded = False
        
        self._load_index()
    
    def _load_index(self):
        """Load index components from disk."""
        try:
            # Load vectorizer
            with open(self.index_dir / "vectorizer.pkl", 'rb') as f:
                self.vectorizer = pickle.load(f)
            
            # Load TF-IDF matrix
            with open(self.index_dir / "tfidf_matrix.pkl", 'rb') as f:
                self.tfidf_matrix = pickle.load(f)
            
            # Load document metadata
            with open(self.index_dir / "doc_metadata.json", 'r', encoding='utf-8') as f:
                self.doc_metadata = json.load(f)
            
            self.loaded = True
            print(f"[OK] Index loaded: {len(self.doc_metadata)} chunks")
            
        except FileNotFoundError:
            print(f"Warning: Index not found in {self.index_dir}/")
            print("Run 'python rag/index_kb.py' to create index first")
            self.loaded = False
        except Exception as e:
            print(f"Error loading index: {e}")
            self.loaded = False
    
    def retrieve(self, 
                query: str, 
                top_k: int = 5,
                min_score: float = 0.01) -> List[Dict]:
        """
        Retrieve top-k most relevant chunks for a query.
        
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
            # Vectorize query
            query_vec = self.vectorizer.transform([query])
            
            # Compute cosine similarity
            similarities = (self.tfidf_matrix * query_vec.T).toarray().flatten()
            
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
                    'strokes': doc.get('strokes', []),
                    'score': score
                })
            
            return results
            
        except Exception as e:
            print(f"Error during retrieval: {e}")
            return []
    
    def compute_retrieval_confidence(self, results: List[Dict]) -> Tuple[str, str]:
        """
        Compute confidence level and explanation for retrieval results.
        
        Args:
            results: Retrieved chunks with scores
            
        Returns:
            (confidence_level, explanation)
            confidence_level: "High", "Medium", or "Low"
            explanation: Human-readable explanation
        """
        if not results:
            return "Low", "No relevant information found in knowledge base"
        
        # Analyze scores
        scores = [r['score'] for r in results]
        max_score = max(scores)
        avg_score = np.mean(scores)
        
        # Confidence thresholds (TF-IDF scores are typically < 1.0)
        if max_score > 0.3 and avg_score > 0.15:
            confidence = "High"
            explanation = f"Found {len(results)} highly relevant sources"
        elif max_score > 0.15 and avg_score > 0.08:
            confidence = "Medium"
            explanation = f"Found {len(results)} moderately relevant sources"
        else:
            confidence = "Low"
            explanation = f"Found {len(results)} sources but relevance is limited"
        
        return confidence, explanation


def combine_retrieval_results(
    tfidf_results: List[Dict],
    embedding_results: List[Dict],
    top_k: int = 5
) -> List[Dict]:
    """
    Combine TF-IDF and embedding results using weighted ensemble.
    
    Args:
        tfidf_results: Results from TF-IDF retrieval
        embedding_results: Results from embedding retrieval
        top_k: Number of final results to return
        
    Returns:
        Combined results sorted by combined score
    """
    # Create a dict keyed by (filename, chunk_id) for deduplication
    combined = {}
    
    # Add TF-IDF results
    for result in tfidf_results:
        key = (result['filename'], result['chunk_id'])
        combined[key] = {
            **result,
            'tfidf_score': result['score'],
            'embed_score': 0.0,
            'combined_score': 0.45 * result['score']  # TF-IDF weight = 0.45
        }
    
    # Add/merge embedding results
    for result in embedding_results:
        key = (result['filename'], result['chunk_id'])
        if key in combined:
            # Chunk appears in both - combine scores
            combined[key]['embed_score'] = result['score']
            combined[key]['combined_score'] = 0.55 * result['score'] + 0.45 * combined[key]['tfidf_score']
        else:
            # Only in embeddings
            combined[key] = {
                **result,
                'tfidf_score': 0.0,
                'embed_score': result['score'],
                'combined_score': 0.55 * result['score']  # Embedding weight = 0.55 (preferred)
            }
    
    # Convert back to list and sort by combined score
    results_list = list(combined.values())
    results_list.sort(key=lambda x: x['combined_score'], reverse=True)
    
    # Update 'score' field to combined score for consistency
    for r in results_list:
        r['score'] = r['combined_score']
    
    return results_list[:top_k]


def compute_ensemble_confidence(results: List[Dict]) -> Tuple[str, str, Dict]:
    """
    Compute confidence level for ensemble retrieval results.
    
    Args:
        results: Retrieved chunks with combined scores
        
    Returns:
        (confidence_level, explanation, stats)
    """
    if not results:
        return "Low", "No relevant information found in knowledge base", {}
    
    # Analyze combined scores
    scores = [r.get('combined_score', r['score']) for r in results]
    top1_score = scores[0] if scores else 0.0
    avg_top3 = np.mean(scores[:3]) if len(scores) >= 3 else np.mean(scores)
    
    # New thresholds for combined scores (higher than TF-IDF alone)
    if top1_score >= 0.45 or avg_top3 >= 0.35:
        confidence = "High"
        explanation = f"Found {len(results)} highly relevant sources"
    elif top1_score >= 0.25 or avg_top3 >= 0.20:
        confidence = "Medium"
        explanation = f"Found {len(results)} moderately relevant sources"
    else:
        confidence = "Low"
        explanation = f"Found {len(results)} sources but relevance is limited"
    
    stats = {
        'top1_score': float(top1_score),
        'avg_top3': float(avg_top3),
        'num_results': len(results)
    }
    
    return confidence, explanation, stats


def retrieve_context(query: str, 
                     top_k: int = 5,
                     index_dir: str = "rag",
                     use_embeddings: bool = True,
                     session_memory=None,
                     stroke: str = None) -> Dict:
    """
    Unified retrieval function supporting TF-IDF, embeddings, or ensemble.
    Now includes intent classification and session memory for smarter retrieval.
    
    Args:
        query: User question
        top_k: Number of chunks to retrieve
        index_dir: Index directory
        use_embeddings: Whether to use embeddings if available
        session_memory: Optional SessionMemory instance for tracking queries
        stroke: The session's stroke. Chunks tagged with it are boosted and
            chunks tagged with a different stroke are dropped (see
            rag.kb_metadata.boost_for_stroke). None means no re-ranking.
        
    Returns:
        Dict with 'results', 'confidence', 'confidence_explanation', 
        'method_used', 'retrieval_stats' (including 'intent', 'intent_description',
        and 'recurring_issue' if session_memory is provided)
    """
    # Classify query intent (lightweight, rule-based)
    try:
        from .intent_classifier import classify_intent, get_intent_context
        intent = classify_intent(query)
        intent_context = get_intent_context(intent)
        intent_description = intent_context['description']
    except Exception as e:
        # Graceful fallback if intent classifier fails
        print(f"Intent classification unavailable: {e}")
        intent = "UNKNOWN"
        intent_description = "General Question"
    
    # Try TF-IDF retrieval
    tfidf_retriever = KnowledgeRetriever(index_dir)
    tfidf_results = []
    
    if tfidf_retriever.loaded:
        tfidf_results = tfidf_retriever.retrieve(query, top_k=top_k)
    else:
        return {
            'results': [],
            'confidence': 'Low',
            'confidence_explanation': 'TF-IDF index not available - run indexing first',
            'method_used': 'none',
            'retrieval_stats': {
                'intent': intent,
                'intent_description': intent_description
            }
        }
    
    # Try embedding retrieval if requested
    embedding_results = []
    if use_embeddings:
        try:
            from .embedding_retrieve import retrieve_with_embeddings
            embedding_results = retrieve_with_embeddings(query, top_k=top_k, index_dir=index_dir)
        except Exception as e:
            print(f"Embedding retrieval unavailable: {e}")
    
    # Determine method and combine results
    if embedding_results and tfidf_results:
        # Ensemble: combine both
        results = combine_retrieval_results(tfidf_results, embedding_results, top_k)
        confidence, explanation, stats = compute_ensemble_confidence(results)
        method_used = "ensemble"
    elif embedding_results:
        # Embeddings only
        results = embedding_results[:top_k]
        confidence, explanation, stats = compute_ensemble_confidence(results)
        method_used = "embeddings"
    else:
        # TF-IDF only (fallback)
        results = tfidf_results
        confidence, explanation = tfidf_retriever.compute_retrieval_confidence(results)
        stats = {
            'top1_score': float(results[0]['score']) if results else 0.0,
            'avg_top3': float(np.mean([r['score'] for r in results[:3]])) if len(results) >= 3 else 0.0,
            'num_results': len(results)
        }
        method_used = "tfidf"
    
    # Re-rank for the session's stroke (confidence above was computed on the
    # raw scores so the boost cannot manufacture confidence).
    if stroke:
        from .kb_metadata import boost_for_stroke
        results = boost_for_stroke(results, stroke)[:top_k]
        stats['stroke'] = stroke

    # Add intent to retrieval stats
    stats['intent'] = intent
    stats['intent_description'] = intent_description
    
    # Add session memory tracking if provided
    if session_memory:
        # Extract KB source filenames from results
        kb_sources = [r['filename'] for r in results if 'filename' in r]
        
        # Add query to session memory
        top_score = stats.get('top1_score', 0.0)
        session_memory.add_query(
            query=query,
            intent=intent,
            kb_sources=kb_sources,
            confidence=confidence,
            top_score=top_score
        )
        
        # Detect recurring issues (rule-based)
        issue_detection = session_memory.detect_recurring_issues()
        stats['recurring_issue'] = issue_detection['has_recurring_issue']
        stats['issue_topics'] = issue_detection.get('issue_topics', [])
        stats['issue_topic_counts'] = issue_detection.get('topic_counts', {})
    else:
        # No session memory - default to no recurring issues
        stats['recurring_issue'] = False
        stats['issue_topics'] = []
    
    return {
        'results': results,
        'confidence': confidence,
        'confidence_explanation': explanation,
        'method_used': method_used,
        'retrieval_stats': stats
    }


if __name__ == "__main__":
    # Test retrieval
    print("=" * 60)
    print("Testing Knowledge Retrieval")
    print("=" * 60)
    
    test_queries = [
        "How do I improve my hip rotation?",
        "What causes balance drift?",
        "How should I film my strokes?",
        "What is recovery time?"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 60)
        
        context = retrieve_context(query, top_k=3)
        
        print(f"Confidence: {context['confidence']}")
        print(f"Explanation: {context['confidence_explanation']}")
        print(f"Retrieved {len(context['results'])} chunks:")
        
        for i, result in enumerate(context['results'], 1):
            print(f"  {i}. {result['title']} (score: {result['score']:.3f})")
            print(f"     {result['text'][:100]}...")

