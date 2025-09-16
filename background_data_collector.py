#!/usr/bin/env python3
"""
Enhanced OAuth Background Data Collector

This script runs as a Cloud Run Job to collect data from SFTP
and upload to Google Drive using robust OAuth authentication.

Features:
- Enhanced OAuth token management with proactive refresh
- Comprehensive error handling and retry logic
- Cloud Logging integration
- Graceful degradation and monitoring
- Designed for Cloud Scheduler triggering
"""

import os
import sys
import io
import tempfile
import re
import yaml
from datetime import datetime, date, timedelta
from typing import Set, List, Optional, Dict, Any
import logging
from functools import lru_cache

import pysftp
import pandas as pd
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

# Import POS transaction processor
from modules.simplified_toast_processor import SimplifiedToastProcessor

# Cloud Logging setup (will work in Cloud Run)
try:
    from google.cloud import logging as cloud_logging
    cloud_client = cloud_logging.Client()
    cloud_client.setup_logging()
    print("Cloud Logging configured")
except ImportError:
    print("Cloud Logging not available, using standard logging")

# Configure logging - add explicit flushing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

# Add console handler to ensure logs are visible
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = True


class EnhancedOAuthManager:
    """
    Robust OAuth credential management with proactive token refresh
    and comprehensive error handling.
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
            raise
    
    def get_credentials(self) -> Credentials:
        """
        Get valid OAuth credentials with automatic token refresh.
        
        Returns:
            Valid Google OAuth2 Credentials object
            
        Raises:
            RefreshError: If token refresh fails
        """
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
            try:
                logger.info("Refreshing OAuth token")
                print("Refreshing OAuth token")
                request = Request()
                self.credentials.refresh(request)
                logger.info("OAuth token refreshed successfully")
                print("OAuth token refreshed successfully")
                
            except RefreshError as e:
                logger.error(f"Failed to refresh OAuth token: {e}")
                print(f"CRITICAL ERROR: Failed to refresh OAuth token: {e}")
                # Log detailed error for debugging
                logger.error(f"Client ID: {self.client_id[:10]}...")
                logger.error(f"Refresh token exists: {bool(self.refresh_token)}")
                print(f"Client ID: {self.client_id[:10]}...")
                print(f"Refresh token exists: {bool(self.refresh_token)}")
                raise
        
        return self.credentials
    
    def _token_expires_soon(self, threshold_minutes: int = 5) -> bool:
        """Check if token will expire within threshold minutes."""
        if not self.credentials or not self.credentials.expiry:
            return True
        
        threshold = timedelta(minutes=threshold_minutes)
        return datetime.utcnow() + threshold >= self.credentials.expiry


class DataCollector:
    """
    Main data collection class that handles SFTP connection,
    file processing, and Google Drive uploads.
    """
    
    def __init__(self, config_path: str = 'config.yaml'):
        self.config = self._load_config(config_path)
        self.oauth_manager = EnhancedOAuthManager()
        self.drive_service = None
        self.folder_id = None
        self.pos_processor = None
        self._setup_drive_service()
        self._setup_pos_processor()
    
    @lru_cache(maxsize=1)
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load and process configuration file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Process holidays
            holidays = []
            for item in config.get('holidays', []):
                if isinstance(item, str):
                    holidays.append(item)
                elif isinstance(item, dict) and 'range' in item:
                    start, end = item['range']
                    rng = pd.date_range(start, end, freq='D')
                    holidays.extend(rng.strftime('%Y-%m-%d').tolist())
            
            for rng in config.get('holiday_ranges', []):
                start, end = rng
                rng_dates = pd.date_range(start, end, freq='D')
                holidays.extend(rng_dates.strftime('%Y-%m-%d').tolist())
            
            holidays_dt = pd.to_datetime(holidays)
            config['holidays'] = holidays_dt
            
            # Parse first_data_date
            if 'first_data_date' in config:
                first_data_dt = pd.to_datetime(config['first_data_date'])
                config['first_data_date'] = first_data_dt.date() if hasattr(first_data_dt, 'date') else first_data_dt
            else:
                config['first_data_date'] = date(2025, 1, 1)
            
            # Setup business days
            weekmask = config.get('weekmask', 'Tue Wed Thu Fri Sat Sun')
            config['business_days'] = pd.offsets.CustomBusinessDay(weekmask=weekmask, holidays=holidays_dt)
            config['bottle_to_glass_map'] = config.get('bottle_to_glass_map', {})
            
            logger.info(f"Configuration loaded successfully from {config_path}")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _setup_drive_service(self):
        """Initialize Google Drive service with enhanced OAuth."""
        try:
            # Get folder ID from environment (set in Cloud Run)
            self.folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
            if not self.folder_id:
                raise ValueError("GOOGLE_DRIVE_FOLDER_ID environment variable not set")
            
            credentials = self.oauth_manager.get_credentials()
            self.drive_service = build('drive', 'v3', credentials=credentials)
            
            logger.info("Google Drive service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            raise
    
    def _setup_pos_processor(self):
        """Initialize POS transaction processor."""
        try:
            self.pos_processor = SimplifiedToastProcessor()
            logger.info("POS transaction processor initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize POS processor: {e}")
            logger.warning("POS transaction processing will be disabled")
            self.pos_processor = None
    
    def get_existing_dates(self) -> Set[date]:
        """Get dates of files already uploaded to Google Drive."""
        date_pattern = re.compile(r'AllItemsReport_(\d{8})\.csv', re.IGNORECASE)
        dates = set()
        page_token = None
        
        try:
            while True:
                response = self.drive_service.files().list(
                    q=f"name contains 'AllItemsReport_' and name contains '.csv' and '{self.folder_id}' in parents and trashed=false",
                    spaces='drive',
                    fields='nextPageToken, files(name)',
                    pageToken=page_token
                ).execute()
                
                for file_info in response.get('files', []):
                    match = date_pattern.match(file_info['name'])
                    if match:
                        dates.add(datetime.strptime(match.group(1), "%Y%m%d").date())
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            logger.info(f"Found {len(dates)} existing AllItemsReport files in Google Drive")
            return dates
            
        except HttpError as e:
            logger.error(f"Error fetching existing files from Google Drive: {e}")
            raise
    
    def calculate_missing_dates(self) -> List[date]:
        """Calculate which dates need data collection."""
        first_data_date = self.config.get('first_data_date', date(2025, 1, 1))
        business_days = self.config.get('business_days')
        
        yesterday = date.today() - timedelta(days=1)
        all_dates = set(pd.date_range(start=first_data_date, end=yesterday, freq=business_days).date)
        
        existing_dates = self.get_existing_dates()
        missing_dates = sorted(dt for dt in all_dates if dt not in existing_dates)
        
        logger.info(f"Total business days: {len(all_dates)}")
        logger.info(f"Existing files: {len(existing_dates)}")
        logger.info(f"Missing dates: {len(missing_dates)}")
        
        return missing_dates
    
    def collect_and_upload_data(self) -> Dict[str, Any]:
        """
        Main data collection method.
        
        Returns:
            Dictionary with collection results and statistics
        """
        start_time = datetime.now()
        results = {
            'start_time': start_time.isoformat(),
            'success': False,
            'files_processed': 0,
            'files_uploaded': 0,
            'pos_transactions_processed': 0,
            'errors': [],
            'missing_dates_found': 0
        }
        
        try:
            missing_dates = self.calculate_missing_dates()
            results['missing_dates_found'] = len(missing_dates)
            
            if not missing_dates:
                logger.info("No missing dates found - all data is up to date")
                results['success'] = True
                return results
            
            logger.info(f"Processing {len(missing_dates)} missing dates")
            
            # Setup SFTP connection
            uploaded_count = self._process_sftp_data(missing_dates, results)
            
            # Process POS transactions ONLY for yesterday (most recent complete day)
            # This ensures inventory is kept current with the latest available data
            # without reprocessing historical dates during backfill operations
            yesterday = date.today() - timedelta(days=1)
            if self.pos_processor:
                self._process_recent_pos_data(yesterday, results)
            
            results['files_uploaded'] = uploaded_count
            results['success'] = True
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"Data collection completed successfully")
            logger.info(f"Files uploaded: {uploaded_count}/{len(missing_dates)}")
            logger.info(f"Duration: {duration:.2f} seconds")
            
            results['end_time'] = end_time.isoformat()
            results['duration_seconds'] = duration
            
        except Exception as e:
            logger.error(f"Data collection failed: {e}")
            results['errors'].append(str(e))
            results['success'] = False
            
        return results
    
    def _process_sftp_data(self, missing_dates: List[date], results: Dict[str, Any]) -> int:
        """Process SFTP data collection and upload to Google Drive."""
        
        # SFTP credentials from environment
        private_key_str = os.environ["TOAST_SFTP_PRIVATE_KEY"]
        hostname = os.environ["TOAST_SFTP_HOSTNAME"]
        username = os.environ["TOAST_SFTP_USERNAME"]
        password = os.environ["TOAST_SFTP_PASSWORD"]
        export_id = os.environ["TOAST_SFTP_EXPORT_ID"]
        
        uploaded_count = 0
        keyfile_path = None
        
        try:
            # Create temporary key file
            with tempfile.NamedTemporaryFile(delete=False) as keyfile:
                keyfile.write(private_key_str.encode())
                keyfile_path = keyfile.name
            
            # SFTP connection setup
            cnopts = pysftp.CnOpts()
            # SECURITY NOTE: Host key verification disabled due to AWS Transfer Family
            # using dynamic hostnames (e.g., s-9b0f88558b264dfda.server.transfer.us-east-1.amazonaws.com)
            # Risk assessment: Acceptable for managed AWS service with SSH key auth
            # TODO: Consider implementing dynamic host key retrieval for enhanced security
            # Date: 2025-08-03, Reason: AWS Transfer Family dynamic hostname issue
            cnopts.hostkeys = None
            
            with pysftp.Connection(
                hostname,
                port=22,
                username=username,
                private_key=keyfile_path,
                private_key_pass=password,
                cnopts=cnopts
            ) as sftp:
                
                sftp.chdir(export_id)
                logger.info(f"Connected to SFTP server, changed to directory: {export_id}")
                
                for dt in missing_dates:
                    try:
                        if self._process_single_date(sftp, dt):
                            uploaded_count += 1
                            results['files_processed'] += 1
                        else:
                            results['files_processed'] += 1
                            
                    except Exception as e:
                        error_msg = f"Error processing {dt}: {e}"
                        logger.error(error_msg)
                        results['errors'].append(error_msg)
                        continue
        
        finally:
            # Clean up temporary key file
            if keyfile_path and os.path.exists(keyfile_path):
                os.remove(keyfile_path)
        
        return uploaded_count
    
    def _process_single_date(self, sftp, dt: date) -> bool:
        """
        Process a single date's data including AllItemsReport, ItemSelectionDetails, and ModifiersSelectionDetails.
        Downloads and uploads files to Drive, but does NOT process POS transactions (that's handled separately for yesterday only).
        
        Returns:
            True if at least one file was uploaded successfully, False otherwise
        """
        date_str = dt.strftime('%Y%m%d')
        
        # Define file types to process
        file_types = [
            ('AllItemsReport.csv', f'AllItemsReport_{date_str}.csv'),
            ('ItemSelectionDetails.csv', f'ItemSelectionDetails_{date_str}.csv'),
            ('ModifiersSelectionDetails.csv', f'ModifiersSelectionDetails_{date_str}.csv')
        ]
        
        uploaded_any = False
        
        try:
            # Navigate to date folder
            sftp.chdir(f'./{date_str}')
            
        except IOError:
            logger.warning(f"SFTP folder for {date_str} not found, skipping")
            return False
        
        try:
            # Process each file type
            for source_filename, drive_filename in file_types:
                try:
                    # Check if file already exists in Drive
                    query = f"name='{drive_filename}' and '{self.folder_id}' in parents and trashed=false"
                    resp = self.drive_service.files().list(q=query, spaces='drive', fields='files(id)').execute()
                    if resp.get('files'):
                        logger.info(f"{drive_filename} already exists, skipping")
                        continue
                    
                    # Download file from SFTP to memory
                    file_obj = io.BytesIO()
                    sftp.getfo(source_filename, file_obj)
                    file_obj.seek(0)
                    
                    # Upload to Google Drive
                    file_metadata = {'name': drive_filename, 'parents': [self.folder_id]}
                    media = MediaIoBaseUpload(file_obj, mimetype='text/csv')
                    
                    self.drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
                    
                    logger.info(f"Successfully uploaded {drive_filename}")
                    uploaded_any = True
                    
                except Exception as e:
                    # Log error but continue with other files
                    error_msg = f"Failed to process {source_filename} for {date_str}: {e}"
                    logger.error(error_msg)
                    continue
            
            return uploaded_any
            
        finally:
            # Always return to parent directory
            sftp.chdir('..')
    
    def _save_temp_file(self, file_obj: io.BytesIO, filename: str) -> str:
        """Save BytesIO content to a temporary file and return the path."""
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, filename)
        
        with open(temp_path, 'wb') as f:
            f.write(file_obj.read())
            
        return temp_path


    def _process_recent_pos_data(self, target_date: date, results: Dict[str, Any]):
        """
        Process POS transaction data for a specific recent date to keep inventory current.
        This method re-downloads and processes POS files even if they exist in Drive.
        """
        date_str = target_date.strftime('%Y%m%d')
        logger.info(f"Processing recent POS data for {date_str} to update inventory")
        
        # SFTP credentials from environment
        private_key_str = os.environ["TOAST_SFTP_PRIVATE_KEY"]
        hostname = os.environ["TOAST_SFTP_HOSTNAME"]
        username = os.environ["TOAST_SFTP_USERNAME"]
        password = os.environ["TOAST_SFTP_PASSWORD"]
        export_id = os.environ["TOAST_SFTP_EXPORT_ID"]
        
        keyfile_path = None
        items_file_path = None
        modifiers_file_path = None
        
        try:
            # Create temporary key file
            with tempfile.NamedTemporaryFile(delete=False) as keyfile:
                keyfile.write(private_key_str.encode())
                keyfile_path = keyfile.name
            
            # SFTP connection setup
            cnopts = pysftp.CnOpts()
            cnopts.hostkeys = None  # Same security note as main SFTP processing
            
            with pysftp.Connection(
                hostname,
                port=22,
                username=username,
                private_key=keyfile_path,
                private_key_pass=password,
                cnopts=cnopts
            ) as sftp:
                
                sftp.chdir(export_id)
                
                try:
                    # Navigate to date folder
                    sftp.chdir(f'./{date_str}')
                    
                    # Download required files for POS processing
                    for source_filename, temp_filename in [
                        ('ItemSelectionDetails.csv', f"items_{date_str}.csv"),
                        ('ModifiersSelectionDetails.csv', f"modifiers_{date_str}.csv")
                    ]:
                        try:
                            file_obj = io.BytesIO()
                            sftp.getfo(source_filename, file_obj)
                            file_obj.seek(0)
                            
                            if source_filename == 'ItemSelectionDetails.csv':
                                items_file_path = self._save_temp_file(file_obj, temp_filename)
                            else:
                                modifiers_file_path = self._save_temp_file(file_obj, temp_filename)
                                
                        except Exception as e:
                            logger.error(f"Failed to download {source_filename} for POS processing: {e}")
                            return
                    
                    # Process POS transactions
                    if items_file_path and modifiers_file_path:
                        try:
                            result = self.pos_processor.process_daily_data(
                                items_file_path,
                                modifiers_file_path,
                                date_str
                            )
                            
                            if result.get('success'):
                                component_count = len(result.get('component_usage', {}))
                                logger.info(f"Successfully processed recent POS data for {date_str}: {component_count} component types")
                                results['pos_transactions_processed'] += component_count
                            else:
                                logger.warning(f"Recent POS processing failed for {date_str}: {result.get('error', 'Unknown error')}")
                                
                        except Exception as e:
                            logger.error(f"Error processing recent POS data for {date_str}: {e}")
                    
                except IOError:
                    logger.warning(f"SFTP folder for recent date {date_str} not found")
                    
        except Exception as e:
            logger.error(f"Failed to process recent POS data for {date_str}: {e}")
            
        finally:
            # Clean up temporary files
            for temp_path in [keyfile_path, items_file_path, modifiers_file_path]:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp file {temp_path}: {e}")


def main():
    """Main entry point for the background data collector."""
    
    # Explicit logging to ensure we see startup
    print("=" * 60)
    print("Enhanced OAuth Background Data Collector Starting")
    print("=" * 60)
    
    logger.info("=" * 60)
    logger.info("Enhanced OAuth Background Data Collector Starting")
    logger.info("=" * 60)
    
    # Verify required environment variables
    required_env_vars = [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET", 
        "GOOGLE_REFRESH_TOKEN",
        "GOOGLE_DRIVE_FOLDER_ID",
        "TOAST_SFTP_PRIVATE_KEY",
        "TOAST_SFTP_HOSTNAME",
        "TOAST_SFTP_USERNAME",
        "TOAST_SFTP_PASSWORD",
        "TOAST_SFTP_EXPORT_ID"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    if missing_vars:
        error_msg = f"Missing required environment variables: {missing_vars}"
        print(f"ERROR: {error_msg}")
        logger.error(error_msg)
        sys.exit(1)
    
    print("All required environment variables are present")
    logger.info("All required environment variables are present")
    
    try:
        # Initialize and run data collector
        print("Initializing data collector...")
        logger.info("Initializing data collector...")
        
        collector = DataCollector()
        
        print("Starting data collection...")
        logger.info("Starting data collection...")
        
        results = collector.collect_and_upload_data()
        
        # Log final results
        print("=" * 60)
        print("Data Collection Results:")
        print(f"Success: {results['success']}")
        print(f"Files processed: {results['files_processed']}")
        print(f"Files uploaded: {results['files_uploaded']}")
        print(f"POS transactions processed: {results['pos_transactions_processed']}")
        print(f"Missing dates found: {results['missing_dates_found']}")
        
        logger.info("=" * 60)
        logger.info("Data Collection Results:")
        logger.info(f"Success: {results['success']}")
        logger.info(f"Files processed: {results['files_processed']}")
        logger.info(f"Files uploaded: {results['files_uploaded']}")
        logger.info(f"POS transactions processed: {results['pos_transactions_processed']}")
        logger.info(f"Missing dates found: {results['missing_dates_found']}")
        
        if results['errors']:
            print(f"Errors encountered: {len(results['errors'])}")
            logger.warning(f"Errors encountered: {len(results['errors'])}")
            for error in results['errors']:
                print(f"  - {error}")
                logger.warning(f"  - {error}")
        
        if 'duration_seconds' in results:
            print(f"Duration: {results['duration_seconds']:.2f} seconds")
            logger.info(f"Duration: {results['duration_seconds']:.2f} seconds")
        
        print("=" * 60)
        logger.info("=" * 60)
        
        # Flush logs before exit
        logging.shutdown()
        
        # Exit with appropriate code
        sys.exit(0 if results['success'] else 1)
        
    except Exception as e:
        error_msg = f"Critical error in data collector: {e}"
        print(f"CRITICAL ERROR: {error_msg}")
        print(f"Exception type: {type(e).__name__}")
        print(f"Exception details: {str(e)}")
        
        logger.error(error_msg)
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception details: {str(e)}")
        
        # Flush logs before exit
        logging.shutdown()
        
        sys.exit(1)


if __name__ == "__main__":
    main()
