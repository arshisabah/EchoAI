# app/core/monitoring.py
"""
Production monitoring and metrics for EchoAI.
"""

import time
import logging
import psutil
from datetime import datetime
from typing import Dict, Any
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collect and track application metrics."""
    
    def __init__(self):
        self._lock = Lock()
        self.metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "websocket_connections": 0,
            "active_sessions": 0,
            "transcripts_processed": 0,
            "emotions_analyzed": 0,
            "summaries_generated": 0,
            "average_response_time_ms": 0.0,
            "uptime_seconds": 0,
        }
        self.request_times = []
        self.max_request_times = 1000
        self.start_time = time.time()
    
    def increment(self, metric: str, amount: int = 1):
        """Increment a metric."""
        with self._lock:
            if metric in self.metrics:
                self.metrics[metric] += amount
    
    def decrement(self, metric: str, amount: int = 1):
        """Decrement a metric."""
        with self._lock:
            if metric in self.metrics:
                self.metrics[metric] = max(0, self.metrics[metric] - amount)
    
    def record_request_time(self, duration_ms: float):
        """Record request processing time."""
        with self._lock:
            self.request_times.append(duration_ms)
            if len(self.request_times) > self.max_request_times:
                self.request_times.pop(0)
            
            # Update average
            if self.request_times:
                self.metrics["average_response_time_ms"] = sum(self.request_times) / len(self.request_times)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        with self._lock:
            self.metrics["uptime_seconds"] = int(time.time() - self.start_time)
            return self.metrics.copy()
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used_mb": psutil.virtual_memory().used / (1024 * 1024),
            "disk_percent": psutil.disk_usage('/').percent,
            "process_count": len(psutil.pids()),
        }


# Global metrics collector
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector."""
    return _metrics_collector


class PerformanceMonitor:
    """Monitor performance of specific operations."""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.metrics = get_metrics_collector()
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        self.metrics.record_request_time(duration_ms)
        
        if exc_type is None:
            self.metrics.increment("requests_success")
            logger.debug(f"{self.operation_name} completed in {duration_ms:.2f}ms")
        else:
            self.metrics.increment("requests_failed")
            logger.error(f"{self.operation_name} failed after {duration_ms:.2f}ms: {exc_val}")
        
        return False  # Don't suppress exceptions


class HealthChecker:
    """Check health of application components."""
    
    @staticmethod
    def check_transcription_service() -> Dict[str, Any]:
        """Check transcription service health."""
        try:
            from app.services.transcription_service import get_transcription_service
            service = get_transcription_service()
            
            return {
                "status": "healthy" if service.model is not None else "degraded",
                "model_type": service.model_type,
                "device": service.device
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    @staticmethod
    def check_emotion_service() -> Dict[str, Any]:
        """Check emotion service health."""
        try:
            from app.services.emotion_analysis import get_emotion_service
            service = get_emotion_service()
            
            return {
                "status": "healthy",
                "supported_emotions": len(service.supported_emotions)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    @staticmethod
    def check_database() -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            from app.modules.realtime_store import get_transcript_store
            store = get_transcript_store()
            
            # Try a simple operation
            sessions = store.list_sessions()
            
            return {
                "status": "healthy",
                "active_sessions": len(sessions)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    @staticmethod
    def get_comprehensive_health() -> Dict[str, Any]:
        """Get comprehensive health check."""
        transcription = HealthChecker.check_transcription_service()
        emotion = HealthChecker.check_emotion_service()
        database = HealthChecker.check_database()
        metrics = get_metrics_collector().get_metrics()
        system = get_metrics_collector().get_system_metrics()
        
        # Determine overall status
        component_statuses = [
            transcription["status"],
            emotion["status"],
            database["status"]
        ]
        
        if all(s == "healthy" for s in component_statuses):
            overall_status = "healthy"
        elif any(s == "unhealthy" for s in component_statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "transcription": transcription,
                "emotion": emotion,
                "database": database
            },
            "metrics": metrics,
            "system": system
        }


class AlertManager:
    """Manage alerts for critical conditions."""
    
    def __init__(self):
        self.alerts = defaultdict(list)
        self._lock = Lock()
    
    def add_alert(self, level: str, message: str, details: Dict[str, Any] = None):
        """Add an alert."""
        alert = {
            "level": level,
            "message": message,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        with self._lock:
            self.alerts[level].append(alert)
            
            # Log the alert
            log_method = getattr(logger, level.lower(), logger.info)
            log_method(f"ALERT: {message}")
            
            # Keep only recent alerts (last 100 per level)
            if len(self.alerts[level]) > 100:
                self.alerts[level] = self.alerts[level][-100:]
    
    def get_alerts(self, level: str = None) -> list:
        """Get alerts, optionally filtered by level."""
        with self._lock:
            if level:
                return self.alerts.get(level, []).copy()
            
            all_alerts = []
            for level_alerts in self.alerts.values():
                all_alerts.extend(level_alerts)
            
            # Sort by timestamp
            all_alerts.sort(key=lambda x: x["timestamp"], reverse=True)
            return all_alerts
    
    def clear_alerts(self, level: str = None):
        """Clear alerts."""
        with self._lock:
            if level:
                self.alerts[level] = []
            else:
                self.alerts.clear()


# Global alert manager
_alert_manager = AlertManager()


def get_alert_manager() -> AlertManager:
    """Get global alert manager."""
    return _alert_manager


def check_system_resources():
    """Check system resources and trigger alerts if needed."""
    alert_manager = get_alert_manager()
    
    # Check memory
    memory_percent = psutil.virtual_memory().percent
    if memory_percent > 90:
        alert_manager.add_alert(
            "critical",
            "High memory usage detected",
            {"memory_percent": memory_percent}
        )
    elif memory_percent > 80:
        alert_manager.add_alert(
            "warning",
            "Elevated memory usage",
            {"memory_percent": memory_percent}
        )
    
    # Check CPU
    cpu_percent = psutil.cpu_percent(interval=1.0)
    if cpu_percent > 90:
        alert_manager.add_alert(
            "critical",
            "High CPU usage detected",
            {"cpu_percent": cpu_percent}
        )
    
    # Check disk
    disk_percent = psutil.disk_usage('/').percent
    if disk_percent > 90:
        alert_manager.add_alert(
            "critical",
            "Low disk space",
            {"disk_percent": disk_percent}
        )