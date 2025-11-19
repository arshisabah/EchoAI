"""
Pytest configuration for test suite.
Mocks external dependencies to allow tests to run without model downloads or API keys.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, AsyncMock, Mock, patch
import numpy as np

# Set environment variables before importing app modules
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["ANTHROPIC_API_KEY"] = "test-key"


# Mock torch and transformers to prevent model loading
sys.modules['torch'] = MagicMock()
sys.modules['torchaudio'] = MagicMock()
sys.modules['transformers'] = MagicMock()


# Mock audio emotion analyzer to prevent model loading
class MockAudioEmotionAnalyzer:
    """Mock audio emotion analyzer."""
    
    def analyze_audio_emotion(self, audio_array, sample_rate=16000):
        """Mock emotion analysis."""
        return {
            "emotion": "neutral",
            "confidence": 0.8,
            "scores": {"neutral": 0.8, "happy": 0.1, "sad": 0.1}
        }


@pytest.fixture(scope="session", autouse=True)
def mock_dependencies():
    """Mock external dependencies for testing."""
    
    # Mock model loading in audio_emotion_analyzer
    with patch('app.modules.audio_emotion_analyzer._model', None):
        with patch('app.modules.audio_emotion_analyzer._processor', None):
            with patch('app.modules.audio_emotion_analyzer._feature_extractor', None):
                with patch('app.modules.audio_emotion_analyzer.analyze_audio_emotion', return_value={
                    "emotion": "neutral",
                    "confidence": 0.8,
                    "scores": {"neutral": 0.8}
                }):
                    yield


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for async tests."""
    import asyncio
    return asyncio.get_event_loop_policy()
