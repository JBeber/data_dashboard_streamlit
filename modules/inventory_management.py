"""
Main Inventory Management Interface for Streamlit Dashboard

This module provides:
- Complete inventory management interface
- Transaction logging and item management
- Dashboard overview with key metrics
- Integration with existing error handling system
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date as Date, timedelta
from typing import List, Dict, Optional
import uuid
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.inventory_data import (
    InventoryDataManager, InventoryItem, Transaction, 
    InventoryCategory, Supplier
)
from utils.logging_config import app_logger, log_function_errors, handle_decorator_errors


@log_function_errors("inventory", "main_interface")
def inventory_management_page():
    """Main inventory management interface"""
    
    st.header("📦 Inventory Management System")
    st.markdown("Comprehensive inventory tracking with real-time updates and analytics.")
    
    # Initialize data manager
    data_manager = InventoryDataManager()
    
    # Sidebar navigation
    with st.sidebar:
        st.subheader("📋 Navigation")
        page = st.selectbox("Choose a section:", [
            "📊 Dashboard Overview",
            "📝 Log Transaction", 
            "⚙️ Manage Items",
            "📈 Analytics",
            "📋 Reports",
            "🔧 Settings"
        ])
    
    # Route to appropriate page
    if page == "📊 Dashboard Overview":
        show_dashboard_overview(data_manager)
    elif page == "📝 Log Transaction":
        show_transaction_entry(data_manager)
    elif page == "⚙️ Manage Items":
        show_item_management(data_manager)
    elif page == "📈 Analytics":
        show_inventory_analytics(data_manager)
    elif page == "📋 Reports":
        show_inventory_reports(data_manager)
    elif page == "🔧 Settings":
        show_settings(data_manager)


@log_function_errors("inventory", "dashboard")
def show_dashboard_overview(data_manager: InventoryDataManager):
    """Display inventory dashboard with key metrics"""
    
    st.subheader("📊 Inventory Dashboard")
    
    with handle_decorator_errors("Unable to load dashboard data"):
        # Load current data
        items = data_manager.load_items()
        current_levels = data_manager.calculate_current_levels(items)
        
        if not items:
            st.info("👋 **Welcome to Inventory Management!**")
            st.markdown("It looks like you're just getting started. Here's what you can do:")
            st.markdown("- **Add Items**: Go to 'Manage Items' to add your first inventory items")
            st.markdown("- **Log Transactions**: Record deliveries, usage, and waste")
            st.markdown("- **View Analytics**: Track trends and performance")
            
            if st.button("🚀 Add Your First Item", type="primary"):
                st.session_state.inventory_page = "⚙️ Manage Items"
                st.rerun()
            return
        
        # Calculate key metrics
        total_items = len(items)
        low_stock_items = sum(1 for item_id, item in items.items() 
                             if current_levels.get(item_id, 0) < item.reorder_point)
        zero_stock_items = sum(1 for level in current_levels.values() if level == 0)
        total_value = sum(current_levels.get(item_id, 0) * item.cost_per_unit 
                         for item_id, item in items.items())
        
        # Key metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Items", total_items)
        
        with col2:
            st.metric("Low Stock", low_stock_items, 
                     delta=-low_stock_items if low_stock_items > 0 else None,
                     delta_color="inverse")
        
        with col3:
            st.metric("Out of Stock", zero_stock_items,
                     delta=-zero_stock_items if zero_stock_items > 0 else None,
                     delta_color="inverse")
        
        with col4:
            st.metric("Total Value", f"${total_value:,.2f}")
        
        # Alerts section
        if low_stock_items > 0 or zero_stock_items > 0:
            st.subheader("🚨 Alerts")
            
            alert_col1, alert_col2 = st.columns(2)
            
            with alert_col1:
                if zero_stock_items > 0:
                    st.error("**Out of Stock Items**")
                    for item_id, level in current_levels.items():
                        if level == 0:
                            item = items[item_id]
                            st.write(f"• **{item.name}** ({item.category})")
            
            with alert_col2:
                if low_stock_items > 0:
                    st.warning("**Low Stock Items**")
                    for item_id, item in items.items():
                        level = current_levels.get(item_id, 0)
                        if 0 < level < item.reorder_point:
                            st.write(f"• **{item.name}**: {level:.1f} {item.unit} (reorder at {item.reorder_point})")
        
        # Recent activity
        st.subheader("📅 Recent Activity")
        show_recent_transactions(data_manager, limit=10)
        
        # Quick actions
        st.subheader("⚡ Quick Actions")
        quick_col1, quick_col2, quick_col3 = st.columns(3)
        
        with quick_col1:
            if st.button("📝 Log New Transaction", type="primary"):
                st.session_state.inventory_page = "📝 Log Transaction"
                st.rerun()
        
        with quick_col2:
            if st.button("📦 Add New Item"):
                st.session_state.inventory_page = "⚙️ Manage Items"
                st.rerun()
        
        with quick_col3:
            if st.button("📊 View Analytics"):
                st.session_state.inventory_page = "📈 Analytics"
                st.rerun()


@log_function_errors("inventory", "transaction_entry")
def show_transaction_entry(data_manager: InventoryDataManager):
    """Interface for logging inventory transactions"""
    
    st.subheader("📝 Log Inventory Transaction")
    
    # Load available items
    items = data_manager.load_items()
    current_levels = data_manager.calculate_current_levels(items)
    
    if not items:
        st.warning("⚠️ No inventory items found. Please add items first in the 'Manage Items' section.")
        return
    
    with st.form("transaction_form", clear_on_submit=True):
        st.markdown("### Transaction Details")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Item selection
            item_options = {item_id: f"{item.name} ({item.category})" 
                          for item_id, item in items.items()}
            selected_item_id = st.selectbox(
                "📦 Item",
                options=list(item_options.keys()),
                format_func=lambda x: item_options[x],
                help="Select the inventory item for this transaction"
            )
            
            # Show current level
            if selected_item_id:
                current_level = current_levels.get(selected_item_id, 0)
                selected_item = items[selected_item_id]
                st.info(f"**Current Level**: {current_level:.1f} {selected_item.unit}")
            
            # Transaction type
            transaction_type = st.selectbox(
                "📋 Transaction Type",
                options=["delivery", "usage", "waste", "adjustment"],
                format_func=lambda x: {
                    "delivery": "📦 Delivery/Receipt",
                    "usage": "📉 Usage/Consumption", 
                    "waste": "🗑️ Waste/Spoilage",
                    "adjustment": "⚖️ Inventory Adjustment"
                }[x],
                help="Choose the type of inventory transaction"
            )
            
            # Quantity
            quantity = st.number_input(
                "📊 Quantity",
                min_value=-999.0 if transaction_type == "adjustment" else 0.0,
                max_value=999.0,
                value=0.0,
                step=0.1,
                help="Enter the quantity (positive for increases, negative for adjustments)"
            )
        
        with col2:
            # Unit cost (for deliveries)
            unit_cost = st.number_input(
                "💰 Unit Cost ($)",
                min_value=0.0,
                value=0.0,
                step=0.01,
                disabled=transaction_type != "delivery",
                help="Unit cost for delivery transactions"
            )
            
            # Source
            source = st.selectbox(
                "📍 Source",
                options=["manual", "delivery", "count", "pos_integration"],
                format_func=lambda x: {
                    "manual": "🖱️ Manual Entry",
                    "delivery": "🚚 Delivery Receipt", 
                    "count": "🔢 Physical Count",
                    "pos_integration": "💻 POS Integration"
                }[x],
                help="How this transaction was recorded"
            )
            
            # User
            user = st.text_input(
                "👤 User",
                value=st.session_state.get('user', 'current_user'),
                help="Who is recording this transaction"
            )
            
            # Notes
            notes = st.text_area(
                "📝 Notes",
                placeholder="Optional notes about this transaction...",
                help="Any additional information about this transaction"
            )
        
        # Validation warnings
        if selected_item_id and quantity > 0:
            current_level = current_levels.get(selected_item_id, 0)
            selected_item = items[selected_item_id]
            
            if transaction_type in ["usage", "waste"] and quantity > current_level:
                st.warning(f"⚠️ Warning: This transaction would result in negative inventory ({current_level - quantity:.1f} {selected_item.unit})")
            
            if transaction_type == "delivery":
                new_level = current_level + quantity
                if new_level > selected_item.par_level * 1.5:
                    st.info(f"💡 Note: This delivery would bring inventory well above par level ({new_level:.1f} vs {selected_item.par_level} {selected_item.unit})")
        
        # Submit button
        submitted = st.form_submit_button("💾 Log Transaction", type="primary")
        
        if submitted:
            with handle_decorator_errors("Unable to log transaction. Please try again."):
                # Validate inputs
                if not selected_item_id:
                    st.error("Please select an item")
                    return
                
                if quantity <= 0:
                    st.error("Please enter a positive quantity")
                    return
                
                # Create transaction
                transaction = Transaction(
                    transaction_id=str(uuid.uuid4()),
                    item_id=selected_item_id,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    unit_cost=unit_cost if transaction_type == "delivery" and unit_cost > 0 else None,
                    timestamp=datetime.now(),
                    user=user,
                    notes=notes.strip() if notes.strip() else None,
                    source=source
                )
                
                # Log the transaction
                data_manager.log_transaction(transaction)
                
                # Update item cost if this is a delivery with cost
                if transaction_type == "delivery" and unit_cost > 0:
                    selected_item.update_cost(unit_cost)
                    items_dict = data_manager.load_items()
                    items_dict[selected_item_id] = selected_item
                    data_manager.save_items(items_dict)
                
                # Success message
                st.success("✅ Transaction logged successfully!")
                
                # Show updated level
                new_levels = data_manager.calculate_current_levels()
                new_level = new_levels.get(selected_item_id, 0)
                st.info(f"📊 **Updated Level**: {new_level:.1f} {selected_item.unit}")
                
                app_logger.log_info("Transaction logged via UI", {
                    "app_module": "inventory",
                    "action": "transaction_entry_ui",
                    "transaction_id": transaction.transaction_id,
                    "item_id": selected_item_id,
                    "transaction_type": transaction_type,
                    "quantity": quantity,
                    "user": user
                })
                
                # Auto-refresh after short delay
                st.rerun()


@log_function_errors("inventory", "recent_transactions")
def show_recent_transactions(data_manager: InventoryDataManager, limit: int = 20):
    """Display recent transactions in a formatted table"""
    
    with handle_decorator_errors("Unable to load recent transactions"):
        # Load recent transactions
        all_transactions = data_manager.load_transactions()
        recent_transactions = sorted(all_transactions, key=lambda t: t.timestamp, reverse=True)[:limit]
        
        if not recent_transactions:
            st.info("No transactions recorded yet.")
            return
        
        # Load items for name lookup
        items = data_manager.load_items()
        
        # Create display data
        display_data = []
        for transaction in recent_transactions:
            item_name = items.get(transaction.item_id, {}).name if transaction.item_id in items else "Unknown Item"
            
            display_data.append({
                "Time": transaction.timestamp.strftime("%m/%d %H:%M"),
                "Item": item_name,
                "Type": transaction.transaction_type.title(),
                "Quantity": f"{transaction.quantity:g}",
                "User": transaction.user,
                "Notes": transaction.notes[:30] + "..." if transaction.notes and len(transaction.notes) > 30 else transaction.notes or ""
            })
        
        # Display as dataframe
        if display_data:
            df = pd.DataFrame(display_data)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Time": st.column_config.TextColumn("Time", width="small"),
                    "Item": st.column_config.TextColumn("Item", width="medium"),
                    "Type": st.column_config.TextColumn("Type", width="small"),
                    "Quantity": st.column_config.TextColumn("Qty", width="small"),
                    "User": st.column_config.TextColumn("User", width="small"),
                    "Notes": st.column_config.TextColumn("Notes", width="medium")
                }
            )


@log_function_errors("inventory", "item_management")
def show_item_management(data_manager: InventoryDataManager):
    """Interface for managing inventory items"""
    
    st.subheader("⚙️ Manage Inventory Items")
    
    # Tabs for different item management functions
    tab1, tab2, tab3 = st.tabs(["📦 Current Items", "➕ Add New Item", "📂 Categories & Suppliers"])
    
    with tab1:
        show_current_items(data_manager)
    
    with tab2:
        show_add_item_form(data_manager)
    
    with tab3:
        show_categories_suppliers(data_manager)


@log_function_errors("inventory", "current_items")
def show_current_items(data_manager: InventoryDataManager):
    """Display and manage current inventory items"""
    
    items = data_manager.load_items()
    current_levels = data_manager.calculate_current_levels(items)
    
    if not items:
        st.info("📦 No inventory items found. Add your first item using the 'Add New Item' tab.")
        return
    
    st.markdown("### Current Inventory Items")
    
    # Create display dataframe
    display_data = []
    for item_id, item in items.items():
        current_level = current_levels.get(item_id, 0)
        status = "🔴 Out of Stock" if current_level == 0 else "🟡 Low Stock" if current_level < item.reorder_point else "🟢 In Stock"
        
        display_data.append({
            "Item": item.name,
            "Category": item.category,
            "Current": f"{current_level:.1f} {item.unit}",
            "Reorder": f"{item.reorder_point:.1f}",
            "Par": f"{item.par_level:.1f}",
            "Cost": f"${item.cost_per_unit:.2f}",
            "Status": status,
            "Location": item.location,
            "ID": item_id  # Hidden column for actions
        })
    
    df = pd.DataFrame(display_data)
    
    # Display with filtering
    col1, col2 = st.columns([3, 1])
    
    with col1:
        category_filter = st.selectbox(
            "Filter by Category:",
            options=["All"] + sorted(df["Category"].unique().tolist()),
            key="item_category_filter"
        )
    
    with col2:
        status_filter = st.selectbox(
            "Filter by Status:",
            options=["All", "🔴 Out of Stock", "🟡 Low Stock", "🟢 In Stock"],
            key="item_status_filter"
        )
    
    # Apply filters
    filtered_df = df.copy()
    if category_filter != "All":
        filtered_df = filtered_df[filtered_df["Category"] == category_filter]
    if status_filter != "All":
        filtered_df = filtered_df[filtered_df["Status"] == status_filter]
    
    # Display filtered results
    if not filtered_df.empty:
        st.dataframe(
            filtered_df.drop("ID", axis=1),  # Hide ID column
            use_container_width=True,
            hide_index=True,
            column_config={
                "Item": st.column_config.TextColumn("Item Name", width="medium"),
                "Category": st.column_config.TextColumn("Category", width="small"),
                "Current": st.column_config.TextColumn("Current Level", width="small"),
                "Reorder": st.column_config.TextColumn("Reorder Point", width="small"), 
                "Par": st.column_config.TextColumn("Par Level", width="small"),
                "Cost": st.column_config.TextColumn("Unit Cost", width="small"),
                "Status": st.column_config.TextColumn("Status", width="medium"),
                "Location": st.column_config.TextColumn("Location", width="medium")
            }
        )
        
        st.caption(f"Showing {len(filtered_df)} of {len(df)} items")
    else:
        st.info("No items match the selected filters.")


@log_function_errors("inventory", "add_item_form")
def show_add_item_form(data_manager: InventoryDataManager):
    """Form for adding new inventory items"""
    
    st.markdown("### Add New Inventory Item")
    
    # Load categories and suppliers
    categories = data_manager.load_categories()
    suppliers = data_manager.load_suppliers()
    
    with st.form("add_item_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            item_name = st.text_input("📦 Item Name *", placeholder="e.g., Pinot Noir 2022")
            
            category = st.selectbox(
                "📂 Category *",
                options=list(categories.keys()),
                format_func=lambda x: categories[x].name if x in categories else x
            )
            
            unit = st.text_input(
                "📏 Unit *", 
                value=categories[category].default_unit if category and category in categories else "units",
                placeholder="e.g., bottles, cases, lbs"
            )
            
            location = st.text_input("📍 Location", placeholder="e.g., Wine Cellar, Dry Storage")
        
        with col2:
            par_level = st.number_input("📊 Par Level *", min_value=0.0, value=20.0, step=0.1)
            
            reorder_point = st.number_input("🔔 Reorder Point *", min_value=0.0, value=5.0, step=0.1)
            
            cost_per_unit = st.number_input("💰 Cost per Unit ($) *", min_value=0.0, value=0.0, step=0.01)
            
            supplier = st.selectbox(
                "🏢 Supplier",
                options=list(suppliers.keys()),
                format_func=lambda x: suppliers[x].name if x in suppliers else x
            )
        
        notes = st.text_area("📝 Notes", placeholder="Optional notes about this item...")
        
        submitted = st.form_submit_button("➕ Add Item", type="primary")
        
        if submitted:
            # Validation
            if not item_name.strip():
                st.error("Item name is required")
                return
            
            if not unit.strip():
                st.error("Unit is required")
                return
            
            if par_level <= 0:
                st.error("Par level must be greater than 0")
                return
            
            if reorder_point < 0:
                st.error("Reorder point cannot be negative")
                return
            
            if reorder_point >= par_level:
                st.error("Reorder point should be less than par level")
                return
            
            if cost_per_unit < 0:
                st.error("Cost per unit cannot be negative")
                return
            
            with handle_decorator_errors("Unable to add item. Please try again."):
                # Generate unique ID
                item_id = f"item_{uuid.uuid4().hex[:8]}"
                
                # Create new item
                new_item = InventoryItem(
                    item_id=item_id,
                    name=item_name.strip(),
                    category=category,
                    unit=unit.strip(),
                    par_level=par_level,
                    reorder_point=reorder_point,
                    supplier_id=supplier,
                    cost_per_unit=cost_per_unit,
                    location=location.strip(),
                    notes=notes.strip() if notes.strip() else None
                )
                
                # Load existing items and add new one
                items = data_manager.load_items()
                items[item_id] = new_item
                data_manager.save_items(items)
                
                st.success(f"✅ Successfully added '{item_name}' to inventory!")
                
                app_logger.log_info("New inventory item added", {
                    "app_module": "inventory",
                    "action": "add_item",
                    "item_id": item_id,
                    "item_name": item_name,
                    "category": category
                })
                
                st.rerun()


@log_function_errors("inventory", "categories_suppliers")
def show_categories_suppliers(data_manager: InventoryDataManager):
    """Manage categories and suppliers"""
    
    st.markdown("### Categories & Suppliers")
    
    cat_col, sup_col = st.columns(2)
    
    with cat_col:
        st.markdown("#### 📂 Categories")
        categories = data_manager.load_categories()
        
        if categories:
            for cat_id, category in categories.items():
                with st.expander(f"{category.name} ({cat_id})"):
                    st.write(f"**Default Unit:** {category.default_unit}")
                    st.write(f"**Temperature Control:** {'Yes' if category.requires_temperature_control else 'No'}")
                    st.write(f"**Shelf Life:** {category.default_shelf_life_days} days")
        else:
            st.info("No categories found")
    
    with sup_col:
        st.markdown("#### 🏢 Suppliers")
        suppliers = data_manager.load_suppliers()
        
        if suppliers:
            for sup_id, supplier in suppliers.items():
                with st.expander(f"{supplier.name} ({sup_id})"):
                    st.write(f"**Email:** {supplier.contact_email}")
                    st.write(f"**Phone:** {supplier.phone}")
                    st.write(f"**Delivery Days:** {', '.join(supplier.delivery_days)}")
                    if supplier.notes:
                        st.write(f"**Notes:** {supplier.notes}")
        else:
            st.info("No suppliers found")


@log_function_errors("inventory", "analytics")
def show_inventory_analytics(data_manager: InventoryDataManager):
    """Display inventory analytics and insights"""
    
    st.subheader("📈 Inventory Analytics")
    st.info("📊 Advanced analytics features will be implemented in Phase 3. Coming soon!")
    
    # Basic analytics for now
    items = data_manager.load_items()
    current_levels = data_manager.calculate_current_levels(items)
    
    if items:
        # Simple category breakdown
        category_counts = {}
        for item in items.values():
            category_counts[item.category] = category_counts.get(item.category, 0) + 1
        
        st.markdown("### Category Breakdown")
        for category, count in category_counts.items():
            st.write(f"**{category}**: {count} items")


@log_function_errors("inventory", "reports")
def show_inventory_reports(data_manager: InventoryDataManager):
    """Generate and display inventory reports"""
    
    st.subheader("📋 Inventory Reports")
    st.info("📄 Advanced reporting features will be implemented in Phase 3. Coming soon!")


@log_function_errors("inventory", "settings")
def show_settings(data_manager: InventoryDataManager):
    """Inventory system settings and configuration"""
    
    st.subheader("🔧 Settings")
    st.info("⚙️ Settings and configuration options will be implemented in Phase 2. Coming soon!")


def main():
    """Main entry point for inventory management"""
    st.set_page_config(
        page_title="Inventory Management",
        page_icon="📦",
        layout="wide"
    )
    inventory_management_page()


if __name__ == "__main__":
    main()
