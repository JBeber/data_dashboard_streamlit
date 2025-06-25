import pysftp, os, sys
from datetime import date, timedelta
import pandas as pd
import streamlit as st


# Set operatings days for date range generation
vv_weekmask = 'Tue Wed Thu Fri Sat Sun'
vv_business_days = pd.offsets.CustomBusinessDay(weekmask=vv_weekmask)

# Parse a Python date object from string in YYYYMMDD format
def parse_date(s: str) -> date:
    year = int(s[:4])
    month = int(s[4:6])
    day = int(s[-2:])

    return date(year, month, day)

def collect_data() -> None:
    last_collect_str = st.session_state['last_data_collect']
    # today_str = date.today().strftime('%Y%m%d')

    last_collect_dt = parse_date(last_collect_str)
    latest_data_dt = date.today() - timedelta(days=1)  # Use yesterday's date as the latest data date

    # Check if the last date data was collected is before today's date
    if last_collect_dt < latest_data_dt:        

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
                                    localpath=f'../Daily_Data/AllItemsReport_{date_str}.csv')
                sftp.chdir('../')