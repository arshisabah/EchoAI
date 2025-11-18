# 🎙️ EchoAI Backend

Production-ready real-time meeting intelligence backend with AI-powered transcription, emotion analysis, and speaker identification.

## ✨ Features

### Core Features
- **Real-time Transcription**: Live speech-to-text using WhisperX/Whisper
- **Speaker Identification**: Automatic speaker detection and tracking
- **Emotion Analysis**: Real-time emotion detection using GPT-4o-mini
- **Meeting Analytics**: Comprehensive insights and statistics
- **Multi-backend Support**: PostgreSQL, MongoDB, or file-based storage
- **WebSocket API**: Real-time bidirectional communication
- **RESTful API**: Complete HTTP API with FastAPI
- **Production Ready**: Docker support, logging, error handling

### 🆕 New in v3.0
- **Meeting Recording**: Record and download complete meeting audio as WAV files
- **Enhanced WebSocket Stability**: Extended timeout (180s) with keep-alive for 30+ minute meetings
- **Improved Diarization**: Voice Activity Detection with 1.5s silence boundary detection
- **Multi-format Transcript Export**: Download transcripts in TXT, JSON, or SRT format
- **Analytics Dashboard**: Fixed `/analytics/sessions/list` endpoint and enhanced session management

📖 **[View Full Documentation](./MEETING_FEATURES.md)** for new features

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- ffmpeg (for audio processing)
- OpenAI API key
- Optional: PostgreSQL, Redis

### Installation

#### Option 1: Automated Setup (Recommended)

```bash
chmod +x setup.sh
./setup.sh
```

#### Option 2: Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create directories
mkdir -p logs data models_cache

# Setup environment
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Edit `.env` file:

```env
# Required
OPENAI_API_KEY=sk-your-key-here

# Optional
ANTHROPIC_API_KEY=sk-ant-your-key
HUGGINGFACE_TOKEN=hf_your-token

# Database (default: file-based)
SESSION_STORE_TYPE=file  # or postgresql, mongodb
DATABASE_URL=postgresql://user:pass@localhost/echoai

# Model settings
WHISPER_MODEL=base  # tiny, base, small, medium, large
USE_GPU=false
```

### Running the Server

#### Development Mode

```bash
# Activate virtual environment
source venv/bin/activate

# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Production Mode

```bash
# Using uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Using gunicorn
gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 4
```

#### Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop
docker-compose down
```

## 📡 API Documentation

### Interactive Docs

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### WebSocket API

#### Connect to Session

```javascript
const ws = new WebSocket('ws://localhost:8000/transcript/ws/session_123');

ws.onopen = () => {
    console.log('Connected');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};
```

#### Send Audio Chunk

```javascript
// Audio must be base64-encoded
const audioBase64 = btoa(String.fromCharCode(...new Uint8Array(audioBuffer)));

ws.send(JSON.stringify({
    type: 'audio_chunk',
    audio_data: audioBase64,
    sample_rate: 16000
}));
```

#### Receive Transcript

```javascript
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    if (message.type === 'transcript_entry') {
        const { speaker, text, emotion, confidence } = message.data;
        console.log(`${speaker}: ${text} (${emotion})`);
    }
};
```

### REST API Examples

#### Create Session

```bash
curl -X POST http://localhost:8000/transcript/session/my_meeting/create
```

#### Get Transcript

```bash
curl http://localhost:8000/transcript/session/my_meeting
```

#### Get Analytics

```bash
curl http://localhost:8000/analytics/session/my_meeting
```

#### Get Emotions

```bash
curl http://localhost:8000/analytics/session/my_meeting/emotions
```

#### Get Summary

```bash
curl http://localhost:8000/transcript/session/my_meeting/summary
```

## 🏗️ Architecture

```
backend/
├── app/
│   ├── core/              # Core configuration
│   │   ├── config.py      # Settings
│   │   └── logging_config.py
│   ├── models/            # Data models
│   │   ├── api_models.py  # API request/response models
│   │   └── registry.py    # Model registry
│   ├── modules/           # Business logic modules
│   │   └── realtime_store.py  # Session management
│   ├── routers/           # API routes
│   │   ├── transcript.py  # Transcription endpoints
│   │   ├── summary.py     # Summary endpoints
│   │   └── analytics.py   # Analytics endpoints
│   ├── services/          # Core services
│   │   ├── transcription_service.py
│   │   ├── emotion_analysis.py
│   │   ├── summary_service.py
│   │   ├── speaker_identification_service.py
│   │   ├── orchestrator_service.py
│   │   ├── audio_utils.py
│   │   └── dependencies.py
│   └── database/          # Database layer
│       └── session_store.py
├── main.py                # Application entry point
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose setup
└── .env                  # Environment variables
```

## 🔧 Configuration Options

### Transcription Backends

1. **WhisperX** (Best quality, requires GPU recommended)
2. **Whisper** (Good quality, CPU-compatible)
3. **OpenAI API** (Fallback, requires API key)

### Storage Backends

1. **File-based** (Default, no setup needed)
2. **PostgreSQL** (Production recommended)
3. **MongoDB** (Flexible schema)

### Model Sizes

- `tiny`: Fastest, lower accuracy (~1GB RAM)
- `base`: Balanced (~1GB RAM)
- `small`: Better accuracy (~2GB RAM)
- `medium`: High accuracy (~5GB RAM)
- `large`: Best accuracy (~10GB RAM, GPU recommended)

## 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Manual Testing with WebSocket

```html
<!DOCTYPE html>
<html>
<body>
    <button onclick="connect()">Connect</button>
    <button onclick="sendAudio()">Send Test Audio</button>
    <div id="output"></div>
    
    <script>
        let ws;
        
        function connect() {
            ws = new WebSocket('ws://localhost:8000/transcript/ws/test_session');
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                document.getElementById('output').innerHTML += 
                    `<p>${data.type}: ${JSON.stringify(data.data)}</p>`;
            };
        }
        
        async function sendAudio() {
            // Get microphone access
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = async (event) => {
                const arrayBuffer = await event.data.arrayBuffer();
                const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
                
                ws.send(JSON.stringify({
                    type: 'audio_chunk',
                    audio_data: base64,
                    sample_rate: 16000
                }));
            };
            
            mediaRecorder.start();
            setTimeout(() => mediaRecorder.stop(), 3000); // Record 3 seconds
        }
    </script>
</body>
</html>
```

## 📊 Performance

### Benchmarks

- **Transcription Latency**: ~300-500ms (base model, CPU)
- **WebSocket Throughput**: ~1000 messages/sec
- **Memory Usage**: ~2GB (base model)
- **Concurrent Sessions**: 100+ (depending on hardware)

### Optimization Tips

1. **Use GPU**: 5-10x faster transcription
2. **Use smaller models**: Trade accuracy for speed
3. **Enable Redis**: Faster session management
4. **Use PostgreSQL**: Better performance for analytics
5. **Scale horizontally**: Run multiple workers

## 🐛 Troubleshooting

### Common Issues

#### "No module named 'whisper'"

```bash
pip install openai-whisper
# or for WhisperX:
pip install git+https://github.com/m-bain/whisperX.git
```

#### "ffmpeg not found"

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/
```

#### "CUDA out of memory"

- Use smaller model: `WHISPER_MODEL=tiny`
- Use CPU: `USE_GPU=false`
- Reduce concurrent sessions

#### WebSocket connection fails

- Check CORS settings in `.env`
- Ensure port 8000 is accessible
- Check firewall rules

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
export DEBUG=True

# Run server
python main.py
```

## 🔒 Security

### Production Checklist

- [ ] Change default passwords in docker-compose.yml
- [ ] Use environment variables for secrets (never commit .env)
- [ ] Enable HTTPS (use nginx reverse proxy)
- [ ] Restrict CORS origins
- [ ] Implement authentication (JWT recommended)
- [ ] Enable rate limiting
- [ ] Set up monitoring and alerting
- [ ] Regular security updates

## 📈 Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### Logs

```bash
# View logs
tail -f logs/transcript_api.log

# Docker logs
docker-compose logs -f backend
```

### Metrics

Access system metrics at:
- `/analytics/sessions/list` - All sessions
- `/analytics/session/{id}/summary` - Session summary

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit pull request

## 📝 License

MIT License - see LICENSE file for details

## 🆘 Support

- **Documentation**: http://localhost:8000/docs
- **Issues**: GitHub Issues
- **Email**: support@echoai.example.com

## 🎯 Roadmap

- [x] ~~Meeting recording storage~~ ✅ v3.0
- [x] ~~Advanced analytics dashboard~~ ✅ v3.0
- [x] ~~Enhanced speaker diarization~~ ✅ v3.0
- [ ] Multi-language support
- [ ] Real-time translation
- [ ] Calendar integration
- [ ] Mobile app support
- [ ] AI-powered meeting notes
- [ ] Video recording support
- [ ] Real-time captions
- [ ] Cloud storage integration (S3, Azure Blob)

## 🙏 Acknowledgments

- OpenAI Whisper
- WhisperX
- FastAPI
- PyTorch
- Hugging Face Transformers