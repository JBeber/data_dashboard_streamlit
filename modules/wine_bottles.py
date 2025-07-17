import pandas as pd
from math import ceil
from datetime import date, datetime
from VV_Utils import get_business_days, load_config

class WineDashboardData:
    def __init__(self, start_date, end_date, data_loader_func, bottle_names, glass_names, bottle_to_glass_map):
        self.config = load_config('config.yaml')
        self.start_date = start_date
        self.end_date = end_date
        self.data_loader_func = data_loader_func # expects a function that returns a DataFrame per date string
        self.bottle_names = bottle_names
        self.glass_names = glass_names
        self.bottle_to_glass_map = bottle_to_glass_map
        self.output_df = pd.DataFrame(columns=['Week Ending Date', 'Bottle', 'Bottles Total'])
        self._load_and_aggregate()

    def _date_list(self):
        vv_business_days = get_business_days()
        return pd.date_range(start=self.start_date, end=self.end_date, freq=vv_business_days).to_list()

    def _date_str_list(self):
        return [dt.strftime('%Y%m%d') for dt in self._date_list()]

    def _date_info(self):
        str_dt_lst = self._date_str_list()
        date_info = pd.DataFrame({
            'date_str': str_dt_lst,
            'date': [datetime.strptime(ds, '%Y%m%d') for ds in str_dt_lst]
        })
        date_info['week'] = date_info['date'].dt.isocalendar().week
        date_info['file'] = date_info['date_str'].apply(lambda ds: f'Daily_Data/AllItemsReport_{ds}.csv')
        return date_info

    def _load_and_aggregate(self):
        date_info = self._date_info()
        week_ending_dates = date_info.groupby('week')['date'].max().reset_index()
        weekly_dfs = {}

        for week, group in date_info.groupby('week'):
            files = group['file'].tolist()
            df_list = []
            for file in files:
                try:
                    df = self.data_loader_func(file)
                    df_list.append(df)
                except Exception as e:
                    print(e) # Could log the error or file name
                    continue
            if df_list:
                weekly_dfs[week] = pd.concat(df_list, ignore_index=True)

        for week, df in weekly_dfs.items():
            bottle_totals = {}
            bottles_df = df[df['Menu Group'].isin(['RETAIL WINE', 'Wine - Bottles']) & df['Menu Item'].isin(self.bottle_names)]
            glasses_df = df[df['Menu Group'].isin(['Wine - Glasses']) & df['Menu Item'].isin(self.glass_names)]
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