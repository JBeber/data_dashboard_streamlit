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
    InventoryCategory, Supplier, InventorySnapshot
)
from modules.pos_mapping import POSMappingManager
from utils.logging_config import app_logger, log_function_errors, handle_decorator_errors

# Configure InventoryDataManager for Cloud Storage
InventoryDataManager.default_data_directory = "gs://vv-inventory-data/inventory"


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
                    with st.expander("View Out of Stock Items", expanded=False):
                        for item_id, level in current_levels.items():
                            if level == 0:
                                item = items[item_id]
                                category_name = categories.get(item.category).name if item.category in categories else item.category
                                st.write(f"• **{item.name}** ({category_name})")
            
            with alert_col2:
                if low_stock_items > 0:
                    st.warning("**Low Stock Items**")
                    with st.expander("View Low Stock Items", expanded=False):
                        for item_id, item in items.items():
                            level = current_levels.get(item_id, 0)
                            if 0 < level < item.reorder_point:
                                st.write(f"• **{item.name}**: {level:.1f} {item.unit} (reorder at {item.reorder_point})")

        # Recent activity
        st.subheader("📅 Recent Activity")
        # show_recent_transactions(data_manager, limit=10)
        show_recent_transactions(data_manager)
        
        # Quick actions
        st.subheader("⚡ Quick Actions")
        quick_col1, quick_col2, quick_col3 = st.columns(3)
        
        with quick_col1:
            if st.button("📝 Log New Transaction", type="primary"):
                st.session_state.nav_target = "📝 Log Transaction"
                st.rerun()
        
        with quick_col2:
            if st.button("📦 View Current Items"):
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

    # Handle post-submit reset before any widgets are instantiated
    if st.session_state.get("reset_txn", False):
        st.session_state["txn_qty_v2"] = 0.0
        st.session_state["txn_unit_cost"] = 0.0
        st.session_state["txn_notes"] = ""
        # Do not reset txn_type; keep user's last selection
        st.session_state["reset_txn"] = False

    # Initialize defaults once per session (before widgets are created)
    if "txn_type" not in st.session_state:
        st.session_state["txn_type"] = "usage"
    if "txn_qty_v2" not in st.session_state:
        st.session_state["txn_qty_v2"] = 0.0
    if "txn_unit_cost" not in st.session_state:
        st.session_state["txn_unit_cost"] = 0.0
    if "txn_notes" not in st.session_state:
        st.session_state["txn_notes"] = ""

    # Select item and transaction type OUTSIDE the form so dependent widgets re-render immediately
    left, right = st.columns(2)
    with left:
        item_options = {item_id: f"{item.name} ({categories.get(item.category).name if item.category in categories else item.category})"
                        for item_id, item in items.items()}
        selected_item_id = st.selectbox(
            "📦 Item",
            options=list(item_options.keys()),
            format_func=lambda x: item_options[x],
            key="txn_item",
            help="Select the inventory item for this transaction"
        )
    with right:
        transaction_type = st.selectbox(
            "📋 Transaction Type",
            options=["delivery", "usage", "waste", "adjustment"],
            format_func=lambda x: {
                "delivery": "📦 Delivery/Receipt",
                "usage": "📉 Usage/Consumption",
                "waste": "🗑️ Waste/Spoilage",
                "adjustment": "⚖️ Inventory Adjustment"
            }[x],
            key="txn_type",
            help="Choose the type of inventory transaction"
        )

    # Ensure session quantity respects bounds when switching types
    if transaction_type != "adjustment" and st.session_state.get("txn_qty_v2", 0.0) < 0:
        st.session_state["txn_qty_v2"] = 0.0
    if transaction_type == "adjustment" and st.session_state.get("txn_qty_v2", 0.0) == -999.0:
        # Avoid auto-filling to -999 by ensuring we keep 0.0 default
        st.session_state["txn_qty_v2"] = 0.0

    # Show current level for the selected item
    if selected_item_id:
        current_level = current_levels.get(selected_item_id, 0)
        selected_item = items[selected_item_id]
        st.info(f"**Current Level**: {current_level:.1f} {selected_item.unit}")

    # Now render the form inputs that depend on selection/type
    with st.form("transaction_form", clear_on_submit=True):
        st.markdown("### Transaction Details")

        col1, col2 = st.columns(2)

        with col1:
            qty_min = -999.0 if transaction_type == "adjustment" else 0.0
            quantity = st.number_input(
                "📊 Quantity",
                min_value=qty_min,
                step=0.1,
                key="txn_qty_v2",
                help="Enter the quantity (positive for increases, negative for adjustments)"
            )

        with col2:
            unit_cost_disabled = transaction_type != "delivery"
            unit_cost = st.number_input(
                "💰 Unit Cost ($)",
                min_value=0.0,
                step=0.01,
                disabled=unit_cost_disabled,
                key="txn_unit_cost",
                help="Unit cost for delivery transactions"
            )

        col3, col4 = st.columns(2)
        with col3:
            source = st.selectbox(
                "📍 Source",
                options=["manual", "delivery", "count", "pos_integration"],
                key="txn_source",
                format_func=lambda x: {
                    "manual": "🖱️ Manual Entry",
                    "delivery": "🚚 Delivery Receipt",
                    "count": "🔢 Physical Count",
                    "pos_integration": "💻 POS Integration"
                }[x],
                help="How this transaction was recorded"
            )
        with col4:
            user = st.text_input(
                "👤 User",
                value=st.session_state.get('user', 'current_user'),
                key="txn_user",
                help="Who is recording this transaction"
            )

        notes = st.text_area(
            "📝 Notes",
            key="txn_notes",
            placeholder="Optional notes about this transaction...",
            help="Any additional information about this transaction"
        )

        # Contextual warnings
        if selected_item_id and quantity > 0:
            current_level = current_levels.get(selected_item_id, 0)
            selected_item = items[selected_item_id]
            if transaction_type in ["usage", "waste"] and quantity > current_level:
                st.warning(f"⚠️ Warning: This transaction would result in negative inventory ({current_level - quantity:.1f} {selected_item.unit})")
            if transaction_type == "delivery":
                new_level = current_level + quantity
                if new_level > selected_item.par_level * 1.5:
                    st.info(f"💡 Note: This delivery would bring inventory well above par level ({new_level:.1f} vs {selected_item.par_level} {selected_item.unit})")

        submitted = st.form_submit_button("💾 Log Transaction", type="primary")

        if submitted:
            with handle_decorator_errors("Unable to log transaction. Please try again."):
                # Validate core inputs
                if not selected_item_id:
                    st.error("Please select an item")
                    return

                # Type-specific validation
                if transaction_type in ["delivery", "usage", "waste"] and quantity <= 0:
                    st.error("Please enter a positive quantity")
                    return
                if transaction_type == "adjustment" and quantity == 0:
                    st.error("Adjustment quantity cannot be zero")
                    return
                if transaction_type == "delivery" and (unit_cost is None or unit_cost <= 0):
                    st.error("Unit cost is required for delivery transactions")
                    return

                # Build transaction
                transaction = Transaction(
                    transaction_id=str(uuid.uuid4()),
                    item_id=selected_item_id,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    unit_cost=unit_cost if transaction_type == "delivery" else None,
                    timestamp=datetime.now(),
                    user=user,
                    notes=notes.strip() if notes.strip() else None,
                    source=source
                )

                # Log the transaction
                data_manager.log_transaction(transaction)

                # Update item cost if delivery
                if transaction_type == "delivery" and unit_cost and unit_cost > 0:
                    selected_item.update_cost(unit_cost)
                    items_dict = data_manager.load_items()
                    items_dict[selected_item_id] = selected_item
                    data_manager.save_items(items_dict)

                # Success + updated level
                st.success("✅ Transaction logged successfully!")
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

                # Trigger a safe reset on next run (can't set widget keys after instantiation)
                st.session_state["reset_txn"] = True
                st.rerun()


@log_function_errors("inventory", "recent_transactions")
# def show_recent_transactions(data_manager: InventoryDataManager, limit: int = 20):
def show_recent_transactions(data_manager: InventoryDataManager):
    """Display recent transactions in a formatted table"""
    
    with handle_decorator_errors("Unable to load recent transactions"):
        # Load recent transactions
        all_transactions = data_manager.load_transactions()
        # recent_transactions = sorted(all_transactions, key=lambda t: t.timestamp, reverse=True)[:limit]
        recent_transactions = sorted(all_transactions, key=lambda t: t.timestamp, reverse=True)
        
        if not recent_transactions:
            st.info("No transactions recorded yet.")
            return
        
        # Load items for name lookup
        items = data_manager.load_items()
        
        # Create display data
        display_data = []
        for transaction in recent_transactions:
            item_name = items.get(transaction.item_id, {}).name if transaction.item_id in items else transaction.item_id
            
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
    tab1, tab2 = st.tabs(["📦 Current Items", "⚙️ Configure Items"])
    
    with tab1:
        show_current_items(data_manager)
    
    with tab2:
        show_configure_items(data_manager)


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
    """Load standardized item names from POS mapping configuration"""
    try:
        from modules.pos_mapping import POSMappingManager
        
        # Initialize POS mapping manager with default config location
        pos_manager = POSMappingManager()
        
        # Track what we've already added to avoid duplicates
        added_keys = set()
        categorized_items = {}
        
        # First, process menu items that are direct inventory items
        # (i.e., don't have component relationships)
        for item_key, details in pos_manager._mappings.items():
            standardized_key = details['standardized_key']
            # Skip if this item has component relationships (it's made of other things)
            if standardized_key in pos_manager._component_relationships:
                continue
                
            menu_group = details['menu_group']
            display_name = details.get('display_name', item_key)
            
            if menu_group not in categorized_items:
                categorized_items[menu_group] = {}
            
            categorized_items[menu_group][standardized_key] = display_name
            added_keys.add(standardized_key)
        
        # Then process components, avoiding duplicates
        for comp_key, details in pos_manager._components.items():
            # Skip if we already added this as a menu item
            if comp_key in added_keys:
                continue
                
            menu_group = details['menu_group']
            display_name = details['display_name']
            
            if menu_group not in categorized_items:
                categorized_items[menu_group] = {}
            
            categorized_items[menu_group][comp_key] = display_name
        
        return categorized_items
    except Exception as e:
        app_logger.log_error("Failed to load standardized item names from POS config", e)
        return {}

@log_function_errors("inventory", "configure_items")
def show_configure_items(data_manager: InventoryDataManager):
    """Interface for configuring inventory items from POS config"""
    
    st.markdown("### Configure Inventory Items")
    st.info("Configure inventory settings for items from the POS system. Set par levels, reorder points, costs, and suppliers.")
    
    # Load necessary data
    categories = data_manager.load_categories()
    suppliers = data_manager.load_suppliers()
    standardized_names = load_standardized_item_names()
    existing_items = data_manager.load_items()
    
    # Create a mapping of standardized keys to existing items
    existing_items_map = {item.standardized_item_name: item for item in existing_items.values()}
    
    # Category filtering
    category_labels = {
        "beverages": "☕ Beverages",
        "wine_bottles": "🍷 Wine Bottles", 
        "wine_glasses": "🥂 Wine Glasses",
        "beer": "🍺 Beer",
        "spirits": "🥃 Spirits",
        "food": "🍽️ Food Items",
        "supplies": "📦 General Supplies",
        "espresso_bar": "☕ Espresso Bar",
        "flavors": "🍯 Flavors & Syrups",
        "condiments": "🧂 Condiments",
        "milk": "🥛 Milk",
        "other": "📦 Other Items"
    }
    
    selected_category = st.selectbox(
        "Filter by Category:",
        options=["All"] + list(standardized_names.keys()),
        format_func=lambda x: category_labels.get(x, x.title()) if x != "All" else "All Categories"
    )
    
    # Display items for configuration
    categories_to_show = [selected_category] if selected_category != "All" else standardized_names.keys()
    
    for category in categories_to_show:
        if category not in standardized_names:
            continue
            
        st.markdown(f"#### {category_labels.get(category, category.title())}")
        
        for key, display_name in standardized_names[category].items():
            with st.expander(f"{display_name}", expanded=False):
                # Get existing item if it exists
                existing_item = existing_items_map.get(key)
                
                with st.form(f"config_form_{key}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        custom_name = st.text_input(
                            "📦 Custom Display Name",
                            value=existing_item.name if existing_item else display_name,
                            help="Optionally provide a custom name for this item"
                        )
                        
                        # Get unit from existing item or POS config
                        default_unit = ""
                        if existing_item:
                            default_unit = existing_item.unit
                        else:
                            # Try to get unit from POS mapping manager
                            pos_manager = POSMappingManager()
                            # For menu items, find item by standardized_key
                            for menu_item in pos_manager._mappings.values():
                                if menu_item.get('standardized_key') == key:
                                    default_unit = menu_item.get('base_unit', '')
                                    break
                            # If not found in menu items, check components
                            if not default_unit and key in pos_manager._components:
                                default_unit = pos_manager._components[key].get('base_unit', '')
                        
                        unit = st.text_input(
                            "📏 Unit",
                            value=default_unit,
                            disabled=True,  # Unit comes from POS config
                            help="Unit is defined in POS configuration"
                        )
                        
                        supplier = st.selectbox(
                            "🏢 Supplier",
                            options=list(suppliers.keys()),
                            index=list(suppliers.keys()).index(existing_item.supplier_id) if existing_item and existing_item.supplier_id else 0,
                            format_func=lambda x: suppliers[x].name if x in suppliers else x
                        )
                    
                    with col2:
                        par_level = st.number_input(
                            "📊 Par Level",
                            min_value=0.0,
                            value=float(existing_item.par_level if existing_item else 20.0),
                            step=0.1
                        )
                        
                        reorder_point = st.number_input(
                            "🔔 Reorder Point",
                            min_value=0.0,
                            value=float(existing_item.reorder_point if existing_item else 5.0),
                            step=0.1
                        )
                        
                        cost_per_unit = st.number_input(
                            "💰 Cost per Unit ($)",
                            min_value=0.0,
                            value=float(existing_item.cost_per_unit if existing_item else 0.0),
                            step=0.01
                        )
                    
                    notes = st.text_area(
                        "📝 Notes",
                        value=existing_item.notes if existing_item else "",
                        placeholder="Optional notes about this item..."
                    )
                    
                    submitted = st.form_submit_button("💾 Save Configuration")
                    
                    if submitted:
                        if par_level <= 0:
                            st.error("Par level must be greater than 0")
                            continue
                        
                        if reorder_point < 0:
                            st.error("Reorder point cannot be negative")
                            continue
                        
                        if reorder_point >= par_level:
                            st.error("Reorder point should be less than par level")
                            continue
                        
                        if cost_per_unit < 0:
                            st.error("Cost per unit cannot be negative")
                            continue
                        
                        with handle_decorator_errors("Unable to save item configuration. Please try again."):
                            # Use standardized key as ID for new items to align with transactions
                            item_id = existing_item.item_id if existing_item else key
                            
                            # Create or update item
                            updated_item = InventoryItem(
                                item_id=item_id,
                                name=custom_name.strip(),
                                category=category,  # Use POS category
                                unit=unit.strip(),
                                par_level=par_level,
                                reorder_point=reorder_point,
                                supplier_id=supplier,
                                cost_per_unit=cost_per_unit,
                                standardized_item_name=key,
                                notes=notes.strip() if notes.strip() else None
                            )
                            
                            # Update items dictionary
                            existing_items[item_id] = updated_item
                            data_manager.save_items(existing_items)
                            
                            st.success(f"✅ Successfully saved configuration for '{custom_name}'!")
                            
                            app_logger.log_info("Item configuration updated", {
                                "app_module": "inventory",
                                "action": "update_item_config",
                                "item_id": item_id,
                                "standardized_name": key
                            })


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
    
    # Create tabs for different settings
    tab1, tab2, tab3 = st.tabs(["🔄 Reset Inventory", "📊 System Info", "⚙️ Configuration"])
    
    with tab1:
        st.markdown("### 🔄 Reset Inventory Counts")
        st.warning("⚠️ **Use with caution!** This will reset inventory counts for testing or initial setup.")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            reset_count = st.number_input(
                "Target count for each item", 
                min_value=0.0, 
                value=500.0, 
                step=10.0,
                help="All items will be set to this count"
            )
            
            reset_scope = st.radio(
                "Items to reset",
                ["Active items only (last 90 days)", "All items"],
                help="Active items = items with recent transactions"
            )
            
            preserve_snapshots = st.checkbox(
                "Keep existing snapshots", 
                value=False,
                help="If unchecked, removes all previous snapshots for a clean reset"
            )
            
            notes = st.text_area(
                "Reset notes (optional)",
                placeholder="e.g., Initial inventory setup, Testing reset, etc."
            )
        
        with col2:
            # Show confirmation dialog first if needed
            if st.session_state.get('confirm_reset', False):
                st.error("⚠️ **CONFIRM RESET**")
                st.markdown(f"**Target:** {reset_count} units")
                st.markdown(f"**Scope:** {reset_scope}")
                if not preserve_snapshots:
                    st.markdown("**⚠️ Will remove existing snapshots**")
                
                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("✅ Confirm Reset", type="primary", width='stretch'):
                        # Perform the actual reset
                        try:
                            items = data_manager.load_items()
                            items_to_process = items
                            
                            # Filter to active items if selected
                            if reset_scope == "Active items only (last 90 days)":
                                txs = data_manager.load_transactions()
                                active_item_ids = set()
                                cutoff_date = datetime.now().timestamp() - (90 * 24 * 60 * 60)
                                
                                for tx in txs:
                                    if hasattr(tx, 'timestamp'):
                                        tx_time = tx.timestamp
                                        item_id = tx.item_id
                                    else:
                                        tx_time = tx.get('timestamp')
                                        item_id = tx.get('item_id')
                                        
                                    if isinstance(tx_time, str):
                                        try:
                                            tx_time = datetime.fromisoformat(tx_time).timestamp()
                                        except ValueError:
                                            continue
                                    elif isinstance(tx_time, datetime):
                                        tx_time = tx_time.timestamp()
                                    else:
                                        continue
                                        
                                    if tx_time >= cutoff_date:
                                        active_item_ids.add(item_id)
                                
                                items_to_process = {k: v for k, v in items.items() if k in active_item_ids}
                            
                            # Create snapshot
                            snapshot_items = {item_id: reset_count for item_id in items_to_process.keys()}
                            
                            reset_notes = notes or f"Inventory reset to {reset_count} via Streamlit interface"
                            snapshot = InventorySnapshot(
                                date=datetime.now().date(),
                                items=snapshot_items,
                                created_at=datetime.now(),
                                created_by="streamlit_user",
                                notes=reset_notes
                            )
                            
                            # Handle existing snapshots
                            snapshots = data_manager.load_snapshots()
                            
                            if not preserve_snapshots:
                                # Clear all existing snapshots
                                snapshots = [snapshot]
                            else:
                                # Update or add current date snapshot
                                existing_idx = None
                                today = datetime.now().date()
                                for i, s in enumerate(snapshots):
                                    if hasattr(s, 'date') and s.date == today:
                                        existing_idx = i
                                        break
                                
                                if existing_idx is not None:
                                    snapshots[existing_idx] = snapshot
                                else:
                                    snapshots.append(snapshot)
                            
                            # Save snapshots
                            data_manager.save_snapshots(snapshots)
                            
                            st.success(f"✅ Successfully reset {len(snapshot_items)} items to {reset_count} units each!")
                            st.info(f"📊 Scope: {reset_scope}")
                            if not preserve_snapshots:
                                st.info("🗑️ All previous snapshots were removed")
                                
                            # Clear confirmation state
                            st.session_state.confirm_reset = False
                            st.rerun()
                            
                        except Exception as e:
                            st.error("❌ An error occurred while resetting the inventory. Please try again or contact support.")
                            app_logger.exception("Error resetting inventory")
                            st.session_state.confirm_reset = False
                with col_cancel:
                    if st.button("❌ Cancel", width='stretch'):
                        st.session_state.confirm_reset = False
                        st.rerun()
            else:
                # Show the initial reset button
                if st.button("🔄 Reset Inventory", type="primary", width='stretch'):
                    # Show confirmation dialog
                    st.session_state.confirm_reset = True
                    st.rerun()
    
    with tab2:
        st.markdown("### 📊 System Information")
        
        try:
            items = data_manager.load_items()
            transactions = data_manager.load_transactions()
            snapshots = data_manager.load_snapshots()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Items", len(items))
            with col2:
                st.metric("Total Transactions", len(transactions))
            with col3:
                st.metric("Snapshots", len(snapshots))
                
            if snapshots:
                st.markdown("#### Recent Snapshots")
                snapshot_data = []
                # Filter and sort snapshots safely
                valid_snapshots = []
                for s in snapshots:
                    if hasattr(s, 'date') and s.date:
                        valid_snapshots.append(s)
                    else:
                        # Log invalid snapshot but don't break the UI
                        app_logger.log_warning(f"Snapshot missing date attribute: {type(s)}")
                
                # Sort valid snapshots and take recent ones
                for s in sorted(valid_snapshots, key=lambda x: x.date, reverse=True)[:5]:
                    try:
                        snapshot_data.append({
                            "Date": s.date.strftime("%Y-%m-%d") if hasattr(s.date, 'strftime') else str(s.date),
                            "Items": len(s.items) if hasattr(s, 'items') and s.items else 0,
                            "Created By": getattr(s, 'created_by', 'Unknown'),
                            "Notes": (s.notes[:50] + "..." if len(s.notes) > 50 else s.notes) if hasattr(s, 'notes') and s.notes else "No notes"
                        })
                    except Exception as e:
                        app_logger.log_error(f"Error processing snapshot for display: {e}")
                        continue
                
                if snapshot_data:
                    st.dataframe(pd.DataFrame(snapshot_data), width='stretch')
                else:
                    st.info("No valid snapshots found to display")
                
        except Exception as e:
            app_logger.error("Error loading system info", exc_info=True)
            st.error("Unable to load system information. Please try again or contact support.")
    
    with tab3:
        st.markdown("### ⚙️ Configuration")
        st.info("⚙️ Advanced configuration options will be implemented in Phase 2. Coming soon!")


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
