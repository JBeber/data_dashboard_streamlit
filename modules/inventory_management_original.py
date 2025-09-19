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
        
        # Define page options
        page_options = [
            "📊 Dashboard Overview",
            "📝 Log Transaction", 
            "⚙️ Manage Items",
            "📈 Analytics",
            "📋 Reports",
            "🔧 Settings"
        ]
        
        # Handle button navigation by directly setting the selectbox value
        if 'nav_target' in st.session_state:
            # Set the selectbox to the target page
            st.session_state.inventory_nav = st.session_state.nav_target
            # Clear the navigation target
            del st.session_state.nav_target
        
        # Initialize selectbox value if not set
        if 'inventory_nav' not in st.session_state:
            st.session_state.inventory_nav = "📊 Dashboard Overview"
        
        page = st.selectbox(
            "Choose a section:", 
            page_options, 
            key="inventory_nav"
        )
    
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
        categories = data_manager.load_categories()
        current_levels = data_manager.calculate_current_levels(items)
        
        if not items:
            st.info("👋 **Welcome to Inventory Management!**")
            st.markdown("It looks like you're just getting started. Here's what you can do:")
            st.markdown("- **Add Items**: Go to 'Manage Items' to add your first inventory items")
            st.markdown("- **Log Transactions**: Record deliveries, usage, and waste")
            st.markdown("- **View Analytics**: Track trends and performance")
            
            if st.button("🚀 Add Your First Item", type="primary"):
                st.session_state.nav_target = "⚙️ Manage Items"
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
                            category_name = categories.get(item.category).name if item.category in categories else item.category
                            st.write(f"• **{item.name}** ({category_name})")
            
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
                st.session_state.nav_target = "📝 Log Transaction"
                st.rerun()
        
        with quick_col2:
            if st.button("📦 Add New Item"):
                st.session_state.nav_target = "⚙️ Manage Items"
                st.rerun()
        
        with quick_col3:
            if st.button("📊 View Analytics"):
                st.session_state.nav_target = "📈 Analytics"
                st.rerun()


@log_function_errors("inventory", "transaction_entry")
def show_transaction_entry(data_manager: InventoryDataManager):
    """Interface for logging inventory transactions"""
    
    st.subheader("📝 Log Inventory Transaction")
    
    # Load available items
    items = data_manager.load_items()
    categories = data_manager.load_categories()
    current_levels = data_manager.calculate_current_levels(items)
    
    if not items:
        st.warning("⚠️ No inventory items found. Please add items first in the 'Manage Items' section.")
        return
    
    with st.form("transaction_form", clear_on_submit=True):
        st.markdown("### Transaction Details")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Item selection - use category name instead of ID
            item_options = {item_id: f"{item.name} ({categories.get(item.category).name if item.category in categories else item.category})" 
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
                width='stretch',
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
    categories = data_manager.load_categories()
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
            "Category": categories.get(item.category).name if item.category in categories else item.category,
            "Current": f"{current_level:.1f} {item.unit}",
            "Reorder": f"{item.reorder_point:.1f}",
            "Par": f"{item.par_level:.1f}",
            "Cost": f"${item.cost_per_unit:.2f}",
            "Status": status,
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
            width='stretch',
            hide_index=True,
            column_config={
                "Item": st.column_config.TextColumn("Item Name", width="medium"),
                "Category": st.column_config.TextColumn("Category", width="small"),
                "Current": st.column_config.TextColumn("Current Level", width="small"),
                "Reorder": st.column_config.TextColumn("Reorder Point", width="small"), 
                "Par": st.column_config.TextColumn("Par Level", width="small"),
                "Cost": st.column_config.TextColumn("Unit Cost", width="small"),
                "Status": st.column_config.TextColumn("Status", width="medium")
            }
        )
        
        st.caption(f"Showing {len(filtered_df)} of {len(df)} items")
    else:
        st.info("No items match the selected filters.")


@log_function_errors("inventory", "load_standardized_names")
def load_standardized_item_names():
    """Load standardized item names for POS mapping"""
    try:
        import json
        with open("data/standardized_item_names.json", "r") as f:
            data = json.load(f)
        
        # Flatten all categories into a single list
        all_items = {}
        for category, items in data.items():
            if category != "metadata":
                all_items.update(items)
        
        return all_items
    except Exception as e:
        app_logger.log_error("Failed to load standardized item names", e)
        return {}

@log_function_errors("inventory", "add_item_form")
def show_add_item_form(data_manager: InventoryDataManager):
    """Form for adding new inventory items"""
    
    st.markdown("### Add New Inventory Item")
    
    # Load categories and suppliers
    categories = data_manager.load_categories()
    suppliers = data_manager.load_suppliers()
    standardized_names = load_standardized_item_names()
    
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
                placeholder="e.g., bottles, cases, lbs"
            )
            
            # Add standardized name dropdown
            standardized_options = [""] + list(standardized_names.keys())
            standardized_item = st.selectbox(
                "🔗 POS Mapping (Optional)",
                options=standardized_options,
                format_func=lambda x: f"{standardized_names[x]} ({x})" if x else "No POS mapping",
                help="Select the standardized name that matches this item in POS data. This allows automatic tracking of usage from Toast POS."
            )
        
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
                    standardized_item_name=standardized_item if standardized_item else None,
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
    
    # Tabs for viewing and adding
    tab1, tab2 = st.tabs(["📋 View Existing", "➕ Add New Supplier"])
    
    with tab1:
        show_existing_categories_suppliers(data_manager)
    
    with tab2:
        show_add_supplier_form(data_manager)


@log_function_errors("inventory", "existing_categories_suppliers")
def show_existing_categories_suppliers(data_manager: InventoryDataManager):
    """Display existing categories and suppliers"""
    
    cat_col, sup_col = st.columns(2)
    
    with cat_col:
        st.markdown("#### 📂 Categories")
        categories = data_manager.load_categories()
        
        if categories:
            for category in categories.values():
                with st.expander(f"{category.name}"):
                    st.write(f"**Default Unit:** {category.default_unit}")
                    st.write(f"**Temperature Control:** {'Yes' if category.requires_temperature_control else 'No'}")
                    st.write(f"**Shelf Life:** {category.default_shelf_life_days} days")
        else:
            st.info("No categories found")
    
    with sup_col:
        st.markdown("#### 🏢 Suppliers")
        suppliers = data_manager.load_suppliers()
        
        if suppliers:
            for supplier in suppliers.values():
                with st.expander(f"{supplier.name}"):
                    if supplier.contact_email and supplier.phone:
                        # External supplier with contact info
                        st.write(f"**Type:** External Supplier")
                        st.write(f"**Email:** {supplier.contact_email}")
                        st.write(f"**Phone:** {supplier.phone}")
                        st.write(f"**Delivery Days:** {', '.join(supplier.delivery_days)}")
                    else:
                        # Internal supplier (like Main Warehouse)
                        st.write(f"**Type:** Internal Supplier")
                        st.write(f"**Delivery Days:** {', '.join(supplier.delivery_days) if supplier.delivery_days else 'N/A'}")
                    
                    if supplier.notes:
                        st.write(f"**Notes:** {supplier.notes}")
        else:
            st.info("No suppliers found")


@log_function_errors("inventory", "add_supplier_form")
def show_add_supplier_form(data_manager: InventoryDataManager):
    """Form for adding new suppliers"""
    
    st.markdown("### Add New Supplier")
    
    with st.form("add_supplier_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            supplier_name = st.text_input(
                "🏢 Supplier Name *", 
                placeholder="e.g., Wine Distributors Inc, Main Warehouse"
            )
            
            supplier_type = st.selectbox(
                "📋 Supplier Type *",
                options=["external", "internal"],
                format_func=lambda x: {
                    "external": "🚚 External Supplier (with contact info)",
                    "internal": "🏠 Internal Supplier (warehouse/in-house)"
                }[x],
                help="Choose whether this is an external supplier or internal warehouse"
            )
            
            # Delivery days (always required)
            st.markdown("**📅 Delivery Days:**")
            delivery_days = []
            days_cols = st.columns(7)
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            day_abbrev = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            
            for i, (day, abbrev) in enumerate(zip(day_names, day_abbrev)):
                with days_cols[i]:
                    if st.checkbox(abbrev, key=f"delivery_day_{i}"):
                        delivery_days.append(day)
        
        with col2:
            # Contact info (only for external suppliers)
            if supplier_type == "external":
                st.markdown("**📞 Contact Information:**")
                contact_email = st.text_input(
                    "📧 Email *", 
                    placeholder="supplier@example.com"
                )
                
                phone = st.text_input(
                    "📱 Phone *", 
                    placeholder="(555) 123-4567"
                )
            else:
                st.info("💡 Internal suppliers don't require contact information")
                contact_email = ""
                phone = ""
            
            # Notes (always optional)
            notes = st.text_area(
                "📝 Notes", 
                placeholder="Optional notes about this supplier..."
            )
        
        submitted = st.form_submit_button("➕ Add Supplier", type="primary")
        
        if submitted:
            # Validation
            if not supplier_name.strip():
                st.error("Supplier name is required")
                return
            
            # Check for duplicate supplier names
            existing_suppliers = data_manager.load_suppliers()
            if any(sup.name.lower() == supplier_name.strip().lower() for sup in existing_suppliers.values()):
                st.error("A supplier with this name already exists")
                return
            
            # Validate external supplier requirements
            if supplier_type == "external":
                if not contact_email.strip():
                    st.error("Email is required for external suppliers")
                    return
                
                if not phone.strip():
                    st.error("Phone is required for external suppliers")
                    return
                
                # Basic email validation
                if "@" not in contact_email or "." not in contact_email:
                    st.error("Please enter a valid email address")
                    return
            
            # At least one delivery day should be selected for external suppliers
            if supplier_type == "external" and not delivery_days:
                st.error("Please select at least one delivery day")
                return
            
            with handle_decorator_errors("Unable to add supplier. Please try again."):
                # Generate unique ID
                supplier_id = f"supplier_{uuid.uuid4().hex[:8]}"
                
                # Create new supplier
                new_supplier = Supplier(
                    supplier_id=supplier_id,
                    name=supplier_name.strip(),
                    contact_email=contact_email.strip() if supplier_type == "external" else "",
                    phone=phone.strip() if supplier_type == "external" else "",
                    delivery_days=delivery_days if delivery_days else [],
                    notes=notes.strip() if notes.strip() else None
                )
                
                # Load existing suppliers and add new one
                suppliers = data_manager.load_suppliers()
                suppliers[supplier_id] = new_supplier
                data_manager.save_suppliers(suppliers)
                
                st.success(f"✅ Successfully added '{supplier_name}' as {'an external' if supplier_type == 'external' else 'an internal'} supplier!")
                
                app_logger.log_info("New supplier added", {
                    "app_module": "inventory",
                    "action": "add_supplier",
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "supplier_type": supplier_type
                })
                
                st.rerun()


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


@log_function_errors("inventory", "pos_integration")
def show_pos_integration(data_manager: InventoryDataManager):
    """POS Integration interface for automated inventory tracking"""
    
    st.subheader("🤖 POS Integration")
    st.markdown("Automatically track inventory usage from Toast POS data files.")
    
    # Import here to avoid circular imports
    try:
        from modules.simplified_toast_processor import SimplifiedToastProcessor, process_daily_toast_data
    except ImportError as e:
        st.error("❌ Simplified POS Integration module not available")
        st.error(f"Error: {e}")
        return
    
    # Create tabs for different POS integration functions
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Process Daily Data", "⚙️ Mapping Configuration", "📊 Processing History", "🔍 Item Reconciliation"])
    
    with tab1:
        show_daily_processing_interface(data_manager)
    
    with tab2:
        show_mapping_configuration(data_manager)
    
    with tab3:
        show_processing_history(data_manager)
    
    with tab4:
        show_item_reconciliation(data_manager)


@log_function_errors("inventory", "daily_processing_interface")
def show_daily_processing_interface(data_manager: InventoryDataManager):
    """Interface for processing daily POS data"""
    
    st.markdown("### Process Daily Toast POS Data")
    st.info("📊 Process Toast POS data files to automatically track inventory usage for direct-mapped items.")
    
    with st.form("process_pos_data_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Date selection
            process_date = st.date_input(
                "📅 Processing Date",
                value=Date.today() - pd.Timedelta(days=1),  # Default to yesterday
                help="Select the date for POS data processing"
            )
            
            # Auto-detect file or manual upload
            auto_detect = st.checkbox(
                "🔍 Auto-detect data file",
                value=True,
                help="Automatically find POS data file for the selected date"
            )
        
        with col2:
            if not auto_detect:
                # Manual file upload
                uploaded_file = st.file_uploader(
                    "📁 Upload POS Data File",
                    type=['csv'],
                    help="Upload ItemSelectionDetails CSV file"
                )
            
            # Processing options
            st.markdown("**Processing Options:**")
            exclude_voids = st.checkbox("Exclude voided items", value=True)
            create_missing = st.checkbox("Auto-create missing inventory items", value=True)
        
        # Show preview of what would be processed
        if st.checkbox("🔍 Preview processing"):
            date_str = process_date.strftime("%Y%m%d")
            items_file = f"Test_Data/ItemSelectionDetails_{date_str}.csv"
            
            if os.path.exists(items_file):
                try:
                    preview_df = pd.read_csv(items_file)
                    if exclude_voids:
                        preview_df = preview_df[preview_df['Void?'] == False]
                    
                    st.markdown("**Preview of POS data:**")
                    st.write(f"Total items: {len(preview_df)}")
                    
                    # Show menu group breakdown
                    group_counts = preview_df.groupby('Menu Group')['Qty'].sum().sort_values(ascending=False)
                    
                    with st.expander("📊 Menu Group Summary"):
                        for group, qty in group_counts.items():
                            st.write(f"**{group}**: {qty} items")
                    
                except Exception as e:
                    st.warning(f"⚠️ Could not preview data: {e}")
            else:
                st.warning(f"⚠️ Data file not found: {items_file}")
        
        # Process button
        submitted = st.form_submit_button("🚀 Process POS Data", type="primary")
        
        if submitted:
            date_str = process_date.strftime("%Y%m%d")
            
            # Determine file path
            if auto_detect:
                items_file = f"Test_Data/ItemSelectionDetails_{date_str}.csv"
            else:
                if uploaded_file:
                    # Save uploaded file temporarily
                    temp_path = f"temp_pos_data_{date_str}.csv"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    items_file = temp_path
                else:
                    st.error("Please upload a POS data file or enable auto-detection")
                    return
            
            # Process the data
            with st.spinner("🔄 Processing POS data..."):
                try:
                    from modules.simplified_toast_processor import process_daily_toast_data
                    
                    results = process_daily_toast_data(date_str, items_file)
                    
                    if results["success"]:
                        st.success("✅ POS data processing completed successfully!")
                        
                        # Show results summary
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("Total POS Items", results["total_pos_items"])
                        
                        with col2:
                            st.metric("✅ Matched Items", len(results["matched_items"]))
                        
                        with col3:
                            st.metric("❓ Unmatched Items", len(results["unmatched_items"]))
                        
                        # Show matched items
                        if results["matched_items"]:
                            with st.expander("✅ Successfully Processed Items"):
                                matched_df = pd.DataFrame(results["matched_items"])
                                st.dataframe(matched_df, width='stretch', hide_index=True)
                        
                        # Show unmatched items
                        if results["unmatched_items"]:
                            with st.expander("❓ Unmatched Items (No Inventory Mapping)"):
                                unmatched_df = pd.DataFrame(results["unmatched_items"])
                                st.dataframe(unmatched_df, width='stretch', hide_index=True)
                                
                                st.info("💡 **Tip**: Create inventory items with matching standardized names, or add these items to your manual inventory with appropriate POS mappings.")
                    
                    else:
                        st.error(f"❌ Processing failed: {results.get('error', 'Unknown error')}")
                        
                    # Clean up temp file if used
                    if not auto_detect and os.path.exists(items_file):
                        os.remove(items_file)
                    
                except Exception as e:
                    st.error(f"❌ Error during processing: {e}")
                    app_logger.log_error("POS data processing failed", e)


@log_function_errors("inventory", "mapping_configuration")
def show_mapping_configuration(data_manager: InventoryDataManager):
    """Show simplified mapping configuration"""
    
    st.markdown("### ⚙️ POS Mapping Configuration")
    st.info("🔗 The simplified system uses standardized item names selected during inventory item creation. No complex configuration needed!")
    
    # Show available standardized names
    try:
        standardized_names = load_standardized_item_names()
        
        st.markdown("#### 📋 Available Standardized Names")
        st.markdown("These are the standardized names available when creating inventory items:")
        
        # Group by category for display
        import json
        with open("data/standardized_item_names.json", "r") as f:
            data = json.load(f)
        
        # Display in tabs by category
        categories = [cat for cat in data.keys() if cat != "metadata"]
        if categories:
            tabs = st.tabs([cat.replace("_", " ").title() for cat in categories])
            
            for i, category in enumerate(categories):
                with tabs[i]:
                    items = data[category]
                    
                    # Create a DataFrame for nice display
                    import pandas as pd
                    items_list = [
                        {"Standardized Name": key, "Display Name": value}
                        for key, value in items.items()
                    ]
                    
                    if items_list:
                        df = pd.DataFrame(items_list)
                        st.dataframe(df, width='stretch', hide_index=True)
                    else:
                        st.info(f"No items in {category.replace('_', ' ')} category yet.")
        
        # Instructions
        st.markdown("#### 💡 How to Use")
        st.markdown("""
        1. **Create Inventory Items**: Go to "Manage Items" tab
        2. **Select POS Mapping**: Choose appropriate standardized name from dropdown
        3. **Process POS Data**: Use "Process Daily Data" tab to automatically track usage
        4. **Review Results**: Check "Item Reconciliation" tab to see what's connected
        
        **Example:**
        - Item Name: "Casa Vinicola Pinot Grigio 2023" (your custom name)
        - POS Mapping: "wine_pinot_grigio_bottle" (standardized name)
        - Result: Toast POS "pinot grigio bottle" → Automatic inventory tracking ✅
        """)
        
    except Exception as e:
        st.error(f"❌ Error loading standardized names: {str(e)}")
        st.info("📁 Make sure the standardized_item_names.json file exists in the data directory.")


@log_function_errors("inventory", "processing_history")  
def show_processing_history(data_manager: InventoryDataManager):
    """Show history of POS data processing"""
    
    st.markdown("### POS Integration Processing History")
    st.info("📊 View history of automated POS data processing sessions.")
    
    # Load transactions from POS integration
    pos_transactions = data_manager.load_transactions()
    pos_transactions = [t for t in pos_transactions if t.source == "pos_integration"]
    
    if not pos_transactions:
        st.info("No POS integration transactions found yet. Process some daily data to see history here.")
        return
    
    # Group by date
    transaction_by_date = {}
    for transaction in pos_transactions:
        date_key = transaction.timestamp.date()
        if date_key not in transaction_by_date:
            transaction_by_date[date_key] = []
        transaction_by_date[date_key].append(transaction)
    
    # Display by date
    st.markdown("#### Recent Processing Sessions")
    
    for date_key in sorted(transaction_by_date.keys(), reverse=True)[:10]:  # Last 10 days
        transactions = transaction_by_date[date_key]
        
        with st.expander(f"📅 {date_key.strftime('%Y-%m-%d')} ({len(transactions)} transactions)"):
            # Summary
            total_quantity = sum(t.quantity for t in transactions)
            items_affected = len(set(t.item_id for t in transactions))
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Transactions", len(transactions))
            with col2:
                st.metric("Total Usage", f"{total_quantity:.1f}")
            with col3:
                st.metric("Items Affected", items_affected)
            
            # Transaction details
            if st.button(f"Show Details - {date_key}", key=f"details_{date_key}"):
                items = data_manager.load_items()
                
                details_data = []
                for transaction in transactions:
                    item_name = items.get(transaction.item_id, {}).name if transaction.item_id in items else transaction.item_id
                    
                    details_data.append({
                        "Item": item_name,
                        "Quantity": f"{transaction.quantity:.2f}",
                        "Time": transaction.timestamp.strftime("%H:%M"),
                        "Notes": transaction.notes[:50] + "..." if transaction.notes and len(transaction.notes) > 50 else transaction.notes or ""
                    })
                
                if details_data:
                    details_df = pd.DataFrame(details_data)
                    st.dataframe(details_df, width='stretch', hide_index=True)


def main():
    """Main entry point for inventory management"""
    # Only set page config if running standalone
    try:
        st.set_page_config(
            page_title="Inventory Management",
            page_icon="📦",
            layout="wide"
        )
    except st.errors.StreamlitAPIException:
        # Page config already set by parent app
        pass
    
    inventory_management_page()



@log_function_errors("inventory", "item_reconciliation")
def show_item_reconciliation(data_manager: InventoryDataManager):
    """Show reconciliation between manual items and POS-processed items"""
    
    st.markdown("### 🔍 Item Reconciliation Report")
    st.markdown("Compare manually entered items with items detected from Toast POS data to identify mapping gaps.")
    
    try:
        from modules.simplified_toast_processor import SimplifiedToastProcessor
        import pandas as pd
        from datetime import datetime, timedelta
        import os
        
        # Get available dates
        dates = get_available_pos_dates()
        if not dates:
            st.warning("📂 No Toast POS data files found in Test_Data directory")
            return
        
        # Date selection
        col1, col2 = st.columns(2)
        with col1:
            selected_date = st.selectbox(
                "📅 Select date to analyze:",
                dates,
                format_func=lambda x: x.strftime('%B %d, %Y (%A)'),
                help="Choose a date to compare manual inventory items with POS data"
            )
        
        with col2:
            if st.button("🔍 Generate Reconciliation Report", type="primary"):
                with st.spinner("Analyzing inventory reconciliation..."):
                    generate_reconciliation_report(data_manager, selected_date)
        
        # Show reconciliation tips
        with st.expander("💡 Understanding Reconciliation Results"):
            st.markdown("""
            **✅ Matched Items**: POS menu items successfully linked to manual inventory items
            - These items will have their usage automatically tracked when processing POS data
            - Verify the mapping accuracy and consumption ratios
            
            **❓ Unmatched POS Items**: Menu items from Toast that couldn't be matched
            - Consider creating manual inventory items for important unmatched items
            - Add custom mappings in the mapping configuration tab
            - Some items (like service charges) may intentionally not need tracking
            
            **🔧 Unused Manual Items**: Manually created inventory items not matched to POS data
            - Items may not have been sold on the selected date
            - May need mapping configuration adjustments
            - Could be items tracked manually rather than through POS data
            """)
    
    except Exception as e:
        st.error(f"❌ Error in reconciliation interface: {str(e)}")
        app_logger.log_error("Reconciliation interface error", e)

def generate_reconciliation_report(data_manager: InventoryDataManager, selected_date):
    """Generate and display the reconciliation report"""
    
    try:
        from modules.simplified_toast_processor import SimplifiedToastProcessor
        processor = SimplifiedToastProcessor()
        
        # Load manual items
        manual_items = data_manager.load_items()
        
        # Process POS data to see what items would be created/matched
        date_str = selected_date.strftime('%Y%m%d')
        
        # Get POS items for this date (without creating new inventory items)
        pos_items = get_pos_items_for_date(date_str)
        
        if not pos_items:
            st.warning(f"📂 No POS data found for {selected_date.strftime('%Y-%m-%d')}")
            return
        
        # Analysis results
        matched_items = []
        unmatched_pos_items = []
        
        # Check each POS item against manual inventory
        for pos_item in pos_items:
            menu_item = pos_item['menu_item']
            menu_group = pos_item.get('menu_group', '')
            
            # Generate standardized name
            standardized_name = processor._generate_standardized_name(menu_item, menu_group)
            
            if standardized_name:
                # Find matching inventory item
                matched_item_id = processor._find_inventory_item_by_standardized_name(
                    standardized_name, manual_items
                )
                
                if matched_item_id:
                    matched_items.append({
                        'POS Menu Item': menu_item,
                        'Menu Group': menu_group,
                        'Standardized Name': standardized_name,
                        'Matched Inventory ID': matched_item_id,
                        'Inventory Name': manual_items[matched_item_id].name,
                        'Quantity Sold': pos_item['quantity'],
                        'Category': manual_items[matched_item_id].category
                    })
                else:
                    unmatched_pos_items.append({
                        'POS Menu Item': menu_item,
                        'Menu Group': menu_group,
                        'Standardized Name': standardized_name,
                        'Quantity Sold': pos_item['quantity'],
                        'Reason': 'No inventory item with this standardized name'
                    })
            else:
                unmatched_pos_items.append({
                    'POS Menu Item': menu_item,
                    'Menu Group': menu_group,
                    'Standardized Name': 'N/A',
                    'Quantity Sold': pos_item['quantity'],
                    'Reason': 'Could not generate standardized name'
                })
        
        # Find unused manual items
        matched_ids = {item['Matched Inventory ID'] for item in matched_items}
        unused_manual_items = [
            {
                'Item ID': item_id, 
                'Item Name': item.name, 
                'Category': item.category,
                'Standardized Name': item.standardized_item_name or 'Not set',
                'Current Stock': item.current_stock,
                'Unit Type': item.unit_type
            }
            for item_id, item in manual_items.items()
            if item_id not in matched_ids and item.standardized_item_name
        ]
        
        # Display results summary
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("✅ Matched Items", len(matched_items), help="POS items successfully linked to inventory")
        
        with col2:
            st.metric("❓ Unmatched POS Items", len(unmatched_pos_items), help="POS items without inventory match")
        
        with col3:
            st.metric("🔧 Unused Manual Items", len(unused_manual_items), help="Manual inventory items not used by POS")
        
        # Detailed breakdown
        if matched_items:
            st.markdown("### ✅ Successfully Matched Items")
            st.success(f"These {len(matched_items)} POS items are properly linked to inventory items")
            matched_df = pd.DataFrame(matched_items)
            st.dataframe(matched_df, width='stretch', hide_index=True)
        
        if unmatched_pos_items:
            st.markdown("### ❓ POS Items Without Inventory Match")
            st.warning(f"Found {len(unmatched_pos_items)} POS menu items that couldn't be matched to existing inventory")
            unmatched_df = pd.DataFrame(unmatched_pos_items)
            st.dataframe(unmatched_df, width='stretch', hide_index=True)
            
            # Suggest actions
            with st.expander("📋 Recommended Actions for Unmatched Items"):
                st.markdown("""
                1. **Create Manual Inventory Items**: For important items you want to track
                2. **Add Custom Mappings**: Use the Mapping Configuration tab to link specific POS items to existing inventory
                3. **Review Necessity**: Some items (service charges, taxes) may not need inventory tracking
                4. **Check Item Names**: Verify POS menu item names match expected inventory items
                """)
        
        if unused_manual_items:
            st.markdown("### 🔧 Manual Items Not Used by POS Processing")
            st.info(f"Found {len(unused_manual_items)} manually created inventory items not being used by POS processing")
            unused_df = pd.DataFrame(unused_manual_items)
            st.dataframe(unused_df, width='stretch', hide_index=True)
            
            with st.expander("📋 Possible Reasons for Unused Items"):
                st.markdown("""
                1. **Not Sold on This Date**: Items may not have been ordered on the selected day
                2. **Mapping Configuration**: May need adjustment in custom mappings
                3. **Manual Tracking**: Items tracked manually rather than through POS data
                4. **Seasonal Items**: Items only available certain times of year
                """)
    
    except Exception as e:
        st.error(f"❌ Error generating reconciliation report: {str(e)}")
        app_logger.log_error("Error in reconciliation report generation", e)

def get_available_pos_dates():
    """Get available POS data dates from Test_Data directory"""
    from datetime import datetime
    import os
    
    dates = []
    data_dir = "Test_Data"
    
    try:
        if os.path.exists(data_dir):
            for filename in os.listdir(data_dir):
                if filename.startswith("ItemSelectionDetails_") and filename.endswith(".csv"):
                    date_str = filename.split("_")[1].split(".")[0]
                    try:
                        date_obj = datetime.strptime(date_str, "%Y%m%d")
                        dates.append(date_obj)
                    except ValueError:
                        continue
        
        return sorted(dates, reverse=True)
    except Exception:
        return []

def get_pos_items_for_date(date_str):
    """Get POS items for a specific date without processing them"""
    import pandas as pd
    import os
    
    items_file = f"Test_Data/ItemSelectionDetails_{date_str}.csv"
    
    if not os.path.exists(items_file):
        return []
    
    try:
        df = pd.read_csv(items_file)
        
        # Group by menu item and sum quantities
        grouped = df.groupby(['Item'], as_index=False).agg({
            'Qty': 'sum',
            'Menu Group': 'first'
        }).rename(columns={'Item': 'menu_item', 'Qty': 'quantity', 'Menu Group': 'menu_group'})
        
        return grouped.to_dict('records')
    
    except Exception as e:
        app_logger.log_error(f"Error reading POS data for {date_str}", e)
        return []


if __name__ == "__main__":
    main()
