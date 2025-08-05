import streamlit as st
from datetime import datetime, timedelta
import os

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

# Background job status indicator
def show_data_status():
    """Show status of background data collection job and OAuth connection."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Data Status")
    
    # Check OAuth status
    try:
        from utils.enhanced_oauth import get_enhanced_drive_service
        drive_service = get_enhanced_drive_service()
        
        if drive_service is not None:
            st.sidebar.success("✅ Google Drive Connected")
        else:
            st.sidebar.error("❌ Google Drive Disconnected")
            st.sidebar.caption("Contact administrator for authentication help")
            
    except Exception as e:
        st.sidebar.warning("⚠️ Drive Status Unknown")
        st.sidebar.caption("Unable to check connection status")
    
    # In production, this could check actual job status via Cloud Run API
    # For now, show a simple status indicator
    last_update = datetime.now() - timedelta(hours=2)  # Placeholder
    st.sidebar.info(f"📅 Data current as of {last_update.strftime('%m/%d %I:%M %p')}")
    st.sidebar.caption("Data is automatically updated daily at 6 AM EST")

# Main navigation
st.sidebar.image("vv_logo.jpeg", use_container_width=True)

# Show data status
show_data_status()

# Navigation buttons
for page_name in PAGES:
    # Highlight current page, disable nav to same page
    if st.sidebar.button(page_name, disabled=st.session_state["page"] == page_name):
        st.session_state["page"] = page_name

# Render selected page
PAGES[st.session_state["page"]].main()