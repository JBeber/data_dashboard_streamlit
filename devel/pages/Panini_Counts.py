import streamlit as st
import plotly.express as px
from pandas import read_csv
import os
from datetime import date
from VV_data_collect import parse_date

# Main project directory
main_dir = 'C:\\Users\\Jeremiah\\OneDrive\\Documents\\VV\\Daily_Order_Data\\data_dashboard_streamlit\\devel\\'
os.chdir(main_dir)

@st.cache_data
def get_directories():
    lst = [name for name in os.listdir(f"{main_dir}Data") 
                if name.startswith('Week_ending_')]    
    return lst

data_directories = get_directories()
# print(data_directories)

# List of strings to populate the selection box
# display_weeks = [name.replace('_', ' ') for name in data_directories]

week = st.selectbox('Select week to display', data_directories)

# Date corresponding to the last day of the currently selected week
# week_ending_date = '20240609'

os.chdir(f'{main_dir}Data\\{week}')

# Items to exclude from the displayed data
excluded_items = ['Piadina Crudo', 'Piadina Ham & Cheese', 'Piadina Nutella', 'Roasted Potatoes', 'PIADINA']
# excluded_items = ['Roasted Potatoes']

@st.cache_data
def load_data(filepath):
    # data = pd.read_csv(filepath, usecols=['Menu Item', 'Menu Group', 'Qty', 'Void?', 'Deferred'])
    data = read_csv(filepath, usecols=['Menu Item', 'Menu Group', 'Qty', 'Void?'])
    return data

# List of data filenames for the currently selected week
week_data = [name for name in os.listdir('.')]

for filename in week_data:
    day_df = load_data(filename)

    # Keep only rows for panini that are not voided transactions
    day_df = day_df[(day_df['Menu Group'] == 'Panini') & 
            (~day_df['Menu Item'].isin(excluded_items)) &
            # (day_df['Deferred'] == False) & 
            (day_df['Void?'] == False)]

    # Aggregate data by item quantity
    aggregation_fn = {'Qty': 'sum'}
    panini_sold_agg = day_df.groupby(day_df['Menu Item']).aggregate(aggregation_fn)

    # Total panini count for the current day
    total_ct = round(sum(panini_sold_agg['Qty']))

    # st.bar_chart(panini_sold_agg)

    # Collect date from the current filename
    date_str = ''.join(filter(str.isdigit, filename))
    # print(date_str)

    # Date object for data currently being processed
    current_date = parse_date(date_str)

    # Plotting
    fig = px.bar(panini_sold_agg, 
                 y=panini_sold_agg.Qty,
                 title=f"Panini Counts for {current_date.strftime('%A, %b %d, %Y')} <br>Total Count: {total_ct}",
                 )
    
    fig.update_xaxes(tickangle=45)
    st.plotly_chart(fig)