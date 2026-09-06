"""
RAG Retrieval Quality Test Script

Tests retrieval performance with KB improvements and ensemble retrieval.
"""

from rag import retrieve_context

def test_retrieval_quality():
    """Test retrieval for common user questions."""
    
    print("=" * 70)
    print("Coach AI - RAG Retrieval Quality Test")
    print("=" * 70)
    print()
    
    test_queries = [
        "What causes balance drift?",
        "Why is my recovery time important?",
        "How do I fix split-step timing?",
        "Why am I swaying sideways when hitting?",
        "What is lateral movement in tennis?",
        "How do I stop losing balance during strokes?"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*70}")
        print(f"Test Query #{i}: {query}")
        print('='*70)
        
        # Retrieve with ensemble (embeddings + TF-IDF)
        result = retrieve_context(query, top_k=3, use_embeddings=True)
        
        print(f"\nRetrieval Method: {result['method_used'].upper()}")
        print(f"Confidence: {result['confidence']}")
        print(f"Explanation: {result['confidence_explanation']}")
        
        # Show stats
        stats = result.get('retrieval_stats', {})
        if stats:
            print("\nStats:")
            print(f"   Top1 Score: {stats.get('top1_score', 0.0):.3f}")
            print(f"   Avg Top3:   {stats.get('avg_top3', 0.0):.3f}")
            print(f"   Results:    {stats.get('num_results', 0)}")
        
        # Show top sources
        results = result.get('results', [])
        if results:
            print(f"\nTop {len(results)} Sources:")
            for j, chunk in enumerate(results, 1):
                # Extract score components if available
                combined_score = chunk.get('score', 0.0)
                tfidf_score = chunk.get('tfidf_score', 0.0)
                embed_score = chunk.get('embed_score', 0.0)
                
                print(f"\n   {j}. {chunk['title']}")
                print(f"      File: {chunk['filename']}")
                print(f"      Combined Score: {combined_score:.3f}", end='')
                
                if tfidf_score > 0 or embed_score > 0:
                    print(f" (TF-IDF: {tfidf_score:.3f}, Embed: {embed_score:.3f})")
                else:
                    print()
                
                # Show snippet (encode-safe for Windows console)
                snippet = chunk['text'][:150].replace('\n', ' ')
                try:
                    print(f"      Snippet: {snippet}...")
                except UnicodeEncodeError:
                    # Fallback for Windows console encoding issues
                    snippet_safe = snippet.encode('ascii', 'ignore').decode('ascii')
                    print(f"      Snippet: {snippet_safe}...")
        else:
            print("\n[WARNING] No sources retrieved")
        
        # Expected outcome for key queries
        if query == "What causes balance drift?":
            print("\n[EXPECTED] balance_drift_explained.md with Medium/High confidence")
            if result['confidence'] in ['Medium', 'High']:
                print(f"   [PASS] Confidence is {result['confidence']}")
            else:
                print(f"   [FAIL] Confidence is {result['confidence']} (expected Medium/High)")
    
    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    test_retrieval_quality()

