import pysftp, io, tempfile, os
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Set operatings days for date range generation
vv_weekmask = 'Tue Wed Thu Fri Sat Sun'
vv_business_days = pd.offsets.CustomBusinessDay(weekmask=vv_weekmask)

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


def collect_data() -> None:
    # Build the Google Drive API client
    drive_service = get_drive_service()

    last_collect_str = st.session_state['last_data_collect']
    # today_str = date.today().strftime('%Y%m%d')

    last_collect_dt = parse_date(last_collect_str)
    latest_data_dt = date.today() - timedelta(days=1)  # Use yesterday's date as the latest data date

    # Check if the last date data was collected is before the last collection date
    if last_collect_dt < latest_data_dt:        

        with st.spinner('Collecting latest restaurant data...'):
            date_lst = pd.date_range(start=last_collect_dt, end=latest_data_dt, freq=vv_business_days).to_list()
            str_dt_lst = [dt.strftime('%Y%m%d') for dt in date_lst]

            # Get private key string from secrets
            private_key_str = st.secrets["Toast_SFTP"]["private_key"]

            # Write to a temporary file
            with tempfile.NamedTemporaryFile(delete=False) as keyfile:
                keyfile.write(private_key_str.encode())
                keyfile_path = keyfile.name

            try:
                cnopts = pysftp.CnOpts()
                # cnopts.hostkeys.clear()
                # cnopts.hostkeys.add(st.secrets['Toast_SFTP']['hostname'], 
                #                     'ssh-rsa', 
                #                     st.secrets['Toast_SFTP']['host_key'])
                # cnopts.hostkeys.add(st.secrets['Toast_SFTP']['hostname'], 
                #                     'ssh-rsa', 
                #                     st.secrets['Toast_SFTP']['host_key'])
                # cnopts.hostkeys.add('s-9b0f88558b264dfda.server.transfer.us-east-1.amazonaws.com', 
                #                     'ssh-rsa', 
                #                     'AAAAB3NzaC1yc2EAAAADAQABAAABAQCpJVs5xW6SNtcFu/hyhuGbqZu9qV6fD62+3mzLkgGRco5LzFlBiKdHPPAnPEIFrRg1GCClCoaF1AbSFO326yyLqu0ealxqHK/ygrguTuGhLZ/pCrejNoqrRGpnP5Gyd3IKhUCkoWWR+HDpMo/107IZVOu6ZvRgm/Yly2lMKioZLzmhNLIL9gJtBk45f247TGnpgX64wc7ho4TMBwN9p9sdLUY3Mq97MwvknfqSplw2Ch8xlYCYVaWVbsWGNoSmLDh1Lu97jElc6EtaRoTVKOPgWZDWJL6Jn20sBSxbCZGhJST9//x4gMIsOqHqL+2qjfWJp+DvS/zhgtEGn/bh/O8z')

                cnopts.hostkeys.load('Toast_SFTP_known_hosts')
                with pysftp.Connection(st.secrets['Toast_SFTP']['hostname'],
                                    port=22,
                                    username=st.secrets['Toast_SFTP']['username'],
                                    private_key=keyfile_path,
                                    private_key_pass=st.secrets['Toast_SFTP']['pwd'],
                                    cnopts=cnopts) as sftp:
                    
                    sftp.chdir(st.secrets['Toast_SFTP']['export_id'])

                    for date_str in str_dt_lst:
                        sftp.chdir(f'./{date_str}')

                        # Read file into memory instead of local disk
                        file_obj = io.BytesIO()
                        sftp.getfo('AllItemsReport.csv', file_obj)
                        file_obj.seek(0)  # Reset pointer

                        # # Prepare upload to Google Drive
                        # file_metadata = {
                        #     'name': f'AllItemsReport_{date_str}.csv',
                        #     'parents': [st.secrets['Google_Drive']['folder_id']],
                        # }
                        
                        # media = MediaIoBaseUpload(file_obj, mimetype='text/csv')

                        # # Upload to Google Drive                        
                        # uploaded_file = drive_service.files().create(
                        # body=file_metadata,
                        # media_body=media,
                        # fields='id'
                        # ).execute()

                        file_name = f'AllItemsReport_{date_str}.csv'
                        folder_id = st.secrets['Google_Drive']['folder_id']

                        # ------------- NEW: Check for existing file -------------
                        query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
                        search = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
                        files = search.get('files', [])

                        media = MediaIoBaseUpload(file_obj, mimetype='text/csv')

                        if files:
                            # File exists, update (overwrite) it
                            file_id = files[0]['id']
                            uploaded_file = drive_service.files().update(
                                fileId=file_id,
                                media_body=media
                            ).execute()
                            st.info(f"Updated file: {file_name} in Google Drive.")
                        else:
                            # File does not exist, create it
                            file_metadata = {
                                'name': file_name,
                                'parents': [folder_id],
                            }
                            uploaded_file = drive_service.files().create(
                                body=file_metadata,
                                media_body=media,
                                fields='id'
                            ).execute()
                            st.info(f"Created file: {file_name} in Google Drive.")

                        sftp.chdir('../')
            finally:
                # Clean up the temporary private key file
                if os.path.exists(keyfile_path):
                    os.remove(keyfile_path)

        # Update the last data collection date in session state
        st.session_state['last_data_collect'] = latest_data_dt.strftime('%Y%m%d')

        # Update the last data collection date in params.txt
        with open('params.txt', 'w') as f:
            f.write(f'last_data_collect={st.session_state["last_data_collect"]}\n')
            
        st.success(f"Data collected successfully from {last_collect_dt.strftime('%Y-%m-%d')} to {latest_data_dt.strftime('%Y-%m-%d')}.")