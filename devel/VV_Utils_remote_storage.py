import pysftp
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Set operatings days for date range generation
vv_weekmask = 'Tue Wed Thu Fri Sat Sun'
vv_business_days = pd.offsets.CustomBusinessDay(weekmask=vv_weekmask)

# Path to your downloaded service account JSON key
SERVICE_ACCOUNT_FILE = "E:\\Documents\\VV\\Daily_Order_Data\\vv-data-dashboard-d05b7f359027.json"

# The required scope for full Drive access
SCOPES = ['https://www.googleapis.com/auth/drive']

# Parse a Python date object from string in YYYYMMDD format
def parse_date(s: str) -> date:
    year = int(s[:4])
    month = int(s[4:6])
    day = int(s[-2:])

    return date(year, month, day)

@st.cache_resource  # Use st.experimental_singleton for earlier Streamlit versions
def get_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes= SCOPES
    )

    return build('drive', 'v3', credentials=credentials)


def collect_data() -> None:
    last_collect_str = st.session_state['last_data_collect']
    # today_str = date.today().strftime('%Y%m%d')

    last_collect_dt = parse_date(last_collect_str)
    latest_data_dt = date.today() - timedelta(days=1)  # Use yesterday's date as the latest data date

    # Check if the last date data was collected is before the last collection date
    if last_collect_dt < latest_data_dt:        

        with st.spinner('Collecting latest restaurant data...'):
            date_lst = pd.date_range(start=last_collect_dt, end=latest_data_dt, freq=vv_business_days).to_list()
            str_dt_lst = [dt.strftime('%Y%m%d') for dt in date_lst]

            with pysftp.Connection(st.secrets['hostname'], 
                                    username=st.secrets['username'],
                                    private_key=st.secrets['private_key'],
                                    private_key_pass=st.secrets['pwd']) as sftp:
                    
                sftp.chdir(st.secrets['export_id'])

                for date_str in str_dt_lst:
                    sftp.chdir(f'./{date_str}')
                    sftp.get('./AllItemsReport.csv', 
                                        localpath=f'Daily_Data/AllItemsReport_{date_str}.csv')
                    sftp.chdir('../')

        # Update the last data collection date in session state
        st.session_state['last_data_collect'] = latest_data_dt.strftime('%Y%m%d')
        # Update the last data collection date in params.txt
        with open('params.txt', 'w') as f:
            f.write(f'last_data_collect={st.session_state["last_data_collect"]}\n')
            
        st.success(f"Data collected successfully from {last_collect_dt.strftime('%Y-%m-%d')} to {latest_data_dt.strftime('%Y-%m-%d')}.")

    # Build the Google Drive API client
    drive_service = get_drive_service()

    # Query to exclude folders
    query = "mimeType != 'application/vnd.google-apps.folder'"

    files = []
    page_token = None
    
    while True:
        response = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='nextPageToken, files(name)',
            pageToken=page_token
        ).execute()
        files.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    file_names = [file['name'] for file in files]

    