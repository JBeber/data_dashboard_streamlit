import streamlit as st
from VV_Utils import collect_data

st.image('vv_logo.jpeg')

# Read params from params.txt into a dictionary
# params = {}
# with open('params.txt', 'r') as f:
#     for line in f:
#         key, value = line.strip().split('=')
#         params[key] = value

# # Add params to Streamlit session state
# for key, value in params.items():
#     if key not in st.session_state:
#         st.session_state[key] = value

# print("Session state initialized with parameters:", st.session_state)
# st.write(params)

if 'data_init_complete' not in st.session_state:
    st.session_state['data_init_complete'] = False

if not st.session_state['data_init_complete']:
    collect_data()
    st.session_state['data_init_complete'] = True
