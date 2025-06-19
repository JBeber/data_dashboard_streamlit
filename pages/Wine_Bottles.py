import streamlit as st
import pandas as pd
from datetime import date, datetime
from VV_Utils import vv_business_days as bdays
from math import ceil


# Specify new date range to use for analysis
date_lst = pd.date_range(start=date(2025, 1, 1), end = date(2025, 6, 17), freq=bdays).to_list()
#date.today().strftime('%Y%m%d')
str_dt_lst = [dt.strftime('%Y%m%d') for dt in date_lst]

# 1. Create a DataFrame mapping each date string to its week number
date_info = pd.DataFrame({
    'date_str': str_dt_lst,
    'date': [datetime.strptime(ds, '%Y%m%d') for ds in str_dt_lst]
})
date_info['week'] = date_info['date'].dt.isocalendar().week

# 2. Map each file to its week
date_info['file'] = date_info['date_str'].apply(lambda ds: f'../Daily_Data/AllItemsReport_{ds}.csv')

# Get the last date for each week
week_ending_dates = date_info.groupby('week')['date'].max().reset_index()

# 3. Group files by week and concatenate
weekly_dfs = {}
for week, group in date_info.groupby('week'):
    files = group['file'].tolist()
    df_list = [pd.read_csv(file) for file in files]
    weekly_dfs[week] = pd.concat(df_list, ignore_index=True)

# Names of BTG bottles as listed in Toast
btg_bottles = ['Barbera D\'Asti - Vigne Vecchie', 'Primitivo Sin - Vigne Vecchie',
               'Pinot Grigio - Villa Loren', 'Chardonnay - Tenuta Maccan', 
               'Moscato D\'Asti - La Morandina', 'Gavi Masera - Stefano Massone', 
               'Negramaro Rosato Soul - Vigne Vecchie', 'Gattinara Rosato Bricco Lorella - Antoniolo', 
               'Prosecco Brut - Castel Nuovo del Garda', 'Prosecco Rose - Castel Nuovo del Garda', 
               'Trento DOC - Maso Bianco - Seiterre', 'Nebbiolo - Vigne Vecchie', 
               'Chianti Superiore - Banfi', 'Nerello Mascalese - Vento di Mare']

# Names of BTG glasses as listed in Toast
btg_glasses = ['Glass Barbera D\'Asti - Vigne Vecchie', 'Glass Primitivo Sin - Vigne Vecchie',
               'Glass Pinot Grigio - Villa Loren', 'Glass Chardonnay - Tenuta Maccan', 
               'Glass Moscato D\'Asti - La Morandina', 'Glass Gavi - Masera', 
               'Glass Rosato Soul - Vigne Vecchie', 'Glass Gattinara Rosato - Antoniolo Bricco Lorella', 
               'Glass Prosecco Brut - Castel Nuovo del Garda', 'Glass Prosecco Rosato - Castel Nuovo del Garda', 
               'Glass Trento DOC - Maso Bianco - Seiterre', 'Glass Nebbiolo - Vigne Vecchie', 
               'Glass Chianti Superiore - Banfi', 'Glass Nerello Mascalese - Vento di Mare']

bottle_to_glass_map = dict(zip(btg_bottles, btg_glasses))

output_df = pd.DataFrame(columns=['Week Ending Date', 'Item', 'Bottles Total'])

for week, df in weekly_dfs.items():
    
    bottle_totals = {}

    bottles_df = df[df['Menu Group'].isin(['RETAIL WINE', 'Wine - Bottles']) & df['Menu Item'].isin(btg_bottles)]
    glasses_df = df[df['Menu Group'].isin(['Wine - Glasses']) & df['Menu Item'].isin(btg_glasses)]    

    whole_bottles_sold = bottles_df.groupby('Menu Item')['Item Qty'].sum() if not bottles_df.empty else 0
    glasses_sold = glasses_df.groupby('Menu Item')['Item Qty'].sum() if not glasses_df.empty else 0

    for bottle in btg_bottles:
        bottle_count = whole_bottles_sold.get(bottle, 0)
        glass_name = bottle_to_glass_map.get(bottle)
        glass_count = glasses_sold.get(glass_name, 0)
        
        bottle_totals[bottle] = bottle_count + ceil(glass_count / 4)

    week_ending_date = week_ending_dates[week_ending_dates['week'] == week]['date'].values[0]

    output_df.loc[len(output_df)] = [
            week_ending_date,
            bottle,
            bottle_totals[bottle]
        ]
    
    st.write(output_df)