"""
Inventory Utility Functions

This module provides utility functions for inventory management operations:
- Validation functions
- Calculation helpers
- Data transformation utilities
- Business logic helpers
"""

from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime, date as Date, timedelta
from dataclasses import asdict
import pandas as pd
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.inventory_data import (
    InventoryDataManager, InventoryItem, Transaction, 
    InventoryCategory, Supplier
)
from utils.logging_config import app_logger, log_function_errors, handle_decorator_errors


@log_function_errors("inventory", "validation")
def validate_inventory_item(item: InventoryItem) -> List[str]:
    """Validate inventory item data and return list of errors"""
    
    errors = []
    
    # Required fields
    if not item.name or not item.name.strip():
        errors.append("Item name is required")
    
    if not item.category or not item.category.strip():
        errors.append("Category is required")
    
    if not item.unit or not item.unit.strip():
        errors.append("Unit is required")
    
    # Numeric validations
    if item.par_level <= 0:
        errors.append("Par level must be greater than 0")
    
    if item.reorder_point < 0:
        errors.append("Reorder point cannot be negative")
    
    if item.reorder_point >= item.par_level:
        errors.append("Reorder point should be less than par level")
    
    if item.cost_per_unit < 0:
        errors.append("Cost per unit cannot be negative")
    
    # String length validations
    if len(item.name) > 100:
        errors.append("Item name must be 100 characters or less")
    
    if item.notes and len(item.notes) > 500:
        errors.append("Notes must be 500 characters or less")
    
    return errors


@log_function_errors("inventory", "transaction_validation")
def validate_transaction(transaction: Transaction, 
                        current_levels: Optional[Dict[str, float]] = None) -> List[str]:
    """Validate transaction data and return list of errors"""
    
    errors = []
    
    # Required fields
    if not transaction.item_id:
        errors.append("Item ID is required")
    
    if not transaction.transaction_type:
        errors.append("Transaction type is required")
    
    if transaction.transaction_type not in ["delivery", "usage", "waste", "adjustment"]:
        errors.append(f"Invalid transaction type: {transaction.transaction_type}")
    
    if transaction.quantity == 0:
        errors.append("Quantity cannot be zero")
    
    # Quantity validations based on type
    if transaction.transaction_type in ["delivery", "usage", "waste"] and transaction.quantity < 0:
        errors.append(f"{transaction.transaction_type} quantity must be positive")
    
    # Check for negative inventory (if current levels provided)
    if current_levels and transaction.item_id in current_levels:
        current_level = current_levels[transaction.item_id]
        
        if transaction.transaction_type in ["usage", "waste"]:
            if transaction.quantity > current_level:
                errors.append(f"Transaction would result in negative inventory ({current_level - transaction.quantity:.1f})")
    
    # Cost validations
    if transaction.unit_cost is not None and transaction.unit_cost < 0:
        errors.append("Unit cost cannot be negative")
    
    if transaction.transaction_type == "delivery" and transaction.unit_cost is None:
        errors.append("Unit cost is recommended for delivery transactions")
    
    return errors


@log_function_errors("inventory", "low_stock_analysis")
def analyze_low_stock_items(data_manager: InventoryDataManager) -> Dict[str, List[InventoryItem]]:
    """Analyze and categorize low stock items"""
    
    items = data_manager.load_items()
    current_levels = data_manager.calculate_current_levels(items)
    
    analysis = {
        "out_of_stock": [],
        "low_stock": [],
        "reorder_needed": [],
        "overstocked": []
    }
    
    for item_id, item in items.items():
        current_level = current_levels.get(item_id, 0)
        
        if current_level == 0:
            analysis["out_of_stock"].append(item)
        elif current_level < item.reorder_point:
            analysis["low_stock"].append(item)
            analysis["reorder_needed"].append(item)
        elif current_level > item.par_level * 1.5:  # 50% over par level
            analysis["overstocked"].append(item)
    
    app_logger.log_info("Low stock analysis completed", {
        "app_module": "inventory",
        "action": "low_stock_analysis",
        "out_of_stock": len(analysis["out_of_stock"]),
        "low_stock": len(analysis["low_stock"]),
        "overstocked": len(analysis["overstocked"])
    })
    
    return analysis


@log_function_errors("inventory", "usage_calculation")
def calculate_usage_statistics(data_manager: InventoryDataManager, 
                              days: int = 30) -> Dict[str, Dict]:
    """Calculate usage statistics for inventory items"""
    
    end_date = Date.today()
    start_date = end_date - timedelta(days=days)
    
    items = data_manager.load_items()
    usage_stats = {}
    
    for item_id, item in items.items():
        transactions = data_manager.load_transactions(
            item_id=item_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate usage (consumption + waste)
        total_usage = sum(t.quantity for t in transactions 
                         if t.transaction_type in ["usage", "waste"])
        
        total_waste = sum(t.quantity for t in transactions 
                         if t.transaction_type == "waste")
        
        total_deliveries = sum(t.quantity for t in transactions 
                              if t.transaction_type == "delivery")
        
        # Calculate averages
        avg_daily_usage = total_usage / days if days > 0 else 0
        avg_weekly_usage = avg_daily_usage * 7
        
        # Calculate waste percentage
        waste_percentage = (total_waste / total_usage * 100) if total_usage > 0 else 0
        
        # Calculate velocity (how many days of inventory at current usage rate)
        current_levels = data_manager.calculate_current_levels({item_id: item})
        current_level = current_levels.get(item_id, 0)
        
        days_of_inventory = (current_level / avg_daily_usage) if avg_daily_usage > 0 else float('inf')
        
        usage_stats[item_id] = {
            "item_name": item.name,
            "total_usage": total_usage,
            "total_waste": total_waste,
            "total_deliveries": total_deliveries,
            "avg_daily_usage": avg_daily_usage,
            "avg_weekly_usage": avg_weekly_usage,
            "waste_percentage": waste_percentage,
            "days_of_inventory": days_of_inventory,
            "current_level": current_level,
            "reorder_point": item.reorder_point,
            "par_level": item.par_level
        }
    
    return usage_stats


@log_function_errors("inventory", "value_calculation")
def calculate_inventory_value(data_manager: InventoryDataManager) -> Dict[str, float]:
    """Calculate total inventory value by category and overall"""
    
    items = data_manager.load_items()
    current_levels = data_manager.calculate_current_levels(items)
    
    values = {
        "total": 0.0,
        "by_category": {}
    }
    
    for item_id, item in items.items():
        current_level = current_levels.get(item_id, 0)
        item_value = current_level * item.cost_per_unit
        
        values["total"] += item_value
        
        if item.category not in values["by_category"]:
            values["by_category"][item.category] = 0.0
        
        values["by_category"][item.category] += item_value
    
    return values


@log_function_errors("inventory", "export_data")
def export_inventory_data(data_manager: InventoryDataManager, 
                         format_type: str = "csv") -> str:
    """Export inventory data in specified format"""
    
    items = data_manager.load_items()
    current_levels = data_manager.calculate_current_levels(items)
    
    # Prepare export data
    export_data = []
    for item_id, item in items.items():
        current_level = current_levels.get(item_id, 0)
        
        export_data.append({
            "Item ID": item_id,
            "Item Name": item.name,
            "Category": item.category,
            "Current Level": current_level,
            "Unit": item.unit,
            "Reorder Point": item.reorder_point,
            "Par Level": item.par_level,
            "Cost Per Unit": item.cost_per_unit,
            "Current Value": current_level * item.cost_per_unit,
            "Location": item.location,
            "Supplier ID": item.supplier_id,
            "Notes": item.notes or "",
            "Created": item.created_at.strftime("%Y-%m-%d %H:%M"),
            "Updated": item.updated_at.strftime("%Y-%m-%d %H:%M")
        })
    
    df = pd.DataFrame(export_data)
    
    if format_type.lower() == "csv":
        return df.to_csv(index=False)
    elif format_type.lower() == "json":
        return df.to_json(orient="records", indent=2)
    else:
        raise ValueError(f"Unsupported format: {format_type}")


@log_function_errors("inventory", "transaction_export")
def export_transaction_history(data_manager: InventoryDataManager,
                              start_date: Optional[Date] = None,
                              end_date: Optional[Date] = None,
                              format_type: str = "csv") -> str:
    """Export transaction history in specified format"""
    
    transactions = data_manager.load_transactions(
        start_date=start_date,
        end_date=end_date
    )
    
    items = data_manager.load_items()
    
    # Prepare export data
    export_data = []
    for transaction in transactions:
        item_name = items.get(transaction.item_id, {}).name if transaction.item_id in items else "Unknown"
        
        export_data.append({
            "Transaction ID": transaction.transaction_id,
            "Date": transaction.timestamp.strftime("%Y-%m-%d"),
            "Time": transaction.timestamp.strftime("%H:%M:%S"),
            "Item ID": transaction.item_id,
            "Item Name": item_name,
            "Transaction Type": transaction.transaction_type,
            "Quantity": transaction.quantity,
            "Unit Cost": transaction.unit_cost or "",
            "Total Value": (transaction.quantity * transaction.unit_cost) if transaction.unit_cost else "",
            "User": transaction.user,
            "Source": transaction.source or "",
            "Notes": transaction.notes or ""
        })
    
    df = pd.DataFrame(export_data)
    
    if format_type.lower() == "csv":
        return df.to_csv(index=False)
    elif format_type.lower() == "json":
        return df.to_json(orient="records", indent=2)
    else:
        raise ValueError(f"Unsupported format: {format_type}")


@log_function_errors("inventory", "forecast_demand")
def forecast_reorder_needs(data_manager: InventoryDataManager, 
                          forecast_days: int = 30) -> List[Dict]:
    """Forecast which items will need reordering in the next X days"""
    
    usage_stats = calculate_usage_statistics(data_manager, days=30)
    reorder_forecast = []
    
    for item_id, stats in usage_stats.items():
        days_remaining = stats["days_of_inventory"]
        
        if days_remaining <= forecast_days:
            reorder_forecast.append({
                "item_id": item_id,
                "item_name": stats["item_name"],
                "current_level": stats["current_level"],
                "daily_usage": stats["avg_daily_usage"],
                "days_remaining": days_remaining,
                "reorder_point": stats["reorder_point"],
                "par_level": stats["par_level"],
                "urgency": "Critical" if days_remaining <= 3 else "High" if days_remaining <= 7 else "Medium"
            })
    
    # Sort by urgency and days remaining
    urgency_order = {"Critical": 0, "High": 1, "Medium": 2}
    reorder_forecast.sort(key=lambda x: (urgency_order[x["urgency"]], x["days_remaining"]))
    
    return reorder_forecast


@log_function_errors("inventory", "duplicate_detection")
def find_duplicate_items(data_manager: InventoryDataManager) -> List[List[InventoryItem]]:
    """Find potential duplicate items based on name similarity"""
    
    items = data_manager.load_items()
    duplicates = []
    checked = set()
    
    for item_id1, item1 in items.items():
        if item_id1 in checked:
            continue
        
        similar_items = [item1]
        
        for item_id2, item2 in items.items():
            if item_id1 != item_id2 and item_id2 not in checked:
                # Simple similarity check - could be enhanced with fuzzy matching
                if (item1.name.lower().strip() == item2.name.lower().strip() or
                    (item1.category == item2.category and 
                     abs(len(item1.name) - len(item2.name)) <= 2 and
                     item1.name.lower()[:5] == item2.name.lower()[:5])):
                    similar_items.append(item2)
                    checked.add(item_id2)
        
        if len(similar_items) > 1:
            duplicates.append(similar_items)
        
        checked.add(item_id1)
    
    return duplicates


@log_function_errors("inventory", "data_integrity_check")
def check_data_integrity(data_manager: InventoryDataManager) -> Dict[str, List[str]]:
    """Check data integrity and return any issues found"""
    
    issues = {
        "item_validation": [],
        "transaction_validation": [],
        "orphaned_transactions": [],
        "negative_inventory": [],
        "duplicate_items": []
    }
    
    # Load data
    items = data_manager.load_items()
    transactions = data_manager.load_transactions()
    current_levels = data_manager.calculate_current_levels(items)
    
    # Validate items
    for item_id, item in items.items():
        item_errors = validate_inventory_item(item)
        if item_errors:
            issues["item_validation"].extend([f"{item.name}: {error}" for error in item_errors])
    
    # Check for orphaned transactions (transactions for non-existent items)
    for transaction in transactions:
        if transaction.item_id not in items:
            issues["orphaned_transactions"].append(
                f"Transaction {transaction.transaction_id} references non-existent item {transaction.item_id}"
            )
    
    # Check for negative inventory
    for item_id, level in current_levels.items():
        if level < 0:
            item_name = items.get(item_id, {}).name if item_id in items else item_id
            issues["negative_inventory"].append(f"{item_name}: {level:.2f}")
    
    # Check for potential duplicates
    duplicates = find_duplicate_items(data_manager)
    for duplicate_group in duplicates:
        names = [item.name for item in duplicate_group]
        issues["duplicate_items"].append(f"Potential duplicates: {', '.join(names)}")
    
    return issues


def generate_inventory_summary(data_manager: InventoryDataManager) -> Dict:
    """Generate comprehensive inventory summary"""
    
    items = data_manager.load_items()
    current_levels = data_manager.calculate_current_levels(items)
    transactions = data_manager.load_transactions()
    
    # Basic counts
    total_items = len(items)
    total_transactions = len(transactions)
    
    # Stock status
    out_of_stock = sum(1 for level in current_levels.values() if level == 0)
    low_stock = sum(1 for item_id, item in items.items() 
                   if 0 < current_levels.get(item_id, 0) < item.reorder_point)
    
    # Value calculations
    total_value = sum(current_levels.get(item_id, 0) * item.cost_per_unit 
                     for item_id, item in items.items())
    
    # Category breakdown
    categories = {}
    for item in items.values():
        if item.category not in categories:
            categories[item.category] = {"count": 0, "value": 0}
        categories[item.category]["count"] += 1
        categories[item.category]["value"] += (current_levels.get(item.item_id, 0) * item.cost_per_unit)
    
    # Recent activity (last 7 days)
    recent_date = datetime.now() - timedelta(days=7)
    recent_transactions = [t for t in transactions if t.timestamp >= recent_date]
    
    return {
        "summary": {
            "total_items": total_items,
            "total_transactions": total_transactions,
            "out_of_stock": out_of_stock,
            "low_stock": low_stock,
            "total_value": total_value
        },
        "categories": categories,
        "recent_activity": {
            "transactions_last_7_days": len(recent_transactions),
            "deliveries_last_7_days": len([t for t in recent_transactions if t.transaction_type == "delivery"]),
            "usage_last_7_days": len([t for t in recent_transactions if t.transaction_type == "usage"])
        }
    }
