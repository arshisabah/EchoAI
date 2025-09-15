"""
AI-powered summary generation service for EchoAI.
Supports multiple LLM providers: OpenAI GPT, Anthropic Claude, and local models.
"""

import logging
import asyncio
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
import json

import openai
import anthropic
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SummaryType = Literal["brief", "detailed", "bullet_points", "action_items", "key_topics"]

class SummaryResult(BaseModel):
    """AI summary generation result"""
    summary: str
    summary_type: SummaryType
    word_count: int
    processing_time_ms: float
    model_used: str
    confidence: float = 1.0
    key_points: Optional[List[str]] = None
    action_items: Optional[List[str]] = None
    topics: Optional[List[str]] = None

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def generate_summary(
        self, 
        transcript_text: str, 
        summary_type: SummaryType = "brief",
        max_words: Optional[int] = None
    ) -> SummaryResult:
        """Generate summary from transcript text"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name/identifier"""
        pass

class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider for summary generation"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = openai.AsyncOpenAI(api_key=self.api_key) if self.api_key else None
    
    def is_available(self) -> bool:
        return self.client is not None
    
    def get_model_name(self) -> str:
        return f"openai/{self.model}"
    
    def _build_prompt(self, transcript_text: str, summary_type: SummaryType, max_words: Optional[int]) -> str:
        """Build prompt based on summary type"""
        word_limit = f" in maximum {max_words} words" if max_words else ""
        
        prompts = {
            "brief": f"Provide a concise summary of the following conversation{word_limit}. Focus on the main points and key outcomes:\n\n{transcript_text}",
            
            "detailed": f"Provide a comprehensive summary of the following conversation{word_limit}. Include main topics discussed, key points, decisions made, and important details:\n\n{transcript_text}",
            
            "bullet_points": f"Summarize the following conversation as bullet points{word_limit}. Each point should capture a key topic or decision:\n\n{transcript_text}",
            
            "action_items": f"Extract action items and next steps from the following conversation{word_limit}. Format as a list of specific tasks or decisions that need to be acted upon:\n\n{transcript_text}",
            
            "key_topics": f"Identify and summarize the key topics discussed in the following conversation{word_limit}. Group related points together:\n\n{transcript_text}"
        }
        
        return prompts.get(summary_type, prompts["brief"])
    
    async def generate_summary(
        self, 
        transcript_text: str, 
        summary_type: SummaryType = "brief",
        max_words: Optional[int] = None
    ) -> SummaryResult:
        """Generate summary using OpenAI GPT"""
        if not self.is_available():
            raise ValueError("OpenAI not available - missing API key")
        
        start_time = time.time()
        
        try:
            prompt = self._build_prompt(transcript_text, summary_type, max_words)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a professional meeting summarizer. Provide clear, concise, and well-structured summaries."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_words * 2 if max_words else 1000,
                temperature=0.3
            )
            
            processing_time = (time.time() - start_time) * 1000
            summary_text = response.choices[0].message.content.strip()
            
            # Extract structured information for certain summary types
            key_points = None
            action_items = None
            topics = None
            
            if summary_type == "bullet_points":
                key_points = [line.strip("• - ").strip() for line in summary_text.split('\n') if line.strip()]
            elif summary_type == "action_items":
                action_items = [line.strip("• - 1234567890.").strip() for line in summary_text.split('\n') if line.strip()]
            elif summary_type == "key_topics":
                topics = [line.strip("• - ").strip() for line in summary_text.split('\n') if line.strip()]
            
            return SummaryResult(
                summary=summary_text,
                summary_type=summary_type,
                word_count=len(summary_text.split()),
                processing_time_ms=processing_time,
                model_used=self.get_model_name(),
                key_points=key_points,
                action_items=action_items,
                topics=topics
            )
            
        except Exception as e:
            logger.error(f"OpenAI summary generation error: {e}")
            raise

class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider for summary generation"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key) if self.api_key else None
    
    def is_available(self) -> bool:
        return self.client is not None
    
    def get_model_name(self) -> str:
        return f"anthropic/{self.model}"
    
    def _build_prompt(self, transcript_text: str, summary_type: SummaryType, max_words: Optional[int]) -> str:
        """Build prompt for Claude"""
        word_limit = f" Keep the summary under {max_words} words." if max_words else ""
        
        prompts = {
            "brief": f"Please provide a brief, concise summary of this conversation.{word_limit} Focus on the most important points and outcomes.\n\nConversation:\n{transcript_text}",
            
            "detailed": f"Please provide a detailed, comprehensive summary of this conversation.{word_limit} Include all major topics, key decisions, and important context.\n\nConversation:\n{transcript_text}",
            
            "bullet_points": f"Please summarize this conversation as clear bullet points.{word_limit} Each bullet should capture a distinct topic or decision.\n\nConversation:\n{transcript_text}",
            
            "action_items": f"Please extract specific action items and next steps from this conversation.{word_limit} List concrete tasks that need to be completed.\n\nConversation:\n{transcript_text}",
            
            "key_topics": f"Please identify and summarize the key topics discussed in this conversation.{word_limit} Group related discussion points together.\n\nConversation:\n{transcript_text}"
        }
        
        return prompts.get(summary_type, prompts["brief"])
    
    async def generate_summary(
        self, 
        transcript_text: str, 
        summary_type: SummaryType = "brief",
        max_words: Optional[int] = None
    ) -> SummaryResult:
        """Generate summary using Anthropic Claude"""
        if not self.is_available():
            raise ValueError("Anthropic not available - missing API key")
        
        start_time = time.time()
        
        try:
            prompt = self._build_prompt(transcript_text, summary_type, max_words)
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_words * 2 if max_words else 1000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            
            processing_time = (time.time() - start_time) * 1000
            summary_text = response.content[0].text.strip()
            
            # Extract structured information
            key_points = None
            action_items = None
            topics = None
            
            if summary_type == "bullet_points":
                key_points = [line.strip("• - ").strip() for line in summary_text.split('\n') if line.strip()]
            elif summary_type == "action_items":
                action_items = [line.strip("• - 1234567890.").strip() for line in summary_text.split('\n') if line.strip()]
            elif summary_type == "key_topics":
                topics = [line.strip("• - ").strip() for line in summary_text.split('\n') if line.strip()]
            
            return SummaryResult(
                summary=summary_text,
                summary_type=summary_type,
                word_count=len(summary_text.split()),
                processing_time_ms=processing_time,
                model_used=self.get_model_name(),
                key_points=key_points,
                action_items=action_items,
                topics=topics
            )
            
        except Exception as e:
            logger.error(f"Anthropic summary generation error: {e}")
            raise

class LocalTransformerProvider(LLMProvider):
    """Local transformer model provider (Hugging Face)"""
    
    def __init__(self, model_name: str = "facebook/bart-large-cnn"):
        self.model_name = model_name
        self.summarizer = None
        self.tokenizer = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize local model"""
        try:
            self.summarizer = pipeline(
                "summarization", 
                model=self.model_name,
                device=0 if os.getenv("USE_GPU", "false").lower() == "true" else -1
            )
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            logger.info(f"Initialized local model: {self.model_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize local model {self.model_name}: {e}")
    
    def is_available(self) -> bool:
        return self.summarizer is not None
    
    def get_model_name(self) -> str:
        return f"local/{self.model_name}"
    
    async def generate_summary(
        self, 
        transcript_text: str, 
        summary_type: SummaryType = "brief",
        max_words: Optional[int] = None
    ) -> SummaryResult:
        """Generate summary using local transformer model"""
        if not self.is_available():
            raise ValueError("Local model not available")
        
        start_time = time.time()
        
        try:
            # Adjust parameters based on summary type
            if summary_type == "brief":
                max_length = max_words or 100
                min_length = max_length // 4
            elif summary_type == "detailed":
                max_length = max_words or 300
                min_length = max_length // 3
            else:
                max_length = max_words or 150
                min_length = max_length // 4
            
            # Handle long text by chunking if necessary
            max_input_length = 1024  # BART limit
            if len(transcript_text.split()) > max_input_length:
                # Simple chunking strategy
                chunks = self._chunk_text(transcript_text, max_input_length)
                chunk_summaries = []
                
                for chunk in chunks:
                    result = self.summarizer(
                        chunk,
                        max_length=max_length // len(chunks),
                        min_length=min_length // len(chunks),
                        do_sample=False
                    )
                    chunk_summaries.append(result[0]['summary_text'])
                
                # Combine chunk summaries
                combined_text = " ".join(chunk_summaries)
                
                # Final summarization pass
                if len(combined_text.split()) > max_length:
                    final_result = self.summarizer(
                        combined_text,
                        max_length=max_length,
                        min_length=min_length,
                        do_sample=False
                    )
                    summary_text = final_result[0]['summary_text']
                else:
                    summary_text = combined_text
            else:
                result = self.summarizer(
                    transcript_text,
                    max_length=max_length,
                    min_length=min_length,
                    do_sample=False
                )
                summary_text = result[0]['summary_text']
            
            processing_time = (time.time() - start_time) * 1000
            
            return SummaryResult(
                summary=summary_text,
                summary_type=summary_type,
                word_count=len(summary_text.split()),
                processing_time_ms=processing_time,
                model_used=self.get_model_name(),
                confidence=0.8  # Local models typically have lower confidence
            )
            
        except Exception as e:
            logger.error(f"Local model summary generation error: {e}")
            raise
    
    def _chunk_text(self, text: str, max_tokens: int) -> List[str]:
        """Chunk text into manageable pieces"""
        words = text.split()
        chunks = []
        current_chunk = []
        
        for word in words:
            current_chunk.append(word)
            if len(current_chunk) >= max_tokens:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks

class AISummaryService:
    """Main AI summary service with provider management"""
    
    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        self.primary_provider: Optional[str] = None
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available LLM providers"""
        # OpenAI GPT
        openai_provider = OpenAIProvider()
        if openai_provider.is_available():
            self.providers["openai"] = openai_provider
            if not self.primary_provider:
                self.primary_provider = "openai"
                logger.info("OpenAI initialized as primary summary provider")
        
        # Anthropic Claude
        anthropic_provider = AnthropicProvider()
        if anthropic_provider.is_available():
            self.providers["anthropic"] = anthropic_provider
            if not self.primary_provider:
                self.primary_provider = "anthropic"
                logger.info("Anthropic Claude initialized as primary summary provider")
        
        # Local transformer model
        local_provider = LocalTransformerProvider()
        if local_provider.is_available():
            self.providers["local"] = local_provider
            if not self.primary_provider:
                self.primary_provider = "local"
                logger.info("Local transformer initialized as primary summary provider")
        
        if not self.providers:
            logger.warning("No LLM providers available for summary generation!")
        else:
            logger.info(f"Available summary providers: {list(self.providers.keys())}")
    
    async def generate_summary(
        self,
        transcript_text: str,
        summary_type: SummaryType = "brief",
        max_words: Optional[int] = None,
        preferred_provider: Optional[str] = None
    ) -> SummaryResult:
        """
        Generate AI summary with provider fallback
        """
        if not self.providers:
            return SummaryResult(
                summary="No AI providers available for summary generation",
                summary_type=summary_type,
                word_count=0,
                processing_time_ms=0.0,
                model_used="none",
                confidence=0.0
            )
        
        if not transcript_text.strip():
            return SummaryResult(
                summary="No transcript content to summarize",
                summary_type=summary_type,
                word_count=0,
                processing_time_ms=0.0,
                model_used="none",
                confidence=0.0
            )
        
        # Determine provider to use
        provider_name = preferred_provider if preferred_provider in self.providers else self.primary_provider
        
        try:
            provider = self.providers[provider_name]
            result = await provider.generate_summary(transcript_text, summary_type, max_words)
            logger.info(f"Generated {summary_type} summary using {provider_name}: {result.word_count} words")
            return result
            
        except Exception as e:
            logger.error(f"Primary summary provider {provider_name} failed: {e}")
            
            # Try fallback providers
            for fallback_name, fallback_provider in self.providers.items():
                if fallback_name != provider_name:
                    try:
                        result = await fallback_provider.generate_summary(transcript_text, summary_type, max_words)
                        logger.info(f"Fallback summary using {fallback_name}: {result.word_count} words")
                        return result
                    except Exception as fallback_error:
                        logger.error(f"Fallback provider {fallback_name} failed: {fallback_error}")
                        continue
            
            # All providers failed - return error summary
            return SummaryResult(
                summary="Summary generation failed - all providers unavailable",
                summary_type=summary_type,
                word_count=0,
                processing_time_ms=0.0,
                model_used="error",
                confidence=0.0
            )
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names"""
        return list(self.providers.keys())
    
    def set_primary_provider(self, provider_name: str) -> bool:
        """Set the primary summary provider"""
        if provider_name in self.providers:
            self.primary_provider = provider_name
            logger.info(f"Primary summary provider set to: {provider_name}")
            return True
        return False

# Enhanced ReportService that integrates with the new AI summary service
class ReportService:
    """Enhanced report service with real AI summary generation"""
    
    def __init__(self):
        self.ai_service = AISummaryService()
    
    async def generate_summary(
        self,
        session_id: str,
        summary_type: SummaryType = "brief",
        max_length: Optional[int] = None,
        include_speakers: bool = True,
        preferred_provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive summary for a session
        """
        start_time = time.time()
        
        try:
            # Import here to avoid circular imports
            from modules.realtime_store import get_transcript_store
            
            store = get_transcript_store()
            
            # Get transcript text
            transcript_text = store.get_full_text(session_id, include_speakers)
            
            if not transcript_text.strip():
                return {
                    "error": "No transcript content found for session",
                    "session_id": session_id
                }
            
            # Get session analytics for context
            analytics = store.get_analytics(session_id)
            
            # Generate AI summary
            summary_result = await self.ai_service.generate_summary(
                transcript_text=transcript_text,
                summary_type=summary_type,
                max_words=max_length,
                preferred_provider=preferred_provider
            )
            
            # Calculate compression ratio
            source_word_count = analytics.get('total_words', 0)
            compression_ratio = (
                summary_result.word_count / source_word_count 
                if source_word_count > 0 else 0.0
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            # Build comprehensive response
            response = {
                "session_id": session_id,
                "summary": summary_result.summary,
                "summary_type": summary_type,
                "word_count": summary_result.word_count,
                "source_transcript_length": source_word_count,
                "compression_ratio": compression_ratio,
                "generated_at": datetime.now().isoformat(),
                "processing_time_ms": processing_time,
                "model_used": summary_result.model_used,
                "confidence": summary_result.confidence,
                
                # Additional structured data
                "key_points": summary_result.key_points,
                "action_items": summary_result.action_items,
                "topics": summary_result.topics,
                
                # Session context
                "session_analytics": {
                    "total_speakers": len(analytics.get('speakers', [])),
                    "total_turns": analytics.get('total_turns', 0),
                    "session_duration": analytics.get('session_duration_seconds', 0)
                }
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Summary generation failed for session {session_id}: {e}")
            return {
                "error": str(e),
                "session_id": session_id,
                "generated_at": datetime.now().isoformat()
            }
    
    def get_available_providers(self) -> List[str]:
        """Get available AI summary providers"""
        return self.ai_service.get_available_providers()
    
    def set_primary_provider(self, provider_name: str) -> bool:
        """Set primary AI summary provider"""
        return self.ai_service.set_primary_provider(provider_name)

# Global service instances
_report_service = None
_ai_summary_service = None

def get_report_service() -> ReportService:
    """Get the global report service instance"""
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service

def get_ai_summary_service() -> AISummaryService:
    """Get the global AI summary service instance"""
    global _ai_summary_service
    if _ai_summary_service is None:
        _ai_summary_service = AISummaryService()
    return _ai_summary_service