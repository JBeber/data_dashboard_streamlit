import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.wine_bottles import WineDashboardData

def wine_bottle_visualization():
    """Main wine bottle visualization widget for Streamlit dashboard"""
    
    st.header("🍷 Wine Bottle Consumption Analysis")
    st.markdown("Track weekly wine bottle consumption including bottles sold directly and equivalent bottles from glass sales.")
    
    # Get available data range
    try:
        # Use a single day to quickly get available dates without processing all data
        temp_data = WineDashboardData(date.today(), date.today())
        available_dates = temp_data.get_available_dates()
        available_wines = temp_data.get_available_wines()
        
        if not available_dates:
            st.error("📅 No data available in Google Drive. Please check your data collection process.")
            return
        
        if not available_wines:
            st.error("🍾 No wines configured. Please check your config.yaml file.")
            return
            
    except Exception as e:
        st.error(f"❌ Error connecting to data source: {e}")
        return
    
    # Date range selection
    col1, col2 = st.columns(2)
    
    min_date = min(available_dates)
    max_date = max(available_dates)
    
    with col1:
        start_date = st.date_input(
            "📅 Start Date",
            value=max_date - timedelta(days=30),  # Default to last 30 days
            min_value=min_date,
            max_value=max_date,
            help="Select the start date for analysis"
        )
    
    with col2:
        end_date = st.date_input(
            "📅 End Date",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            help="Select the end date for analysis"
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
    
    with st.spinner("🔄 Processing wine data..."):
        try:
            # Load data
            wine_data = WineDashboardData(start_date, end_date)
            df = wine_data.get_weekly_bottle_counts()
            
            if df.empty:
                st.warning("📊 No data found for the selected date range and wines.")
                return
            
            # Filter for selected wines or get top performers
            if selection_mode == "Top performers only":
                # Get top performers by total bottles
                top_wines = df.groupby('Bottle')['Bottles Total'].sum().sort_values(ascending=False).head(num_top)
                df = df[df['Bottle'].isin(top_wines.index)]
                st.info(f"🏆 Showing top {len(top_wines)} wines by total consumption")
            else:
                df = df[df['Bottle'].isin(selected_wines)]
            
            # Display visualizations
            create_visualizations(df)
            
            # Display summary statistics
            show_summary_statistics(df)
            
        except Exception as e:
            st.error(f"❌ Error generating analysis: {e}")

def create_visualizations(df):
    """Create various visualizations for wine bottle data"""
    
    # 1. Time Series Line Chart
    st.subheader("📈 Weekly Trends")
    
    fig_line = px.line(
        df.sort_values('Week Ending Date'),
        x='Week Ending Date',
        y='Bottles Total',
        color='Bottle',
        title='Weekly Wine Bottle Consumption Trends',
        markers=True,
        hover_data={'Bottles Total': True}
    )
    
    fig_line.update_layout(
        xaxis_title="Week Ending Date",
        yaxis_title="Bottles Consumed",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig_line, use_container_width=True)
    
    # 2. Bar Chart - Total Consumption
    st.subheader("📊 Total Consumption by Wine")
    
    total_consumption = df.groupby('Bottle')['Bottles Total'].sum().sort_values(ascending=True)
    
    fig_bar = px.bar(
        x=total_consumption.values,
        y=total_consumption.index,
        orientation='h',
        title='Total Wine Bottle Consumption',
        labels={'x': 'Total Bottles', 'y': 'Wine'},
        color=total_consumption.values,
        color_continuous_scale='Blues'
    )
    
    fig_bar.update_layout(
        height=max(400, len(total_consumption) * 30),
        showlegend=False
    )
    
    st.plotly_chart(fig_bar, use_container_width=True)
    
    # 3. Weekly Comparison Bar Chart
    st.subheader("📅 Weekly Comparison")
    
    fig_weekly = px.bar(
        df.sort_values('Week Ending Date'),
        x='Week Ending Date',
        y='Bottles Total',
        color='Bottle',
        title='Weekly Wine Consumption Comparison',
        barmode='group'
    )
    
    fig_weekly.update_layout(
        xaxis_title="Week Ending Date",
        yaxis_title="Bottles Consumed",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig_weekly, use_container_width=True)
    
    # 4. Heatmap (if multiple weeks)
    weeks = df['Week Ending Date'].nunique()
    if weeks > 1:
        st.subheader("🔥 Performance Heatmap")
        
        pivot_df = df.pivot(index='Bottle', columns='Week Ending Date', values='Bottles Total')
        
        fig_heatmap = px.imshow(
            pivot_df,
            title='Wine Performance Heatmap',
            labels={'x': 'Week Ending Date', 'y': 'Wine', 'color': 'Bottles'},
            color_continuous_scale='RdYlBu_r',
            aspect='auto'
        )
        
        st.plotly_chart(fig_heatmap, use_container_width=True)

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
        st.markdown("**Top 5 Wines by Total Consumption:**")
        for i, (wine, total) in enumerate(top_wines.head().items(), 1):
            st.write(f"{i}. **{wine}**: {total} bottles")
    
    with col2:
        # Average weekly performance
        avg_weekly_performance = df.groupby('Bottle')['Bottles Total'].mean().sort_values(ascending=False)
        st.markdown("**Top 5 Wines by Average Weekly Consumption:**")
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
        file_name=f"wine_consumption_{df['Week Ending Date'].min()}_{df['Week Ending Date'].max()}.csv",
        mime="text/csv"
    )

if __name__ == "__main__":
    # For testing
    wine_bottle_visualization()
