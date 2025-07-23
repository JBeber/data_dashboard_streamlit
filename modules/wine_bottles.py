import pandas as pd
from math import ceil
from datetime import date, datetime, timedelta
import io
import sys
import os
import streamlit as st
import time

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from VV_Utils import get_existing_dates, load_config, get_drive_service

def retry_on_ssl_error(max_retries=3, delay=1):
    """Decorator to retry function calls on SSL errors"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e).lower()
                    if 'ssl' in error_str or 'record layer failure' in error_str:
                        if attempt < max_retries - 1:
                            time.sleep(delay * (attempt + 1))  # Exponential backoff
                            continue
                    # If it's not an SSL error or we've exhausted retries, raise the exception
                    if attempt == max_retries - 1:
                        print(f"Error after {max_retries} attempts: {e}")
                    raise e
            return None
        return wrapper
    return decorator

class WineDashboardData:
    def __init__(self, start_date, end_date):
        self.config = load_config('config.yaml')
        self.start_date = start_date
        self.end_date = end_date
        self.bottle_to_glass_map = self.config.get('bottle_to_glass_map', {})
        self.bottle_names = list(self.bottle_to_glass_map.keys())
        self.drive_service = get_drive_service()
        self.folder_id = st.secrets['Google_Drive']['folder_id']
        self.output_df = pd.DataFrame(columns=['Week Ending Date', 'Bottle', 'Bottles Total'])
        self._load_and_aggregate()

    def _date_list(self):
        vv_business_days = self.config.get('business_days', None)
        # Don't include today's date since data is only available the day after
        yesterday = date.today() - timedelta(days=1)
        end_date = min(self.end_date, yesterday)
        return pd.date_range(start=self.start_date, end=end_date, freq=vv_business_days).to_list()

    def _date_str_list(self):
        return [dt.strftime('%Y%m%d') for dt in self._date_list()]

    def _date_info(self):
        str_dt_lst = self._date_str_list()
        date_info = pd.DataFrame({
            'date_str': str_dt_lst,
            'date': [datetime.strptime(ds, '%Y%m%d') for ds in str_dt_lst]
        })
        date_info['week'] = date_info['date'].dt.isocalendar().week
        date_info['file'] = date_info['date_str'].apply(lambda ds: f'AllItemsReport_{ds}.csv')
        return date_info

    @retry_on_ssl_error(max_retries=3, delay=1)
    def _data_loader_func(self, file_name):
        """Load CSV data from Google Drive for a specific date"""
        # Search for the file in Google Drive
        query = f"name='{file_name}' and '{self.folder_id}' in parents and trashed=false"
        response = self.drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        
        files = response.get('files', [])
        if not files:
            return pd.DataFrame()
        
        # Get the file content
        file_id = files[0]['id']
        file_content = self.drive_service.files().get_media(fileId=file_id).execute()
        
        # Convert to DataFrame
        df = pd.read_csv(io.BytesIO(file_content))
        return df

    def _load_and_aggregate(self):
        date_info = self._date_info()
        week_ending_dates = date_info.groupby('week')['date'].max().reset_index()
        weekly_dfs = {}

        for week, group in date_info.groupby('week'):
            files = group['file'].tolist()
            df_list = []
            for file in files:
                try:
                    df = self._data_loader_func(file)
                    if not df.empty:
                        df_list.append(df)
                except Exception as e:
                    # Only print non-SSL errors as they might indicate other issues
                    error_str = str(e).lower()
                    if 'ssl' not in error_str and 'record layer failure' not in error_str:
                        print(f"Non-SSL error loading {file}: {e}")
                    continue
            if df_list:
                weekly_dfs[week] = pd.concat(df_list, ignore_index=True)

        for week, df in weekly_dfs.items():
            bottle_totals = {}
            bottles_df = df[df['Menu Group'].isin(['RETAIL WINE', 'Wine - Bottles']) & df['Menu Item'].isin(self.bottle_names)]
            glasses_df = df[df['Menu Group'].isin(['Wine - Glasses']) & df['Menu Item'].isin(self.bottle_to_glass_map.values())]
            whole_bottles_sold = bottles_df.groupby('Menu Item')['Item Qty'].sum() if not bottles_df.empty else 0
            glasses_sold = glasses_df.groupby('Menu Item')['Item Qty'].sum() if not glasses_df.empty else 0
            week_ending_date = week_ending_dates[week_ending_dates['week'] == week]['date'].values[0]
            for bottle in self.bottle_names:
                bottle_count = whole_bottles_sold.get(bottle, 0)
                glass_name = self.bottle_to_glass_map.get(bottle)
                glass_count = glasses_sold.get(glass_name, 0)
                bottle_totals[bottle] = bottle_count + ceil(glass_count / 4)
                self.output_df.loc[len(self.output_df)] = [
                    week_ending_date,
                    bottle,
                    bottle_totals[bottle]
                ]

    def get_weekly_bottle_counts(self):
        return self.output_df.copy()

    def get_available_wines(self):
        """Return list of available wine bottle names"""
        return self.bottle_names.copy()

    @retry_on_ssl_error(max_retries=3, delay=1)
    def get_available_dates(self):
        """Return list of available dates from Google Drive"""
        existing_dates = get_existing_dates(self.drive_service, self.folder_id)
        return sorted(existing_dates)