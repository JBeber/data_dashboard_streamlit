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
from pathlib import Path

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
        """Initialize POS transaction processor with production configuration."""
        try:
            logger.info("Attempting to initialize POS processor")
            
            # Use absolute path for data directory in production
            data_dir = Path("/var/data/inventory")
            data_dir.mkdir(parents=True, exist_ok=True)
            
            self.pos_processor = SimplifiedToastProcessor(
                data_directory=str(data_dir)
            )
            
            logger.info("POS transaction processor initialized successfully", {
                "data_directory": str(data_dir)
            })
        except Exception as e:
            logger.error(f"Failed to initialize POS processor: {e}")
            logger.error("Full error details:", exc_info=True)
            logger.warning("POS transaction processing will be disabled")
            self.pos_processor = None
    
    def get_existing_dates(self) -> Set[date]:
        """Get dates of files already uploaded to Google Drive."""
        file_patterns = {
            'AllItemsReport': re.compile(r'AllItemsReport_(\d{8})\.csv', re.IGNORECASE),
            'ItemSelectionDetails': re.compile(r'ItemSelectionDetails_(\d{8})\.csv', re.IGNORECASE),
            'ModifiersSelectionDetails': re.compile(r'ModifiersSelectionDetails_(\d{8})\.csv', re.IGNORECASE)
        }
        dates_by_type = {k: set() for k in file_patterns.keys()}
        page_token = None
        
        try:
            while True:
                response = self.drive_service.files().list(
                    q=f"(name contains 'AllItemsReport_' or name contains 'ItemSelectionDetails_' or name contains 'ModifiersSelectionDetails_') and name contains '.csv' and '{self.folder_id}' in parents and trashed=false",
                    spaces='drive',
                    fields='nextPageToken, files(name)',
                    pageToken=page_token
                ).execute()
                
                for file_info in response.get('files', []):
                    for file_type, pattern in file_patterns.items():
                        match = pattern.match(file_info['name'])
                        if match:
                            dates_by_type[file_type].add(datetime.strptime(match.group(1), "%Y%m%d").date())
                            break
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            # Log counts for each file type
            for file_type, dates in dates_by_type.items():
                logger.info(f"Found {len(dates)} existing {file_type} files in Google Drive")
            
            # Return dates that have ALL required file types
            complete_dates = dates_by_type['AllItemsReport'] & dates_by_type['ItemSelectionDetails'] & dates_by_type['ModifiersSelectionDetails']
            logger.info(f"Found {len(complete_dates)} dates with all required file types")
            
            # Log dates missing some files
            all_dates = set.union(*dates_by_type.values())
            incomplete_dates = all_dates - complete_dates
            if incomplete_dates:
                logger.info(f"Found {len(incomplete_dates)} dates with incomplete file sets:")
                for dt in sorted(incomplete_dates)[:5]:  # Show first 5 examples
                    missing_types = [t for t, dates in dates_by_type.items() if dt not in dates]
                    logger.info(f"  {dt}: Missing {', '.join(missing_types)}")
            
            # Return dates that have at least AllItemsReport (to maintain backward compatibility)
            return dates_by_type['AllItemsReport']
            
        except HttpError as e:
            logger.error(f"Error fetching existing files from Google Drive: {e}")
            raise
    
    def calculate_missing_dates(self) -> List[date]:
        """Calculate which dates need data collection."""
        first_data_date = self.config.get('first_data_date', date(2025, 1, 1))
        business_days = self.config.get('business_days')
        
        yesterday = date.today() - timedelta(days=1)
        all_dates = set(pd.date_range(start=first_data_date, end=yesterday, freq=business_days).date)
        
        # Get dates with each type of file
        date_pattern = {
            'AllItemsReport': re.compile(r'AllItemsReport_(\d{8})\.csv', re.IGNORECASE),
            'ItemSelectionDetails': re.compile(r'ItemSelectionDetails_(\d{8})\.csv', re.IGNORECASE),
            'ModifiersSelectionDetails': re.compile(r'ModifiersSelectionDetails_(\d{8})\.csv', re.IGNORECASE)
        }
        dates_by_type = {k: set() for k in date_pattern.keys()}
        page_token = None
        
        # Search for all file types at once
        while True:
            response = self.drive_service.files().list(
                q=f"(name contains 'AllItemsReport_' or name contains 'ItemSelectionDetails_' or name contains 'ModifiersSelectionDetails_') and name contains '.csv' and '{self.folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='nextPageToken, files(name)',
                pageToken=page_token
            ).execute()
            
            for file_info in response.get('files', []):
                for file_type, pattern in date_pattern.items():
                    match = pattern.match(file_info['name'])
                    if match:
                        dates_by_type[file_type].add(datetime.strptime(match.group(1), "%Y%m%d").date())
                        break
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        
        # A date is complete only if it has all file types
        complete_dates = dates_by_type['AllItemsReport'] & dates_by_type['ItemSelectionDetails'] & dates_by_type['ModifiersSelectionDetails']
        missing_dates = sorted(dt for dt in all_dates if dt not in complete_dates)
        
        # Log detailed status
        logger.info(f"Total business days: {len(all_dates)}")
        for file_type, dates in dates_by_type.items():
            logger.info(f"Dates with {file_type}: {len(dates)}")
        logger.info(f"Dates with complete file sets: {len(complete_dates)}")
        logger.info(f"Dates needing files: {len(missing_dates)}")
        
        if missing_dates:
            logger.info(f"First 5 dates needing files:")
            for dt in sorted(missing_dates)[:5]:
                missing_types = [t for t, dates in dates_by_type.items() if dt not in dates]
                logger.info(f"  {dt}: Missing {', '.join(missing_types)}")
        
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
            
            # Initialize uploaded_count
            uploaded_count = 0
            
            if not missing_dates:
                logger.info("No missing dates found - all data is up to date")
                results['success'] = True
            else:
                logger.info(f"Processing {len(missing_dates)} missing dates")
                # Setup SFTP connection
                uploaded_count = self._process_sftp_data(missing_dates, results)
            
            # Always set files_uploaded in results
            results['files_uploaded'] = uploaded_count
            
            # Process POS transactions REGARDLESS of missing dates status
            # We want to process yesterday's transactions every time the job runs
            yesterday = date.today() - timedelta(days=1)
            logger.info(f"Checking POS processing for yesterday ({yesterday.strftime('%Y%m%d')})")
            
            if not self.pos_processor:
                logger.warning("POS processor not initialized, skipping transaction processing")
            else:
                try:
                    logger.info("Starting POS data processing")
                    self._process_recent_pos_data(yesterday, results)
                except Exception as e:
                    error_msg = f"Failed to process POS data for yesterday: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
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
            
            # List available files in SFTP directory
            try:
                available_files = set(sftp.listdir())
                logger.info(f"Found {len(available_files)} files in SFTP for {date_str}: {', '.join(sorted(available_files))}")
            except IOError as e:
                logger.error(f"Could not list directory contents for {date_str}: {e}")
                return False
            
            # Process each file type
            for source_filename, drive_filename in file_types:
                try:
                    # Check if file already exists in Drive
                    query = f"name='{drive_filename}' and '{self.folder_id}' in parents and trashed=false"
                    resp = self.drive_service.files().list(q=query, spaces='drive', fields='files(id)').execute()
                    if resp.get('files'):
                        logger.info(f"{drive_filename} already exists, skipping")
                        continue
                    
                    # Verify source file exists in SFTP
                    if source_filename not in available_files:
                        logger.warning(f"Source file {source_filename} not found in SFTP for date {date_str}")
                        continue
                    
                    # Download file from SFTP to memory
                    file_obj = io.BytesIO()
                    try:
                        sftp.getfo(source_filename, file_obj)
                    except IOError as e:
                        logger.error(f"Failed to download {source_filename} from SFTP for date {date_str}: {e}")
                        continue
                    
                    file_obj.seek(0)
                    content = file_obj.getvalue()
                    
                    # Check if file is empty
                    if not content:
                        logger.warning(f"Downloaded file {source_filename} is empty for date {date_str}")
                        continue
                    
                    # Upload to Google Drive
                    file_metadata = {'name': drive_filename, 'parents': [self.folder_id]}
                    media = MediaIoBaseUpload(io.BytesIO(content), mimetype='text/csv')
                    
                    try:
                        self.drive_service.files().create(
                            body=file_metadata,
                            media_body=media,
                            fields='id'
                        ).execute()
                        
                        logger.info(f"Successfully uploaded {drive_filename}")
                        uploaded_any = True
                        
                    except HttpError as e:
                        logger.error(f"Failed to upload {drive_filename} to Drive for date {date_str}: {e}")
                        continue
                    
                except Exception as e:
                    logger.error(f"Unexpected error processing {source_filename} for date {date_str}: {e}")
                    continue
            
            return uploaded_any
            
        except IOError:
            logger.warning(f"SFTP folder for {date_str} not found, skipping")
            return False
            
        finally:
            # Always attempt to return to parent directory
            try:
                sftp.chdir('..')
            except Exception as e:
                logger.error(f"Failed to return to parent directory: {e}")
    
    def _save_temp_file(self, file_obj: io.BytesIO, filename: str) -> str:
        """Save BytesIO content to both archive and temp locations for debugging.
        
        Args:
            file_obj: The file content in memory
            filename: The name to save the file as
            
        Returns:
            str: Path to the temporary file for immediate processing
        """
        # Save to archive location for debugging
        archive_dir = Path("data/pos_archives")
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Create dated subdirectory
        date_str = datetime.now().strftime('%Y%m%d')
        dated_dir = archive_dir / date_str
        dated_dir.mkdir(exist_ok=True)
        
        # Save archive copy
        archive_path = dated_dir / filename
        file_obj.seek(0)
        content = file_obj.read()
        
        with open(archive_path, 'wb') as f:
            f.write(content)
            
        # Also save to temp for processing
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, filename)
        
        with open(temp_path, 'wb') as f:
            f.write(content)
            
        logger.info(f"Saved file {filename} to archive: {archive_path}")
        return temp_path


    def _process_recent_pos_data(self, target_date: date, results: Dict[str, Any]):
        """
        Process POS transaction data for a specific recent date to keep inventory current.
        This method re-downloads and processes POS files even if they exist in Drive.
        """
        date_str = target_date.strftime('%Y%m%d')
        logger.info(f"Processing recent POS data for {date_str} to update inventory")
        
        if not self.pos_processor:
            logger.warning("POS processor not initialized, skipping transaction processing")
            return
            
        # SFTP credentials from environment
        try:
            private_key_str = os.environ["TOAST_SFTP_PRIVATE_KEY"]
            hostname = os.environ["TOAST_SFTP_HOSTNAME"]
            username = os.environ["TOAST_SFTP_USERNAME"]
            password = os.environ["TOAST_SFTP_PASSWORD"]
            export_id = os.environ["TOAST_SFTP_EXPORT_ID"]
        except KeyError as e:
            logger.error(f"Missing required SFTP environment variable: {e}")
            return
        
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
                    if not (items_file_path and modifiers_file_path):
                        logger.error(f"Missing required files for POS processing. Items file: {bool(items_file_path)}, Modifiers file: {bool(modifiers_file_path)}")
                        return
                        
                    # Verify files exist and are readable
                    for filepath in [items_file_path, modifiers_file_path]:
                        if not os.path.exists(filepath):
                            logger.error(f"File does not exist: {filepath}")
                            return
                        if not os.path.isfile(filepath):
                            logger.error(f"Path is not a file: {filepath}")
                            return
                        if not os.access(filepath, os.R_OK):
                            logger.error(f"File is not readable: {filepath}")
                            return
                            
                    try:
                        # Log file sizes for debugging
                        items_size = os.path.getsize(items_file_path)
                        modifiers_size = os.path.getsize(modifiers_file_path)
                        logger.info(f"Processing files - Items: {items_size} bytes, Modifiers: {modifiers_size} bytes")
                        
                        result = self.pos_processor.process_daily_data(
                            items_file_path,
                            modifiers_file_path,
                            date_str
                        )
                        
                        if not result:
                            logger.error(f"POS processor returned None for {date_str}")
                            return
                            
                        if result.get('success'):
                            component_count = len(result.get('component_usage', {}))
                            logger.info(f"Successfully processed recent POS data for {date_str}: {component_count} component types")
                            results['pos_transactions_processed'] += component_count
                            
                            # Log component details for verification
                            components = list(result.get('component_usage', {}).keys())
                            logger.info(f"Processed components: {', '.join(components[:5])}...")
                        else:
                            error_msg = result.get('error', 'Unknown error')
                            logger.error(f"Recent POS processing failed for {date_str}: {error_msg}")
                            if 'traceback' in result:
                                logger.error(f"Error traceback: {result['traceback']}")
                                
                    except Exception as e:
                        logger.error(f"Error processing recent POS data for {date_str}: {str(e)}")
                        import traceback
                        logger.error(f"Full traceback: {traceback.format_exc()}")
                    
                except IOError as e:
                    logger.error(f"SFTP folder or file access error for {date_str}: {str(e)}")
                    
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
