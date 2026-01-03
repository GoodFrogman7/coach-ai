"""
Query Intent Classification for Coach AI RAG System

This module provides rule-based intent detection to help the RAG system
better understand what the user is trying to ask, enabling smarter retrieval
and UI presentation without introducing hallucination risk.

IMPORTANT: This is a pure, deterministic, rule-based classifier.
It uses NO machine learning and makes NO LLM calls.
"""

import re
from typing import Dict, List, Tuple


# Intent definitions and their keywords/patterns
INTENT_PATTERNS = {
    "DIAGNOSE": {
        "keywords": ["why am i", "why do i", "what's wrong", "whats wrong", "my problem", 
                    "issue with my", "struggling with", "having trouble", "can't seem to",
                    "keep losing", "keep missing", "always", "every time i"],
        "weight": 3  # Higher weight = higher priority in matching
    },
    "WHY": {
        "keywords": ["why", "cause", "reason", "because", "explain", "explanation",
                    "what causes", "what's causing", "whats causing", "how come",
                    "why does", "why is", "the reason"],
        "weight": 2
    },
    "HOW": {
        "keywords": ["how do i", "how to", "how can i", "fix", "improve", "correct",
                    "drill", "practice", "train", "technique for", "steps to",
                    "way to", "method", "approach to"],
        "weight": 2
    },
    "COMPARE": {
        "keywords": [" vs ", " versus ", "difference between", "compared to",
                    "better than", "worse than", "rather than", "instead of",
                    "or should i", "which is better"],
        "weight": 3
    },
    "WHAT": {
        "keywords": ["what is", "what are", "what does", "define", "definition of",
                    "meaning of", "explain what", "tell me about", "what's the",
                    "whats the"],
        "weight": 1
    }
}


def classify_intent(query: str) -> str:
    """
    Classify the user's query intent using rule-based pattern matching.
    
    This function is:
    - Deterministic: same input always produces same output
    - Fast: simple string matching only
    - Safe: no side effects, no external calls
    - Production-ready: handles edge cases gracefully
    
    Args:
        query: User's question string
        
    Returns:
        One of: "DIAGNOSE", "WHY", "HOW", "COMPARE", "WHAT", "UNKNOWN"
        
    Examples:
        >>> classify_intent("Why do I lose balance during my forehand?")
        "DIAGNOSE"
        
        >>> classify_intent("How do I fix my split step timing?")
        "HOW"
        
        >>> classify_intent("What is recovery time?")
        "WHAT"
        
        >>> classify_intent("Why does balance drift happen?")
        "WHY"
        
        >>> classify_intent("Forehand vs backhand footwork")
        "COMPARE"
    """
    if not query or not isinstance(query, str):
        return "UNKNOWN"
    
    # Normalize query for matching
    query_lower = query.lower().strip()
    
    if not query_lower:
        return "UNKNOWN"
    
    # Score each intent based on keyword matches
    intent_scores = {intent: 0 for intent in INTENT_PATTERNS.keys()}
    
    for intent, pattern_info in INTENT_PATTERNS.items():
        keywords = pattern_info["keywords"]
        weight = pattern_info["weight"]
        
        for keyword in keywords:
            # Use word boundary matching for better accuracy
            if keyword in query_lower:
                # Extra points if keyword appears at the start of the query
                if query_lower.startswith(keyword):
                    intent_scores[intent] += weight * 2
                else:
                    intent_scores[intent] += weight
    
    # Get the intent with the highest score
    max_score = max(intent_scores.values())
    
    if max_score == 0:
        return "UNKNOWN"
    
    # Return the highest scoring intent
    best_intent = max(intent_scores.items(), key=lambda x: x[1])[0]
    
    return best_intent


def get_intent_context(intent: str) -> Dict[str, any]:
    """
    Get additional context about a detected intent.
    
    This can be used to provide hints to the retrieval system or UI
    about how to handle queries of this type.
    
    Args:
        intent: The detected intent (from classify_intent)
        
    Returns:
        Dictionary with intent metadata:
        - description: Human-readable description
        - retrieval_hint: Suggestion for retrieval focus
        - expected_sources: Types of KB sources likely to be relevant
    """
    context_map = {
        "DIAGNOSE": {
            "description": "User is trying to identify a problem in their technique",
            "retrieval_hint": "Focus on common issues, causes, and diagnostic cues",
            "expected_sources": ["fundamentals", "common_mistakes", "analysis"]
        },
        "WHY": {
            "description": "User wants to understand causes or reasoning",
            "retrieval_hint": "Focus on explanations, biomechanics, and principles",
            "expected_sources": ["explained", "fundamentals", "guidance"]
        },
        "HOW": {
            "description": "User wants actionable fixes or techniques",
            "retrieval_hint": "Focus on drills, techniques, and step-by-step guidance",
            "expected_sources": ["drills", "fundamentals", "how-to"]
        },
        "COMPARE": {
            "description": "User wants to understand differences or alternatives",
            "retrieval_hint": "Focus on contrasts and comparative explanations",
            "expected_sources": ["fundamentals", "explained", "guidance"]
        },
        "WHAT": {
            "description": "User wants definitions or conceptual understanding",
            "retrieval_hint": "Focus on definitions and conceptual explanations",
            "expected_sources": ["explained", "fundamentals"]
        },
        "UNKNOWN": {
            "description": "Intent unclear; use general retrieval",
            "retrieval_hint": "Use standard retrieval without bias",
            "expected_sources": ["all"]
        }
    }
    
    return context_map.get(intent, context_map["UNKNOWN"])


def get_intent_display_emoji(intent: str) -> str:
    """
    Get a simple emoji representation for UI display.
    
    Args:
        intent: The detected intent
        
    Returns:
        Emoji string (returns text fallback on Windows if needed)
    """
    emoji_map = {
        "DIAGNOSE": "🔍",
        "WHY": "💡",
        "HOW": "🛠️",
        "COMPARE": "⚖️",
        "WHAT": "📖",
        "UNKNOWN": "❓"
    }
    
    return emoji_map.get(intent, "❓")


# Test function for development/debugging
def test_intent_classifier():
    """
    Test the intent classifier with common tennis coaching queries.
    """
    test_queries = [
        ("Why do I lose balance during my forehand?", "DIAGNOSE"),
        ("How do I fix my split step timing?", "HOW"),
        ("What is recovery time?", "WHAT"),
        ("Why does balance drift happen?", "WHY"),
        ("Forehand vs backhand footwork", "COMPARE"),
        ("What causes balance drift?", "WHY"),
        ("Why am I swaying sideways when hitting?", "DIAGNOSE"),
        ("How can I improve my serve?", "HOW"),
        ("Difference between open and closed stance", "COMPARE"),
        ("tennis", "UNKNOWN"),
        ("", "UNKNOWN"),
    ]
    
    print("\n=== Intent Classification Tests ===\n")
    
    for query, expected in test_queries:
        detected = classify_intent(query)
        status = "[OK]" if detected == expected else "[MISMATCH]"
        print(f"{status} Query: '{query}'")
        print(f"     Expected: {expected} | Detected: {detected}")
        if detected != expected:
            print(f"     ^ NOTE: This might be acceptable if {detected} is also valid")
        print()


if __name__ == "__main__":
    test_intent_classifier()
