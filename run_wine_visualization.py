#!/usr/bin/env python3
"""
Wine Visualization Launcher
Run this script to launch the wine bottle visualization widget
"""

import streamlit as st
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.wine_visualization import wine_bottle_visualization

if __name__ == "__main__":
    # Configure the Streamlit page
    st.set_page_config(
        page_title="VV Wine Bottle Analysis",
        page_icon="🍷",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Run the visualization
    wine_bottle_visualization()
