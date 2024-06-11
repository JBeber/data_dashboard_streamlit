import streamlit as st
import plotly.express as px
import pandas as pd

# Date corresponding to the last day of the currently selected week
week_ending_date = '20240609'

# Items to exclude from the displayed data
# excluded_items = ['Piadina Crudo', 'Piadina Ham & Cheese', 'Piadina Nutella', 'Roasted Potatoes']
excluded_items = ['Roasted Potatoes']

@st.cache_data
def load_data(filepath):
    data = pd.read_csv(filepath, usecols=['Menu Item', 'Menu Group', 'Qty', 'Void?', 'Deferred'])
    return data

day_df = load_data('C:\\Users\\Jeremiah\\OneDrive\\Documents\\VV\\Daily_Order_Data\\data_dashboard_streamlit\\Week_ending_20240505\\ItemSelectionDetails_20240505.csv')

# Keep only rows for panini that are not voided transactions
day_df = day_df[(day_df['Menu Group'] == 'Panini') & 
        (~day_df['Menu Item'].isin(excluded_items)) &
        (day_df['Deferred'] == False) & 
        (day_df['Void?'] == False)]

# Aggregate data by item quantity
aggregation_fn = {'Qty': 'sum'}
panini_sold_agg = day_df.groupby(day_df['Menu Item']).aggregate(aggregation_fn)

# st.bar_chart(panini_sold_agg)

fig = px.bar(panini_sold_agg, y=panini_sold_agg.Qty)
st.plotly_chart(fig)