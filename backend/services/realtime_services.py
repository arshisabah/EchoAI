from fastapi import WebSocket
from backend.modules.transcription import transcribe_audio
from backend.modules.sentiment_analysis import analyze_sentiment

# simple in-memory demo – later replace with streaming Whisper
async def handle_realtime_audio(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            # here data = transcript chunk (simulate real-time)
            sentiment = analyze_sentiment(data)
            await ws.send_json({"text": data, "sentiment": sentiment})
    except Exception:
        await ws.close()
