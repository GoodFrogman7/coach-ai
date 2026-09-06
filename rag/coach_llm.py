"""
LLM Answering Module for Coach AI RAG System

This module builds prompts with guardrails and retrieved context,
then calls an LLM to generate explanations (explanation-only, no decision-making).
"""

import os
from typing import Dict, List, Optional
import re


def extract_session_summary(report_path: str = "outputs/report.md") -> str:
    """
    Extract key information from the latest session report.
    
    Args:
        report_path: Path to report.md
        
    Returns:
        Summary text of current session
    """
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report = f.read()
        
        # Extract key sections (simple regex-based extraction)
        summary_parts = []
        
        # Overall score
        overall_match = re.search(r'Overall Technique Score.*?(\d+\.\d+)/100', report)
        if overall_match:
            summary_parts.append(f"Overall Score: {overall_match.group(1)}/100")
        
        # Match readiness
        readiness_match = re.search(r'Match Readiness.*?(\d+\.\d+)/100.*?\((.*?)\)', report)
        if readiness_match:
            summary_parts.append(f"Match Readiness: {readiness_match.group(1)}/100 ({readiness_match.group(2)})")
        
        # Training recommendation
        training_match = re.search(r'Session Type.*?\*\*(.*?)\*\*', report)
        if training_match:
            summary_parts.append(f"Recommended Training: {training_match.group(1)}")
        
        # Key issues (first 2)
        issues = re.findall(r'(?:CRITICAL|PRIORITY):.*?-\s+(.*?)(?:\n|$)', report)
        if issues:
            summary_parts.append(f"Key Issues: {', '.join(issues[:2])}")
        
        if summary_parts:
            return "Current Session:\n" + "\n".join(f"- {part}" for part in summary_parts)
        else:
            return "Current Session: Analysis available in full report"
            
    except FileNotFoundError:
        return "Current Session: No recent session data available"
    except Exception as e:
        print(f"Error extracting session summary: {e}")
        return "Current Session: Unable to extract summary"


def build_prompt(question: str, 
                retrieved_chunks: List[Dict],
                session_summary: str,
                mode: str = "Explain my session",
                depth: str = "Quick",
                strict_grounding: bool = True) -> str:
    """
    Build a complete prompt with guardrails, context, and question.
    
    Args:
        question: User's question
        retrieved_chunks: Retrieved KB chunks with scores
        session_summary: Summary of user's current session
        mode: Answer mode ("Explain my session", "Teach the concept", "Drill how-to")
        depth: Answer depth ("Quick", "Detailed")
        strict_grounding: If True, enforce strict source citation requirements
        
    Returns:
        Complete prompt string
    """
    # Guardrails
    guardrails = """You are Coach AI, an assistant tennis coach focused on explanation and education.

CRITICAL RULES:
- You provide EXPLANATIONS ONLY. You do NOT make decisions or recommendations.
- You do NOT modify training plans, drill recommendations, or readiness assessments.
- You do NOT provide medical advice or injury diagnosis.
- You explain what the metrics mean, how techniques work, and why things matter.
- If unsure or if information is missing, say so clearly.
- Be encouraging and supportive while remaining honest.
- Use coach-like language: clear, practical, motivating.

Your role is to help the user UNDERSTAND their analysis, not to override it."""

    # Add strict grounding requirement
    if strict_grounding:
        guardrails += """

STRICT GROUNDING REQUIREMENT:
- You MUST cite sources explicitly when providing information.
- You MUST NOT introduce concepts not found in the provided context.
- If the context doesn't cover something, say "The knowledge base doesn't cover this topic in detail."
- Always indicate which source supports each claim you make."""

    # Format retrieved context
    context_section = "\n\n--- KNOWLEDGE BASE CONTEXT ---\n"
    
    if not retrieved_chunks:
        context_section += "No relevant knowledge base information found for this question.\n"
    else:
        for i, chunk in enumerate(retrieved_chunks, 1):
            context_section += f"\n[Source {i}: {chunk['title']}]\n"
            context_section += f"{chunk['text'][:800]}\n"  # Limit chunk size
            context_section += f"(Relevance: {chunk['score']:.2f})\n"
    
    # Add session context
    session_section = f"\n\n--- USER'S CURRENT SESSION ---\n{session_summary}\n"
    
    # Mode-specific instructions
    mode_instructions = {
        "Explain my session": "Focus on explaining their current session data in context of the KB information.",
        "Teach the concept": "Focus on teaching the fundamental concept from the KB, with examples.",
        "Drill how-to": "Focus on explaining how to perform drills correctly, with step-by-step guidance."
    }
    mode_instruction = mode_instructions.get(mode, mode_instructions["Explain my session"])
    
    # Depth-specific instructions
    depth_instruction = "Keep the answer concise (2-3 paragraphs)." if depth == "Quick" else "Provide a detailed explanation with examples."
    
    # Build response format requirement
    response_format = """
--- RESPONSE FORMAT ---
Structure your answer as follows:

**Short Answer:**
[2-3 sentences directly answering the question]

**Why This Matters For You:**
[Explain relevance using their session context if available; otherwise explain general importance]

**What To Do Next:**
[Only reference existing training plan/drill recommendations from their session; do NOT invent new recommendations]

**Sources:**
[List KB sources used: "Based on [Source 1: Title], [Source 2: Title]"]
"""
    
    # Build complete prompt
    prompt = f"""{guardrails}

{context_section}

{session_section}

--- USER QUESTION ---
{question}

--- INSTRUCTIONS ---
Mode: {mode}
{mode_instruction}

Depth: {depth}
{depth_instruction}

{response_format}
"""
    
    return prompt


def call_llm(prompt: str, api_key: Optional[str] = None) -> str:
    """
    Call LLM API to generate response.
    
    Args:
        prompt: Complete prompt
        api_key: API key (or None to use env var)
        
    Returns:
        LLM response text
    """
    # Check for Ollama first (local, no API key needed)
    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    
    if use_ollama:
        try:
            return _call_ollama(prompt)
        except ImportError:
            return """⚠️ **Ollama Not Installed**

To use local LLM with Ollama:
1. Download and install Ollama: https://ollama.ai
2. Run: `ollama pull llama3.2:3b`
3. Set environment variable: `USE_OLLAMA=true`

For now, please review the retrieved knowledge base sources above."""
        except Exception as e:
            return f"⚠️ **Ollama Error**: {str(e)}\n\nPlease review the retrieved knowledge base sources above."
    
    # Get API key from env if not provided
    if api_key is None:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    
    # If no API key and not using Ollama, return stub response
    if not api_key:
        return """⚠️ **LLM Not Configured**

I don't have an LLM configured. Choose one option:

**Option 1: Local LLM (Recommended - Free)**
1. Install Ollama: https://ollama.ai/download
2. Run: `ollama pull llama3.2:3b`
3. Set environment variable: `USE_OLLAMA=true`
4. Restart Streamlit

**Option 2: Cloud LLM (Requires API Key)**
- Set `OPENAI_API_KEY` for OpenAI GPT models
- Set `ANTHROPIC_API_KEY` for Anthropic Claude models

For now, please review the retrieved knowledge base sources above - they contain information relevant to your question."""
    
    try:
        # Try OpenAI first
        if os.getenv("OPENAI_API_KEY"):
            return _call_openai(prompt, api_key)
        # Then try Anthropic
        elif os.getenv("ANTHROPIC_API_KEY"):
            return _call_anthropic(prompt, api_key)
        else:
            return "Error: No supported LLM API key found"
            
    except ImportError:
        return """⚠️ **LLM Libraries Not Installed**

To use LLM-powered explanations, install one of:
- `pip install openai` for OpenAI
- `pip install anthropic` for Anthropic Claude

For now, please review the retrieved knowledge base sources above."""
    except Exception as e:
        return f"⚠️ **LLM Error**: {str(e)}\n\nPlease review the retrieved knowledge base sources above."


def _call_openai(prompt: str, api_key: str) -> str:
    """Call OpenAI API."""
    import openai
    
    client = openai.OpenAI(api_key=api_key)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Cost-effective model
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=800
    )
    
    return response.choices[0].message.content


def _call_anthropic(prompt: str, api_key: str) -> str:
    """Call Anthropic API."""
    import anthropic
    
    client = anthropic.Anthropic(api_key=api_key)
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=800,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.content[0].text


def _call_ollama(prompt: str, model: str = "llama3.2:3b") -> str:
    """
    Call Ollama local LLM.
    
    Args:
        prompt: Complete prompt
        model: Ollama model name (default: llama3.2:3b)
        
    Returns:
        LLM response text
    """
    import requests
    
    # Get model from environment or use default
    model = os.getenv("OLLAMA_MODEL", model)
    
    # Ollama API endpoint (default local)
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    
    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 500  # Reduced for faster responses
                }
            },
            timeout=180  # Increased timeout to 3 minutes
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "No response generated")
        else:
            return f"Ollama API error (status {response.status_code}): {response.text}"
            
    except requests.exceptions.ConnectionError:
        return """⚠️ **Ollama Not Running**

Ollama is installed but not running. To start it:

**Windows:**
- Ollama runs automatically after installation
- If not running, launch "Ollama" from Start Menu

**If Ollama isn't installed:**
1. Download: https://ollama.ai/download
2. Install and restart
3. Run: `ollama pull llama3.2:3b`

Please review the retrieved knowledge base sources above."""
    except Exception as e:
        return f"⚠️ **Ollama Error**: {str(e)}\n\nPlease review the retrieved knowledge base sources above."


def create_retrieval_only_response(
    question: str,
    retrieved_chunks: List[Dict],
    session_summary: str,
    retrieval_confidence: str
) -> str:
    """
    Create a response when LLM is not used (low confidence or strict grounding policy).
    
    Args:
        question: User's question
        retrieved_chunks: Retrieved KB chunks
        session_summary: Session summary
        retrieval_confidence: Confidence level
        
    Returns:
        Formatted response without LLM generation
    """
    response = f"""**Retrieval-Only Response** (Confidence: {retrieval_confidence})

I found some relevant information in the knowledge base, but the match isn't strong enough for me to provide a confident AI-generated answer. Here's what I found:

"""
    
    if retrieved_chunks:
        response += "**Relevant Knowledge Base Sources:**\n\n"
        for i, chunk in enumerate(retrieved_chunks, 1):
            response += f"**{i}. {chunk['title']}** (relevance: {chunk['score']:.2f})\n"
            response += f"{chunk['text'][:300]}...\n\n"
        
        response += """---

**To Get a Better Answer:**
- Try rephrasing your question more specifically
- Check if your question relates to concepts covered in the knowledge base
- Ensure you've selected an appropriate answer mode

"""
    else:
        response += """**No relevant sources found** in the knowledge base.

**To Get an Answer:**
- Try rephrasing your question
- Ask about tennis fundamentals, biomechanics, or training concepts
- Check that the knowledge base index is built (`python rag/index_kb.py`)

"""
    
    # Add clarifying question suggestions
    response += "**Try asking:**\n"
    if "hip" in question.lower() or "rotation" in question.lower():
        response += "- What is the target range for hip rotation in a backhand?\n"
        response += "- How can I improve my hip rotation?\n"
    elif "balance" in question.lower() or "drift" in question.lower():
        response += "- What causes balance drift during strokes?\n"
        response += "- How do I improve my balance during contact?\n"
    elif "recovery" in question.lower():
        response += "- What is recovery time and why does it matter?\n"
        response += "- How can I reduce my recovery time?\n"
    else:
        response += "- How do I improve my [specific metric]?\n"
        response += "- What does [specific term] mean?\n"
        response += "- How should I train for [specific goal]?\n"
    
    return response


def ask_coach(question: str, 
              retrieved_chunks: List[Dict],
              retrieval_confidence: str,
              session_summary: Optional[str] = None,
              report_path: str = "outputs/report.md",
              mode: str = "Explain my session",
              depth: str = "Quick",
              strict_grounding: bool = True) -> Dict:
    """
    Complete pipeline: build prompt and get LLM response with grounding policy.
    
    Args:
        question: User's question
        retrieved_chunks: Retrieved KB chunks
        retrieval_confidence: "High", "Medium", or "Low"
        session_summary: Optional session summary (extracted if None)
        report_path: Path to report for session extraction
        mode: Answer mode
        depth: Answer depth
        strict_grounding: If True, enforce strict grounding policy
        
    Returns:
        Dict with 'answer', 'prompt', 'session_summary', 'num_sources', 
        'used_llm', 'grounding_policy_applied'
    """
    # Extract session summary if not provided
    if session_summary is None:
        session_summary = extract_session_summary(report_path)
    
    # Apply grounding policy
    if strict_grounding and retrieval_confidence == "Low":
        # Do NOT call LLM for low confidence retrieval
        answer = create_retrieval_only_response(
            question, retrieved_chunks, session_summary, retrieval_confidence
        )
        
        return {
            'answer': answer,
            'prompt': None,
            'session_summary': session_summary,
            'num_sources': len(retrieved_chunks),
            'used_llm': False,
            'grounding_policy_applied': True,
            'policy_reason': 'Low retrieval confidence - strict grounding prevented LLM call'
        }
    
    # Build prompt with mode and depth
    prompt = build_prompt(
        question, retrieved_chunks, session_summary, 
        mode, depth, strict_grounding
    )
    
    # Call LLM
    answer = call_llm(prompt)
    
    # Add source citation reminder if Medium confidence
    if strict_grounding and retrieval_confidence == "Medium":
        answer += "\n\n---\n**Note**: This answer is based on moderately relevant sources. Please verify against the cited sources above."
    
    return {
        'answer': answer,
        'prompt': prompt,
        'session_summary': session_summary,
        'num_sources': len(retrieved_chunks),
        'used_llm': True,
        'grounding_policy_applied': strict_grounding,
        'policy_reason': None
    }


if __name__ == "__main__":
    # Test LLM module
    print("=" * 60)
    print("Testing Coach AI LLM Module")
    print("=" * 60)
    
    # Mock retrieved chunks
    mock_chunks = [
        {
            'title': 'Hip Rotation Fundamentals',
            'text': 'Hip rotation is critical for power generation. Minimum 40-45° for backhand...',
            'score': 0.85,
            'filename': 'backhand_fundamentals.md'
        }
    ]
    
    question = "Why is my hip rotation score low?"
    
    print(f"\nQuestion: {question}\n")
    
    result = ask_coach(question, mock_chunks)
    
    print("Answer:")
    print(result['answer'])
    print(f"\nSources used: {result['num_sources']}")

