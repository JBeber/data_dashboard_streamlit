import streamlit as st
from VV_Utils_local_storage import collect_data

st.image('vv_logo.jpeg')

# Read params from params.txt into a dictionary
params = {}
with open('params.txt', 'r') as f:
    for line in f:
        key, value = line.strip().split('=')
        params[key] = value

# Add params to Streamlit session state
for key, value in params.items():
    if key not in st.session_state:
        st.session_state[key] = value

# print("Session state initialized with parameters:", st.session_state)
# st.write(params)

collect_data()