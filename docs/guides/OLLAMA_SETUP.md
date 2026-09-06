# Ollama Setup Guide for Coach AI

## What is Ollama?

Ollama allows you to run powerful LLMs (like Llama 3.2) **locally on your computer** - completely free, no API keys needed, and your data never leaves your machine.

## Installation Steps

### Step 1: Download and Install Ollama

1. **Download Ollama**:
   - Visit: https://ollama.ai/download
   - Download the Windows installer
   - Run the installer (it will install to `C:\Users\{YourName}\AppData\Local\Programs\Ollama`)

2. **Verify Installation**:
   ```bash
   ollama --version
   ```
   
   Expected output: `ollama version 0.x.x`

### Step 2: Download the LLM Model

Coach AI is configured to use **Llama 3.2 3B** (small, fast, good quality):

```bash
ollama pull llama3.2:3b
```

**Download size**: ~2GB  
**Time**: 2-5 minutes depending on internet speed  
**Disk space required**: ~2GB

**Alternative models** (optional):
```bash
# Larger, better quality (recommended if you have 16GB+ RAM)
ollama pull llama3.2:7b

# Even larger, best quality (requires 32GB+ RAM)
ollama pull llama3.1:8b

# Faster, smaller (good for testing)
ollama pull llama3.2:1b
```

### Step 3: Verify Ollama is Running

After installation, Ollama should run automatically. Verify:

```bash
ollama list
```

Expected output:
```
NAME              ID              SIZE      MODIFIED
llama3.2:3b       a80c4f17acd5    2.0 GB    2 minutes ago
```

### Step 4: Test Ollama (Optional)

```bash
ollama run llama3.2:3b "What is tennis?"
```

You should see a response about tennis. Press `Ctrl+D` or type `/bye` to exit.

### Step 5: Configure Coach AI to Use Ollama

**Windows PowerShell**:
```powershell
$env:USE_OLLAMA="true"
```

**Windows Command Prompt**:
```cmd
set USE_OLLAMA=true
```

**To make it permanent (Windows PowerShell - Run as Administrator)**:
```powershell
[System.Environment]::SetEnvironmentVariable('USE_OLLAMA', 'true', 'User')
```

### Step 6: Restart Streamlit

Stop the running Streamlit app (Ctrl+C in the terminal) and restart:

```bash
cd C:\coach_ai
python -m streamlit run streamlit_app.py
```

### Step 7: Test in Coach AI

1. Navigate to: http://localhost:8503
2. Click "🤖 Ask Coach" in the sidebar
3. Ask a question: "What causes balance drift?"
4. Click "Get Answer"

You should now see AI-generated answers from Ollama! 🎉

## Configuration Options

### Change Model

If you want to use a different model:

```powershell
$env:OLLAMA_MODEL="llama3.2:7b"
```

### Change Ollama Host

If running Ollama on a different machine:

```powershell
$env:OLLAMA_HOST="http://192.168.1.100:11434"
```

## Troubleshooting

### Issue: "Ollama Not Running"

**Solution**:
1. Check if Ollama is running:
   ```bash
   ollama list
   ```
2. If not running, launch "Ollama" from Windows Start Menu
3. Wait 5 seconds for it to start
4. Try again

### Issue: "Model not found"

**Solution**:
```bash
ollama pull llama3.2:3b
```

### Issue: Slow responses

**Solutions**:
1. Use a smaller model: `ollama pull llama3.2:1b`
2. Close other applications to free RAM
3. Check your computer meets minimum requirements

### Issue: "Connection refused"

**Solution**:
1. Ensure Ollama is installed
2. Restart Ollama:
   - Close Ollama from System Tray
   - Launch from Start Menu
3. Check port 11434 is not blocked by firewall

## System Requirements

### Minimum
- **RAM**: 8GB
- **Disk**: 4GB free space
- **OS**: Windows 10/11, macOS, or Linux
- **Model**: llama3.2:1b or llama3.2:3b

### Recommended
- **RAM**: 16GB+
- **Disk**: 10GB free space
- **GPU**: Not required but speeds up responses
- **Model**: llama3.2:3b or llama3.2:7b

### High-End
- **RAM**: 32GB+
- **Disk**: 20GB free space
- **GPU**: NVIDIA GPU with 8GB+ VRAM
- **Model**: llama3.1:8b or larger

## Performance Expectations

| Model | Size | Speed (Response Time) | Quality |
|-------|------|----------------------|---------|
| llama3.2:1b | ~1GB | 5-10 seconds | Good |
| llama3.2:3b | ~2GB | 10-20 seconds | Very Good |
| llama3.2:7b | ~4.7GB | 20-40 seconds | Excellent |
| llama3.1:8b | ~4.7GB | 20-40 seconds | Excellent |

*Times are approximate on a modern CPU without GPU acceleration*

## Comparison: Ollama vs Cloud APIs

| Feature | Ollama (Local) | Cloud APIs |
|---------|---------------|------------|
| Cost | Free | $0.01-0.10 per query |
| Privacy | 100% private | Data sent to provider |
| Speed | 10-30 seconds | 2-5 seconds |
| Quality | Very Good | Excellent |
| Setup | 5 minutes | 1 minute |
| Internet | Not required | Required |

## Best Practices

### For Coach AI

1. ✅ Use **llama3.2:3b** for best balance of speed/quality
2. ✅ Keep **Strict Grounding ON** (prevents hallucination)
3. ✅ Use **"Quick" depth** for faster responses
4. ✅ Close other heavy applications when using Coach AI
5. ✅ Pull model updates periodically: `ollama pull llama3.2:3b`

### For Demos/Investors

1. ✅ Pre-warm Ollama (run a test query before demo)
2. ✅ Use **llama3.2:3b** or larger for best answers
3. ✅ Have example questions ready
4. ✅ Explain "Local LLM" as a privacy/cost feature
5. ✅ Show source citations to demonstrate grounding

## Advanced: Vector Embeddings (Optional)

Want even better retrieval? Upgrade from TF-IDF to vector embeddings:

### Step 1: Install sentence-transformers

```bash
pip install sentence-transformers
```

### Step 2: Enable embeddings

```powershell
$env:USE_EMBEDDINGS="true"
```

### Step 3: Rebuild index

```bash
python rag/index_kb.py
```

**Benefits**:
- Better semantic understanding
- More accurate retrieval
- Higher confidence scores

**Trade-offs**:
- Slower indexing (~30 seconds)
- Requires ~500MB model download
- Slightly slower retrieval (~200ms vs ~50ms)

## FAQ

**Q: Is Ollama really free?**  
A: Yes, completely free and open-source.

**Q: Can I use Ollama offline?**  
A: Yes, once the model is downloaded, no internet is needed.

**Q: Will it work on my computer?**  
A: If you have 8GB+ RAM and Windows 10/11, yes.

**Q: How does it compare to ChatGPT?**  
A: Llama 3.2 3B is very capable for explanations. GPT-4 is better for complex reasoning, but Ollama is excellent for Coach AI's use case.

**Q: Can I use GPU acceleration?**  
A: Yes, Ollama automatically uses NVIDIA GPUs if available. Speeds up responses 5-10x.

**Q: What if I already have OpenAI/Anthropic API keys?**  
A: Keep using them! Set `USE_OLLAMA=false` or don't set it at all. Cloud APIs are faster but cost money.

## Support

- **Ollama Docs**: https://ollama.ai/docs
- **Ollama Discord**: https://discord.gg/ollama
- **Coach AI Issues**: https://github.com/your-repo/issues

## Next Steps

Once Ollama is working:

1. ✅ Try different question modes ("Explain my session", "Teach the concept", "Drill how-to")
2. ✅ Test strict grounding (toggle on/off to see the difference)
3. ✅ Review Q&A history in the sidebar
4. ✅ Check `outputs/{session_id}/qa_log.json` for audit trails
5. ✅ Experiment with different models for your use case

Enjoy your free, private, local AI coach! 🎾🤖

