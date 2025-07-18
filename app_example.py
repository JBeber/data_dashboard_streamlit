# Example integration into your main app.py
import streamlit as st
from modules.wine_visualization import wine_bottle_visualization

def main():
    st.set_page_config(
        page_title="VV Wine Dashboard",
        page_icon="🍷",
        layout="wide"
    )
    
    # Sidebar navigation
    st.sidebar.title("🍷 VV Wine Dashboard")
    
    page = st.sidebar.selectbox(
        "Choose a page:",
        ["Wine Bottle Analysis", "Other Analytics", "Data Collection"]
    )
    
    if page == "Wine Bottle Analysis":
        wine_bottle_visualization()
    elif page == "Other Analytics":
        st.header("Other Analytics")
        st.write("Future analytics modules will go here")
    elif page == "Data Collection":
        st.header("Data Collection")
        # Your existing collect_data functionality
        from VV_Utils import collect_data
        if st.button("Collect Latest Data"):
            collect_data()

if __name__ == "__main__":
    main()
