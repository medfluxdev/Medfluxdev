# AI Model Configuration & Provider Setup

## Overview

Medflux supports multiple local AI providers for contract analysis. The system uses **dynamic provider discovery** – providers and models are detected at runtime rather than from a static inventory.

### Supported Providers

1. **Ollama** (Recommended)
   - Local LLM framework with vision support
   - Default model: Qwen3.5-VL (8B)
   - Endpoint: `http://127.0.0.1:11434`

2. **LM Studio**
   - Alternative local LLM runtime
   - Endpoint: `http://127.0.0.1:1234`
   - Via OpenAI-compatible API

3. **llama.cpp**
   - Pure C++ inference engine
   - Endpoint: `http://127.0.0.1:8000` (optional)

4. **OpenAI-Compatible**
   - Generic endpoint for OpenAI-compatible APIs
   - Configurable via `GENERIC_OPENAI_BASE_URL`

---

## Configuration

### Environment Variables

Set these in `backend/.env` or as system environment variables:

```bash
# Primary provider (default: ollama)
AI_PROVIDER=ollama

# Ollama configuration
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_NUM_GPU=           # Empty = Ollama decides; 999 = maximize GPU offload

# LM Studio configuration
LMSTUDIO_BASE_URL=http://127.0.0.1:1234

# llama.cpp configuration
LLAMA_CPP_BASE_URL=       # Leave empty if not using

# Generic OpenAI-compatible endpoint
GENERIC_OPENAI_BASE_URL=  # Leave empty if not using

# AI discovery timeout (seconds)
AI_DISCOVERY_TIMEOUT_SECONDS=2.0

# AI request timeout (seconds)
AI_REQUEST_TIMEOUT_SECONDS=300
```

### Model Selection

Model selection is done **per-organization** through the Web UI:

1. Go to **Admin Settings** → **AI Configuration**
2. Select a **Provider** from available providers
3. Select a **Model** from available models for that provider
4. Selection is stored in the database (`application_setting` table)

If a model selection becomes unavailable:
- The UI will report it as "unavailable"
- You must select a different model
- There is NO automatic fallback (fail-closed design)

---

## Ollama Setup

### Installation

1. **Download Ollama**: https://ollama.ai
2. **Install and run**: `ollama serve`
3. **Verify**: `curl http://127.0.0.1:11434/api/tags`

### Install Qwen3.5-VL (Recommended)

```bash
ollama pull qwen3.5:4b
# or for larger model:
ollama pull qwen3.5:7b
# or for vision support:
ollama pull qwen:vision
```

### Check Installed Models

```bash
# List all models
ollama list

# Output should include:
# qwen3.5:4b      <size>        <date>
# qwen3.5:7b      <size>        <date>
```

### Performance Tuning

Medflux extracts contract data efficiently. Typical analysis times:
- Small PDF (2-5 pages): 30-60 seconds
- Medium PDF (5-15 pages): 60-180 seconds
- Large PDF (15-50 pages): 180-300 seconds

If analysis is slower:
1. Check GPU offload: `ollama show qwen3.5:4b | grep -i layer`
2. Increase `OLLAMA_NUM_GPU` if GPU available
3. Check system load: `nvidia-smi` (if NVIDIA GPU)

---

## LM Studio Setup

### Installation

1. **Download LM Studio**: https://lmstudio.ai
2. **Install and launch**
3. **Load a model** in the LM Studio UI
4. **Start Local Server** on port 1234

### Configuration in Medflux

1. Start LM Studio with local server running
2. Go to Medflux Admin Settings → AI Configuration
3. Provider: **LM Studio**
4. Model: (will be discovered from the running LM Studio server)

---

## Provider Discovery Process

When Medflux starts (or when settings are refreshed):

1. **Detect Ollama**:
   ```
   GET http://127.0.0.1:11434/api/tags
   ```
   If successful → list all Ollama models

2. **Detect LM Studio**:
   ```
   GET http://127.0.0.1:1234/v1/models
   ```
   If successful → list all available models

3. **Detect llama.cpp** (if configured):
   ```
   GET http://127.0.0.1:8000/v1/models
   ```

4. **Report Status**:
   - Available providers shown in UI
   - Available models for each provider
   - Current selection status (ready/unavailable/unselected)

---

## Troubleshooting

### "No AI Provider Available"

**Cause**: All providers are unreachable

**Solutions**:
1. Start Ollama: `ollama serve`
2. Or start LM Studio with local server
3. Wait 2-3 seconds for discovery
4. Refresh admin settings page

### "Model Not Found"

**Cause**: Selected model is no longer installed

**Solutions**:
1. Check what models are available: `ollama list`
2. Install the model: `ollama pull qwen3.5:4b`
3. Or select a different available model in Medflux

### "AI Request Timeout"

**Cause**: Analysis taking longer than 300 seconds

**Solutions**:
1. Increase `AI_REQUEST_TIMEOUT_SECONDS` in `.env`
2. Use smaller model: `qwen3.5:4b` instead of larger
3. Check system resources: RAM, disk, CPU
4. Check GPU status if NVIDIA GPU present

### "Provider Reachable but Model Failing"

**Cause**: Provider is working, but model requests are failing

**Solutions**:
1. Test directly:
   ```bash
   curl http://127.0.0.1:11434/api/generate \
     -d '{"model":"qwen3.5:4b","prompt":"test","stream":false}'
   ```
2. Check provider logs/output
3. Restart provider (Ollama, LM Studio)
4. Select a different model

---

## Model Recommendations

### For Contract Analysis

**Best for accuracy & speed:**
```
Model: Qwen3.5-VL 4B
Provider: Ollama
RAM Required: 8-12 GB
GPU: Optional (NVIDIA recommended)
Analysis Time: 1-5 minutes per contract
```

**Alternatives:**
```
Model: Llama 2 7B (good quality, slower)
Model: Mistral 7B (fast, lower accuracy)
Model: Qwen 32B (best accuracy, slow)
```

---

## Integration with Contract Analysis

During contract import:

1. Selected model is used for analysis
2. Each extracted fact includes:
   - Source location (page, text region)
   - Confidence score (0-100%)
   - Timestamp of analysis
3. If model selection becomes unavailable:
   - Existing analyses are NOT re-run
   - New imports will fail with clear error message
   - User must select a model first

---

## References

- **Code**: `backend/app/ai/providers/`
- **Configuration**: `backend/app/core/config.py`
- **Selection Logic**: `backend/app/ai/selection.py`
- **Discovery**: `backend/app/ai/service.py`

