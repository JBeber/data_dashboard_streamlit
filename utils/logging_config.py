"""
Centralized logging configuration for the VV Data Dashboard.

This module provides a unified logging system that supports:
- Global Google Drive error handling
- Module-specific error tracking  
- Structured logging with error categorization
- Google Cloud Logging integration for Cloud Run deployment
- Page-independent user tracking with session timestamps
"""

import logging
import sys
import traceback
import uuid
from datetime import datetime
from functools import wraps
from typing import Dict, Any, Optional
import streamlit as st

try:
    from google.cloud import logging as cloud_logging
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False


class AppLogger:
    """
    Centralized logger for the VV Data Dashboard application.
    
    Provides structured logging with support for:
    - Global error handling (Google Drive, infrastructure)
    - Module-specific error tracking
    - Error categorization by type
    - Google Cloud Logging integration
    """
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())[:8]  # Short session ID
        self.setup_logger()
    
    def setup_logger(self):
        """Initialize logging configuration with Cloud Logging if available."""
        
        # Setup standard Python logger
        self.logger = logging.getLogger('vv_dashboard')
        self.logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Add console handler for local development
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Setup Google Cloud Logging if available
        self.cloud_client = None
        if GOOGLE_CLOUD_AVAILABLE:
            try:
                self.cloud_client = cloud_logging.Client()
                cloud_handler = self.cloud_client.get_default_handler()
                self.logger.addHandler(cloud_handler)
                self.logger.info("Google Cloud Logging initialized successfully")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Google Cloud Logging: {e}")
                self.logger.info("Falling back to console logging only")
    
    def _create_log_context(self, module: str = None, error_type: str = None, 
                           custom_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create structured log context with session and error information."""
        
        context = {
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'app': 'vv_dashboard'
        }
        
        if module:
            context['module'] = module
        
        if error_type:
            context['error_type'] = error_type
        
        # Add Streamlit session info if available
        try:
            if hasattr(st, 'session_state'):
                context['streamlit_session'] = str(id(st.session_state))
        except:
            pass
        
        # Merge custom context
        if custom_context:
            context.update(custom_context)
        
        return context
    
    def is_google_drive_error(self, error: Exception) -> bool:
        """Check if the error is related to Google Drive connectivity."""
        error_str = str(error).lower()
        google_drive_indicators = [
            'ssl', 'record layer failure', 'network', 'timeout',
            'quota', 'rate limit', 'authentication', 'oauth',
            'google', 'drive', 'connection'
        ]
        return any(indicator in error_str for indicator in google_drive_indicators)
    
    def handle_google_drive_error(self, error: Exception, context: Dict[str, Any] = None) -> str:
        """
        Centralized Google Drive error handling.
        
        Args:
            error: The exception that occurred
            context: Additional context (module, user action, etc.)
            
        Returns:
            user_message: Appropriate message to show to the user
        """
        error_str = str(error).lower()
        base_context = self._create_log_context(
            error_type="google_drive_error",
            custom_context=context or {}
        )
        
        # Categorize Google Drive errors
        if any(term in error_str for term in ['ssl', 'record layer failure', 'network']):
            base_context.update({
                'error_category': 'connectivity',
                'scope': 'global',
                'severity': 'warning'
            })
            user_message = "⚠️ Temporary network connectivity issue. Please refresh the page or try again in a moment."
            
        elif any(term in error_str for term in ['quota', 'rate limit']):
            base_context.update({
                'error_category': 'quota_exceeded',
                'scope': 'global', 
                'severity': 'error'
            })
            user_message = "📊 Google Drive quota exceeded. Please try again later or contact support."
            
        elif any(term in error_str for term in ['authentication', 'oauth', 'token']):
            base_context.update({
                'error_category': 'authentication',
                'scope': 'global',
                'severity': 'error'
            })
            user_message = "🔐 Authentication error. Please check your Google Drive connection."
            
        else:
            base_context.update({
                'error_category': 'unknown_google_drive',
                'scope': 'global',
                'severity': 'error'
            })
            user_message = "❌ Error connecting to Google Drive. Please check your configuration."
        
        # Log the error
        self.log_error("google_drive_error", error, base_context)
        
        return user_message
    
    def log_module_error(self, module: str, error_type: str, error: Exception, 
                        context: Dict[str, Any] = None) -> None:
        """
        Log module-specific errors.
        
        Args:
            module: Module name (e.g., 'wine_analysis', 'bar_sales')
            error_type: Type of error (e.g., 'data_processing', 'visualization')
            error: The exception that occurred
            context: Additional context information
        """
        log_context = self._create_log_context(
            module=module,
            error_type=error_type,
            custom_context=context or {}
        )
        log_context.update({
            'scope': 'module',
            'module': module
        })
        
        self.log_error(f"{module}_{error_type}", error, log_context)
    
    def log_error(self, error_name: str, error: Exception, context: Dict[str, Any] = None):
        """Log an error with full stack trace and context."""
        
        log_context = context or {}
        log_context.update({
            'error_name': error_name,
            'error_message': str(error),
            'error_type_name': type(error).__name__,
            'stack_trace': traceback.format_exc()
        })
        
        self.logger.error(f"Error: {error_name}", extra=log_context)
    
    def log_warning(self, message: str, context: Dict[str, Any] = None):
        """Log a warning with context."""
        log_context = self._create_log_context(custom_context=context or {})
        self.logger.warning(message, extra=log_context)
    
    def log_info(self, message: str, context: Dict[str, Any] = None):
        """Log an info message with context."""
        log_context = self._create_log_context(custom_context=context or {})
        self.logger.info(message, extra=log_context)


# Global logger instance
app_logger = AppLogger()


def log_function_errors(module: str, error_type: str = "function_error"):
    """
    Decorator to automatically log function errors.
    
    Args:
        module: Module name for the decorated function
        error_type: Type of error for categorization
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Check if it's a Google Drive error first
                if app_logger.is_google_drive_error(e):
                    user_message = app_logger.handle_google_drive_error(e, {
                        'function': func.__name__,
                        'module': module
                    })
                    # Re-raise with user-friendly message
                    raise Exception(user_message) from e
                else:
                    # Log as module-specific error
                    app_logger.log_module_error(module, error_type, e, {
                        'function': func.__name__
                    })
                    raise
        return wrapper
    return decorator


def get_module_logger(module: str):
    """
    Get a logger instance configured for a specific module.
    
    Args:
        module: Module name
        
    Returns:
        A logger instance with module context
    """
    return app_logger


# Helper function for quick error categorization
def categorize_error(error: Exception) -> str:
    """Categorize an error based on its type and message."""
    error_str = str(error).lower()
    
    if app_logger.is_google_drive_error(error):
        return "google_drive"
    elif any(term in error_str for term in ['key', 'missing', 'not found']):
        return "data_structure"
    elif any(term in error_str for term in ['chart', 'plot', 'visualization']):
        return "visualization"
    elif any(term in error_str for term in ['date', 'time', 'parse']):
        return "date_parsing"
    else:
        return "unknown"
