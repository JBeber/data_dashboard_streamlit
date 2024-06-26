import streamlit as st
import plotly.express as px
from pandas import read_csv
from VV_data_collect import get_five_weeks_dirs, parse_date
import os
from calendar import day_name

# Root and data directories
main_dir = st.secrets['main_dir']
data_dir = st.secrets['data_dir']

five_weeks_dirs = get_five_weeks_dirs(data_dir)

weekday_selected = st.selectbox('Select day of the week:', 
                                options=('Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'))

files_lst = []
for dir in five_weeks_dirs:
    # Get a sorted list of file names in this directory
    sorted_files = sorted(os.listdir(f'{data_dir}{dir}'))
    print(sorted_files)

    # Get list index for the currently selected weekday
    weekday_index = list(day_name).index(weekday_selected)
    # print(weekday_index)

    # Append the absolute path of the data file for the 
    # corresponding weekday to the files list
    files_lst.append(f'{data_dir}{dir}/{sorted_files[weekday_index-1]}')

# print(files_lst)

# Initialize a dictionary to store a date and the
# corresponding sales total for that date
sales_totals = {}
for filepath in files_lst:
    # Collect date from the current filename
    date_str = ''.join(filter(str.isdigit, filepath[-12:-3]))

    df = read_csv(filepath, usecols=['Net Price', 'Void?'])
    df = df[df['Void?'] != 'TRUE']

    total_sales = round(sum(df['Net Price']), 2)

    sales_totals[parse_date(date_str)] = total_sales

# print(sales_totals)
# print(sales_totals.keys())
# print(sales_totals.values())

# Plotting
fig = px.bar(title=f"Total Sales Comparison for the Last 5 {weekday_selected}s",
                 x=list(sales_totals.keys()),
                 y=list(sales_totals.values())
                 )
    
fig.update_xaxes(ticklabelposition='outside right')
fig.update_xaxes(tickangle=45)

fig.update_layout(
    # This is required in order to avoid a graph
    # with a continuous array of dates for the x-axis
    # tick labels. Instead, only the dates corresponding to
    # the data are displayed.
    xaxis = dict(
        tickmode = 'array',
        tickvals = list(sales_totals.keys())
    ),
    xaxis_title = 'Date', yaxis_title = 'Total Sales',
    yaxis_tickformat = '$'
)

st.plotly_chart(fig)