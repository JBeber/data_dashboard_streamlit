# Inventory Management System - Phase 1

## 📦 Overview

This is the Phase 1 implementation of the inventory management system for the VV restaurant data dashboard. It provides a foundation for tracking inventory items, logging transactions, and monitoring stock levels using JSON-based persistence.

## 🚀 Features

### Core Functionality
- **Inventory Items**: Manage restaurant inventory with categories, suppliers, and stock levels
- **Transaction Logging**: Record deliveries, usage, waste, and adjustments with full audit trail
- **Real-time Calculations**: Current inventory levels calculated from transaction history
- **Low Stock Alerts**: Automatic identification of items needing reorder
- **Data Validation**: Comprehensive validation for data integrity

### User Interface
- **Dashboard Overview**: Key metrics, alerts, and recent activity
- **Transaction Entry**: User-friendly form for logging inventory changes
- **Item Management**: Add, view, and organize inventory items
- **Categories & Suppliers**: Manage organizational data

### Technical Features
- **Type Safety**: Full typing support with dataclasses and type hints
- **Error Handling**: Integrated with existing logging infrastructure
- **JSON Persistence**: Reliable file-based storage with datetime handling
- **UUID Support**: Unique identifiers for all records
- **Data Export**: CSV and JSON export capabilities

## 📁 File Structure

```
modules/
├── inventory_data.py          # Core data models and persistence
├── inventory_management.py    # Main Streamlit interface
└── inventory_utils.py         # Utility functions and validation

data/
├── inventory_items.json       # Inventory item configurations
├── inventory_transactions.json # Transaction log
├── inventory_categories.json  # Category definitions
└── inventory_suppliers.json   # Supplier information
```

## 🏗️ Data Models

### InventoryItem
```python
@dataclass
class InventoryItem:
    item_id: str
    name: str
    category: str
    unit: str
    par_level: float
    reorder_point: float
    supplier_id: str
    cost_per_unit: float
    location: str
    notes: Optional[str] = None
```

### Transaction
```python
@dataclass
class Transaction:
    transaction_id: str
    item_id: str
    transaction_type: str  # "delivery", "usage", "waste", "adjustment"
    quantity: float
    unit_cost: Optional[float] = None
    timestamp: datetime
    user: str
    notes: Optional[str] = None
    source: Optional[str] = None
```

## 🧪 Testing

Run the test script to validate functionality:

```bash
python test_inventory.py
```

This will:
- Create sample data
- Test all core operations
- Validate error handling
- Generate usage statistics
- Test export functionality

## 🔧 Integration

The inventory system integrates seamlessly with the existing dashboard:

1. **Navigation**: Added to main app navigation
2. **Error Handling**: Uses existing `utils.logging_config`
3. **Styling**: Matches existing Streamlit interface
4. **Authentication**: Protected by existing auth system

## 📊 Usage Examples

### Adding an Item
```python
from modules.inventory_data import InventoryDataManager, InventoryItem

data_manager = InventoryDataManager()
new_item = InventoryItem(
    item_id="wine_001",
    name="Pinot Noir 2022",
    category="wine",
    unit="bottles",
    par_level=24.0,
    reorder_point=6.0,
    supplier_id="wine_distributor",
    cost_per_unit=15.50,
    location="Wine Cellar"
)

items = data_manager.load_items()
items[new_item.item_id] = new_item
data_manager.save_items(items)
```

### Logging a Transaction
```python
from modules.inventory_data import Transaction
import uuid

transaction = Transaction(
    transaction_id=str(uuid.uuid4()),
    item_id="wine_001",
    transaction_type="delivery",
    quantity=12.0,
    unit_cost=15.50,
    user="manager",
    notes="Weekly delivery"
)

data_manager.log_transaction(transaction)
```

### Checking Stock Levels
```python
current_levels = data_manager.calculate_current_levels()
for item_id, level in current_levels.items():
    print(f"Item {item_id}: {level} units")
```

## 🔮 Future Phases

### Phase 2: SQLite Integration
- Database migration for better performance
- Advanced querying capabilities
- Concurrent access support
- Backup and restore functionality

### Phase 3: Advanced Analytics
- Demand forecasting
- Waste analysis
- Cost optimization
- Performance dashboards
- Email notifications

### Phase 4: Production Deployment
- Cloud Run deployment
- PostgreSQL integration
- User management
- API endpoints

## 🐛 Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure write access to `data/` directory
2. **Import Errors**: Check Python path and module imports
3. **JSON Errors**: Validate JSON file integrity in `data/` directory
4. **Type Errors**: Ensure proper data types in form inputs

### Data Recovery

If data files become corrupted:
1. Check `data/` directory for backup files
2. Use `test_inventory.py` to recreate sample data
3. Export/import functionality for data migration

## 📞 Support

For questions or issues:
1. Check the test script output for validation
2. Review error logs in the logging system
3. Examine JSON files for data integrity
4. Verify all required dependencies are installed

---

**Phase 1 Complete** ✅  
Ready for user testing and feedback before Phase 2 development.
