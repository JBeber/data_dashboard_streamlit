import streamlit as st
from VV_Utils import collect_data

# Modular page imports
from modules import home

# Navigation config
PAGES = {
    "Home": home,
    # "Wine Bottles": wine_bottles
}

# Session state setup
if "page" not in st.session_state:
    st.session_state["page"] = "Home"
if "data_init_complete" not in st.session_state:
    st.session_state["data_init_complete"] = False

# Data collection logic
if not st.session_state["data_init_complete"]:
    st.sidebar.warning("Data upload in progress. Navigation is disabled.")
    collect_data()
    st.session_state["data_init_complete"] = True
    st.rerun()  # Refresh to enable navigation

# Modular custom sidebar
else:
    st.sidebar.image("vv_logo.jpeg", use_container_width=True)
    for page_name in PAGES:
        # Highlight current page, disable nav to same page
        if st.sidebar.button(page_name, disabled=st.session_state["page"] == page_name):
            st.session_state["page"] = page_name

    st.sidebar.markdown("---")
    st.sidebar.info("Custom sidebar content here if needed.")

    # Render selected page
    PAGES[st.session_state["page"]].main()