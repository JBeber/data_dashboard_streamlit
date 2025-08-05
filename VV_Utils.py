import io, tempfile, os, re, time
import yaml
from functools import lru_cache
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv

# Import enhanced OAuth management
from utils.enhanced_oauth import get_enhanced_drive_service

load_dotenv()
folder_id = st.secrets['Google_Drive']['folder_id']

@lru_cache(maxsize=1)
def load_config(config_path):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    holidays = []
    # Single dates
    for item in config.get('holidays', []):
        if isinstance(item, str):
            holidays.append(item)
        elif isinstance(item, dict) and 'range' in item:
            start, end = item['range']
            # Expand range
            rng = pd.date_range(start, end, freq='D')
            holidays.extend(rng.strftime('%Y-%m-%d').tolist())
    # Ranges in separate section
    for rng in config.get('holiday_ranges', []):
        start, end = rng
        rng_dates = pd.date_range(start, end, freq='D')
        holidays.extend(rng_dates.strftime('%Y-%m-%d').tolist())

    # Convert holidays to datetime for business days calculation
    holidays_dt = pd.to_datetime(holidays)
    config['holidays'] = holidays_dt

    # Parse first_data_date if present
    if 'first_data_date' in config:
        first_data_dt = pd.to_datetime(config['first_data_date'])
        config['first_data_date'] = first_data_dt.date() if hasattr(first_data_dt, 'date') else first_data_dt
    else:
        config['first_data_date'] = date(2025, 1, 1)

    weekmask = config.get('weekmask', 'Tue Wed Thu Fri Sat Sun')
    # Use the converted datetime holidays for business days calculation
    config['business_days'] = pd.offsets.CustomBusinessDay(weekmask=weekmask, holidays=holidays_dt)

    config['bottle_to_glass_map'] = config.get('bottle_to_glass_map', {})

    return config


@st.cache_resource
def get_drive_service():
    """
    Build and return the Google Drive API client using enhanced OAuth credentials.
    This is a compatibility wrapper that uses the new enhanced OAuth system.
    """
    return get_enhanced_drive_service()


def get_existing_dates(drive_service, folder_id, max_retries=3):
    """Get existing dates from Google Drive with enhanced error handling and retry logic."""
    if drive_service is None:
        st.warning("⚠️ Google Drive service unavailable. Cannot load existing dates.")
        return set()
    
    date_pattern = re.compile(r'AllItemsReport_(\d{8})\.csv', re.IGNORECASE)
    dates = set()
    
    for attempt in range(max_retries):
        try:
            page_token = None
            while True:
                response = drive_service.files().list(
                    q=f"name contains 'AllItemsReport_' and name contains '.csv' and '{folder_id}' in parents and trashed=false",
                    spaces='drive',
                    fields='nextPageToken, files(name)',
                    pageToken=page_token
                ).execute()
                for f in response.get('files', []):
                    m = date_pattern.match(f['name'])
                    if m:
                        dates.add(datetime.strptime(m.group(1), "%Y%m%d").date())
                page_token = response.get('nextPageToken', None)
                if page_token is None:
                    break
            
            # If we get here, success!
            return dates
                
        except Exception as e:
            error_str = str(e).lower()
            is_network_error = any(term in error_str for term in [
                'incompleteread', 'connection', 'timeout', 'network', 'ssl'
            ])
            
            if is_network_error and attempt < max_retries - 1:
                # Network error and we have retries left
                st.info(f"🔄 Network issue detected, retrying... (attempt {attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                continue
            else:
                # Final attempt failed or non-network error
                st.error(f"🔍 **Error Loading Data from Google Drive**")
                st.error("Unable to retrieve the list of available data files.")
                
                if is_network_error:
                    st.error("This appears to be a network connectivity issue.")
                    st.info("💡 **Suggestions:**")
                    st.info("• Check your internet connection")
                    st.info("• Try refreshing the page in a few moments")
                    st.info("• The issue may resolve itself automatically")
                else:
                    st.error("Please try refreshing the page or contact your administrator.")
                
                with st.expander("ℹ️ Technical Details"):
                    st.write("**Error:**", str(e))
                    st.write("**Error Type:**", type(e).__name__)
                    st.write("**Folder ID:**", folder_id)
                    st.write("**Attempt:**", f"{attempt + 1}/{max_retries}")
                
                return set()
        
    return set()


def collect_data() -> None:
    """
    DEPRECATED: Data collection function - not used in production.
    Data collection is now handled by the background_data_collector.py Cloud Run Job.
    This function is kept for reference but should not be called.
    """
    st.warning("⚠️ **Data Collection Not Available**")
    st.info("Data collection is handled automatically by the background data collection system.")
    st.info("Data is updated daily at 6 AM EST. No manual collection is needed.")
    return