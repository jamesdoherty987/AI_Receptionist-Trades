"""
AI Logging Service
Centralized logging for all AI-related operations.
Uses print() so logs appear in Render.com's log viewer.

Usage:
    from src.utils.ai_logger import ai_logger
    
    ai_logger.info("Processing request", user_text="hello")
    ai_logger.error("OpenAI API failed", error=str(e), model="gpt-4o-mini")
"""
import json
import traceback
from datetime import datetime
from typing import Any, Optional, Dict
from functools import wraps
import time


class AILogger:
    """
    Simple logger for AI operations.
    Prints structured logs that show up in Render's log viewer.
    """
    
    def __init__(self, name: str = "ai"):
        self.name = name
        
        # Track metrics in memory for the /api/ai-logs endpoint
        self._call_counts: Dict[str, int] = {}
        self._error_counts: Dict[str, int] = {}
        self._recent_errors: list = []
        self.ERROR_SAMPLE_LIMIT = 50
        self.SLOW_THRESHOLD_MS = 2000
    
    def _format_extras(self, kwargs: dict) -> str:
        """Format extra fields for logging"""
        if not kwargs:
            return ""
        # Filter out traceback for inline display
        filtered = {k: v for k, v in kwargs.items() if k != 'traceback'}
        if not filtered:
            return ""
        return " | " + " | ".join(f"{k}={v}" for k, v in filtered.items())
    
    def debug(self, message: str, **kwargs):
        """Debug level - only logs if AI_DEBUG=true"""
        import os
        if os.getenv('AI_DEBUG', '').lower() == 'true':
            extras = self._format_extras(kwargs)
            print(f"[AI:DEBUG] {message}{extras}")
    
    def info(self, message: str, **kwargs):
        """Info level log"""
        operation = kwargs.get('operation', 'unknown')
        self._call_counts[operation] = self._call_counts.get(operation, 0) + 1
        
        extras = self._format_extras(kwargs)
        print(f"[AI] {message}{extras}")
    
    def warning(self, message: str, **kwargs):
        """Warning level log"""
        extras = self._format_extras(kwargs)
        print(f"[AI:WARN] ⚠️ {message}{extras}")
    
    def error(self, message: str, exception: Optional[Exception] = None, **kwargs):
        """Error level log with optional exception details"""
        error_type = type(exception).__name__ if exception else kwargs.get('error_type', 'unknown')
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1
        
        if exception:
            kwargs['error_type'] = error_type
            kwargs['error_message'] = str(exception)
            kwargs['traceback'] = traceback.format_exc()
        
        # Store recent errors for API endpoint
        error_record = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'error_type': error_type,
            **{k: v for k, v in kwargs.items() if k != 'traceback'}
        }
        self._recent_errors.append(error_record)
        if len(self._recent_errors) > self.ERROR_SAMPLE_LIMIT:
            self._recent_errors.pop(0)
        
        extras = self._format_extras(kwargs)
        print(f"[AI:ERROR] ❌ {message}{extras}")
        
        # Print traceback on separate line for readability
        if 'traceback' in kwargs:
            # Only print first few lines of traceback
            tb_lines = kwargs['traceback'].strip().split('\n')[-4:]
            print(f"[AI:ERROR] Traceback: {' -> '.join(line.strip() for line in tb_lines)}")
    
    def critical(self, message: str, exception: Optional[Exception] = None, **kwargs):
        """Critical level log"""
        if exception:
            kwargs['error_type'] = type(exception).__name__
            kwargs['error_message'] = str(exception)
        
        extras = self._format_extras(kwargs)
        print(f"[AI:CRITICAL] 🚨 {message}{extras}")
    
    def log_llm_call(self, model: str, operation: str, duration_ms: float = 0, 
                     success: bool = True, error: str = None, **kwargs):
        """Log an LLM API call"""
        log_data = {
            'operation': operation,
            'model': model,
            'duration_ms': round(duration_ms, 2),
            **kwargs
        }
        
        if not success:
            log_data['error'] = error
            self.error(f"LLM call failed: {operation}", **log_data)
        elif duration_ms > self.SLOW_THRESHOLD_MS:
            self.warning(f"Slow LLM call: {operation} ({round(duration_ms)}ms)", **log_data)
        else:
            self.info(f"LLM call: {operation}", **log_data)
    
    def log_tool_call(self, tool_name: str, arguments: dict, result: Any = None,
                      duration_ms: float = 0, success: bool = True, error: str = None):
        """Log a tool/function call"""
        log_data = {
            'operation': f'tool:{tool_name}',
            'tool_name': tool_name,
            'duration_ms': round(duration_ms, 2),
        }
        
        if not success:
            log_data['error'] = error
            self.error(f"Tool call failed: {tool_name}", **log_data)
        else:
            self.info(f"Tool call: {tool_name}", **log_data)
    
    def log_intent_detection(self, user_text: str, detected_intent: str, 
                             confidence: str, details: dict = None):
        """Log appointment intent detection"""
        self.info(
            f"Intent: {detected_intent} ({confidence})",
            operation='intent_detection',
            user_text=user_text[:100],
            intent=detected_intent,
            confidence=confidence
        )
    
    def get_stats(self) -> dict:
        """Get logging statistics"""
        return {
            'call_counts': self._call_counts.copy(),
            'error_counts': self._error_counts.copy(),
            'recent_errors_count': len(self._recent_errors),
            'total_calls': sum(self._call_counts.values()),
            'total_errors': sum(self._error_counts.values())
        }
    
    def get_recent_errors(self, limit: int = 10) -> list:
        """Get recent errors"""
        return self._recent_errors[-limit:]


def log_ai_operation(operation_name: str = None):
    """
    Decorator to automatically log AI operations with timing.
    
    Usage:
        @log_ai_operation("extract_name")
        def extract_name_ai(text: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                if duration_ms > ai_logger.SLOW_THRESHOLD_MS:
                    ai_logger.warning(f"Slow operation: {op_name}", 
                                     operation=op_name, duration_ms=round(duration_ms, 2))
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                ai_logger.error(
                    f"Operation failed: {op_name}",
                    exception=e,
                    operation=op_name,
                    duration_ms=round(duration_ms, 2)
                )
                raise
        
        return wrapper
    return decorator


def log_async_ai_operation(operation_name: str = None):
    """Async version of the AI operation logging decorator."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                if duration_ms > ai_logger.SLOW_THRESHOLD_MS:
                    ai_logger.warning(f"Slow async operation: {op_name}",
                                     operation=op_name, duration_ms=round(duration_ms, 2))
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                ai_logger.error(
                    f"Async operation failed: {op_name}",
                    exception=e,
                    operation=op_name,
                    duration_ms=round(duration_ms, 2)
                )
                raise
        
        return wrapper
    return decorator


# Global logger instance
ai_logger = AILogger()
