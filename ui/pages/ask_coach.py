"""
Ask Coach page: RAG-grounded Q&A over the knowledge base and session.
"""
import streamlit as st
import sys

from ui.data import get_recent_sessions


@st.cache_data(show_spinner=False)
def get_cached_answer(
    question: str,
    session_id: str,
    mode: str,
    depth: str,
    strict_grounding: bool,
    base_dir: str = "outputs"
):
    """
    Cached wrapper for retrieval + LLM answer generation.
    
    Caches by: (question, session_id, mode, depth, strict_grounding)
    Returns complete answer object to avoid duplicate Ollama calls.
    Session memory handled outside cache to avoid hashing issues.
    """
    from rag import retrieve_context, ask_coach, extract_session_summary
    import os
    
    # Retrieve relevant context (with embeddings if available)
    # Note: session_memory handled outside cache in render_ask_coach
    retrieval_result = retrieve_context(
        question, 
        top_k=5, 
        use_embeddings=True,
        session_memory=None  # Don't use session_memory in cached function
    )
    retrieved_chunks = retrieval_result['results']
    confidence = retrieval_result['confidence']
    confidence_explanation = retrieval_result['confidence_explanation']
    retrieval_method = retrieval_result.get('method_used', 'tfidf')
    retrieval_stats = retrieval_result.get('retrieval_stats', {})
    
    # Extract session summary
    if session_id:
        report_path = f"{base_dir}/{session_id}/report.md"
        if not os.path.exists(report_path):
            report_path = f"{base_dir}/report.md"
    else:
        sessions = get_recent_sessions(base_dir, n=1)
        report_path = f"{base_dir}/report.md" if sessions else None
    
    session_summary = extract_session_summary(report_path) if report_path and os.path.exists(report_path) else "No recent session data available"
    
    # Get LLM answer with grounding policy
    result = ask_coach(
        question=question,
        retrieved_chunks=retrieved_chunks,
        retrieval_confidence=confidence,
        session_summary=session_summary,
        report_path=report_path,
        mode=mode,
        depth=depth,
        strict_grounding=strict_grounding
    )
    
    # Return complete answer object
    return {
        'answer': result['answer'],
        'used_llm': result.get('used_llm', False),
        'grounding_policy_applied': result.get('grounding_policy_applied', False),
        'policy_reason': result.get('policy_reason', None),
        'retrieved_chunks': retrieved_chunks,
        'confidence': confidence,
        'confidence_explanation': confidence_explanation,
        'retrieval_method': retrieval_method,
        'retrieval_stats': retrieval_stats,
        'session_summary': session_summary,
        'cached': False  # Will be set to True on subsequent calls
    }


def render_ask_coach(base_dir="outputs", selected_session=None):
    """Render Ask Coach AI screen with RAG-powered Q&A, UI controls, and Q&A history."""
    st.title("🤖 Ask Coach AI")
    
    st.markdown("Get AI-generated explanations with strict grounding in your data and knowledge base.")
    
    # Import RAG modules
    try:
        from rag import retrieve_context, ask_coach, extract_session_summary, log_qa_interaction, get_recent_questions, load_qa_log
        from rag.session_memory import get_or_create_session_memory
        rag_available = True
    except ImportError:
        st.error("⚠️ RAG system not available. Please ensure the `rag` module is installed.")
        rag_available = False
        return
    
    # Initialize session memory (session-only, no persistence)
    session_memory = get_or_create_session_memory(st.session_state)
    
    # Check if index exists
    import os
    if not os.path.exists("rag/index_meta.json"):
        st.warning("⚠️ Knowledge base index not found.")
        st.markdown("**One-click setup:**")
        st.code("python rag/index_kb.py", language="bash")
        if st.button("📖 Show Setup Instructions"):
            st.info("""
            1. Open a terminal in the project directory
            2. Run: `python rag/index_kb.py`
            3. Wait ~2 seconds for indexing to complete
            4. Refresh this page
            """)
        return
    
    # Initialize session state for question input (SINGLE SOURCE OF TRUTH)
    if "user_question" not in st.session_state:
        st.session_state.user_question = ""
    
    # Initialize session state for answer display
    if "show_answer" not in st.session_state:
        st.session_state.show_answer = False
    
    if "current_answer" not in st.session_state:
        st.session_state.current_answer = None
    
    # Two-column layout: Main Q&A | Recent Questions sidebar
    col_main, col_history = st.columns([2, 1])
    
    with col_history:
        st.subheader("📜 Recent Questions")
        
        if selected_session:
            recent_qa = get_recent_questions(selected_session, n=5, output_dir=base_dir)
            
            if recent_qa:
                for i, qa in enumerate(recent_qa):
                    # Create button for each past question
                    if st.button(f"Q: {qa['question'][:40]}...", key=f"past_q_{i}", use_container_width=True):
                        # Load saved answer WITHOUT calling retrieval or LLM
                        st.session_state.user_question = qa['question']
                        st.session_state.show_answer = True
                        st.session_state.current_answer = {
                            'answer': qa['answer'],
                            'used_llm': True,  # Assume was LLM generated
                            'grounding_policy_applied': qa.get('strict_grounding', True),
                            'policy_reason': None,
                            'retrieved_chunks': qa.get('sources', []),
                            'confidence': qa.get('retrieval_confidence', 'Unknown'),
                            'confidence_explanation': f"Loaded from saved answer (asked {qa['timestamp'][:19]})",
                            'session_summary': "From saved Q&A log",
                            'cached': True,
                            'from_history': True
                        }
                        st.rerun()
                    
                    # Show preview in expander
                    with st.expander(f"Preview", expanded=False):
                        st.caption(f"**Asked:** {qa['timestamp'][:19]}")
                        st.caption(f"**Confidence:** {qa['retrieval_confidence']}")
                        st.caption(f"**Mode:** {qa['mode']}")
                        if qa.get('sources'):
                            st.caption(f"**Sources:** {len(qa['sources'])}")
            else:
                st.info("No questions asked yet for this session.")
        else:
            st.info("Select a session to view Q&A history.")
    
    with col_main:
        # UI Controls
        st.subheader("⚙️ Answer Controls")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            mode = st.selectbox(
                "Mode",
                ["Explain my session", "Teach the concept", "Drill how-to"],
                help="Choose the focus of the answer"
            )
        
        with col2:
            depth = st.selectbox(
                "Depth",
                ["Quick", "Detailed"],
                help="Quick: 2-3 paragraphs, Detailed: comprehensive explanation"
            )
        
        with col3:
            strict_grounding = st.checkbox(
                "Strict grounding",
                value=True,
                help="Recommended: Prevents LLM hallucination by enforcing source citations"
            )
        
        if strict_grounding:
            st.info("🛡️ **Strict Grounding ON**: Low-confidence retrievals won't call LLM (prevents hallucination)")
        
        st.markdown("---")
        
        # Question input
        st.subheader("💬 Ask Your Question")
        
        # Example questions as buttons
        example_questions = [
            "How do I improve my hip rotation?",
            "What causes balance drift?",
            "Why is my recovery time important?",
            "How should I film my strokes?",
            "What does my match readiness score mean?",
            "When should I do recovery sessions vs full training?"
        ]
        
        st.markdown("**Quick Examples:**")
        cols = st.columns(3)
        
        # Handle example button clicks - set session_state directly
        for i, q in enumerate(example_questions):
            with cols[i % 3]:
                if st.button(f"💡 {q[:30]}...", key=f"example_{i}"):
                    st.session_state.user_question = q
                    st.session_state.show_answer = False  # Reset answer display
                    st.rerun()
        
        # Text input - SINGLE SOURCE OF TRUTH using session_state
        question = st.text_input(
            "Or type your own question:",
            value=st.session_state.user_question,
            placeholder="e.g., Why is my hip rotation score low?",
            key="question_input_widget",
            on_change=lambda: setattr(st.session_state, 'user_question', st.session_state.question_input_widget)
        )
        
        # Get answer button
        if st.button("🔍 Get Answer", type="primary", key="get_answer_btn"):
            # Read question from session state (SINGLE SOURCE OF TRUTH)
            current_question = st.session_state.user_question.strip()
            
            if not current_question:
                st.warning("Please enter a question.")
            else:
                # Call cached answer function
                with st.spinner("🤔 Thinking..."):
                    # Get cached answer (will only call LLM once per unique combination)
                    result = get_cached_answer(
                        question=current_question,
                        session_id=selected_session or "",
                        mode=mode,
                        depth=depth,
                        strict_grounding=strict_grounding,
                        base_dir=base_dir
                    )
                    
                    # Mark as cached if this is not first call
                    # (Streamlit cache will make subsequent calls instant)
                    result['cached'] = True
                    
                    # Update session memory AFTER getting cached result
                    if session_memory and result.get('retrieval_stats'):
                        session_memory.add_query(
                            query=current_question,
                            intent=result['retrieval_stats'].get('intent', 'UNKNOWN'),
                            kb_sources=[c.get('filename', '') for c in result.get('retrieved_chunks', []) if isinstance(c, dict)],
                            confidence=result.get('confidence', 'Low'),
                            top_score=result['retrieval_stats'].get('top1_score', 0.0)
                        )
                    
                    # Log Q&A interaction
                    if selected_session:
                        log_qa_interaction(
                            session_id=selected_session,
                            question=current_question,
                            answer=result['answer'],
                            retrieved_sources=result['retrieved_chunks'],
                            retrieval_confidence=result['confidence'],
                            mode=mode,
                            depth=depth,
                            strict_grounding=strict_grounding,
                            output_dir=base_dir
                        )
                    
                    # Store answer in session state
                    st.session_state.show_answer = True
                    st.session_state.current_answer = result
        
        # Display answer if available (outside button click to persist across reruns)
        if st.session_state.show_answer and st.session_state.current_answer:
            result = st.session_state.current_answer
            
            st.markdown("---")
            st.subheader("💡 Coach AI Answer")
            
            # Show grounding policy notice if applied
            if result.get('grounding_policy_applied') and not result.get('used_llm'):
                st.warning(f"🛡️ **Grounding Policy Applied**: {result.get('policy_reason')}")
            
            st.markdown(result['answer'])
            
            # Developer visibility caption
            llm_status = "Yes" if result.get('used_llm') else "No"
            confidence_status = result.get('confidence', 'Unknown')
            cached_status = "Yes (from history)" if result.get('from_history') else ("Yes" if result.get('cached') else "No")
            retrieval_method = result.get('retrieval_method', 'tfidf').upper()
            st.caption(f"🔧 LLM used: {llm_status} | Source confidence: {confidence_status} | Cached: {cached_status} | Retrieval: {retrieval_method}")
            
            st.markdown("---")
            
            # Sources display (always visible)
            st.subheader("📚 Sources Used")
            
            # Show intent classification
            retrieval_stats = result.get('retrieval_stats', {})
            intent = retrieval_stats.get('intent', 'UNKNOWN')
            intent_desc = retrieval_stats.get('intent_description', 'General inquiry')
            
            # Check for recurring issues (session memory)
            has_recurring_issue = retrieval_stats.get('recurring_issue', False)
            issue_topics = retrieval_stats.get('issue_topics', [])
            
            if has_recurring_issue and issue_topics:
                # Display recurring issue notice
                topics_str = ', '.join(issue_topics)
                st.info(f"🔄 **Recurring Topic:** This question relates to **{topics_str}**, which you've asked about earlier in this session.")
            
            if intent != 'UNKNOWN':
                # Show intent badge with color coding
                intent_colors = {
                    'WHY': '🔍',
                    'HOW': '🛠️',
                    'WHAT': '📖',
                    'DIAGNOSE': '🔬',
                    'COMPARE': '⚖️',
                }
                intent_icon = intent_colors.get(intent, '❓')
                st.info(f"{intent_icon} **Detected Intent:** {intent} — {intent_desc}")
            
            # Show retrieval method and stats
            if retrieval_stats:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Method", result.get('retrieval_method', 'tfidf').upper())
                with col2:
                    st.metric("Intent", intent)
                with col3:
                    st.metric("Top1 Score", f"{retrieval_stats.get('top1_score', 0.0):.3f}")
                with col4:
                    st.metric("Avg Top3", f"{retrieval_stats.get('avg_top3', 0.0):.3f}")
            
            st.markdown(f"**Retrieval Confidence:** {result['confidence']}")
            st.caption(result['confidence_explanation'])
            
            # Suggest rephrasings for low confidence
            if result['confidence'] == 'Low' and not result.get('from_history'):
                st.warning("💡 **Try Rephrasing Your Question:**")
                
                # Detect topic and suggest rephrasings
                question_lower = st.session_state.user_question.lower()
                suggestions = []
                
                if any(word in question_lower for word in ['balance', 'drift', 'sway', 'lean']):
                    suggestions = [
                        "Why do I sway sideways when hitting?",
                        "What causes me to lose balance during strokes?",
                        "How do I stop leaning sideways?"
                    ]
                elif any(word in question_lower for word in ['recovery', 'recover', 'slow', 'back']):
                    suggestions = [
                        "Why is recovery time important?",
                        "How do I get back to ready position faster?",
                        "What slows down my recovery?"
                    ]
                elif any(word in question_lower for word in ['split', 'step', 'footwork', 'move']):
                    suggestions = [
                        "How do I improve my split step?",
                        "When should I split step?",
                        "What is good footwork in tennis?"
                    ]
                else:
                    suggestions = [
                        "Try being more specific about what you want to know",
                        "Ask about a specific metric or technique",
                        "Rephrase using terms from your analysis report"
                    ]
                
                for suggestion in suggestions:
                    st.caption(f"• {suggestion}")
            
            retrieved_chunks = result.get('retrieved_chunks', [])
            if retrieved_chunks:
                for i, chunk in enumerate(retrieved_chunks, 1):
                    # Handle both dict chunks and source records from history
                    if isinstance(chunk, dict):
                        title = chunk.get('title', 'Unknown')
                        score = chunk.get('score', 0.0)
                        filename = chunk.get('filename', 'unknown.md')
                        st.markdown(f"{i}. **{title}** (relevance: {score:.2f}) - *{filename}*")
            else:
                st.info("No specific KB sources found.")
            
            # Context used expander
            with st.expander("🔍 Full Context Details", expanded=False):
                st.markdown("**Your Current Session:**")
                st.text(result.get('session_summary', 'No session data'))
                
                if retrieved_chunks and not result.get('from_history'):
                    st.markdown("---")
                    st.markdown("**Retrieved Knowledge Base Excerpts:**")
                    for i, chunk in enumerate(retrieved_chunks, 1):
                        if isinstance(chunk, dict) and 'text' in chunk:
                            st.markdown(f"### Source {i}: {chunk['title']}")
                            st.markdown(f"*From: {chunk['filename']}*")
                            st.markdown(chunk['text'][:500] + "...")
                            st.markdown("---")
        
        st.markdown("---")
        
        # Rebuild KB Index section
        with st.expander("🔧 Rebuild Knowledge Base Index", expanded=False):
            st.markdown("""
            Rebuild the retrieval index after:
            - Adding new KB files
            - Editing existing KB content
            - Installing sentence-transformers
            
            This will regenerate both TF-IDF and embedding indices.
            """)
            
            col_confirm, col_rebuild = st.columns([3, 1])
            
            with col_confirm:
                rebuild_confirmed = st.checkbox(
                    "I understand this will take 30-60 seconds",
                    key="rebuild_confirm"
                )
            
            with col_rebuild:
                if st.button("🔨 Rebuild", type="secondary", disabled=not rebuild_confirmed):
                    with st.spinner("Rebuilding indices..."):
                        import subprocess
                        import sys
                        
                        try:
                            # Rebuild TF-IDF index
                            st.info("Step 1/2: Rebuilding TF-IDF index...")
                            result1 = subprocess.run(
                                [sys.executable, "rag/index_kb.py"],
                                capture_output=True,
                                text=True,
                                timeout=60
                            )
                            
                            if result1.returncode == 0:
                                st.success("✓ TF-IDF index rebuilt")
                            else:
                                st.error(f"TF-IDF indexing failed: {result1.stderr}")
                            
                            # Rebuild embedding index
                            st.info("Step 2/2: Rebuilding embedding index...")
                            result2 = subprocess.run(
                                [sys.executable, "rag/embedding_index.py"],
                                capture_output=True,
                                text=True,
                                timeout=60
                            )
                            
                            if result2.returncode == 0:
                                st.success("✓ Embedding index rebuilt")
                            else:
                                st.warning(f"Embedding indexing not available (sentence-transformers may not be installed)")
                            
                            st.success("🎉 Index rebuild complete! Refresh the page to use the new index.")
                            
                            # Clear cache to force reload
                            st.cache_data.clear()
                            
                        except subprocess.TimeoutExpired:
                            st.error("⏱️ Indexing timed out (>60s). Try running manually.")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
        
        st.markdown("---")
        
        # Guidelines
        st.subheader("📋 Guidelines")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **✅ What Coach AI CAN do:**
            - Explain biomechanical metrics
            - Clarify training recommendations
            - Provide tennis technique fundamentals
            - Help interpret your data
            """)
        
        with col2:
            st.markdown("""
            **❌ What Coach AI CANNOT do:**
            - Modify your training plans
            - Override analysis decisions
            - Provide medical/injury advice
            - Make performance predictions
            """)


# ============================================================================
# Main App
