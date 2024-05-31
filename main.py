import streamlit as st
import plotly.express as px
import pandas as pd

# This method is preferred so the excel file only has to be read
# once instead of every time the app refreshes
# data = pd.read_excel('sales_data.xlsx')

@st.cache_data
def load_data(filename):
    data = pd.read_excel(filename)
    return data

data = load_data('sales_data.xlsx')

st.title('Sales Data Visualization')

year = st.select_slider('Select a year', options=data, key='year')
# st.write(st.session_state)
# st.write(data)

# Calling int on a single element Series is deprecated and 
# will raise a TypeError in the future. Use int(ser.iloc[0]) instead

# sales = int(data.loc[data['Year'] == year, 'Sales'])

# Instead get a list with selected year and corresponding sales
row_by_year = data.loc[data['Year'] == year].values.squeeze()
# Then extract the sales value
sales = row_by_year[1]

# Display data
st.write(f"Sales for {year}: ${sales:,.2f}")

# Plotting
fig = px.bar(data, x=data.Year, y=data.Sales, color=data.Sales)
fig.add_vline(x=year, line={'color': 'red', 'dash': 'dash'})
st.plotly_chart(fig)