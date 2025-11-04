# app/services/speaker_identification_service.py
"""
Speaker identification service - production ready.
Uses audio fingerprinting for simple speaker tracking.
"""

import logging
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

class SpeakerProfile:
    """Profile for a speaker in a session."""
    
    def __init__(self, speaker_id: str, name: str = None):
        self.speaker_id = speaker_id
        self.name = name or speaker_id
        self.created_at = datetime.utcnow()
        self.last_active = datetime.utcnow()
        self.total_speaking_time = 0.0
        self.turn_count = 0
        self.total_words = 0
        # Simple audio fingerprint (mean, std of audio features)
        self.audio_fingerprint: Optional[np.ndarray] = None


class SpeakerIdentificationService:
    """Service for identifying and tracking speakers."""

    def __init__(self):
        self.session_speakers: Dict[str, List[str]] = {}
        self.speaker_profiles: Dict[str, SpeakerProfile] = {}
        self.speaker_counter = 0
        logger.info("SpeakerIdentificationService initialized (simple mode)")

    async def identify_speaker(
        self, 
        audio_array: np.ndarray, 
        session_id: str,
        sample_rate: int = 16000
    ) -> str:
        """
        Identify speaker from audio.
        Uses simple audio fingerprinting.
        
        Args:
            audio_array: Audio data
            session_id: Session ID
            sample_rate: Sample rate
            
        Returns:
            Speaker ID
        """
        try:
            if len(audio_array) == 0:
                return self._get_or_create_default_speaker(session_id)

            # Extract simple audio features
            fingerprint = self._extract_fingerprint(audio_array)
            
            # Get existing speakers in session
            session_speakers = self.session_speakers.get(session_id, [])
            
            if not session_speakers:
                # First speaker in session
                speaker_id = self._create_new_speaker(session_id, fingerprint)
                return speaker_id
            
            # Try to match with existing speakers
            best_match = None
            best_similarity = 0.0
            similarity_threshold = 0.7
            
            for speaker_id in session_speakers:
                profile = self.speaker_profiles.get(speaker_id)
                if profile and profile.audio_fingerprint is not None:
                    similarity = self._calculate_similarity(
                        fingerprint, 
                        profile.audio_fingerprint
                    )
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = speaker_id
            
            # If good match found, use it
            if best_match and best_similarity > similarity_threshold:
                profile = self.speaker_profiles[best_match]
                profile.last_active = datetime.utcnow()
                return best_match
            
            # No good match, create new speaker
            speaker_id = self._create_new_speaker(session_id, fingerprint)
            return speaker_id

        except Exception as e:
            logger.error(f"Speaker identification failed: {e}")
            return self._get_or_create_default_speaker(session_id)

    def _extract_fingerprint(self, audio: np.ndarray) -> np.ndarray:
        """Extract simple audio fingerprint."""
        try:
            # Basic audio features
            features = []
            
            # Spectral features
            if len(audio) > 0:
                # Energy
                energy = np.sqrt(np.mean(audio ** 2))
                features.append(energy)
                
                # Zero crossing rate
                zcr = np.mean(np.abs(np.diff(np.sign(audio)))) / 2
                features.append(zcr)
                
                # Spectral centroid (approximate)
                fft = np.fft.fft(audio)
                magnitude = np.abs(fft[:len(fft)//2])
                freqs = np.fft.fftfreq(len(audio))[:len(fft)//2]
                spectral_centroid = np.sum(magnitude * freqs) / (np.sum(magnitude) + 1e-10)
                features.append(spectral_centroid)
                
                # Pitch estimate (very rough)
                autocorr = np.correlate(audio, audio, mode='full')
                autocorr = autocorr[len(autocorr)//2:]
                # Find first peak
                peaks = []
                for i in range(1, min(len(autocorr)-1, 500)):
                    if autocorr[i] > autocorr[i-1] and autocorr[i] > autocorr[i+1]:
                        peaks.append(i)
                
                if peaks:
                    pitch_period = peaks[0]
                    pitch = 16000 / pitch_period  # Rough estimate
                    features.append(pitch)
                else:
                    features.append(100.0)  # Default
            
            return np.array(features, dtype=np.float32)
            
        except Exception as e:
            logger.warning(f"Feature extraction failed: {e}")
            return np.array([0.0, 0.0, 0.0, 100.0], dtype=np.float32)

    def _calculate_similarity(self, fp1: np.ndarray, fp2: np.ndarray) -> float:
        """Calculate similarity between fingerprints (0-1)."""
        try:
            # Normalize fingerprints
            fp1_norm = fp1 / (np.linalg.norm(fp1) + 1e-10)
            fp2_norm = fp2 / (np.linalg.norm(fp2) + 1e-10)
            
            # Cosine similarity
            similarity = np.dot(fp1_norm, fp2_norm)
            
            # Convert to 0-1 range
            similarity = (similarity + 1) / 2
            
            return float(similarity)
        except Exception:
            return 0.0

    def _create_new_speaker(self, session_id: str, fingerprint: np.ndarray) -> str:
        """Create a new speaker."""
        self.speaker_counter += 1
        speaker_id = f"Speaker_{self.speaker_counter}"
        
        profile = SpeakerProfile(speaker_id)
        profile.audio_fingerprint = fingerprint
        
        self.speaker_profiles[speaker_id] = profile
        
        # Add to session
        if session_id not in self.session_speakers:
            self.session_speakers[session_id] = []
        self.session_speakers[session_id].append(speaker_id)
        
        logger.info(f"Created new speaker: {speaker_id} in session {session_id}")
        return speaker_id

    def _get_or_create_default_speaker(self, session_id: str) -> str:
        """Get or create default speaker for session."""
        session_speakers = self.session_speakers.get(session_id, [])
        
        if not session_speakers:
            return self._create_new_speaker(session_id, np.array([0.0, 0.0, 0.0, 100.0]))
        
        return session_speakers[0]

    async def update_speaker_statistics(
        self, 
        speaker_id: str, 
        speaking_duration: float,
        word_count: int = 0
    ) -> None:
        """Update speaker statistics."""
        if speaker_id in self.speaker_profiles:
            profile = self.speaker_profiles[speaker_id]
            profile.total_speaking_time += speaking_duration
            profile.turn_count += 1
            profile.total_words += word_count
            profile.last_active = datetime.utcnow()

    async def get_session_speakers(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all speakers in a session."""
        session_speakers = self.session_speakers.get(session_id, [])
        
        result = []
        for speaker_id in session_speakers:
            profile = self.speaker_profiles.get(speaker_id)
            if profile:
                result.append({
                    "speaker_id": speaker_id,
                    "name": profile.name,
                    "total_speaking_time": profile.total_speaking_time,
                    "turn_count": profile.turn_count,
                    "total_words": profile.total_words,
                    "last_active": profile.last_active.isoformat()
                })
        
        return result

    async def analyze_speaker_patterns(self, session_id: str) -> Dict[str, Any]:
        """Analyze speaking patterns in a session."""
        speakers = await self.get_session_speakers(session_id)
        
        if not speakers:
            return {
                "total_speakers": 0,
                "speaking_distribution": {},
                "most_active_speaker": None
            }

        total_time = sum(s["total_speaking_time"] for s in speakers)
        total_words = sum(s["total_words"] for s in speakers)
        
        distribution = {}
        for speaker in speakers:
            if total_time > 0:
                time_pct = (speaker["total_speaking_time"] / total_time) * 100
            else:
                time_pct = 0
            
            distribution[speaker["speaker_id"]] = {
                "time_percentage": round(time_pct, 2),
                "word_count": speaker["total_words"],
                "turn_count": speaker["turn_count"]
            }
        
        most_active = max(speakers, key=lambda x: x["total_speaking_time"]) if speakers else None
        
        return {
            "total_speakers": len(speakers),
            "total_speaking_time": total_time,
            "total_words": total_words,
            "speaking_distribution": distribution,
            "most_active_speaker": most_active["speaker_id"] if most_active else None
        }


# Singleton
_speaker_service: Optional[SpeakerIdentificationService] = None


def get_speaker_service() -> SpeakerIdentificationService:
    """Get singleton speaker service."""
    global _speaker_service
    if _speaker_service is None:
        _speaker_service = SpeakerIdentificationService()
    return _speaker_service