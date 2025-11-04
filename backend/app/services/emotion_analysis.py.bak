"""
Comprehensive logging system for EchoAI real-time emotion analysis
Handles WebSocket connections, emotion processing, alerts, and performance monitoring
"""

import logging
import logging.handlers
import asyncio
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from contextlib import asynccontextmanager
import sys
import traceback

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogCategory(str, Enum):
    WEBSOCKET = "websocket"
    EMOTION_ANALYSIS = "emotion_analysis"
    ALERT_SYSTEM = "alert_system"
    TRANSCRIPT = "transcript"
    PERFORMANCE = "performance"
    API = "api"
    SYSTEM = "system"

@dataclass
class LogEntry:
    """Structured log entry for EchoAI"""
    timestamp: float
    level: str
    category: str
    message: str
    session_id: Optional[str] = None
    speaker: Optional[str] = None
    processing_time_ms: Optional[float] = None
    emotion: Optional[str] = None
    sentiment_score: Optional[float] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

class RealTimeMetrics:
    """Real-time metrics collector for logging"""
    
    def _init_(self):
        self.metrics = {
            'websocket_connections': 0,
            'active_sessions': 0,
            'total_transcripts_processed': 0,
            'total_emotions_analyzed': 0,
            'alerts_triggered': 0,
            'avg_processing_time_ms': 0.0,
            'error_count': 0,
            'uptime_seconds': 0
        }
        self.start_time = time.time()
        self._lock = threading.Lock()
        
        # Performance tracking
        self.processing_times: List[float] = []
        self.max_processing_times = 1000  # Keep last 1000 measurements
        
    def update_metric(self, key: str, value: Any):
        """Thread-safe metric update"""
        with self._lock:
            if key in self.metrics:
                self.metrics[key] = value
            
    def increment_metric(self, key: str, amount: int = 1):
        """Thread-safe metric increment"""
        with self._lock:
            if key in self.metrics:
                self.metrics[key] += amount
                
    def add_processing_time(self, time_ms: float):
        """Add processing time measurement"""
        with self._lock:
            self.processing_times.append(time_ms)
            if len(self.processing_times) > self.max_processing_times:
                self.processing_times.pop(0)
            
            # Update average
            if self.processing_times:
                self.metrics['avg_processing_time_ms'] = sum(self.processing_times) / len(self.processing_times)
    
    def get_snapshot(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        with self._lock:
            self.metrics['uptime_seconds'] = time.time() - self.start_time
            return self.metrics.copy()

class AsyncLogHandler:
    """Async log handler for real-time logging"""
    
    def _init_(self, max_queue_size: int = 10000):
        self.log_queue = asyncio.Queue(maxsize=max_queue_size)
        self.handlers: List[Callable[[LogEntry], None]] = []
        self.processing_task: Optional[asyncio.Task] = None
        self.running = False
        
    def add_handler(self, handler: Callable[[LogEntry], None]):
        """Add log handler"""
        self.handlers.append(handler)
        
    async def start(self):
        """Start async log processing"""
        if not self.running:
            self.running = True
            self.processing_task = asyncio.create_task(self._process_logs())
            
    async def stop(self):
        """Stop async log processing"""
        self.running = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
                
    async def log(self, entry: LogEntry):
        """Add log entry to queue"""
        try:
            self.log_queue.put_nowait(entry)
        except asyncio.QueueFull:
            # If queue is full, drop oldest entry and add new one
            try:
                self.log_queue.get_nowait()
                self.log_queue.put_nowait(entry)
            except asyncio.QueueEmpty:
                pass
                
    async def _process_logs(self):
        """Process logs from queue"""
        while self.running:
            try:
                entry = await asyncio.wait_for(self.log_queue.get(), timeout=1.0)
                
                for handler in self.handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(entry)
                        else:
                            handler(entry)
                    except Exception as e:
                        # Log handler errors to stderr to avoid infinite loops
                        print(f"Log handler error: {e}", file=sys.stderr)
                        
                self.log_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Log processing error: {e}", file=sys.stderr)

class EchoAILogger:
    """Main logging system for EchoAI"""
    
    def _init_(self, 
                 log_level: str = "INFO",
                 log_dir: str = "logs",
                 enable_console: bool = True,
                 enable_file: bool = True,
                 enable_json: bool = True,
                 max_file_size_mb: int = 100,
                 backup_count: int = 5):
        
        self.log_level = getattr(logging, log_level.upper())
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.metrics = RealTimeMetrics()
        self.async_handler = AsyncLogHandler()
        
        # Setup standard Python logging
        self._setup_standard_logging(enable_console, enable_file, max_file_size_mb, backup_count)
        
        # Setup async handlers
        if enable_json:
            self.async_handler.add_handler(self._json_file_handler)
        self.async_handler.add_handler(self._metrics_handler)
        
        # Performance tracking
        self.session_contexts: Dict[str, Dict[str, Any]] = {}
        
    def _setup_standard_logging(self, enable_console: bool, enable_file: bool, 
                               max_file_size_mb: int, backup_count: int):
        """Setup standard Python logging"""
        
        # Create formatters
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        
        # Root logger setup
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self.log_level)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # File handler with rotation
        if enable_file:
            file_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / "echoai.log",
                maxBytes=max_file_size_mb * 1024 * 1024,
                backupCount=backup_count
            )
            file_handler.setLevel(self.log_level)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        
        # Error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "echoai_errors.log",
            maxBytes=50 * 1024 * 1024,
            backupCount=backup_count
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
    async def _json_file_handler(self, entry: LogEntry):
        """Handler for JSON structured logs"""
        json_log_file = self.log_dir / "echoai_structured.jsonl"
        
        try:
            with open(json_log_file, 'a', encoding='utf-8') as f:
                json.dump(entry.to_dict(), f, ensure_ascii=False)
                f.write('\n')
        except Exception as e:
            logging.error(f"Failed to write JSON log: {e}")
            
    async def _metrics_handler(self, entry: LogEntry):
        """Handler for metrics updates"""
        if entry.processing_time_ms:
            self.metrics.add_processing_time(entry.processing_time_ms)
            
        if entry.level == "ERROR":
            self.metrics.increment_metric('error_count')
            
    async def start(self):
        """Start the logging system"""
        await self.async_handler.start()
        logging.info("EchoAI logging system started")
        
    async def stop(self):
        """Stop the logging system"""
        await self.async_handler.stop()
        logging.info("EchoAI logging system stopped")

    # Context managers for session tracking
    @asynccontextmanager
    async def session_context(self, session_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Context manager for session logging"""
        self.session_contexts[session_id] = {
            'start_time': time.time(),
            'metadata': metadata or {}
        }
        
        await self.log_session_start(session_id, metadata)
        self.metrics.increment_metric('active_sessions')
        
        try:
            yield session_id
        finally:
            duration = time.time() - self.session_contexts[session_id]['start_time']
            await self.log_session_end(session_id, duration)
            self.metrics.increment_metric('active_sessions', -1)
            del self.session_contexts[session_id]

    # Specialized logging methods for EchoAI
    async def log_websocket_connection(self, session_id: str, client_info: Dict[str, Any], connected: bool = True):
        """Log WebSocket connection events"""
        action = "connected" if connected else "disconnected"
        
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,
            category=LogCategory.WEBSOCKET,
            message=f"WebSocket {action}",
            session_id=session_id,
            metadata=client_info
        )
        
        if connected:
            self.metrics.increment_metric('websocket_connections')
        else:
            self.metrics.increment_metric('websocket_connections', -1)
            
        await self.async_handler.log(entry)
        logging.info(f"WebSocket {action} - Session: {session_id}")
        
    async def log_transcript_processing(self, session_id: str, speaker: str, text: str, 
                                      processing_time_ms: float, is_final: bool = True):
        """Log transcript processing"""
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.DEBUG,
            category=LogCategory.TRANSCRIPT,
            message=f"Transcript processed: {text[:50]}{'...' if len(text) > 50 else ''}",
            session_id=session_id,
            speaker=speaker,
            processing_time_ms=processing_time_ms,
            metadata={'is_final': is_final, 'text_length': len(text)}
        )
        
        self.metrics.increment_metric('total_transcripts_processed')
        await self.async_handler.log(entry)
        
    async def log_emotion_analysis(self, session_id: str, speaker: str, emotion_result, 
                                 processing_time_ms: float):
        """Log emotion analysis results"""
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.DEBUG,
            category=LogCategory.EMOTION_ANALYSIS,
            message=f"Emotion analyzed: {emotion_result.primary_emotion.value}",
            session_id=session_id,
            speaker=speaker,
            processing_time_ms=processing_time_ms,
            emotion=emotion_result.primary_emotion.value,
            sentiment_score=emotion_result.sentiment_score,
            confidence=emotion_result.confidence,
            metadata={
                'emotional_intensity': emotion_result.emotional_intensity,
                'valence': emotion_result.valence,
                'arousal': emotion_result.arousal,
                'context_influenced': emotion_result.context_influenced
            }
        )
        
        self.metrics.increment_metric('total_emotions_analyzed')
        await self.async_handler.log(entry)
        
    async def log_alert(self, alert_type: str, alert_data: Dict[str, Any], session_id: str = None):
        """Log emotion alerts"""
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.WARNING,
            category=LogCategory.ALERT_SYSTEM,
            message=f"Emotion alert triggered: {alert_type}",
            session_id=session_id,
            speaker=alert_data.get('speaker'),
            emotion=alert_data.get('emotion'),
            sentiment_score=alert_data.get('sentiment_score'),
            confidence=alert_data.get('confidence'),
            metadata={'alert_type': alert_type, 'full_alert_data': alert_data}
        )
        
        self.metrics.increment_metric('alerts_triggered')
        await self.async_handler.log(entry)
        logging.warning(f"EMOTION ALERT: {alert_type} - {alert_data}")
        
    async def log_performance_metric(self, metric_name: str, value: float, 
                                   session_id: str = None, metadata: Dict[str, Any] = None):
        """Log performance metrics"""
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,
            category=LogCategory.PERFORMANCE,
            message=f"Performance metric: {metric_name} = {value}",
            session_id=session_id,
            processing_time_ms=value if 'time' in metric_name.lower() else None,
            metadata={'metric_name': metric_name, 'metric_value': value, **(metadata or {})}
        )
        
        await self.async_handler.log(entry)
        
    async def log_api_request(self, endpoint: str, method: str, status_code: int, 
                            response_time_ms: float, session_id: str = None):
        """Log API requests"""
        level = LogLevel.ERROR if status_code >= 400 else LogLevel.INFO
        
        entry = LogEntry(
            timestamp=time.time(),
            level=level,
            category=LogCategory.API,
            message=f"{method} {endpoint} - {status_code}",
            session_id=session_id,
            processing_time_ms=response_time_ms,
            metadata={'endpoint': endpoint, 'method': method, 'status_code': status_code}
        )
        
        await self.async_handler.log(entry)
        
    async def log_error(self, error: Exception, session_id: str = None, 
                       context: str = None, trace_id: str = None):
        """Log errors with full traceback"""
        tb_str = traceback.format_exc()
        
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.ERROR,
            category=LogCategory.SYSTEM,
            message=f"Error in {context or 'unknown'}: {str(error)}",
            session_id=session_id,
            trace_id=trace_id,
            metadata={'error_type': type(error)._name_, 'traceback': tb_str}
        )
        
        await self.async_handler.log(entry)
        logging.error(f"Error in {context or 'unknown'}: {str(error)}", exc_info=True)
        
    async def log_session_start(self, session_id: str, metadata: Dict[str, Any] = None):
        """Log session start"""
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,
            category=LogCategory.SYSTEM,
            message=f"Session started: {session_id}",
            session_id=session_id,
            metadata=metadata
        )
        
        await self.async_handler.log(entry)
        logging.info(f"Session started: {session_id}")
        
    async def log_session_end(self, session_id: str, duration_seconds: float):
        """Log session end"""
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,
            category=LogCategory.SYSTEM,
            message=f"Session ended: {session_id}",
            session_id=session_id,
            metadata={'duration_seconds': duration_seconds}
        )
        
        await self.async_handler.log(entry)
        logging.info(f"Session ended: {session_id} (duration: {duration_seconds:.2f}s)")
        
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self.metrics.get_snapshot()
        
    def get_log_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get log summary for dashboard"""
        # This would typically query the JSON logs
        # For now, return current metrics
        return {
            'current_metrics': self.get_metrics(),
            'time_period_hours': hours_back,
            'log_files': {
                'main_log': str(self.log_dir / "echoai.log"),
                'error_log': str(self.log_dir / "echoai_errors.log"),
                'structured_log': str(self.log_dir / "echoai_structured.jsonl")
            }
        }

# Usage examples and integration
logger_instance = None

async def get_logger() -> EchoAILogger:
    """Get global logger instance"""
    global logger_instance
    if logger_instance is None:
        logger_instance = EchoAILogger(
            log_level="INFO",
            log_dir="logs",
            enable_console=True,
            enable_file=True,
            enable_json=True
        )
        await logger_instance.start()
    return logger_instance

# Integration with your RealTimeEmotionApp
class LoggedRealTimeEmotionApp:
    """Enhanced RealTimeEmotionApp with comprehensive logging"""
    
    def _init_(self):
        # Your existing initialization
        self.analyzer = None  # Your RealTimeEmotionAnalyzer
        self.alert_system = None  # Your EmotionAlertSystem
        
    async def initialize(self):
        """Initialize with logging"""
        self.logger = await get_logger()
        
        # Initialize your components here
        # self.analyzer = RealTimeEmotionAnalyzer()
        # self.alert_system = EmotionAlertSystem()
        
        # Setup alert callback with logging
        # self.alert_system.add_alert_callback(self._handle_logged_emotion_alert)
        
    async def process_transcript_with_logging(self, session_id: str, text: str, 
                                            speaker: str, is_final: bool = True):
        """Process transcript with comprehensive logging"""
        start_time = time.time()
        
        try:
            # Your existing processing logic would go here
            # result = await self.analyzer.analyze_immediate(entry)
            
            # For demo, create a mock result
            processing_time_ms = (time.time() - start_time) * 1000
            
            # Log transcript processing
            await self.logger.log_transcript_processing(
                session_id, speaker, text, processing_time_ms, is_final
            )
            
            # Log emotion analysis (with your actual result)
            # await self.logger.log_emotion_analysis(
            #     session_id, speaker, result, processing_time_ms
            # )
            
            # Log performance metrics
            await self.logger.log_performance_metric(
                "transcript_processing_time_ms", processing_time_ms, session_id
            )
            
            return {"status": "processed", "processing_time_ms": processing_time_ms}
            
        except Exception as e:
            await self.logger.log_error(e, session_id, "transcript_processing")
            raise
            
    async def _handle_logged_emotion_alert(self, alert_type: str, alert_data: Dict[str, Any]):
        """Handle emotion alerts with logging"""
        session_id = alert_data.get('session_id')  # You'd need to add this to alert_data
        
        await self.logger.log_alert(alert_type, alert_data, session_id)
        
        # Your existing alert handling logic
        # ... existing code ...

# Example usage
async def demo_logging_system():
    """Demo the logging system"""
    logger = await get_logger()
    
    # Simulate session
    session_id = "demo_session_123"
    
    async with logger.session_context(session_id, {"user_agent": "demo", "ip": "127.0.0.1"}):
        
        # Simulate WebSocket connection
        await logger.log_websocket_connection(session_id, {"ip": "127.0.0.1"}, connected=True)
        
        # Simulate transcript processing
        await logger.log_transcript_processing(
            session_id, "Alice", "Hello everyone, I'm excited about this project!", 25.5
        )
        
        # Simulate emotion analysis
        # You'd use your actual EmotionAnalysisResult here
        mock_emotion_result = type('MockResult', (), {
            'primary_emotion': type('Emotion', (), {'value': 'excitement'}),
            'sentiment_score': 0.8,
            'confidence': 0.9,
            'emotional_intensity': 0.7,
            'valence': 0.8,
            'arousal': 0.6,
            'context_influenced': False
        })()
        
        await logger.log_emotion_analysis(session_id, "Alice", mock_emotion_result, 15.2)
        
        # Simulate alert
        await logger.log_alert("high_positive_emotion", {
            "speaker": "Alice",
            "emotion": "excitement",
            "sentiment_score": 0.8,
            "confidence": 0.9
        }, session_id)
        
        # Simulate API request
        await logger.log_api_request("/api/analytics", "GET", 200, 45.3, session_id)
        
        # WebSocket disconnect
        await logger.log_websocket_connection(session_id, {"ip": "127.0.0.1"}, connected=False)
    
    # Get metrics
    metrics = logger.get_metrics()
    print("\nCurrent Metrics:")
    print(json.dumps(metrics, indent=2))
    
    await logger.stop()

if _name_ == "_main_":
    asyncio.run(demo_logging_system())