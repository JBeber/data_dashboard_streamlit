import streamlit as st
from VV_Utils import collect_data

# Modular page imports
from modules import home
from modules import wine_visualization


# Load the password from Streamlit secrets
PASSWORD = st.secrets["auth"]["password"]

def check_password():
    """Simple password check and session state."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        pwd = st.text_input("Enter password", type="password")
        if st.button("Login"):
            if pwd == PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password")
        st.stop()

check_password()

# Navigation config
PAGES = {
    "Home": home,
    "BTG Wine Bottles": wine_visualization
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