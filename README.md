# 🎙️ EchoAI

> **An open-source, real-time AI-powered transcription and emotion analysis platform for meetings and conversations.**

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
[![Contributors](https://img.shields.io/github/contributors/arshisabah/EchoAI. svg)](https://github.com/arshisabah/EchoAI/graphs/contributors)
[![Stars](https://img.shields.io/github/stars/arshisabah/EchoAI.svg)](https://github.com/arshisabah/EchoAI/stargazers)
[![Issues](https://img.shields.io/github/issues/arshisabah/EchoAI.svg)](https://github.com/arshisabah/EchoAI/issues)

**EchoAI** is a real-time AI-powered transcription and emotion analysis platform designed for meetings, conversations, and collaborative sessions. Built with FastAPI and React, it leverages cutting-edge AI models to provide live transcription, emotion detection, and insightful analytics.

---

## ✨ Features

- 🎤 **Real-time Transcription** - Powered by Faster-Whisper for fast, unlimited, local transcription
- 🧠 **Emotion Analysis** - Advanced emotion detection using OpenAI GPT-4o-mini
- 🎵 **Audio Emotion Detection** - Analyze emotional tone from voice patterns
- 📹 **WebRTC Video/Audio** - High-quality peer-to-peer communication
- 👥 **Multi-user Rooms** - Collaborative meeting spaces with live participants
- 📊 **Continuous Transcript Bars** - Visual representation of conversation flow
- 💡 **Emotion Guidance** - Real-time feedback and insights based on detected emotions
- 🎬 **Meeting Recording** - Capture and save important conversations
- 🔊 **Speaker Diarization** - Identify and separate different speakers (optional)

---

## 🎯 Why EchoAI?

- **100% Open Source** - Free to use, modify, and distribute
- **Privacy First** - Run locally with Faster-Whisper, no data leaves your machine
- **Unlimited Transcription** - No API rate limits or usage costs
- **GPU Accelerated** - Blazing fast performance with NVIDIA/AMD GPU support
- **Production Ready** - Built with FastAPI and React for scalability
- **Highly Customizable** - Easy to extend and adapt to your needs

---

## 🏗️ Tech Stack

### Backend
- **Framework**:  FastAPI, Uvicorn
- **AI/ML**: PyTorch, Transformers, Faster-Whisper
- **APIs**: OpenAI, Anthropic, Deepgram (optional)
- **Database**: PostgreSQL (asyncpg), MongoDB (motor), SQLAlchemy
- **Audio Processing**: librosa, soundfile, pydub

### Frontend
- **Framework**: React 18
- **Build Tool**: Vite
- **UI Components**: Lucide React
- **Routing**: React Router DOM
- **Data Visualization**:  Recharts
- **HTTP Client**: Axios

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed: 

- **Python 3.10 or higher**
- **Node.js 16+**
- **Git**
- **NVIDIA GPU** (optional, for faster transcription)

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/arshisabah/EchoAI.git
cd EchoAI
```

### 2. Backend Setup

#### Create and activate virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on Linux/Mac
source venv/bin/activate
```

#### Install Python dependencies:

```bash
pip install -r backend/requirements.txt
```

#### Set up environment variables:

```bash
# Copy example env file
cp backend/.env. example backend/.env

# Edit backend/.env and add your API keys:
# - OPENAI_API_KEY=your_key_here
# - DEEPGRAM_API_KEY=your_key_here (optional)
```

#### Run the backend server:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

#### Install dependencies:

```bash
cd frontend
npm install
```

#### Run the development server:

```bash
npm run dev
```

---

## 🌐 Access the Application

Once both servers are running, you can access:

- **Frontend**: [http://localhost:5173](http://localhost:5173)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## ⚡ GPU Acceleration Setup

For faster transcription performance, install PyTorch with GPU support:

### For NVIDIA GPU:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### For AMD GPU:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
```

📖 **Detailed GPU setup instructions**:  See [GPU_INSTALL_GUIDE.md](./GPU_INSTALL_GUIDE.md)

---

## ⚙️ Configuration

You can customize EchoAI's behavior by editing `backend/app/core/config. py`:

- **`USE_STREAMING_TRANSCRIPTION`**: Enable/disable real-time streaming
- **`USE_ROOM_DIARIZATION`**: Enable/disable speaker identification
- **Model Settings**: Configure Faster-Whisper model size and parameters

---

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Change backend port
uvicorn app.main:app --reload --port 8001

# Change frontend port in vite.config.js
```

### Missing Dependencies

```bash
pip install --upgrade pip
pip install -r backend/requirements.txt --force-reinstall
```

### Audio Issues

```bash
# Linux
sudo apt-get install portaudio19-dev python3-pyaudio

# macOS
brew install portaudio
```

### Check Logs

- **Backend**: Terminal output where uvicorn is running
- **Frontend**: Browser console (Press F12)

---

## 🐳 Docker Support

EchoAI includes Docker support for easy deployment:

```bash
docker-compose up -d
```

See `docker-compose.yml` for configuration details.

---

## 📁 Project Structure

```
EchoAI/
├── backend/              # FastAPI backend
│   ├── app/             # Application code
│   ├── requirements.txt # Python dependencies
│   └── . env.example     # Environment variables template
├── frontend/            # React frontend
│   ├── src/            # Source code
│   ├── package.json    # Node dependencies
│   └── vite.config.js  # Vite configuration
├── SETUP.md            # Detailed setup guide
├── GPU_INSTALL_GUIDE.md # GPU installation instructions
└── docker-compose.yml  # Docker configuration
```

---

## 📝 Documentation

- **[SETUP.md](./SETUP.md)** - Complete setup instructions for new laptops
- **[GPU_INSTALL_GUIDE.md](./GPU_INSTALL_GUIDE.md)** - GPU acceleration setup

---

## 🤝 Contributing

We love contributions! Whether it's bug fixes, new features, or documentation improvements, we welcome all contributions to make EchoAI better. 

### How to Contribute

1. **Fork the repository**
   ```bash
   # Click the "Fork" button at the top right of this page
   ```

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/EchoAI. git
   cd EchoAI
   ```

3. **Create a new branch**
   ```bash
   git checkout -b feature/AmazingFeature
   ```

4. **Make your changes and commit**
   ```bash
   git add .
   git commit -m 'Add some AmazingFeature'
   ```

5. **Push to your fork**
   ```bash
   git push origin feature/AmazingFeature
   ```

6. **Open a Pull Request**
   - Go to the original repository
   - Click "New Pull Request"
   - Select your fork and branch
   - Describe your changes and submit! 

### Contribution Guidelines

- Write clear, concise commit messages
- Follow the existing code style
- Add tests for new features
- Update documentation as needed
- Be respectful and constructive in discussions

### Areas We Need Help With

- 🐛 Bug fixes and testing
- 📚 Documentation improvements
- 🌐 Internationalization (i18n)
- 🎨 UI/UX enhancements
- ⚡ Performance optimizations
- 🧪 Writing tests

---

## 👥 Contributors

Thanks to these wonderful people who have contributed to EchoAI:

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/Parvej001">
        <img src="https://avatars.githubusercontent.com/u/154591536?v=4" width="100px;" alt="Parvej001"/>
        <br />
        <sub><b>Parvej001</b></sub>
      </a>
      <br />
      <sub>53 commits</sub>
    </td>
    <td align="center">
      <a href="https://github.com/arshisabah">
        <img src="https://avatars.githubusercontent.com/u/127011456?v=4" width="100px;" alt="arshisabah"/>
        <br />
        <sub><b>Arshi Sabah</b></sub>
      </a>
      <br />
      <sub>26 commits</sub>
    </td>
    <td align="center">
      <a href="https://github.com/Vishal28-07">
        <img src="https://avatars.githubusercontent.com/u/124597002?v=4" width="100px;" alt="Vishal28-07"/>
        <br />
        <sub><b>Vishal28-07</b></sub>
      </a>
      <br />
      <sub>15 commits</sub>
    </td>
  </tr>
</table>

**Want to see your name here?** Check out our [Contributing Guidelines](#-contributing) and start contributing today!

---

## 💬 Community & Support

- **Issues**: Found a bug?  [Open an issue](https://github.com/arshisabah/EchoAI/issues/new)
- **Discussions**: Have questions?  [Start a discussion](https://github.com/arshisabah/EchoAI/discussions)
- **Pull Requests**: Want to contribute? [Submit a PR](https://github.com/arshisabah/EchoAI/pulls)

---

## 🗺️ Roadmap

- [ ] Add support for more languages
- [ ] Implement real-time translation
- [ ] Mobile app (React Native)
- [ ] Desktop app (Electron)
- [ ] Cloud deployment option
- [ ] Advanced analytics dashboard
- [ ] Plugin system for extensibility
- [ ] Integration with popular meeting platforms (Zoom, Teams, etc.)

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](./LICENSE) file for details.

```
MIT License

Copyright (c) 2026 Arshi Sabah & Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software. 
```

---

## 🙏 Acknowledgments

- **Faster-Whisper** - Fast and efficient speech-to-text
- **OpenAI** - GPT-4o-mini for emotion analysis
- **FastAPI** - Modern, fast web framework
- **React** - UI library
- **WebRTC** - Real-time communication
- All our amazing [contributors](#-contributors)!

---

## ⭐ Star History

If you find EchoAI useful, please consider giving it a star! ⭐

[![Star History Chart](https://api.star-history.com/svg?repos=arshisabah/EchoAI&type=Date)](https://star-history.com/#arshisabah/EchoAI&Date)

---

## 📧 Contact

**Arshi Sabah** - [@arshisabah](https://github.com/arshisabah)

**Project Link**: [https://github.com/arshisabah/EchoAI](https://github.com/arshisabah/EchoAI)

---

<div align="center">
  <strong>Made with ❤️ by Arshi Sabah and the EchoAI Community</strong>
  <br />
  <br />
  <a href="https://github.com/arshisabah/EchoAI">⭐ Star us on GitHub</a>
  •
  <a href="https://github.com/arshisabah/EchoAI/issues">🐛 Report Bug</a>
  •
  <a href="https://github.com/arshisabah/EchoAI/issues">💡 Request Feature</a>
</div>
