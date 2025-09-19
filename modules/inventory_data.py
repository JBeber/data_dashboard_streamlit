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
from utils.environment import get_data_directory
from utils.cloud_storage import CloudStorageManager


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
    standardized_item_name: Optional[str] = None  # Maps to POS processing standard names
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
    
    default_data_directory = None
    
    def __init__(self, data_directory: str = None):
        # Use class-level default if no directory provided
        if data_directory is None and self.default_data_directory is not None:
            data_directory = self.default_data_directory
        # Use environment-specific data directory if none provided
        data_dir_str = data_directory if data_directory else str(get_data_directory())
        
        # Check if we're using cloud storage
        if data_dir_str.startswith('gs://'):
            self.use_cloud = True
            bucket_name = data_dir_str.split('/')[2]
            prefix = '/'.join(data_dir_str.split('/')[3:])
            self.cloud_storage = CloudStorageManager(bucket_name)
            self.data_dir = prefix
        else:
            self.use_cloud = False
            self.data_dir = Path(data_dir_str)
            self.data_dir.mkdir(exist_ok=True, parents=True)
        
        app_logger.log_info(f"Initializing inventory data manager", {
            "app_module": "inventory",
            "action": "init",
            "data_dir": str(self.data_dir),
            "use_cloud": str(self.use_cloud),
            "data_directory_param": str(data_directory) if data_directory else "None",
            "is_docker": str(os.path.exists('/.dockerenv'))
        })
        
        # Log existence of key files
        for filename in ['inventory_items.json', 'inventory_transactions.json', 'inventory_snapshots.json']:
            file_path = self._get_file_path(filename)
            if self.use_cloud:
                exists = self.cloud_storage.file_exists(file_path)
            else:
                exists = file_path.exists()
            app_logger.log_info(f"Checking for {filename}", {
                "app_module": "inventory",
                "action": "init",
                "file": str(file_path),
                "exists": str(exists)
            })
        
        # File paths for different data types using absolute paths
        if self.use_cloud:
            self.items_file = f"{self.data_dir}/inventory_items.json"
            self.transactions_file = f"{self.data_dir}/inventory_transactions.json"
            self.snapshots_file = f"{self.data_dir}/inventory_snapshots.json"
            self.categories_file = f"{self.data_dir}/inventory_categories.json"
            self.suppliers_file = f"{self.data_dir}/inventory_suppliers.json"
        else:
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
                        "(555) 234-5678", ["Monday", "Wednesday", "Friday"], "Food and supplies"),
                Supplier("supplier_internal_001", "Main Warehouse", "", "", 
                        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], 
                        "Internal warehouse inventory")
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
        
        try:
            if self.use_cloud:
                data = self.cloud_storage.read_json(self.items_file)
            else:
                if not Path(self.items_file).exists():
                    app_logger.log_info("No items file found, returning empty dict", {
                        "app_module": "inventory",
                        "action": "items_load",
                        "file_path": str(self.items_file)
                    })
                    return {}
                with open(self.items_file, 'r') as f:
                    data = json.load(f)
        except Exception as e:
            app_logger.log_warning(f"Error loading items: {str(e)}", {
                "app_module": "inventory",
                "action": "items_load",
                "error": str(e)
            })
            return {}
            
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
            if self.use_cloud:
                self.cloud_storage.write_json(f"{self.data_dir}/inventory_items.json", data, default=self._serialize_datetime)
            else:
                with open(self.items_file, 'w') as f:
                    json.dump(data, f, indent=2, default=self._serialize_datetime)
            
            app_logger.log_info("Successfully saved inventory items", {
                "app_module": "inventory",
                "action": "items_save",
                "items_count": len(items),
                "storage": "cloud" if self.use_cloud else "local"
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
        
        if self.use_cloud:
            if not self.cloud_storage.blob_exists(self.transactions_file):
                return []
        else:
            if not Path(self.transactions_file).exists():
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

    @log_function_errors("inventory", "transactions_save_all")
    def save_transactions(self, transactions: List[Transaction]):
        """Overwrite transactions file with provided list."""
        with handle_decorator_errors("Unable to save transactions"):
            data = [asdict(t) for t in transactions]
            with open(self.transactions_file, 'w') as f:
                json.dump(data, f, indent=2, default=self._serialize_datetime)
            app_logger.log_info("Successfully saved transactions", {
                "app_module": "inventory",
                "action": "transactions_save_all",
                "transactions_count": len(transactions)
            })

    @log_function_errors("inventory", "transactions_purge_by_source_date")
    def purge_transactions_by_source_date(self, target_date: Date, source: str, types: Optional[List[str]] = None) -> int:
        """Remove transactions matching date (by timestamp.date()), source, and optional types.

        Only transactions whose source equals `source` AND whose date equals `target_date`
        AND whose transaction_type is in `types` (when provided) will be removed.

        Returns: number of transactions removed.
        """
        with handle_decorator_errors("Unable to purge transactions"):
            # Load all transactions without filtering to preserve others
            all_txns = self.load_transactions()

            # Create a timestamped backup before purging
            try:
                backup_dir = self.data_dir / "backups"
                backup_dir.mkdir(exist_ok=True, parents=True)
                backup_path = backup_dir / f"inventory_transactions.{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
                with open(backup_path, 'w') as bf:
                    json.dump([asdict(t) for t in all_txns], bf, indent=2, default=self._serialize_datetime)
                app_logger.log_info("Created transactions backup prior to purge", {
                    "app_module": "inventory",
                    "action": "transactions_backup",
                    "path": str(backup_path)
                })
            except Exception as e:
                # Do not block purge if backup fails; just log a warning
                app_logger.log_warning(f"Failed to create transactions backup: {e}")

            kept: List[Transaction] = []
            removed = 0
            for t in all_txns:
                try:
                    t_date = t.timestamp.date() if isinstance(t.timestamp, datetime) else Date.fromisoformat(str(t.timestamp))
                except Exception:
                    # If timestamp parsing fails, keep the transaction
                    kept.append(t)
                    continue

                match_source = (t.source == source)
                match_date = (t_date == target_date)
                match_type = (t.transaction_type in types) if types else True

                if match_source and match_date and match_type:
                    removed += 1
                    continue
                kept.append(t)

            # Save back
            self.save_transactions(kept)
            app_logger.log_info("Purged transactions by source/date/types", {
                "app_module": "inventory",
                "action": "transactions_purge_by_source_date",
                "source": source,
                "date": target_date.isoformat(),
                "types": types,
                "removed": removed
            })
            return removed
    
    @log_function_errors("inventory", "categories_load")
    def load_categories(self) -> Dict[str, InventoryCategory]:
        """Load inventory categories"""
        
        if self.use_cloud:
            if not self.cloud_storage.blob_exists(self.categories_file):
                return {}
        else:
            if not Path(self.categories_file).exists():
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
        
        if self.use_cloud:
            if not self.cloud_storage.blob_exists(self.suppliers_file):
                return {}
        else:
            if not Path(self.suppliers_file).exists():
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
    
    @log_function_errors("inventory", "snapshots_load")
    def load_snapshots(self) -> List[InventorySnapshot]:
        """Load inventory snapshots from JSON file"""
        
        if self.use_cloud:
            if not self.cloud_storage.blob_exists(self.snapshots_file):
                app_logger.log_info("No snapshots file found, returning empty list", {
                    "app_module": "inventory",
                    "action": "snapshots_load",
                    "file_path": str(self.snapshots_file)
                })
                return []
        else:
            if not Path(self.snapshots_file).exists():
                app_logger.log_info("No snapshots file found, returning empty list", {
                    "app_module": "inventory",
                    "action": "snapshots_load",
                    "file_path": str(self.snapshots_file)
                })
                return []
        
        with handle_decorator_errors("Unable to load inventory snapshots"):
            with open(self.snapshots_file, 'r') as f:
                data = json.load(f)
            
            snapshots = []
            for snapshot_data in data:
                # Convert datetime strings back to datetime objects
                snapshot_data = self._deserialize_datetime(snapshot_data)
                snapshots.append(InventorySnapshot(**snapshot_data))
            
            app_logger.log_info("Successfully loaded inventory snapshots", {
                "app_module": "inventory",
                "action": "snapshots_load",
                "snapshots_count": len(snapshots)
            })
            
            return snapshots
    
    @log_function_errors("inventory", "snapshots_save")
    def save_snapshots(self, snapshots: List[InventorySnapshot]):
        """Save inventory snapshots to JSON file"""
        
        with handle_decorator_errors("Unable to save inventory snapshots"):
            # Convert dataclasses to dictionaries
            data = [asdict(s) for s in snapshots]
            
            # Save to file with datetime serialization
            with open(self.snapshots_file, 'w') as f:
                json.dump(data, f, indent=2, default=self._serialize_datetime)
            
            app_logger.log_info("Successfully saved inventory snapshots", {
                "app_module": "inventory",
                "action": "snapshots_save",
                "snapshots_count": len(snapshots)
            })
    
    @log_function_errors("inventory", "get_latest_snapshot")
    def get_latest_snapshot(self) -> Optional[InventorySnapshot]:
        """Get the most recent inventory snapshot"""
        
        snapshots = self.load_snapshots()
        if not snapshots:
            return None
            
        # Sort by date descending, then by created_at descending
        latest = sorted(snapshots, key=lambda s: (s.date, s.created_at), reverse=True)[0]
        
        # Log debug information about the latest snapshot
        app_logger.log_info(
            f"Using snapshot from {latest.date} with {len(latest.items)} items. First few items: {list(latest.items.items())[:5]}",
            {
                "app_module": "inventory",
                "action": "get_latest_snapshot",
                "snapshot_date": str(latest.date),
                "items_count": len(latest.items),
                "first_few_items": list(latest.items.items())[:5]
            }
        )
        
        return latest
    
    @log_function_errors("inventory", "create_snapshot_from_current")
    def create_snapshot_from_current(self, snapshot_date: Optional[Date] = None, notes: Optional[str] = None) -> InventorySnapshot:
        """
        Create a new snapshot from current inventory levels
        
        Args:
            snapshot_date: Date for the snapshot (default: today)
            notes: Optional notes for the snapshot
            
        Returns:
            The created snapshot (already saved to storage)
        """
        
        if snapshot_date is None:
            snapshot_date = Date.today()
            
        # Calculate current levels
        items = self.load_items()
        current_levels = self.calculate_current_levels(items, snapshot_date)
        
        # Create snapshot
        snapshot = InventorySnapshot(
            date=snapshot_date,
            items=current_levels,
            created_at=datetime.now(),
            created_by="system",
            notes=notes or f"Automatically created snapshot as of {snapshot_date}"
        )
        
        # Save snapshot
        snapshots = self.load_snapshots()
        
        # Check if there's already a snapshot for this date
        existing_snapshot = None
        for s in snapshots:
            if hasattr(s, 'date') and s.date == snapshot_date:
                existing_snapshot = s
                break
        
        if existing_snapshot:
            existing_snapshot.items = current_levels
            existing_snapshot.created_at = datetime.now()
            existing_snapshot.notes = notes or f"Updated snapshot as of {snapshot_date}"
        else:
            snapshots.append(snapshot)
        
        # Save snapshots
        self.save_snapshots(snapshots)
        
        app_logger.log_info(f"Created inventory snapshot from current levels", {
            "app_module": "inventory",
            "action": "create_snapshot_from_current",
            "snapshot_date": snapshot_date.isoformat() if hasattr(snapshot_date, 'isoformat') else str(snapshot_date),
            "items_count": len(current_levels)
        })
        
        return snapshot
    
    @log_function_errors("inventory", "current_levels_calculate")
    def calculate_current_levels(self, items: Optional[Dict[str, InventoryItem]] = None,
                                reference_date: Optional[Date] = None) -> Dict[str, float]:
        """
        Calculate current inventory levels from snapshots and transaction history
        
        Args:
            items: Optional dictionary of inventory items
            reference_date: Optional date to calculate levels for (defaults to today)
        
        Returns:
            Dictionary mapping item_id to current quantity
        """
        
        if items is None:
            items = self.load_items()
            
        if reference_date is None:
            reference_date = Date.today()
            
        # First check if we have a snapshot to use as baseline
        latest_snapshot = self.get_latest_snapshot()
        
        if latest_snapshot:
            # Start with snapshot levels
            app_logger.log_info(f"Using snapshot from {latest_snapshot.date} as baseline", {
                "app_module": "inventory",
                "action": "current_levels_calculate",
                "snapshot_date": latest_snapshot.date.isoformat() if hasattr(latest_snapshot.date, 'isoformat') else str(latest_snapshot.date),
                "reference_date": reference_date.isoformat() if hasattr(reference_date, 'isoformat') else str(reference_date)
            })
            
            # Debug print
            print(f"DEBUG: calculate_current_levels using snapshot from {latest_snapshot.date}")
            app_logger.log_info(
                "First few items in snapshot",
                {
                    "app_module": "inventory",
                    "action": "current_levels_calculate",
                    "snapshot_date": latest_snapshot.date.isoformat() if hasattr(latest_snapshot.date, 'isoformat') else str(latest_snapshot.date),
                    "reference_date": reference_date.isoformat() if hasattr(reference_date, 'isoformat') else str(reference_date),
                    "first_few_items": list(latest_snapshot.items.items())[:5]
                }
            )
            
            current_levels = dict(latest_snapshot.items)
            
            # Only apply transactions after the snapshot date
            snapshot_datetime = datetime.combine(latest_snapshot.date, datetime.min.time())
            
            # Apply transactions after the snapshot date
            for item_id in items.keys():
                # Skip if item not in items we're tracking
                if item_id not in current_levels:
                    current_levels[item_id] = 0.0
                    
                # Get transactions after the snapshot
                transactions = self.load_transactions(item_id=item_id)
                
                # Filter to only transactions after the snapshot date and up to reference date
                filtered_transactions = []
                for tx in transactions:
                    tx_date = tx.timestamp.date() if isinstance(tx.timestamp, datetime) else None
                    if tx_date and tx_date > latest_snapshot.date and tx_date <= reference_date:
                        filtered_transactions.append(tx)
                
                # Apply filtered transactions
                for transaction in filtered_transactions:
                    if transaction.transaction_type == "delivery":
                        current_levels[item_id] += transaction.quantity
                    elif transaction.transaction_type == "adjustment":
                        current_levels[item_id] += transaction.quantity  # Can be positive or negative
                    elif transaction.transaction_type in ["usage", "waste"]:
                        current_levels[item_id] -= transaction.quantity
                
                # Prevent negative inventory
                current_levels[item_id] = max(0.0, current_levels[item_id])
        else:
            # No snapshot available, fall back to transaction-based calculation
            app_logger.log_info("No snapshots found, calculating from all transactions", {
                "app_module": "inventory",
                "action": "current_levels_calculate"
            })
            
            current_levels = {}
            
            for item_id in items.keys():
                # Only include transactions up to the reference date
                transactions = self.load_transactions(item_id=item_id)
                
                # Filter transactions by date
                filtered_transactions = []
                for tx in transactions:
                    tx_date = tx.timestamp.date() if isinstance(tx.timestamp, datetime) else None
                    if tx_date and tx_date <= reference_date:
                        filtered_transactions.append(tx)
                
                current_quantity = 0.0
                for transaction in filtered_transactions:
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
            "items_processed": len(current_levels),
            "reference_date": reference_date.isoformat() if hasattr(reference_date, 'isoformat') else str(reference_date)
        })
        
        return current_levels

    def _get_file_path(self, filename: str) -> Union[Path, str]:
        """
        Get the file path for a given filename, handling cloud and local paths.
        
        Args:
            filename: The name of the file to get the path for.
        
        Returns:
            The file path as a Path object (for local) or string (for cloud).
        """
        if self.use_cloud:
            # For cloud storage, use string concatenation
            return f"{self.data_dir}/{filename}"
        else:
            # For local storage, use Path concatenation
            return self.data_dir / filename
