"""
Q&A Logging Module for Coach AI RAG System

Handles append-only logging of questions, answers, and retrieval metadata
to support session Q&A history and audit trails.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def log_qa_interaction(
    session_id: str,
    question: str,
    answer: str,
    retrieved_sources: List[Dict],
    retrieval_confidence: str,
    mode: str = "Explain my session",
    depth: str = "Quick",
    strict_grounding: bool = True,
    output_dir: str = "outputs"
) -> bool:
    """
    Log a Q&A interaction to the session's qa_log.json file (append-only).
    
    Args:
        session_id: Session identifier (e.g., "20231230_123456")
        question: User's question
        answer: System's answer
        retrieved_sources: List of retrieved KB chunks with metadata
        retrieval_confidence: "High", "Medium", or "Low"
        mode: Answer mode selected by user
        depth: Answer depth selected by user
        strict_grounding: Whether strict grounding was enabled
        output_dir: Base output directory
        
    Returns:
        True if logged successfully, False otherwise
    """
    try:
        # Construct log file path
        session_dir = Path(output_dir) / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = session_dir / "qa_log.json"
        
        # Load existing log or create new
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                qa_log = json.load(f)
        else:
            qa_log = {
                'session_id': session_id,
                'interactions': []
            }
        
        # Create new interaction entry
        interaction = {
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'answer': answer,
            'retrieval_confidence': retrieval_confidence,
            'num_sources': len(retrieved_sources),
            'sources': [
                {
                    'title': src.get('title', 'Unknown'),
                    'filename': src.get('filename', 'unknown.md'),
                    'score': src.get('score', 0.0)
                }
                for src in retrieved_sources
            ],
            'mode': mode,
            'depth': depth,
            'strict_grounding': strict_grounding
        }
        
        # Append to log
        qa_log['interactions'].append(interaction)
        
        # Save updated log
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(qa_log, f, indent=2, ensure_ascii=False)
        
        return True
        
    except Exception as e:
        print(f"Error logging Q&A interaction: {e}")
        return False


def load_qa_log(session_id: str, output_dir: str = "outputs") -> Dict:
    """
    Load Q&A log for a specific session.
    
    Args:
        session_id: Session identifier
        output_dir: Base output directory
        
    Returns:
        Dict with 'session_id' and 'interactions' keys,
        or empty dict if not found
    """
    try:
        log_file = Path(output_dir) / session_id / "qa_log.json"
        
        if not log_file.exists():
            return {
                'session_id': session_id,
                'interactions': []
            }
        
        with open(log_file, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    except Exception as e:
        print(f"Error loading Q&A log: {e}")
        return {
            'session_id': session_id,
            'interactions': []
        }


def get_recent_questions(session_id: str, n: int = 5, output_dir: str = "outputs") -> List[Dict]:
    """
    Get the n most recent Q&A interactions for a session.
    
    Args:
        session_id: Session identifier
        n: Number of recent interactions to retrieve
        output_dir: Base output directory
        
    Returns:
        List of interaction dicts (most recent first)
    """
    qa_log = load_qa_log(session_id, output_dir)
    interactions = qa_log.get('interactions', [])
    
    # Return most recent n interactions
    return list(reversed(interactions[-n:]))


def clear_qa_log(session_id: str, output_dir: str = "outputs") -> bool:
    """
    Clear Q&A log for a session (use with caution).
    
    Args:
        session_id: Session identifier
        output_dir: Base output directory
        
    Returns:
        True if cleared successfully
    """
    try:
        log_file = Path(output_dir) / session_id / "qa_log.json"
        
        if log_file.exists():
            os.remove(log_file)
        
        return True
        
    except Exception as e:
        print(f"Error clearing Q&A log: {e}")
        return False


if __name__ == "__main__":
    # Test logging
    print("=" * 60)
    print("Testing Q&A Logging")
    print("=" * 60)
    
    # Mock interaction
    test_session = "20231230_test"
    
    success = log_qa_interaction(
        session_id=test_session,
        question="How do I improve hip rotation?",
        answer="Hip rotation is critical for power generation...",
        retrieved_sources=[
            {'title': 'Backhand Fundamentals', 'filename': 'backhand_fundamentals.md', 'score': 0.85},
            {'title': 'Drill Explanations', 'filename': 'drill_explanations.md', 'score': 0.72}
        ],
        retrieval_confidence="High",
        mode="Explain my session",
        depth="Quick"
    )
    
    print(f"Logged: {success}")
    
    # Load and display
    qa_log = load_qa_log(test_session)
    print(f"\nInteractions logged: {len(qa_log['interactions'])}")
    
    # Get recent
    recent = get_recent_questions(test_session, n=5)
    print(f"Recent questions: {len(recent)}")
    for i, q in enumerate(recent, 1):
        print(f"  {i}. {q['question'][:50]}... (confidence: {q['retrieval_confidence']})")
    
    # Cleanup
    clear_qa_log(test_session)
    print("\n[OK] Test complete")

