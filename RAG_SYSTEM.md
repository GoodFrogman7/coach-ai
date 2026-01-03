# Coach AI RAG System Documentation

## Overview

The Coach AI RAG (Retrieval-Augmented Generation) system provides an interactive "Ask Coach AI" interface that combines:

1. **Knowledge Base**: 11 comprehensive markdown files covering tennis fundamentals, biomechanics, and training concepts
2. **TF-IDF Retrieval**: Semantic search to find relevant knowledge base content
3. **LLM Integration**: Optional LLM (OpenAI GPT or Anthropic Claude) for natural language explanations
4. **Session Context**: Integration with user's current session data

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Question                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              TF-IDF Retrieval Engine                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Knowledge Base (11 .md files → 20 chunks)          │  │
│  │  - Backhand/Forehand/Serve Fundamentals             │  │
│  │  - Footwork & Movement                              │  │
│  │  - Fatigue vs Technique                             │  │
│  │  - Recovery Time & Balance Drift                    │  │
│  │  - Match Readiness & Training Load                  │  │
│  │  - Filming & Drill Explanations                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Returns: Top-K relevant chunks + confidence score          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   Prompt Builder                             │
│  Combines:                                                   │
│  - Guardrails (explanation-only, no medical advice)         │
│  - Retrieved KB chunks                                      │
│  - User's current session summary                           │
│  - User question                                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLM (Optional)                            │
│  - OpenAI GPT-4o-mini (if OPENAI_API_KEY set)              │
│  - Anthropic Claude (if ANTHROPIC_API_KEY set)             │
│  - Fallback: Show retrieved KB excerpts only                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Answer + Sources                            │
│  - Natural language explanation                             │
│  - Retrieved KB sources with relevance scores               │
│  - Current session context                                  │
│  - Confidence assessment                                    │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Knowledge Base (`kb/`)

11 markdown files covering:

- **backhand_fundamentals.md**: Two-handed backhand technique, phases, common issues
- **forehand_fundamentals.md**: Forehand technique, hip rotation, grip considerations
- **serve_fundamentals.md**: Serve mechanics, ball toss, kinetic chain
- **footwork_fundamentals.md**: Split step, lateral movement, recovery
- **fatigue_vs_technique.md**: Differentiating fatigue from technique issues
- **recovery_time_explained.md**: What recovery time means, improvement strategies
- **balance_drift_explained.md**: Stability metrics, common causes, corrections
- **drill_explanations.md**: Purpose and execution of common drills
- **filming_for_analysis.md**: Camera setup, lighting, video quality
- **match_readiness_explained.md**: Understanding readiness scores
- **training_load_guidance.md**: Session types, intensity levels, decision logic

**Maintenance**: Add new .md files to `kb/` and re-run indexing.

### 2. Indexing (`rag/index_kb.py`)

**Purpose**: Loads KB files, chunks them, creates TF-IDF index.

**Usage**:
```bash
python rag/index_kb.py
```

**Output**:
- `rag/vectorizer.pkl`: TF-IDF vectorizer
- `rag/tfidf_matrix.pkl`: Document-term matrix
- `rag/doc_metadata.json`: Chunk metadata (text, title, filename)
- `rag/index_meta.json`: Index statistics

**Re-run when**: KB files are added/modified.

### 3. Retrieval (`rag/retrieve.py`)

**Purpose**: Finds relevant KB chunks for user queries.

**API**:
```python
from rag import retrieve_context

result = retrieve_context(
    query="How do I improve my hip rotation?",
    top_k=5
)

# Returns:
# {
#     'results': [
#         {'text': '...', 'title': '...', 'score': 0.85, ...},
#         ...
#     ],
#     'confidence': 'High' | 'Medium' | 'Low',
#     'confidence_explanation': '...'
# }
```

**Confidence Levels**:
- **High**: max_score > 0.3, avg_score > 0.15
- **Medium**: max_score > 0.15, avg_score > 0.08
- **Low**: Below thresholds or no results

### 4. LLM Answering (`rag/coach_llm.py`)

**Purpose**: Builds prompts with guardrails and calls LLM.

**API**:
```python
from rag import ask_coach

result = ask_coach(
    question="Why is my hip rotation low?",
    retrieved_chunks=[...],
    session_summary="..."
)

# Returns:
# {
#     'answer': 'Natural language explanation...',
#     'prompt': 'Full prompt sent to LLM...',
#     'session_summary': '...',
#     'num_sources': 3
# }
```

**LLM Configuration**:
- Set `OPENAI_API_KEY` for OpenAI GPT models
- Set `ANTHROPIC_API_KEY` for Anthropic Claude
- If neither set: Returns stub message + shows KB excerpts

**Guardrails**:
- Explanation-only (no decision-making)
- No training plan modifications
- No medical advice
- Honest about limitations

### 5. Streamlit Integration (`streamlit_app.py`)

**Location**: "🤖 Ask Coach" screen

**Features**:
- Quick example questions (buttons)
- Text input for custom questions
- RAG-powered answers with sources
- Context expanders (session + KB sources)
- Confidence warnings for low-quality retrieval

**Workflow**:
1. User enters/selects question
2. System retrieves relevant KB chunks
3. Extracts current session summary
4. Builds prompt with guardrails
5. Calls LLM (or shows fallback)
6. Displays answer + sources

## Setup Instructions

### 1. Install Dependencies

```bash
pip install scikit-learn  # Already in requirements.txt
```

**Optional** (for LLM):
```bash
pip install openai        # For OpenAI GPT
# OR
pip install anthropic     # For Anthropic Claude
```

### 2. Build Knowledge Base Index

```bash
python rag/index_kb.py
```

Expected output:
```
============================================================
Coach AI - Knowledge Base Indexing
============================================================
Loaded 11 KB documents
Created 20 chunks from 11 documents
Creating TF-IDF index...
[OK] Index created: 20 chunks, 4602 vocabulary terms
[OK] Saved to: rag/
============================================================
[OK] Indexing complete!
============================================================
```

### 3. (Optional) Configure LLM

**For OpenAI**:
```bash
export OPENAI_API_KEY="sk-..."
```

**For Anthropic**:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Without LLM**: System will still work, showing retrieved KB excerpts only.

### 4. Run Streamlit

```bash
python -m streamlit run streamlit_app.py
```

Navigate to "🤖 Ask Coach" screen.

## Usage Examples

### Example 1: Technique Question

**Question**: "How do I improve my hip rotation?"

**Expected**:
- Retrieves: Backhand/Forehand fundamentals
- Confidence: Medium-High
- Answer: Explains hip rotation importance, target ranges, wall drills
- Sources: Backhand fundamentals, Drill explanations

### Example 2: Metrics Explanation

**Question**: "What does my match readiness score mean?"

**Expected**:
- Retrieves: Match readiness explained
- Confidence: High
- Answer: Explains readiness levels, contributors, how to use it
- Sources: Match readiness explained

### Example 3: Session Context

**Question**: "Why is my recovery time high today?"

**Expected**:
- Retrieves: Recovery time explained, Fatigue vs technique
- Session context: Current session metrics
- Answer: Personalized explanation based on session + KB
- Sources: Recovery time explained, Fatigue analysis

## Extending the System

### Add New KB Content

1. Create new markdown file in `kb/`:
   ```markdown
   # New Topic Title
   
   ## Section 1
   Content...
   
   ## Section 2
   More content...
   ```

2. Re-index:
   ```bash
   python rag/index_kb.py
   ```

3. Test retrieval:
   ```bash
   python rag/retrieve.py
   ```

### Improve Retrieval Quality

**Current**: TF-IDF (simple, fast, no external dependencies)

**Potential upgrades**:
- Sentence-BERT embeddings (better semantic understanding)
- Hybrid search (keyword + semantic)
- Query expansion
- Re-ranking

**Trade-off**: Complexity vs. dependency management

### Add More LLM Providers

Edit `rag/coach_llm.py`:

```python
def _call_custom_provider(prompt: str, api_key: str) -> str:
    # Your implementation
    pass
```

## Safety & Guardrails

### 1. Explanation-Only

LLM prompt includes strict guardrails:
```
You provide EXPLANATIONS ONLY. You do NOT make decisions or recommendations.
You do NOT modify training plans, drill recommendations, or readiness assessments.
```

### 2. No Medical Advice

Explicit prohibition:
```
You do NOT provide medical advice or injury diagnosis.
```

### 3. Honest About Limitations

Instructs LLM:
```
If unsure or if information is missing, say so clearly.
```

### 4. Retrieval Confidence

Low confidence retrieval triggers warning:
```
⚠️ Low Confidence Retrieval
The knowledge base may not have specific information about your question.
```

## Testing

### Test Indexing

```bash
python rag/index_kb.py
```

Expected: 20 chunks, ~4600 vocabulary terms

### Test Retrieval

```bash
python rag/retrieve.py
```

Expected: 4 test queries with High/Medium confidence

### Test LLM Module

```bash
python rag/coach_llm.py
```

Expected: Mock answer (stub if no API key)

## Troubleshooting

### Issue: "Index not found"

**Solution**: Run `python rag/index_kb.py`

### Issue: "LLM not configured"

**Options**:
1. Set API key (see Setup #3)
2. Use fallback mode (KB excerpts only)

### Issue: Low retrieval confidence

**Solutions**:
- Rephrase question (more specific or more general)
- Add relevant KB content
- Check if topic is covered in KB

### Issue: Unicode errors in Windows console

**Cause**: Windows cp1252 encoding
**Impact**: Test scripts only (print statements)
**Workaround**: Run in Streamlit (renders properly in browser)

## Performance

**Indexing**: ~1-2 seconds for 11 docs, 20 chunks
**Retrieval**: <100ms per query
**LLM call**: 1-3 seconds (depends on provider)
**Total latency**: ~2-4 seconds for full Q&A

## Limitations

1. **Retrieval**: TF-IDF is keyword-based, not fully semantic
2. **Chunk size**: 500 tokens may miss context for very long documents
3. **No session history**: Each question is independent
4. **LLM optional**: Requires API key for full experience
5. **No feedback loop**: Doesn't learn from user interactions

## Future Enhancements

### Phase 1 (Current)
✅ TF-IDF retrieval  
✅ LLM integration (OpenAI/Anthropic)  
✅ Streamlit UI  
✅ Session context integration  

### Phase 2 (Potential)
- [ ] Sentence-BERT embeddings
- [ ] Multi-turn conversations
- [ ] User feedback collection
- [ ] Query history and favorites

### Phase 3 (Advanced)
- [ ] Fine-tuned embedding model
- [ ] Personalized retrieval (based on user history)
- [ ] Multi-modal support (images, videos)
- [ ] Active learning from feedback

## License & Usage

This RAG system is part of Coach AI and follows the same license and usage terms.

**Key principle**: This system is for **explanation and education**, not for decision-making or medical advice.

