import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta
import sys
import os
import altair as alt

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.wine_bottles import WineDashboardData

def wine_bottle_visualization():
    """BTG wine bottle visualization widget for Streamlit dashboard"""

    st.header("🍷 BTG Wine Bottle Sales Analysis")
    st.markdown("Track weekly BTG wine bottle sales including bottles sold directly and equivalent bottles from glass sales.")
    
    # Info about data availability
    st.info("📊 **Data Availability**: Restaurant data becomes available the day after service. The latest available data is from yesterday.")
    
    # Get available data range
    try:
        # Use a single day to quickly get available dates without processing all data
        yesterday = date.today() - timedelta(days=1)
        temp_data = WineDashboardData(yesterday, yesterday)
        available_dates = temp_data.get_available_dates()
        available_wines = temp_data.get_available_wines()
        
        if not available_dates:
            st.error("📅 No data available in Google Drive. Please check your data collection process.")
            return
        
        if not available_wines:
            st.error("🍾 No wines configured. Please check your config.yaml file.")
            return
            
    except Exception as e:
        error_str = str(e).lower()
        if 'ssl' in error_str or 'record layer failure' in error_str:
            st.warning("⚠️ Temporary network connectivity issue. Please refresh the page or try again in a moment.")
        else:
            st.error(f"❌ Error connecting to data source: {e}")
        st.error("Please check your configuration and Google Drive connection.")
        return
    
    # Date range selection
    col1, col2 = st.columns(2)
    
    min_date = min(available_dates)
    max_date = max(available_dates)
    # Don't allow selection beyond yesterday since data is only available the day after
    yesterday = date.today() - timedelta(days=1)
    max_selectable_date = min(max_date, yesterday)
    
    with col1:
        start_date = st.date_input(
            "📅 Start Date",
            value=max_selectable_date - timedelta(days=30),  # Default to last 30 days
            min_value=min_date,
            max_value=max_selectable_date,
            help="Select the start date for analysis"
        )
    
    with col2:
        end_date = st.date_input(
            "📅 End Date",
            value=max_selectable_date,
            min_value=min_date,
            max_value=max_selectable_date,
            help="Select the end date for analysis (data is available up to yesterday)"
        )
    
    # Wine selection
    st.subheader("🍾 Wine Selection")
    
    # Selection options
    selection_mode = st.radio(
        "Choose wines to analyze:",
        ["All wines", "Select specific wines", "Top performers only"],
        horizontal=True
    )
    
    if selection_mode == "All wines":
        selected_wines = available_wines
    elif selection_mode == "Select specific wines":
        selected_wines = st.multiselect(
            "Select wines to analyze:",
            options=available_wines,
            default=available_wines[:5] if len(available_wines) > 5 else available_wines,
            help="Choose specific wines to include in the analysis"
        )
    else:  # Top performers only
        num_top = st.slider("Number of top wines to show:", 3, 10, 5)
        selected_wines = available_wines[:num_top]  # Will be filtered by actual performance later
    
    # Validation
    if start_date > end_date:
        st.error("❌ Start date must be before end date")
        return
    
    if not selected_wines:
        st.warning("⚠️ Please select at least one wine to analyze")
        return
    
    # Generate analysis button
    if st.button("📊 Generate Analysis", type="primary"):
        generate_wine_analysis(start_date, end_date, selected_wines, selection_mode, num_top if selection_mode == "Top performers only" else None)

def generate_wine_analysis(start_date, end_date, selected_wines, selection_mode, num_top=None):
    """Generate and display wine bottle analysis"""
    
    with st.spinner("🔄 Loading wine data from Google Drive..."):
        try:
            # Load data
            wine_data = WineDashboardData(start_date, end_date)
            df = wine_data.get_weekly_bottle_counts()
            
            if df.empty:
                st.warning("📊 No data found for the selected date range and wines.")
                st.info("💡 This could be due to:")
                st.info("• No sales during the selected period")
                st.info("• Network connectivity issues (try refreshing)")
                st.info("• Missing data files for those dates")
                return
            
            # Filter for selected wines or get top performers
            if selection_mode == "Top performers only":
                # Get top performers by total bottles
                top_wines = df.groupby('Bottle')['Bottles Total'].sum().sort_values(ascending=False).head(num_top)
                df = df[df['Bottle'].isin(top_wines.index)]
                st.info(f"🏆 Showing top {len(top_wines)} wines by total bottles sold")
            else:
                df = df[df['Bottle'].isin(selected_wines)]
            
            # Display visualizations
            create_visualizations(df)
            
            # Display summary statistics
            show_summary_statistics(df)
            
        except Exception as e:
            error_str = str(e).lower()
            if 'ssl' in error_str or 'record layer failure' in error_str:
                st.error("🌐 Network connectivity issue occurred while loading data.")
                st.info("💡 Please try again in a moment. Some data may have loaded successfully.")
            else:
                st.error(f"❌ Error generating analysis: {e}")
                st.info("💡 Please check your date range and wine selections.")

def create_visualizations(df):
    """Create various visualizations for wine bottle data"""
    
    # 1. Time Series Line Chart (Altair)
    st.subheader("📈 Weekly Trends")
    
    # Prepare data for Altair
    trend_data = df.sort_values('Week Ending Date').copy()
    trend_data['Week Ending Date'] = pd.to_datetime(trend_data['Week Ending Date']).dt.strftime('%Y-%m-%d')
    
    # Create Altair line chart
    line_chart = alt.Chart(trend_data).mark_line(
        point=alt.OverlayMarkDef(
            filled=True,
            size=80,
            stroke='white',
            strokeWidth=2
        ),
        strokeWidth=3,
        interpolate='monotone'
    ).encode(
        x=alt.X('Week Ending Date:T', 
                title='Week Ending Date',
                axis=alt.Axis(labelAngle=-45, labelFontSize=11, format='%m/%d')),
        y=alt.Y('Bottles Total:Q', 
                title='Bottles Sold',
                scale=alt.Scale(nice=True, zero=False)),
        color=alt.Color('Bottle:N', 
                       title='Wine',
                       scale=alt.Scale(range=['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#592E83', '#048A81', '#F39C12', '#8E44AD']),
                       legend=alt.Legend(
                           orient='right',
                           titleFontSize=12,
                           labelFontSize=11,
                           symbolSize=120,
                           symbolType='circle',
                           labelLimit=200
                       )),
        tooltip=['Week Ending Date:T', 'Bottle:N', 'Bottles Total:Q']
    ).properties(
        title=alt.TitleParams(
            text='Weekly Wine Bottle Sales Trends',
            fontSize=16,
            anchor='start',
            color='#2c3e50',
            fontWeight='bold'
        ),
        height=400,
        width=800
    ).configure_axis(
        labelFontSize=11,
        titleFontSize=12,
        grid=True,
        gridColor='#f0f0f0',
        gridOpacity=0.5,
        domain=False
    ).configure_view(
        strokeWidth=0
    )
    
    st.altair_chart(line_chart, use_container_width=True)

    # 2. Bar Chart - Total Bottles by Wine (Altair)
    st.subheader("📊 Total Bottles by Wine")
    
    total_bottles = df.groupby('Bottle')['Bottles Total'].sum().sort_values(ascending=False)
    
    # Create DataFrame for Altair
    chart_data = pd.DataFrame({
        'Wine': total_bottles.index,
        'Total Bottles': total_bottles.values
    })
    
    # Create Altair horizontal bar chart
    bar_chart = alt.Chart(chart_data).mark_bar(
        color='#1f77b4',
        cornerRadiusEnd=3
    ).encode(
        x=alt.X('Total Bottles:Q', 
                title='Total Bottles Sold',
                scale=alt.Scale(nice=True)),
        y=alt.Y('Wine:N', 
                title=None,
                sort='-x'),
        color=alt.Color('Total Bottles:Q',
                       scale=alt.Scale(scheme='blues'),
                       legend=None),
        tooltip=['Wine:N', 'Total Bottles:Q']
    ).properties(
        title=alt.TitleParams(
            text='Total Wine Bottles Sold',
            fontSize=16,
            anchor='start',
            color='#333333'
        ),
        height=max(300, len(total_bottles) * 40),
        width=600
    ).configure_axis(
        labelFontSize=11,
        titleFontSize=12,
        grid=False
    ).configure_view(
        strokeWidth=0
    )
    
    st.altair_chart(bar_chart, use_container_width=True)
    
    # 3. Weekly Comparison Bar Chart (Altair)
    st.subheader("📅 Weekly Comparison")
    
    # Prepare data for Altair
    weekly_data = df.sort_values('Week Ending Date').copy()
    weekly_data['Week Ending Date'] = pd.to_datetime(weekly_data['Week Ending Date']).dt.strftime('%Y-%m-%d')
    
    # Create Altair grouped bar chart using facet approach
    base = alt.Chart(weekly_data).add_selection(
        alt.selection_single()
    )
    
    weekly_chart = base.mark_bar(
        cornerRadiusEnd=3,
        stroke='white',
        strokeWidth=0.5
    ).encode(
        x=alt.X('Bottle:N', 
                title=None,
                axis=alt.Axis(labelAngle=-45, labelFontSize=10)),
        y=alt.Y('Bottles Total:Q', 
                title='Bottles Sold',
                scale=alt.Scale(nice=True)),
        color=alt.Color('Bottle:N', 
                       title='Wine',
                       scale=alt.Scale(range=['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#592E83', '#048A81', '#F39C12', '#8E44AD']),
                       legend=alt.Legend(
                           orient='right',
                           titleFontSize=12,
                           labelFontSize=11,
                           symbolSize=120,
                           symbolType='square',
                           labelLimit=200
                       )),
        tooltip=['Week Ending Date:O', 'Bottle:N', 'Bottles Total:Q']
    ).properties(
        width=150,
        height=400
    ).facet(
        column=alt.Column('Week Ending Date:O',
                         title='Week Ending Date',
                         header=alt.Header(titleFontSize=12, labelFontSize=11))
    ).resolve_scale(
        color='independent'
    ).configure_axis(
        labelFontSize=11,
        titleFontSize=12,
        grid=False,
        domain=False
    ).configure_view(
        strokeWidth=0
    ).configure_header(
        titleFontSize=14,
        titleColor='#2c3e50',
        titleFontWeight='bold'
    )
    
    st.altair_chart(weekly_chart, use_container_width=True)

def show_summary_statistics(df):
    """Display summary statistics and insights"""
    
    st.subheader("📊 Summary Statistics")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_bottles = df['Bottles Total'].sum()
    avg_weekly = df['Bottles Total'].mean()
    unique_wines = df['Bottle'].nunique()
    weeks_analyzed = df['Week Ending Date'].nunique()
    
    with col1:
        st.metric("Total Bottles", f"{total_bottles:,}")
    
    with col2:
        st.metric("Average Weekly", f"{avg_weekly:.1f}")
    
    with col3:
        st.metric("Wines Analyzed", unique_wines)
    
    with col4:
        st.metric("Weeks Analyzed", weeks_analyzed)
    
    # Top performers
    st.subheader("🏆 Top Performers")
    
    top_wines = df.groupby('Bottle')['Bottles Total'].sum().sort_values(ascending=False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Top 5 Wines by Total Bottles Sold:**")
        for i, (wine, total) in enumerate(top_wines.head().items(), 1):
            st.write(f"{i}. **{wine}**: {total} bottles")
    
    with col2:
        # Average weekly performance
        avg_weekly_performance = df.groupby('Bottle')['Bottles Total'].mean().sort_values(ascending=False)
        st.markdown("**Top 5 Wines by Average Weekly Bottles Sold:**")
        for i, (wine, avg) in enumerate(avg_weekly_performance.head().items(), 1):
            st.write(f"{i}. **{wine}**: {avg:.1f} bottles/week")
    
    # Detailed data table
    st.subheader("📋 Detailed Data")
    
    # Format the data for display
    display_df = df.copy()
    display_df['Week Ending Date'] = pd.to_datetime(display_df['Week Ending Date']).dt.strftime('%Y-%m-%d')
    display_df = display_df.sort_values(['Week Ending Date', 'Bottles Total'], ascending=[True, False])
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Week Ending Date": st.column_config.DateColumn("Week Ending"),
            "Bottle": st.column_config.TextColumn("Wine"),
            "Bottles Total": st.column_config.NumberColumn("Bottles", format="%d")
        }
    )
    
    # Export option
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download Data as CSV",
        data=csv,
        file_name=f"btg_wine_sales_{df['Week Ending Date'].min()}_{df['Week Ending Date'].max()}.csv",
        mime="text/csv"
    )

if __name__ == "__main__":
    # For testing
    wine_bottle_visualization()
