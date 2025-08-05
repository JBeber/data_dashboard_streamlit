"""
Enhanced OAuth Manager for Streamlit App

This module provides robust OAuth credential management for the Streamlit app,
using the same enhanced system as the background data collector.

Features:
- Proactive token refresh with comprehensive error handling
- Streamlit-specific caching and session state management
- Graceful degradation when authentication fails
- User-friendly error messages
"""

import os
import streamlit as st
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logger = logging.getLogger(__name__)


class StreamlitOAuthManager:
    """
    Enhanced OAuth credential management optimized for Streamlit apps.
    Based on the EnhancedOAuthManager from background_data_collector.py
    """
    
    def __init__(self):
        self.credentials = None
        self.client_id = None
        self.client_secret = None
        self.refresh_token = None
        self._load_credentials()
    
    def _load_credentials(self):
        """Load OAuth credentials from environment variables."""
        try:
            self.client_id = os.environ["GOOGLE_CLIENT_ID"]
            self.client_secret = os.environ["GOOGLE_CLIENT_SECRET"] 
            self.refresh_token = os.environ["GOOGLE_REFRESH_TOKEN"]
            
            logger.info("OAuth credentials loaded successfully")
            
        except KeyError as e:
            logger.error(f"Missing required environment variable: {e}")
            st.error(f"🔐 Authentication configuration missing: {e}")
            st.error("Please contact your administrator to configure Google Drive access.")
            st.stop()
    
    def get_credentials(self) -> Optional[Credentials]:
        """
        Get valid OAuth credentials with automatic token refresh.
        
        Returns:
            Valid Google OAuth2 Credentials object, or None if authentication fails
        """
        try:
            if self.credentials is None:
                self.credentials = Credentials(
                    token=None,  # Will be refreshed automatically
                    refresh_token=self.refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    scopes=["https://www.googleapis.com/auth/drive"],
                )
            
            # Proactively refresh if token is expired or will expire soon
            if self.credentials.expired or self._token_expires_soon():
                logger.info("Refreshing OAuth token")
                request = Request()
                self.credentials.refresh(request)
                logger.info("OAuth token refreshed successfully")
                
            return self.credentials
            
        except RefreshError as e:
            logger.error(f"Failed to refresh OAuth token: {e}")
            self._handle_auth_error(e)
            return None
            
        except Exception as e:
            logger.error(f"Unexpected authentication error: {e}")
            self._handle_auth_error(e)
            return None
    
    def _token_expires_soon(self, threshold_minutes: int = 5) -> bool:
        """Check if token will expire within threshold minutes."""
        if not self.credentials or not self.credentials.expiry:
            return True
        
        threshold = timedelta(minutes=threshold_minutes)
        return datetime.now(timezone.utc) + threshold >= self.credentials.expiry
    
    def _handle_auth_error(self, error):
        """Handle authentication errors with user-friendly messages."""
        error_str = str(error).lower()
        
        if "invalid_client" in error_str:
            st.error("🔐 **Google Drive Authentication Error**")
            st.error("The application's Google Drive credentials are invalid or expired.")
            st.error("Please contact your administrator to refresh the authentication setup.")
            
        elif "invalid_grant" in error_str:
            st.error("🔐 **Google Drive Access Expired**")
            st.error("Your Google Drive access has expired and needs to be renewed.")
            st.error("Please contact your administrator to refresh your access.")
            
        else:
            st.error("🔐 **Google Drive Connection Error**")
            st.error("Unable to connect to Google Drive. This may be a temporary issue.")
            st.error("Please try refreshing the page, or contact your administrator if the problem persists.")
        
        # Add troubleshooting info in expander
        with st.expander("ℹ️ Troubleshooting Information"):
            st.write("**Error Details:**")
            st.code(str(error))
            st.write("**Possible Solutions:**")
            st.write("1. Refresh the page and try again")
            st.write("2. Check your internet connection")
            st.write("3. Contact your system administrator")
            st.write("4. Try again in a few minutes")


@st.cache_resource
def get_enhanced_drive_service():
    """
    Get Google Drive service with enhanced OAuth management.
    
    Returns:
        Google Drive API service object, or None if authentication fails
    """
    try:
        oauth_manager = StreamlitOAuthManager()
        credentials = oauth_manager.get_credentials()
        
        if credentials is None:
            return None
            
        return build('drive', 'v3', credentials=credentials)
        
    except Exception as e:
        logger.error(f"Failed to initialize Google Drive service: {e}")
        st.error("🔐 **Unable to Initialize Google Drive Connection**")
        st.error("The application cannot connect to Google Drive at this time.")
        return None


def test_drive_connection():
    """
    Test Google Drive connection and show status in Streamlit.
    Useful for debugging and status checks.
    """
    try:
        with st.spinner("Testing Google Drive connection..."):
            drive_service = get_enhanced_drive_service()
            
            if drive_service is None:
                st.error("❌ Google Drive connection failed")
                return False
            
            # Simple test - list files in root (limited results)
            response = drive_service.files().list(pageSize=1, fields="files(id, name)").execute()
            files = response.get('files', [])
            
            st.success("✅ Google Drive connection successful")
            st.info(f"📁 Found {len(files)} file(s) in root directory")
            
            if files:
                with st.expander("📋 Sample Files"):
                    for file in files[:3]:  # Show max 3 files
                        st.write(f"• {file.get('name', 'Unnamed')}")
            
            return True
            
    except Exception as e:
        logger.error(f"Drive connection test failed: {e}")
        st.error(f"❌ Google Drive connection test failed")
        
        error_str = str(e).lower()
        if 'incompleteread' in error_str or 'connection' in error_str:
            st.warning("🌐 This appears to be a network connectivity issue")
            st.info("Try refreshing the page or checking your internet connection")
        
        with st.expander("🔍 Error Details"):
            st.code(str(e))
        
        return False


# Compatibility function to replace the old get_drive_service
def get_drive_service():
    """
    Compatibility wrapper for the old get_drive_service function.
    This ensures existing code continues to work.
    """
    return get_enhanced_drive_service()
