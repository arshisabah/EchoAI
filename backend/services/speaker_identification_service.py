# backend/services/speaker_identification_service.py
"""
Speaker Identification Service for EchoAI.

Responsibilities:
- Identify speakers using voice characteristics
- Manage speaker enrollment and recognition
- Track speaker changes and turn-taking
- Provide speaker statistics and analytics
"""

import logging
import uuid
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import json

logger = logging.getLogger(__name__)

try:
    # Optional: Use speechbrain for advanced speaker recognition
    from speechbrain.pretrained import SpeakerRecognition
    SPEECHBRAIN_AVAILABLE = True
except ImportError:
    SPEECHBRAIN_AVAILABLE = False
    logger.warning("SpeechBrain not available, using fallback speaker identification")


class SpeakerProfile:
    """Profile for a recognized speaker."""
    
    def __init__(self, speaker_id: str, name: str = None, voice_embedding: np.ndarray = None):
        self.speaker_id = speaker_id
        self.name = name or f"Speaker_{speaker_id}"
        self.voice_embedding = voice_embedding
        self.created_at = datetime.utcnow()
        self.last_active = datetime.utcnow()
        self.total_speaking_time = 0.0
        self.turn_count = 0


class SpeakerIdentificationService:
    """Service for identifying and tracking speakers in meetings."""

    def __init__(self):
        self.enrolled_speakers: Dict[str, SpeakerProfile] = {}
        self.session_speakers: Dict[str, List[str]] = {}  # session_id -> list of speaker_ids
        self.current_speaker_count = 0
        
        # Initialize speaker recognition model if available
        self.speaker_model = None
        if SPEECHBRAIN_AVAILABLE:
            try:
                self.speaker_model = SpeakerRecognition.from_hparams(
                    source="speechbrain/spkrec-ecapa-voxceleb",
                    savedir="pretrained_models/spkrec-ecapa-voxceleb"
                )
                logger.info("SpeechBrain speaker recognition model loaded")
            except Exception as e:
                logger.warning(f"Failed to load SpeechBrain model: {e}")
                self.speaker_model = None
        
        logger.info("SpeakerIdentificationService initialized")

    async def identify_speaker(
        self, 
        audio_array: np.ndarray, 
        session_id: str,
        sample_rate: int = 16000
    ) -> str:
        """
        Identify the speaker from audio data.

        Args:
            audio_array (np.ndarray): Audio data as numpy array
            session_id (str): Session identifier
            sample_rate (int): Audio sample rate

        Returns:
            str: Speaker identifier
        """
        try:
            if self.speaker_model and len(audio_array) > 0:
                return await self._identify_with_model(audio_array, session_id, sample_rate)
            else:
                return await self._identify_fallback(audio_array, session_id)
        except Exception as e:
            logger.error(f"Speaker identification failed: {e}")
            return self._get_default_speaker(session_id)

    async def _identify_with_model(
        self, 
        audio_array: np.ndarray, 
        session_id: str,
        sample_rate: int
    ) -> str:
        """Identify speaker using advanced speech recognition model."""
        try:
            # Ensure audio is long enough for analysis
            if len(audio_array) < sample_rate * 0.5:  # At least 0.5 seconds
                return self._get_default_speaker(session_id)

            # Get speaker embedding
            embedding = self.speaker_model.encode_batch(audio_array.unsqueeze(0))
            embedding_np = embedding.numpy().flatten()

            # Compare with enrolled speakers
            best_match = None
            best_similarity = -1.0

            for speaker_id, profile in self.enrolled_speakers.items():
                if profile.voice_embedding is not None:
                    similarity = self._calculate_similarity(embedding_np, profile.voice_embedding)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = speaker_id

            # Threshold for speaker recognition (adjust as needed)
            recognition_threshold = 0.7

            if best_match and best_similarity > recognition_threshold:
                # Update speaker profile
                self.enrolled_speakers[best_match].last_active = datetime.utcnow()
                return best_match
            else:
                # Create new speaker profile
                return await self._enroll_new_speaker(embedding_np, session_id)

        except Exception as e:
            logger.error(f"Model-based speaker identification failed: {e}")
            return self._get_default_speaker(session_id)

    async def _identify_fallback(self, audio_array: np.ndarray, session_id: str) -> str:
        """Fallback speaker identification using basic audio features."""
        try:
            # Simple heuristics based on audio characteristics
            # This is a basic implementation - in production, you'd want more sophisticated methods
            
            # Calculate basic audio features
            features = self._extract_basic_features(audio_array)
            
            # Try to match with existing speakers in session
            session_speakers = self.session_speakers.get(session_id, [])
            
            if not session_speakers:
                # First speaker in session
                speaker_id = self._create_speaker_id()
                self._add_speaker_to_session(speaker_id, session_id)
                return speaker_id
            
            # Simple decision based on features (placeholder logic)
            # In reality, you'd use more sophisticated audio analysis
            speaker_index = hash(str(features)) % len(session_speakers)
            return session_speakers[speaker_index]

        except Exception as e:
            logger.error(f"Fallback speaker identification failed: {e}")
            return self._get_default_speaker(session_id)

    def _extract_basic_features(self, audio_array: np.ndarray) -> Dict[str, float]:
        """Extract basic audio features for speaker identification."""
        try:
            # Basic audio features
            features = {
                "mean_amplitude": float(np.mean(np.abs(audio_array))),
                "std_amplitude": float(np.std(audio_array)),
                "rms": float(np.sqrt(np.mean(audio_array**2))),
                "zero_crossing_rate": float(np.mean(np.diff(np.signbit(audio_array))))
            }
            
            # Basic spectral features (simplified)
            if len(audio_array) > 0:
                fft = np.fft.fft(audio_array)
                power_spectrum = np.abs(fft)**2
                features["spectral_centroid"] = float(np.mean(power_spectrum))
            
            return features
        except Exception:
            return {"mean_amplitude": 0.0, "std_amplitude": 0.0, "rms": 0.0, "zero_crossing_rate": 0.0}

    def _calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        try:
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
        except Exception:
            return 0.0

    async def _enroll_new_speaker(self, embedding: np.ndarray, session_id: str) -> str:
        """Enroll a new speaker with their voice embedding."""
        speaker_id = self._create_speaker_id()
        
        # Create speaker profile
        profile = SpeakerProfile(
            speaker_id=speaker_id,
            voice_embedding=embedding
        )
        
        self.enrolled_speakers[speaker_id] = profile
        self._add_speaker_to_session(speaker_id, session_id)
        
        logger.info(f"New speaker enrolled: {speaker_id} in session {session_id}")
        return speaker_id

    def _create_speaker_id(self) -> str:
        """Create a unique speaker ID."""
        self.current_speaker_count += 1
        return f"Speaker_{self.current_speaker_count:02d}"

    def _get_default_speaker(self, session_id: str) -> str:
        """Get default speaker for a session."""
        session_speakers = self.session_speakers.get(session_id, [])
        
        if not session_speakers:
            speaker_id = self._create_speaker_id()
            self._add_speaker_to_session(speaker_id, session_id)
            return speaker_id
        
        return session_speakers[0]  # Return first speaker as default

    def _add_speaker_to_session(self, speaker_id: str, session_id: str) -> None:
        """Add speaker to session tracking."""
        if session_id not in self.session_speakers:
            self.session_speakers[session_id] = []
        
        if speaker_id not in self.session_speakers[session_id]:
            self.session_speakers[session_id].append(speaker_id)

    async def enroll_speaker_by_name(
        self, 
        name: str, 
        audio_samples: List[np.ndarray],
        session_id: Optional[str] = None
    ) -> str:
        """
        Enroll a speaker with a specific name using multiple audio samples.

        Args:
            name (str): Speaker's name
            audio_samples (List[np.ndarray]): Multiple audio samples for training
            session_id (str): Optional session ID to associate with

        Returns:
            str: Speaker ID
        """
        try:
            speaker_id = f"speaker_{name.lower().replace(' ', '_')}"
            
            # If using advanced model, create averaged embedding
            if self.speaker_model and audio_samples:
                embeddings = []
                for audio in audio_samples:
                    if len(audio) > 0:
                        embedding = self.speaker_model.encode_batch(audio.unsqueeze(0))
                        embeddings.append(embedding.numpy().flatten())
                
                if embeddings:
                    # Average embeddings for better representation
                    avg_embedding = np.mean(embeddings, axis=0)
                else:
                    avg_embedding = None
            else:
                avg_embedding = None

            # Create speaker profile
            profile = SpeakerProfile(
                speaker_id=speaker_id,
                name=name,
                voice_embedding=avg_embedding
            )
            
            self.enrolled_speakers[speaker_id] = profile
            
            if session_id:
                self._add_speaker_to_session(speaker_id, session_id)
            
            logger.info(f"Speaker enrolled: {name} (ID: {speaker_id})")
            return speaker_id

        except Exception as e:
            logger.error(f"Speaker enrollment failed for {name}: {e}")
            return self._create_speaker_id()

    async def get_session_speakers(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all speakers in a session with their statistics.

        Args:
            session_id (str): Session identifier

        Returns:
            List of speaker dictionaries with statistics
        """
        session_speakers = self.session_speakers.get(session_id, [])
        speaker_info = []
        
        for speaker_id in session_speakers:
            profile = self.enrolled_speakers.get(speaker_id)
            if profile:
                speaker_info.append({
                    "speaker_id": speaker_id,
                    "name": profile.name,
                    "total_speaking_time": profile.total_speaking_time,
                    "turn_count": profile.turn_count,
                    "last_active": profile.last_active.isoformat(),
                    "enrolled": profile.voice_embedding is not None
                })
            else:
                speaker_info.append({
                    "speaker_id": speaker_id,
                    "name": speaker_id,
                    "total_speaking_time": 0.0,
                    "turn_count": 0,
                    "last_active": datetime.utcnow().isoformat(),
                    "enrolled": False
                })
        
        return speaker_info

    async def update_speaker_statistics(
        self, 
        speaker_id: str, 
        speaking_duration: float,
        word_count: int = 0
    ) -> None:
        """
        Update speaking statistics for a speaker.

        Args:
            speaker_id (str): Speaker identifier
            speaking_duration (float): Duration in seconds
            word_count (int): Number of words spoken
        """
        if speaker_id in self.enrolled_speakers:
            profile = self.enrolled_speakers[speaker_id]
            profile.total_speaking_time += speaking_duration
            profile.turn_count += 1
            profile.last_active = datetime.utcnow()

    async def analyze_speaker_patterns(self, session_id: str) -> Dict[str, Any]:
        """
        Analyze speaking patterns in a session.

        Args:
            session_id (str): Session identifier

        Returns:
            Dict with speaker pattern analysis
        """
        try:
            speakers = await self.get_session_speakers(session_id)
            
            if not speakers:
                return {
                    "total_speakers": 0,
                    "speaking_distribution": {},
                    "most_active_speaker": None,
                    "turn_taking_analysis": {}
                }

            total_speaking_time = sum(s["total_speaking_time"] for s in speakers)
            total_turns = sum(s["turn_count"] for s in speakers)

            # Calculate speaking distribution
            distribution = {}
            for speaker in speakers:
                if total_speaking_time > 0:
                    percentage = (speaker["total_speaking_time"] / total_speaking_time) * 100
                else:
                    percentage = 0
                
                distribution[speaker["speaker_id"]] = {
                    "percentage": round(percentage, 2),
                    "speaking_time": speaker["total_speaking_time"],
                    "turn_count": speaker["turn_count"]
                }

            # Find most active speaker
            most_active = max(speakers, key=lambda x: x["total_speaking_time"])

            # Turn-taking analysis
            avg_turns_per_speaker = total_turns / len(speakers) if speakers else 0
            turn_distribution = {
                s["speaker_id"]: s["turn_count"] for s in speakers
            }

            return {
                "total_speakers": len(speakers),
                "total_speaking_time": total_speaking_time,
                "total_turns": total_turns,
                "speaking_distribution": distribution,
                "most_active_speaker": most_active["speaker_id"],
                "average_turns_per_speaker": round(avg_turns_per_speaker, 2),
                "turn_distribution": turn_distribution,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Speaker pattern analysis failed: {e}")
            return {
                "total_speakers": 0,
                "error": str(e)
            }

    async def detect_speaker_changes(
        self, 
        audio_chunks: List[np.ndarray], 
        session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Detect speaker changes across multiple audio chunks.

        Args:
            audio_chunks (List[np.ndarray]): Sequential audio chunks
            session_id (str): Session identifier

        Returns:
            List of speaker change events
        """
        try:
            changes = []
            current_speaker = None
            
            for i, chunk in enumerate(audio_chunks):
                speaker = await self.identify_speaker(chunk, session_id)
                
                if speaker != current_speaker:
                    changes.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "chunk_index": i,
                        "previous_speaker": current_speaker,
                        "new_speaker": speaker,
                        "change_type": "speaker_change" if current_speaker else "first_speaker"
                    })
                    current_speaker = speaker
            
            return changes

        except Exception as e:
            logger.error(f"Speaker change detection failed: {e}")
            return []

    def remove_speaker(self, speaker_id: str) -> bool:
        """
        Remove a speaker from the system.

        Args:
            speaker_id (str): Speaker identifier to remove

        Returns:
            bool: True if removed successfully
        """
        try:
            if speaker_id in self.enrolled_speakers:
                del self.enrolled_speakers[speaker_id]
                
                # Remove from all sessions
                for session_id, speakers in self.session_speakers.items():
                    if speaker_id in speakers:
                        speakers.remove(speaker_id)
                
                logger.info(f"Speaker removed: {speaker_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to remove speaker {speaker_id}: {e}")
            return False

    def get_speaker_profile(self, speaker_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed profile information for a speaker.

        Args:
            speaker_id (str): Speaker identifier

        Returns:
            Dict with speaker profile or None if not found
        """
        profile = self.enrolled_speakers.get(speaker_id)
        if profile:
            return {
                "speaker_id": profile.speaker_id,
                "name": profile.name,
                "created_at": profile.created_at.isoformat(),
                "last_active": profile.last_active.isoformat(),
                "total_speaking_time": profile.total_speaking_time,
                "turn_count": profile.turn_count,
                "has_voice_profile": profile.voice_embedding is not None
            }
        return None


# ---------------- Singleton accessor ---------------- #
_speaker_service: Optional[SpeakerIdentificationService] = None


def get_speaker_service() -> SpeakerIdentificationService:
    """Get the singleton speaker identification service instance."""
    global _speaker_service
    if _speaker_service is None:
        _speaker_service = SpeakerIdentificationService()
    return _speaker_service


# ---------------- Compatibility function ---------------- #
def identify_speaker(audio_bytes: bytes, session_speakers: List[str] = None) -> str:
    """
    Legacy compatibility function for speaker identification.
    
    Args:
        audio_bytes: Raw audio data
        session_speakers: List of known speakers in session
        
    Returns:
        str: Speaker identifier
    """
    # Simple fallback implementation
    session_speakers = session_speakers or []
    
    if not session_speakers:
        return "Speaker_01"
    
    # Basic hash-based assignment (placeholder)
    speaker_index = hash(audio_bytes) % len(session_speakers)
    return session_speakers[speaker_index] if session_speakers else "Speaker_01"