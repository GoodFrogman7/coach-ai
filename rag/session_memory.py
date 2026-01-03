"""
Session-Based Memory for Coach AI RAG System

This module provides SHORT-TERM, session-only memory to improve coaching continuity.
It tracks what the student has asked, detects recurring issues, and enables context-aware responses.

CRITICAL SAFETY FEATURES:
- Session-only (no persistence, no database)
- Stores ONLY observed facts (queries, intents, KB sources)
- Rule-based issue detection (no LLM inference)
- Never overrides grounding policy
- Never increases confidence scores
- Fully inspectable and transparent
"""

from typing import List, Dict, Optional
from datetime import datetime
from collections import Counter


class SessionMemory:
    """
    Session-only memory for tracking student queries and detected issues.
    
    This class is designed to:
    - Remember recent queries within a session
    - Detect recurring topics from KB sources
    - Enable "coach-like" continuity
    - Maintain complete transparency and safety
    
    IMPORTANT: This memory is ephemeral and lives only in Streamlit session_state.
    """
    
    def __init__(self, max_queries: int = 10):
        """
        Initialize session memory.
        
        Args:
            max_queries: Maximum number of recent queries to retain (default: 10)
        """
        self.max_queries = max_queries
        self.recent_queries: List[Dict] = []
        self.session_start = datetime.now()
    
    def add_query(
        self,
        query: str,
        intent: str,
        kb_sources: List[str],
        confidence: str,
        top_score: float = 0.0
    ):
        """
        Add a query to session memory.
        
        This stores ONLY observable facts:
        - The exact query text
        - The detected intent
        - The KB sources that were retrieved
        - The retrieval confidence
        
        NO inference, NO summarization, NO LLM calls.
        
        Args:
            query: User's question
            intent: Detected intent (from intent_classifier)
            kb_sources: List of KB filenames that were retrieved
            confidence: Retrieval confidence ("High", "Medium", "Low")
            top_score: Top retrieval score (optional)
        """
        entry = {
            'query': query,
            'intent': intent,
            'kb_sources': kb_sources,
            'confidence': confidence,
            'top_score': top_score,
            'timestamp': datetime.now().isoformat()
        }
        
        self.recent_queries.append(entry)
        
        # Auto-prune to max_queries
        if len(self.recent_queries) > self.max_queries:
            self.recent_queries = self.recent_queries[-self.max_queries:]
    
    def get_recent_queries(self, n: int = 5) -> List[Dict]:
        """
        Get the n most recent queries.
        
        Args:
            n: Number of recent queries to return
            
        Returns:
            List of query dictionaries (most recent first)
        """
        return list(reversed(self.recent_queries[-n:]))
    
    def detect_recurring_issues(self) -> Dict[str, any]:
        """
        Detect recurring issues using RULE-BASED analysis.
        
        Rules:
        - If the same KB source filename appears ≥2 times → recurring issue
        - Extract topic name from filename (e.g., "balance_drift_explained.md" → "balance_drift")
        - Return issue detection result
        
        This is PURELY observational - no inference, no guessing.
        
        Returns:
            Dict with:
            - has_recurring_issue: bool
            - issue_topics: List[str] (topics that appear ≥2 times)
            - topic_counts: Dict[str, int] (all topic counts)
        """
        if len(self.recent_queries) < 2:
            return {
                'has_recurring_issue': False,
                'issue_topics': [],
                'topic_counts': {}
            }
        
        # Collect all KB source topics
        all_topics = []
        for entry in self.recent_queries:
            for source in entry.get('kb_sources', []):
                # Extract topic from filename
                # e.g., "balance_drift_explained.md" → "balance_drift"
                # e.g., "footwork_fundamentals.md" → "footwork"
                topic = self._extract_topic_from_filename(source)
                if topic:
                    all_topics.append(topic)
        
        # Count topic occurrences
        topic_counter = Counter(all_topics)
        
        # Find recurring topics (≥2 occurrences)
        recurring_topics = [
            topic for topic, count in topic_counter.items()
            if count >= 2
        ]
        
        return {
            'has_recurring_issue': len(recurring_topics) > 0,
            'issue_topics': recurring_topics,
            'topic_counts': dict(topic_counter)
        }
    
    def _extract_topic_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract topic name from KB filename.
        
        Examples:
            "balance_drift_explained.md" → "balance_drift"
            "footwork_fundamentals.md" → "footwork"
            "recovery_time_explained.md" → "recovery_time"
            "kb/balance_drift_explained.md" → "balance_drift"
        
        Args:
            filename: KB source filename
            
        Returns:
            Topic name or None
        """
        if not filename:
            return None
        
        # Remove directory prefix if present
        if '/' in filename:
            filename = filename.split('/')[-1]
        
        # Remove .md extension
        if filename.endswith('.md'):
            filename = filename[:-3]
        
        # Remove common suffixes
        for suffix in ['_explained', '_fundamentals', '_guidance']:
            if filename.endswith(suffix):
                filename = filename[:len(filename) - len(suffix)]
                break
        
        return filename if filename else None
    
    def get_memory_summary(self) -> Dict[str, any]:
        """
        Get a summary of session memory for display/debugging.
        
        Returns:
            Dict with memory statistics
        """
        issue_detection = self.detect_recurring_issues()
        
        intents = [q['intent'] for q in self.recent_queries]
        intent_counter = Counter(intents)
        
        confidences = [q['confidence'] for q in self.recent_queries]
        confidence_counter = Counter(confidences)
        
        return {
            'total_queries': len(self.recent_queries),
            'session_duration_minutes': (datetime.now() - self.session_start).seconds // 60,
            'intent_distribution': dict(intent_counter),
            'confidence_distribution': dict(confidence_counter),
            'recurring_issues': issue_detection,
            'recent_topics': [
                self._extract_topic_from_filename(source)
                for entry in self.recent_queries[-5:]
                for source in entry.get('kb_sources', [])
            ]
        }
    
    def clear(self):
        """
        Clear all session memory.
        
        This is useful for:
        - User explicitly starting a new session
        - Testing
        - Memory reset
        """
        self.recent_queries = []
        self.session_start = datetime.now()
    
    def to_dict(self) -> Dict:
        """
        Export memory to a dictionary for storage in session_state.
        
        Returns:
            Dict representation of memory
        """
        return {
            'recent_queries': self.recent_queries,
            'session_start': self.session_start.isoformat(),
            'max_queries': self.max_queries
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SessionMemory':
        """
        Restore memory from a dictionary.
        
        Args:
            data: Dict from to_dict()
            
        Returns:
            SessionMemory instance
        """
        memory = cls(max_queries=data.get('max_queries', 10))
        memory.recent_queries = data.get('recent_queries', [])
        
        session_start_str = data.get('session_start')
        if session_start_str:
            try:
                memory.session_start = datetime.fromisoformat(session_start_str)
            except (ValueError, TypeError):
                memory.session_start = datetime.now()
        
        return memory


def get_or_create_session_memory(session_state: Dict, key: str = "rag_session_memory") -> SessionMemory:
    """
    Get or create a SessionMemory instance from Streamlit session_state.
    
    This is the recommended way to use SessionMemory in Streamlit.
    
    Args:
        session_state: Streamlit st.session_state object
        key: Key to store memory under (default: "rag_session_memory")
        
    Returns:
        SessionMemory instance
    
    Example:
        >>> import streamlit as st
        >>> memory = get_or_create_session_memory(st.session_state)
        >>> memory.add_query("Why do I lose balance?", "DIAGNOSE", ["balance_drift.md"], "High")
    """
    if key not in session_state:
        session_state[key] = SessionMemory()
    
    return session_state[key]


# Test function for development
def test_session_memory():
    """
    Test session memory with simulated queries.
    """
    print("\n" + "="*80)
    print("Testing Session Memory")
    print("="*80 + "\n")
    
    memory = SessionMemory(max_queries=10)
    
    # Simulate a coaching session
    test_queries = [
        {
            'query': "Why do I lose balance on my forehand?",
            'intent': "DIAGNOSE",
            'kb_sources': ["balance_drift_explained.md", "forehand_fundamentals.md"],
            'confidence': "Medium",
            'top_score': 0.35
        },
        {
            'query': "How do I improve my recovery time?",
            'intent': "HOW",
            'kb_sources': ["recovery_time_explained.md"],
            'confidence': "High",
            'top_score': 0.52
        },
        {
            'query': "What causes balance drift during strokes?",
            'intent': "WHY",
            'kb_sources': ["balance_drift_explained.md"],
            'confidence': "High",
            'top_score': 0.48
        },
    ]
    
    for i, query_data in enumerate(test_queries, 1):
        print(f"Query {i}: '{query_data['query']}'")
        print(f"  Intent: {query_data['intent']}")
        print(f"  KB Sources: {', '.join(query_data['kb_sources'])}")
        print(f"  Confidence: {query_data['confidence']}")
        
        memory.add_query(
            query=query_data['query'],
            intent=query_data['intent'],
            kb_sources=query_data['kb_sources'],
            confidence=query_data['confidence'],
            top_score=query_data['top_score']
        )
        
        # Check for recurring issues
        issue_detection = memory.detect_recurring_issues()
        if issue_detection['has_recurring_issue']:
            print(f"  [RECURRING ISSUE DETECTED]")
            print(f"  Topics: {', '.join(issue_detection['issue_topics'])}")
        
        print()
    
    # Print memory summary
    print("="*80)
    print("Memory Summary")
    print("="*80)
    summary = memory.get_memory_summary()
    print(f"Total Queries: {summary['total_queries']}")
    print(f"Intent Distribution: {summary['intent_distribution']}")
    print(f"Confidence Distribution: {summary['confidence_distribution']}")
    print(f"Recurring Issues: {summary['recurring_issues']}")
    print()


if __name__ == "__main__":
    test_session_memory()

