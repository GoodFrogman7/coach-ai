"""
Coach AI RAG System

This module provides knowledge base indexing, retrieval, and LLM-powered
explanations for the Coach AI tennis intelligence system.
"""

from .index_kb import build_index
from .retrieve import retrieve_context, KnowledgeRetriever
from .coach_llm import ask_coach, extract_session_summary
from .qa_logging import log_qa_interaction, load_qa_log, get_recent_questions

__all__ = [
    'build_index',
    'retrieve_context',
    'KnowledgeRetriever',
    'ask_coach',
    'extract_session_summary',
    'log_qa_interaction',
    'load_qa_log',
    'get_recent_questions'
]

