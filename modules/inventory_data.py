"""
Inventory Data Models and Persistence Layer for Phase 1 Implementation

This module provides:
- Dataclass models for inventory items, transactions, and snapshots
- JSON-based persistence layer
- Type-safe data operations with comprehensive error handling
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Union, Set
from datetime import datetime, date as Date
from pathlib import Path
import json
import uuid
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logging_config import app_logger, log_function_errors, handle_decorator_errors


@dataclass(frozen=True)
class InventoryCategory:
    """Immutable inventory category configuration"""
    category_id: str
    name: str
    default_unit: str
    requires_temperature_control: bool
    default_shelf_life_days: int
    display_order: int = 0
    
    def __hash__(self):
        return hash(self.category_id)


@dataclass(frozen=True)
class Supplier:
    """Immutable supplier information"""
    supplier_id: str
    name: str
    contact_email: str
    phone: str
    delivery_days: List[str]
    notes: Optional[str] = None
    
    def __hash__(self):
        return hash(self.supplier_id)


@dataclass
class InventoryItem:
    """Mutable inventory item with configuration and current state"""
    item_id: str
    name: str
    category: str
    unit: str  # "bottles", "cases", "gallons", "lbs", etc.
    par_level: float
    reorder_point: float
    supplier_id: str
    cost_per_unit: float
    location: str
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __hash__(self):
        """Hash based on immutable item_id for use in collections"""
        return hash(self.item_id)
    
    def update_cost(self, new_cost: float):
        """Update unit cost and timestamp"""
        self.cost_per_unit = new_cost
        self.updated_at = datetime.now()
    
    def update_par_levels(self, par_level: float, reorder_point: float):
        """Update par and reorder levels"""
        self.par_level = par_level
        self.reorder_point = reorder_point
        self.updated_at = datetime.now()


@dataclass
class Transaction:
    """Inventory transaction record"""
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    item_id: str = ""
    transaction_type: str = ""  # "delivery", "usage", "waste", "adjustment"
    quantity: float = 0.0
    unit_cost: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    user: str = "system"
    notes: Optional[str] = None
    source: Optional[str] = None  # "toast_pos", "manual", "delivery", "count"
    
    def __hash__(self):
        """Hash based on immutable transaction_id"""
        return hash(self.transaction_id)
    
    def __post_init__(self):
        """Validate transaction data after initialization"""
        if not self.item_id:
            raise ValueError("item_id is required")
        if not self.transaction_type:
            raise ValueError("transaction_type is required")
        if self.transaction_type not in ["delivery", "usage", "waste", "adjustment"]:
            raise ValueError(f"Invalid transaction_type: {self.transaction_type}")


@dataclass
class InventorySnapshot:
    """Daily inventory snapshot for historical tracking"""
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    date: Date = field(default_factory=Date.today)
    items: Dict[str, float] = field(default_factory=dict)  # item_id -> current_quantity
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"
    notes: Optional[str] = None
    
    def __hash__(self):
        """Hash based on date for unique daily snapshots"""
        return hash((self.date, self.created_by))


class InventoryDataManager:
    """Manages inventory data persistence using JSON files with error handling"""
    
    def __init__(self, data_directory: str = "data"):
        self.data_dir = Path(data_directory)
        self.data_dir.mkdir(exist_ok=True)
        
        # File paths for different data types
        self.items_file = self.data_dir / "inventory_items.json"
        self.transactions_file = self.data_dir / "inventory_transactions.json"
        self.snapshots_file = self.data_dir / "inventory_snapshots.json"
        self.categories_file = self.data_dir / "inventory_categories.json"
        self.suppliers_file = self.data_dir / "inventory_suppliers.json"
        
        # Initialize with default categories if none exist
        self._ensure_default_data()
    
    @log_function_errors("inventory", "data_initialization")
    def _ensure_default_data(self):
        """Create default categories and suppliers if files don't exist"""
        
        # Default categories
        if not self.categories_file.exists():
            default_categories = [
                InventoryCategory("wine", "Wine", "bottles", True, 1825, 1),
                InventoryCategory("beer", "Beer", "cases", True, 180, 2),
                InventoryCategory("spirits", "Spirits", "bottles", False, 3650, 3),
                InventoryCategory("food", "Food Items", "lbs", True, 7, 4),
                InventoryCategory("supplies", "Supplies", "units", False, 365, 5)
            ]
            self.save_categories({cat.category_id: cat for cat in default_categories})
        
        # Default suppliers
        if not self.suppliers_file.exists():
            default_suppliers = [
                Supplier("supplier_001", "Wine Distributor", "orders@winedist.com", 
                        "(555) 123-4567", ["Tuesday", "Friday"], "Primary wine supplier"),
                Supplier("supplier_002", "Food Service Co", "orders@foodservice.com",
                        "(555) 234-5678", ["Monday", "Wednesday", "Friday"], "Food and supplies")
            ]
            self.save_suppliers({sup.supplier_id: sup for sup in default_suppliers})
    
    def _serialize_datetime(self, obj):
        """Custom JSON serializer for datetime objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Date):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def _deserialize_datetime(self, data: dict) -> dict:
        """Convert ISO datetime strings back to datetime objects"""
        datetime_fields = ['created_at', 'updated_at', 'timestamp']
        date_fields = ['date']
        
        for field in datetime_fields:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError:
                    app_logger.log_warning(f"Invalid datetime format for {field}: {data[field]}")
        
        for field in date_fields:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = Date.fromisoformat(data[field])
                except ValueError:
                    app_logger.log_warning(f"Invalid date format for {field}: {data[field]}")
        
        return data
    
    @log_function_errors("inventory", "items_load")
    def load_items(self) -> Dict[str, InventoryItem]:
        """Load inventory items from JSON file"""
        
        if not self.items_file.exists():
            app_logger.log_info("No items file found, returning empty dict", {
                "app_module": "inventory",
                "action": "items_load",
                "file_path": str(self.items_file)
            })
            return {}
        
        with handle_decorator_errors("Unable to load inventory items"):
            with open(self.items_file, 'r') as f:
                data = json.load(f)
            
            items = {}
            for item_id, item_data in data.items():
                # Convert datetime strings back to datetime objects
                item_data = self._deserialize_datetime(item_data)
                items[item_id] = InventoryItem(**item_data)
            
            app_logger.log_info("Successfully loaded inventory items", {
                "app_module": "inventory",
                "action": "items_load",
                "items_count": len(items)
            })
            
            return items
    
    @log_function_errors("inventory", "items_save")
    def save_items(self, items: Dict[str, InventoryItem]):
        """Save inventory items to JSON file"""
        
        with handle_decorator_errors("Unable to save inventory items"):
            # Convert dataclasses to dictionaries
            data = {}
            for item_id, item in items.items():
                data[item_id] = asdict(item)
            
            # Save to file with datetime serialization
            with open(self.items_file, 'w') as f:
                json.dump(data, f, indent=2, default=self._serialize_datetime)
            
            app_logger.log_info("Successfully saved inventory items", {
                "app_module": "inventory",
                "action": "items_save",
                "items_count": len(items)
            })
    
    @log_function_errors("inventory", "transaction_log")
    def log_transaction(self, transaction: Transaction):
        """Append transaction to log file"""
        
        with handle_decorator_errors("Unable to log transaction"):
            # Load existing transactions
            transactions = self.load_transactions()
            
            # Add new transaction
            transactions.append(transaction)
            
            # Save back to file
            data = [asdict(t) for t in transactions]
            with open(self.transactions_file, 'w') as f:
                json.dump(data, f, indent=2, default=self._serialize_datetime)
            
            app_logger.log_info("Successfully logged transaction", {
                "app_module": "inventory",
                "action": "transaction_log",
                "transaction_id": transaction.transaction_id,
                "item_id": transaction.item_id,
                "transaction_type": transaction.transaction_type,
                "quantity": transaction.quantity
            })
    
    @log_function_errors("inventory", "transactions_load")
    def load_transactions(self, item_id: Optional[str] = None, 
                         start_date: Optional[Date] = None,
                         end_date: Optional[Date] = None) -> List[Transaction]:
        """Load transactions with optional filtering"""
        
        if not self.transactions_file.exists():
            return []
        
        with handle_decorator_errors("Unable to load transactions"):
            with open(self.transactions_file, 'r') as f:
                data = json.load(f)
            
            transactions = []
            for t_data in data:
                # Convert datetime strings back to datetime objects
                t_data = self._deserialize_datetime(t_data)
                transaction = Transaction(**t_data)
                
                # Apply filters
                if item_id and transaction.item_id != item_id:
                    continue
                
                if start_date and transaction.timestamp.date() < start_date:
                    continue
                
                if end_date and transaction.timestamp.date() > end_date:
                    continue
                
                transactions.append(transaction)
            
            app_logger.log_info("Successfully loaded transactions", {
                "app_module": "inventory",
                "action": "transactions_load",
                "transactions_count": len(transactions),
                "item_filter": item_id,
                "date_filter": f"{start_date} to {end_date}" if start_date or end_date else None
            })
            
            return transactions
    
    @log_function_errors("inventory", "categories_load")
    def load_categories(self) -> Dict[str, InventoryCategory]:
        """Load inventory categories"""
        
        if not self.categories_file.exists():
            return {}
        
        with handle_decorator_errors("Unable to load categories"):
            with open(self.categories_file, 'r') as f:
                data = json.load(f)
            
            categories = {}
            for cat_id, cat_data in data.items():
                categories[cat_id] = InventoryCategory(**cat_data)
            
            return categories
    
    @log_function_errors("inventory", "categories_save")
    def save_categories(self, categories: Dict[str, InventoryCategory]):
        """Save inventory categories"""
        
        with handle_decorator_errors("Unable to save categories"):
            data = {cat_id: asdict(cat) for cat_id, cat in categories.items()}
            
            with open(self.categories_file, 'w') as f:
                json.dump(data, f, indent=2)
    
    @log_function_errors("inventory", "suppliers_load")
    def load_suppliers(self) -> Dict[str, Supplier]:
        """Load suppliers"""
        
        if not self.suppliers_file.exists():
            return {}
        
        with handle_decorator_errors("Unable to load suppliers"):
            with open(self.suppliers_file, 'r') as f:
                data = json.load(f)
            
            suppliers = {}
            for sup_id, sup_data in data.items():
                suppliers[sup_id] = Supplier(**sup_data)
            
            return suppliers
    
    @log_function_errors("inventory", "suppliers_save")  
    def save_suppliers(self, suppliers: Dict[str, Supplier]):
        """Save suppliers"""
        
        with handle_decorator_errors("Unable to save suppliers"):
            data = {sup_id: asdict(sup) for sup_id, sup in suppliers.items()}
            
            with open(self.suppliers_file, 'w') as f:
                json.dump(data, f, indent=2)
    
    @log_function_errors("inventory", "current_levels_calculate")
    def calculate_current_levels(self, items: Optional[Dict[str, InventoryItem]] = None) -> Dict[str, float]:
        """Calculate current inventory levels from transaction history"""
        
        if items is None:
            items = self.load_items()
        
        current_levels = {}
        
        for item_id in items.keys():
            transactions = self.load_transactions(item_id=item_id)
            
            current_quantity = 0.0
            for transaction in transactions:
                if transaction.transaction_type == "delivery":
                    current_quantity += transaction.quantity
                elif transaction.transaction_type == "adjustment":
                    current_quantity += transaction.quantity  # Can be positive or negative
                elif transaction.transaction_type in ["usage", "waste"]:
                    current_quantity -= transaction.quantity
            
            current_levels[item_id] = max(0.0, current_quantity)  # Prevent negative inventory
        
        app_logger.log_info("Calculated current inventory levels", {
            "app_module": "inventory",
            "action": "current_levels_calculate",
            "items_processed": len(current_levels)
        })
        
        return current_levels
