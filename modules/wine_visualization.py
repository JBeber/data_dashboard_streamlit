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
from utils.logging_config import app_logger, log_function_errors, DecoratorError, handle_decorator_errors, handle_chart_errors


@log_function_errors("wine_analysis", "initialization")
def wine_bottle_visualization():
    """BTG wine bottle visualization widget for Streamlit dashboard"""

    st.header("🍷 BTG Wine Bottle Sales Analysis")
    st.markdown("Track weekly BTG wine bottle sales including bottles sold directly and equivalent bottles from glass sales.")
    
    # Info about data availability
    st.info("📊 **Data Availability**: Restaurant data becomes available the day after service. The latest available data is from yesterday.")
    
    # Get available data range
    available_dates = None
    available_wines = None
    
    with handle_decorator_errors("Unable to connect to data source. Please check your configuration and Google Drive connection."):
        # Use a single day to quickly get available dates without processing all data
        yesterday = date.today() - timedelta(days=1)
        temp_data = WineDashboardData(yesterday, yesterday)
        available_dates = temp_data.get_available_dates()
        available_wines = temp_data.get_available_wines()
    
    # If we couldn't get data due to connection issues, stop here
    if available_dates is None or available_wines is None:
        return
    
    # Validate data availability
    if not available_dates:
        st.error("📅 No data available in Google Drive. Please check your data collection process.")
        app_logger.log_warning("No data available in Google Drive", {
            "app_module": "wine_analysis",
            "action": "data_availability_check"
        })
        return
    
    if not available_wines:
        st.error("🍾 No wines configured. Please check your config.yaml file.")
        app_logger.log_warning("No wines configured", {
            "app_module": "wine_analysis", 
            "action": "wine_configuration_check"
        })
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

@log_function_errors("wine_analysis", "data_processing")
def generate_wine_analysis(start_date, end_date, selected_wines, selection_mode, num_top=None):
    """Generate and display wine bottle analysis"""
    
    with st.spinner("🔄 Loading wine data from Google Drive..."):
        # Load data with error handling for decorated function
        wine_data = None
        df = None
        
        with handle_decorator_errors("Unable to generate analysis. Please try again in a moment."):
            wine_data = WineDashboardData(start_date, end_date)
            df = wine_data.get_weekly_bottle_counts()
        
        # If we couldn't load data due to connection issues, stop here
        if df is None:
            return
            
        if df.empty:
            st.warning("📊 No data found for the selected date range and wines.")
            st.info("💡 This could be due to:")
            st.info("• No sales during the selected period")
            st.info("• Network connectivity issues (try refreshing)")
            st.info("• Missing data files for those dates")
            app_logger.log_warning("No data found for selected range", {
                "app_module": "wine_analysis",
                "action": "data_loading",
                "start_date": str(start_date),
                "end_date": str(end_date),
                "selected_wines_count": len(selected_wines)
            })
            return
        
        # Filter for selected wines or get top performers
        if selection_mode == "Top performers only":
            # Get top performers by total bottles
            top_wines = df.groupby('Bottle')['Bottles Total'].sum().sort_values(ascending=False).head(num_top)
            df = df[df['Bottle'].isin(top_wines.index)]
            st.info(f"🏆 Showing top {len(top_wines)} wines by total bottles sold")
            app_logger.log_info("Showing top performers", {
                "app_module": "wine_analysis",
                "action": "wine_filtering",
                "num_top": num_top,
                "wines_found": len(top_wines)
            })
        else:
            df = df[df['Bottle'].isin(selected_wines)]
            app_logger.log_info("Data filtered successfully", {
                "app_module": "wine_analysis", 
                "action": "wine_filtering",
                "selection_mode": selection_mode,
                "wines_selected": len(selected_wines),
                "data_rows": len(df)
            })
        
        # Display visualizations
        create_visualizations(df)
        
        # Display summary statistics
        with handle_decorator_errors("Unable to display summary statistics."):
            show_summary_statistics(df)

@log_function_errors("wine_analysis", "visualization")
def create_visualizations(df):
    """Create various visualizations for wine bottle data"""
    
    # 1. Time Series Line Chart (Altair)
    st.subheader("📈 Weekly Trends")
    st.info("💡 **Interactive Chart**: Click on any wine name in the legend to highlight that wine's trend line.")
    
    with handle_chart_errors("line_chart", df):
        # Prepare data for Altair
        trend_data = df.sort_values('Week Ending Date').copy()
        # Create string version of date for tooltip to avoid temporal parsing issues
        trend_data['Date_String'] = pd.to_datetime(trend_data['Week Ending Date']).dt.strftime('%Y-%m-%d')
        trend_data['Week Ending Date'] = pd.to_datetime(trend_data['Week Ending Date']).dt.strftime('%Y-%m-%d')
        
        app_logger.log_info("Creating line chart visualization", {
            "app_module": "wine_analysis",
            "chart_type": "line_chart",
            "data_points": len(trend_data),
            "unique_wines": trend_data['Bottle'].nunique()
        })
        
        # Create selection for interactive legend
        click_selection = alt.selection_point(fields=['Bottle'], bind='legend')
        
        # Create Altair line chart with interactive selection
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
                    axis=alt.Axis(
                        labelAngle=-45, 
                        labelFontSize=11, 
                        format='%m/%d',
                        tickCount='week',
                        grid=True
                    )),
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
            opacity=alt.condition(click_selection, alt.value(1.0), alt.value(0.1)),
            strokeWidth=alt.condition(click_selection, alt.value(4), alt.value(2)),
            tooltip=[
                alt.Tooltip('Date_String:N', title='Week Ending Date'),
                alt.Tooltip('Bottle:N', title='Wine'),
                alt.Tooltip('Bottles Total:Q', title='Bottles Sold')
            ]
        ).add_params(
            click_selection
        ).properties(
            title=alt.TitleParams(
                text='Weekly Wine Bottle Sales Trends - Click legend to highlight',
                fontSize=16,
                anchor='start',
                color='#2c3e50',
                fontWeight='bold'
            ),
            height=450,
            width=1200
        ).configure_axis(
            labelFontSize=11,
            titleFontSize=12,
            grid=True,
            gridColor='#f0f0f0',
            gridOpacity=0.3,
            domain=False
        ).configure_view(
            strokeWidth=0
        )
        
        st.altair_chart(line_chart, use_container_width=False)

    # 2. Bar Chart - Total Bottles by Wine (Altair)
    st.subheader("📊 Total Bottles by Wine")
    
    with handle_chart_errors("bar_chart", df, continue_on_error=True, 
                            continue_message="Continuing with remaining visualizations..."):
        total_bottles = df.groupby('Bottle')['Bottles Total'].sum().sort_values(ascending=False)
        
        # Create DataFrame for Altair
        chart_data = pd.DataFrame({
            'Wine': total_bottles.index,
            'Total Bottles': total_bottles.values
        })
        
        app_logger.log_info("Creating bar chart visualization", {
            "app_module": "wine_analysis",
            "chart_type": "bar_chart",
            "data_points": len(chart_data),
            "unique_wines": len(total_bottles)
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
    
    with handle_chart_errors("weekly_comparison", df, continue_on_error=True,
                            continue_message="Continuing with remaining content..."):
        # Prepare data for Altair
        weekly_data = df.sort_values('Week Ending Date').copy()
        weekly_data['Week Ending Date'] = pd.to_datetime(weekly_data['Week Ending Date']).dt.strftime('%Y-%m-%d')
        
        app_logger.log_info("Creating weekly comparison chart", {
            "app_module": "wine_analysis",
            "chart_type": "weekly_comparison",
            "data_points": len(weekly_data),
            "unique_weeks": weekly_data['Week Ending Date'].nunique()
        })
        
        # Create Altair grouped bar chart using facet approach
        base = alt.Chart(weekly_data).add_params(
            alt.selection_point()
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

@log_function_errors("wine_analysis", "summary_statistics")
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

def main():
    """Main entry point for the wine visualization module"""
    st.set_page_config(layout="wide")
    wine_bottle_visualization()

if __name__ == "__main__":
    # For testing
    st.set_page_config(layout="wide")
    wine_bottle_visualization()
