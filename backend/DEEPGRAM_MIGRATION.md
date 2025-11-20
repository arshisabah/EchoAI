# Deepgram Real-Time Streaming Transcription Migration Guide

This guide explains how to migrate from the legacy buffered Whisper transcription to Deepgram's real-time streaming API for ultra-low latency (<700ms) transcription.

## Table of Contents
1. [Why Deepgram?](#why-deepgram)
2. [Getting Started](#getting-started)
3. [Configuration](#configuration)
4. [Feature Comparison](#feature-comparison)
5. [Troubleshooting](#troubleshooting)
6. [FAQ](#faq)

---

## Why Deepgram?

### Problems with Legacy System
- **High Latency**: 2-5 seconds delay due to audio buffering
- **Manual VAD**: Aggressive voice activity detection misses soft-spoken words
- **No Partial Results**: Users wait for complete utterances before seeing any text
- **Complex Pipeline**: Multi-layer buffering and processing causes delays

### Benefits of Deepgram Streaming
- ✅ **<700ms Latency**: Real-time word-by-word transcription
- ✅ **Built-in VAD**: Professional-grade voice activity detection
- ✅ **Partial Results**: See transcription as users speak
- ✅ **Simplified Code**: No manual buffering or silence detection needed
- ✅ **Better Accuracy**: State-of-the-art Nova-2 model
- ✅ **Free Credits**: $200 in free credits to start

---

## Getting Started

### 1. Get Your Deepgram API Key

1. Sign up at [https://console.deepgram.com/signup](https://console.deepgram.com/signup)
2. You'll receive **$200 in free credits** (no credit card required)
3. Navigate to **API Keys** in the console
4. Create a new API key and copy it

### 2. Update Your Environment

Add the following to your `.env` file:

```env
# Deepgram API for real-time transcription
DEEPGRAM_API_KEY=your_deepgram_api_key_here
USE_STREAMING_TRANSCRIPTION=true
```

### 3. Install Dependencies

```bash
cd backend
pip install deepgram-sdk==3.2.7
```

### 4. Restart the Backend

```bash
cd backend
python -m uvicorn app.main:app --reload
```

You should see in the logs:
```
✅ Deepgram streaming transcription enabled
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPGRAM_API_KEY` | None | Your Deepgram API key (required for streaming) |
| `USE_STREAMING_TRANSCRIPTION` | `true` | Enable streaming mode (set to `false` for legacy) |
| `WHISPER_MODEL` | `base` | Whisper model used in legacy mode |

### Toggling Between Modes

**Streaming Mode (Recommended)**
```env
USE_STREAMING_TRANSCRIPTION=true
DEEPGRAM_API_KEY=your_key_here
```

**Legacy Mode (Fallback)**
```env
USE_STREAMING_TRANSCRIPTION=false
# or simply don't set DEEPGRAM_API_KEY
```

The system will automatically fall back to legacy mode if:
- `USE_STREAMING_TRANSCRIPTION` is set to `false`
- `DEEPGRAM_API_KEY` is not provided
- Deepgram service fails to initialize
- Network connection to Deepgram is unavailable

---

## Feature Comparison

| Feature | Legacy (Whisper) | Streaming (Deepgram) |
|---------|------------------|----------------------|
| **Latency** | 2-5 seconds | <700ms |
| **Partial Results** | ❌ No | ✅ Yes |
| **VAD** | Manual (aggressive) | Built-in (professional) |
| **Word-by-Word** | ❌ No | ✅ Yes |
| **Buffering** | Required (1.2-2.5s) | ❌ None |
| **Silence Detection** | Manual energy threshold | Built-in VAD events |
| **API Cost** | OpenAI Whisper API | Deepgram ($0.0043/min) |
| **Offline Mode** | ✅ Yes (local models) | ❌ No (requires internet) |
| **Soft Speech Detection** | ⚠️ Often missed | ✅ Better accuracy |

### What's Preserved?

All existing features continue to work with Deepgram:

- ✅ **Emotion Analysis**: Runs on final results
- ✅ **Speaker Identification**: Works with all transcription modes
- ✅ **Meeting Recording**: Full audio recording still available
- ✅ **Transcript Storage**: All transcripts stored identically
- ✅ **WebSocket API**: No changes to client integration

---

## Troubleshooting

### Issue: "Deepgram service unavailable, falling back to legacy mode"

**Causes:**
- Missing or invalid `DEEPGRAM_API_KEY`
- `deepgram-sdk` not installed
- Network connectivity issues

**Solutions:**
1. Verify your API key is correct in `.env`
2. Ensure `deepgram-sdk==3.2.7` is installed: `pip install deepgram-sdk==3.2.7`
3. Check network connectivity to `api.deepgram.com`
4. Check backend logs for detailed error messages

### Issue: No transcription appearing

**Causes:**
- Microphone not working
- Audio format issues
- WebSocket connection dropped

**Solutions:**
1. Check browser console for WebSocket errors
2. Verify microphone permissions in browser
3. Test with legacy mode: `USE_STREAMING_TRANSCRIPTION=false`
4. Check backend logs for audio processing errors

### Issue: Delayed transcription in streaming mode

**Causes:**
- Poor network connection
- High system load
- Deepgram API rate limiting

**Solutions:**
1. Check network latency to Deepgram
2. Monitor system resources (CPU/Memory)
3. Verify Deepgram account status and credits
4. Consider upgrading Deepgram plan if rate-limited

### Issue: Missing partial results

**Causes:**
- Frontend not handling `is_final: false` messages
- WebSocket message filtering

**Solutions:**
1. Check browser console for incoming WebSocket messages
2. Verify frontend displays partial results (if implemented)
3. Look for `is_final` field in transcript messages

---

## FAQ

### Q: How much does Deepgram cost?

**A:** Deepgram offers $200 in free credits for new accounts. After that:
- **Pay-as-you-go**: $0.0043 per minute of audio
- **Example**: 100 hours of meetings = $25.80

### Q: Can I use both modes simultaneously?

**A:** No. The system uses either streaming or legacy mode per session. However, you can switch modes by changing the environment variables and restarting.

### Q: What happens if I run out of Deepgram credits?

**A:** The system will log errors and you can either:
1. Add more credits to your Deepgram account
2. Switch to legacy mode: `USE_STREAMING_TRANSCRIPTION=false`

### Q: Does streaming mode work offline?

**A:** No. Deepgram requires an internet connection. For offline transcription, use legacy mode with local Whisper models.

### Q: Can I customize the Deepgram model?

**A:** Yes. In `deepgram_transcription.py`, modify the `start_stream` method:

```python
options = LiveOptions(
    model="nova-2",      # Options: nova-2, nova, enhanced, base
    language="en",       # Language code
    smart_format=True,   # Automatic formatting
    # ... other options
)
```

### Q: How do I monitor Deepgram usage?

**A:** Check your usage in the [Deepgram Console](https://console.deepgram.com/):
- Dashboard shows real-time usage
- Billing section shows detailed breakdown
- Set up usage alerts

### Q: Is transcription quality better with Deepgram?

**A:** Generally yes, especially for:
- Real-time scenarios (lower latency = better UX)
- Soft-spoken speakers (better VAD)
- Multiple speakers (faster processing)

However, quality also depends on:
- Audio quality
- Network stability
- Language and accent

### Q: Can I use different transcription providers?

**A:** Yes. The architecture supports multiple backends. To add a new provider:
1. Create a service in `app/services/` (similar to `deepgram_transcription.py`)
2. Update `orchestrator_service.py` to route to your service
3. Add configuration in `config.py`

---

## Performance Tips

### 1. Optimize Network Connection
- Use a stable internet connection
- Consider a dedicated network for production
- Monitor latency to Deepgram API

### 2. Reduce System Load
- Close unnecessary applications
- Allocate sufficient CPU/memory
- Use async processing for multiple sessions

### 3. Audio Quality
- Use quality microphones
- Reduce background noise
- Maintain consistent audio levels

### 4. Backend Configuration
```python
# In deepgram_transcription.py
options = LiveOptions(
    model="nova-2",           # Latest model
    interim_results=True,     # Enable partial results
    smart_format=True,        # Auto punctuation/formatting
    vad_events=True,          # Voice activity detection
    punctuate=True,           # Add punctuation
    diarize=False,            # Disable if not needed (faster)
)
```

---

## Migration Checklist

- [ ] Sign up for Deepgram account
- [ ] Copy API key to `.env` file
- [ ] Install `deepgram-sdk==3.2.7`
- [ ] Set `USE_STREAMING_TRANSCRIPTION=true`
- [ ] Restart backend server
- [ ] Verify "Deepgram streaming enabled" in logs
- [ ] Test with a meeting
- [ ] Monitor latency and quality
- [ ] Update frontend to display partial results (optional)
- [ ] Set up usage monitoring in Deepgram console

---

## Support

### EchoAI Support
- GitHub Issues: [https://github.com/arshisabah/EchoAI/issues](https://github.com/arshisabah/EchoAI/issues)
- Documentation: Check `README.md` and other guides

### Deepgram Support
- Documentation: [https://developers.deepgram.com](https://developers.deepgram.com)
- Community: [https://discord.gg/deepgram](https://discord.gg/deepgram)
- Support: [support@deepgram.com](mailto:support@deepgram.com)

---

## Additional Resources

- [Deepgram API Documentation](https://developers.deepgram.com/docs)
- [Deepgram Python SDK](https://github.com/deepgram/deepgram-python-sdk)
- [Deepgram Pricing](https://deepgram.com/pricing)
- [EchoAI GitHub Repository](https://github.com/arshisabah/EchoAI)
