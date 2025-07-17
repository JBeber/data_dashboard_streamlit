import pysftp
import io, tempfile, os, re
import yaml
from functools import lru_cache
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv


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

    config['holidays'] = pd.to_datetime(holidays)

    # Parse first_data_date if present
    if 'first_data_date' in config:
        config['first_data_date'] = pd.to_datetime(config['first_data_date'])
    else:
        config['first_data_date'] = date(2025, 1, 1)

    weekmask = config.get('weekmask', 'Tue Wed Thu Fri Sat Sun')
    holidays = config.get('holidays', [])
    config['business_days'] = pd.offsets.CustomBusinessDay(weekmask=weekmask, holidays=holidays)

    config['bottle_to_glass_map'] = config.get('bottle_to_glass_map', {})

    return config


@st.cache_resource
def get_drive_service():
    """Build and return the Google Drive API client using OAuth credentials."""

    # Load credentials from environment variables set by Secret Manager
    client_id = os.environ["GOOGLE_CLIENT_ID"]
    client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
    refresh_token = os.environ["GOOGLE_REFRESH_TOKEN"]

    creds = Credentials(
        token=None,  # No access token, will be refreshed automatically
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/drive"],
    )

    return build('drive', 'v3', credentials=creds)


def get_existing_dates(drive_service, folder_id):
    date_pattern = re.compile(r'AllItemsReport_(\d{8})\.csv', re.IGNORECASE)
    dates = set()
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
    return dates


def collect_data() -> None:
    config = load_config('config.yaml')
    first_data_date = config.get('first_data_date', date(2025, 1, 1))
    vv_business_days = config.get('business_days', 'Tue Wed Thu Fri Sat Sun')

    # Build the Google Drive API client
    drive_service = get_drive_service()

    existing_dates = get_existing_dates(drive_service, folder_id)
    # st.write(f"Existing dates in Google Drive: {sorted(existing_dates)}")
    yesterday = date.today() - timedelta(days=1)
    all_dates = set(pd.date_range(start=first_data_date, end=yesterday, freq=vv_business_days).date)
    missing_dates = sorted(dt for dt in all_dates if dt not in existing_dates)
    # st.write(f"Missing dates: {missing_dates}")

    if not missing_dates:
        st.success("All available data files have been uploaded.")
        return

    with st.spinner('Collecting latest restaurant data, please wait...'):
        # SFTP setup
        private_key_str = st.secrets["Toast_SFTP"]["private_key"]
        with tempfile.NamedTemporaryFile(delete=False) as keyfile:
            keyfile.write(private_key_str.encode())
            keyfile_path = keyfile.name

        try:
            cnopts = pysftp.CnOpts()
            cnopts.hostkeys.load('Toast_SFTP_known_hosts')
            with pysftp.Connection(
                st.secrets['Toast_SFTP']['hostname'],
                port=22,
                username=st.secrets['Toast_SFTP']['username'],
                private_key=keyfile_path,
                private_key_pass=st.secrets['Toast_SFTP']['pwd'],
                cnopts=cnopts
            ) as sftp:
                export_id = st.secrets['Toast_SFTP']['export_id']
                sftp.chdir(export_id)
                
                for dt in all_dates:
                    date_str = dt.strftime('%Y%m%d')
                    file_name = f'AllItemsReport_{date_str}.csv'

                    # Check again just before uploading to avoid duplicates
                    query = (
                        f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
                    )
                    resp = drive_service.files().list(q=query, spaces='drive', fields='files(id)').execute()
                    if resp.get('files'):
                        continue

                    try:
                        sftp.chdir(f'./{date_str}')
                    except IOError:
                        st.warning(f"SFTP folder for {date_str} not found, skipping.")
                        sftp.chdir('..')
                        continue

                    file_obj = io.BytesIO()
                    try:
                        sftp.getfo('AllItemsReport.csv', file_obj)
                        file_obj.seek(0)
                    except Exception as e:
                        st.warning(f"AllItemsReport.csv not found for {date_str}, skipping. Error: {e}")
                        sftp.chdir('..')
                        continue

                    file_metadata = {'name': file_name, 'parents': [folder_id]}
                    media = MediaIoBaseUpload(file_obj, mimetype='text/csv')
                    drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
                    st.success(f"{file_name} uploaded.")
                    sftp.chdir('..')
        finally:
            if os.path.exists(keyfile_path):
                os.remove(keyfile_path)