import pysftp, io, tempfile, os, re
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Set operatings days for date range generation
vv_weekmask = 'Tue Wed Thu Fri Sat Sun'
vv_business_days = pd.offsets.CustomBusinessDay(weekmask=vv_weekmask)

first_data_date = date(2025, 1, 1)  # First date for which data is available

folder_id = st.secrets['Google_Drive']['folder_id']

# Parse a Python date object from string in YYYYMMDD format
def parse_date(s: str) -> date:
    year = int(s[:4])
    month = int(s[4:6])
    day = int(s[-2:])

    return date(year, month, day)

@st.cache_resource  # Use st.experimental_singleton for earlier Streamlit versions
def get_drive_service():
    """Build and return the Google Drive API client."""

    # Get the JSON key from secrets
    service_account_json_str = st.secrets["Google_Drive"]["service_account_json"]

    # Write to a temporary file
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
        f.write(service_account_json_str)
        f.flush()
        keyfile_path = f.name

    try:
        # Create credentials from the service account file
        credentials = service_account.Credentials.from_service_account_file(
            keyfile_path,
            scopes = ['https://www.googleapis.com/auth/drive']
        )
    finally:
        # Clean up the temporary file
        if os.path.exists(keyfile_path):
            os.remove(keyfile_path)

    return build('drive', 'v3', credentials=credentials)


def get_existing_dates(drive_service, folder_id):
    # List all files matching the pattern
    query = f"name contains 'AllItemsReport_' and name contains '.csv' and '{folder_id}' in parents and trashed=false"
    response = drive_service.files().list(q=query, spaces='drive', fields='files(name)').execute()
    file_names = [f['name'] for f in response.get('files', [])]

    # Extract dates
    date_pattern = re.compile(r'AllItemsReport_(\d{8})\.csv')
    dates = set()
    for name in file_names:
        m = date_pattern.match(name)
        if m:
            dates.add(datetime.strptime(m.group(1), "%Y%m%d").date())

    st.write(dates)
    return dates


def collect_data() -> None:
    # Build the Google Drive API client
    drive_service = get_drive_service()

    existing_dates = get_existing_dates(drive_service, folder_id)
    yesterday = date.today() - timedelta(days=1)
    all_dates = set(pd.date_range(start=first_data_date, end=yesterday, freq=vv_business_days).date)
    missing_dates = sorted(dt for dt in all_dates if dt not in existing_dates)

    if not missing_dates:
        st.success("All available AllItemsReport files are already uploaded to Google Drive.")
        return

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
            for dt in missing_dates:
                date_str = dt.strftime('%Y%m%d')
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

                file_name = f'AllItemsReport_{date_str}.csv'
                file_metadata = {'name': file_name, 'parents': [folder_id]}
                media = MediaIoBaseUpload(file_obj, mimetype='text/csv')
                drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                st.success(f"Uploaded {file_name} to Google Drive.")
                sftp.chdir('..')

    finally:
        if os.path.exists(keyfile_path):
            os.remove(keyfile_path)