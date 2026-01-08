# Quick Testing Guide

## 1. Restart Backend
```bash
cd backend
python -m app.main
```

**Expected Log Output:**
```
🎮 GPU detected: [GPU Name] - using CUDA acceleration
OR
💻 No GPU detected - using CPU with int8 quantization

🔧 Loading Faster-Whisper 'base' model on cpu/cuda...
✅ Faster-Whisper 'base' model loaded successfully on cpu/cuda
```

## 2. Test Scenario: Multi-Speaker Meeting

### Setup:
1. Open browser window 1 (User: Alice)
2. Open browser window 2 (User: Bob)
3. Create meeting room from Alice's window
4. Join from Bob's window

### Test Speaker Change:
1. **Alice speaks**: "Hello everyone, how are you?"
   - **Expected**: Bar 1 created for Alice
   
2. **Alice continues**: "I hope everyone is doing well"
   - **Expected**: Bar 1 **updated** (not new bar)
   
3. **Bob interrupts**: "Hi Alice, I'm doing great!"
   - **Expected**: 
     - Bar 1 **finalized** (emotion processing starts in background)
     - Bar 2 **created** for Bob
   
4. **Check logs**:
   ```
   📝 Created new transcript bar: session=roomName, speaker=Alice_ID, bar_id=xxx
   📝 Created new transcript bar: session=roomName, speaker=Bob_ID, bar_id=yyy
   🔒 Finalized bar: session=roomName, bar_id=xxx
   🎭 Processing emotion for bar: xxx
   ```

## 3. Test Scenario: 30-Second Duration

### Setup:
1. Single user meeting

### Test:
1. **User speaks continuously for 30+ seconds**
   - Use a long passage or read text aloud
   
2. **Expected**:
   - Bar 1 created at 0s
   - Bar 1 updated every few seconds (text grows)
   - At 30s: Log shows `⏱️ 30s duration reached`
   - Next speech: Bar 1 finalized, Bar 2 created
   
3. **Check logs**:
   ```
   ⏱️ 30.0s duration reached - will create new bar on next speech
   🔒 Finalized bar: session=roomName, bar_id=xxx, duration=30.1s
   📝 Created new transcript bar: session=roomName, bar_id=yyy
   🎭 Processing emotion for bar: xxx
   ```

## 4. Test Scenario: Silence Detection

### Setup:
1. Single user meeting

### Test:
1. **User speaks**: "Hello"
   - Bar 1 created
   
2. **Wait 15 seconds in silence**
   - **Expected log**: `🔇 15s silence detected - will create new bar on next speech`
   
3. **User speaks again**: "Are you there?"
   - **Expected**:
     - Bar 1 finalized (emotion starts)
     - Bar 2 created

## 5. Verify Emotion Processing

### What to Check:
1. **Emotion processes ONLY on finalized bars**
   - Check logs for `🎭 Processing emotion for bar`
   - Should NOT see it immediately on bar creation
   - Should see it after 30s duration, speaker change, or silence

2. **Emotion updates correct bar**
   - Bar status changes: `active` → `processing_emotion` → `finalized`
   - Frontend shows emotion results on the **finalized bar**, not new bar

3. **No duplicate emotion processing**
   - Each bar should only have ONE emotion processing log entry

## 6. Check GPU Usage (if available)

### Startup:
```
🎮 GPU detected: NVIDIA GeForce RTX 3060 - using CUDA acceleration
OR
🎮 GPU detected: AMD Radeon RX 6800 - using CUDA acceleration
```

### During Transcription:
- GPU usage should spike when processing audio
- CPU usage should be lower than pure CPU mode

### Check in logs:
```
faster_whisper | INFO | Processing audio with duration 00:00.512
```
- Should complete faster on GPU (~0.3-0.5s vs 0.8-1.2s on CPU)

## 7. Expected Performance Metrics

### With GPU:
- First model load: 2-3 seconds
- Transcription latency: 0.5-1.0 seconds
- Accuracy: 85-90%

### With CPU:
- First model load: 3-5 seconds
- Transcription latency: 1.0-1.5 seconds
- Accuracy: 85-90%

## 8. Common Issues & Solutions

### Issue: Transcription still using "tiny" model
**Solution**: 
- Verify line 50 in `faster_whisper_transcription.py`: Should be `"base"`, not `"tiny"`
- Restart backend

### Issue: Bars not created after 30s
**Solution**:
- Check log for `⏱️ 30.0s duration reached`
- If missing, verify `duration_threshold = 30.0` in line 129

### Issue: Speaker change not creating new bar
**Solution**:
- Verify each user has unique `user_id`
- Check logs for speaker IDs - should be different

### Issue: Emotion processing on every transcript
**Solution**:
- Check `continuous_transcript_manager.py` line 151
- Should NOT have `await self.emotion_queue.put(new_bar)`
- Should only be in `_finalize_bar()` method

### Issue: GPU not detected
**Solution**:
- Check PyTorch installation: `python -c "import torch; print(torch.cuda.is_available())"`
- For AMD GPUs: Ensure ROCm is installed
- For NVIDIA GPUs: Ensure CUDA drivers installed

## 9. Log File Location

Check detailed logs at:
```
backend/logs/transcript_api.log
```

Search for:
- `📝 Created new transcript bar` - Bar creation
- `🔒 Finalized bar` - Bar finalization
- `🎭 Processing emotion` - Emotion analysis start
- `✅ Emotion analysis complete` - Emotion results ready

## 10. Success Criteria

✅ **Transcription**:
- Text accuracy > 80%
- Bars created on speaker change
- Bars created after 30s continuous speech
- Bars created after 15s silence + new speech

✅ **Emotion Processing**:
- Starts ONLY when bar finalized
- Updates correct bar with emotion results
- No duplicate processing

✅ **Performance**:
- Latency < 2 seconds (GPU) or < 3 seconds (CPU)
- No memory leaks during long meetings
- GPU properly detected and utilized

✅ **Multi-User**:
- Each speaker gets separate bars
- Bars don't mix between speakers
- Real-time updates visible to all participants
