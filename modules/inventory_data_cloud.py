"""
Inventory Data Models and Persistence Layer with Cloud Storage Support

This module provides:
- Dataclass models for inventory items, transactions, and snapshots
- Cloud Storage-based persistence layer with local fallback
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

# Re-export the dataclass models (they don't change)
from .inventory_data import (
    InventoryCategory,
    Supplier,
    InventoryItem,
    Transaction,
    InventorySnapshot
)

class CloudInventoryDataManager:
    """Manages inventory data persistence using Cloud Storage with local fallback"""
    
    def __init__(self, data_directory: str = None, bucket_name: str = "vv-inventory-data"):
        """Initialize the data manager with Cloud Storage support
        
        Args:
            data_directory: Optional local directory for data storage
            bucket_name: Name of the Cloud Storage bucket to use
        """
        try:
            self.storage = CloudStorageManager(bucket_name)
            self.use_cloud = True
            app_logger.log_info("Successfully initialized Cloud Storage", {
                "app_module": "inventory",
                "action": "init",
                "storage": "cloud",
                "bucket": bucket_name
            })
        except Exception as e:
            app_logger.log_warning(f"Failed to initialize Cloud Storage, falling back to local: {e}", {
                "app_module": "inventory",
                "action": "init",
                "storage": "local"
            })
            self.use_cloud = False
            
        # Set up local paths as fallback
        self.data_dir = Path(data_directory) if data_directory else get_data_directory()
        self.data_dir.mkdir(exist_ok=True, parents=True)
        
        # Define file paths/names (same for both cloud and local)
        self.items_file = "inventory/items.json"
        self.transactions_file = "inventory/transactions.json"
        self.snapshots_file = "inventory/snapshots.json"
        self.categories_file = "inventory/categories.json"
        self.suppliers_file = "inventory/suppliers.json"
        
        if not self.use_cloud:
            # Convert to full local paths
            self.items_file = self.data_dir / self.items_file
            self.transactions_file = self.data_dir / self.transactions_file
            self.snapshots_file = self.data_dir / self.snapshots_file
            self.categories_file = self.data_dir / self.categories_file
            self.suppliers_file = self.data_dir / self.suppliers_file
        
        # Log configuration
        app_logger.log_info("Inventory data manager initialized", {
            "app_module": "inventory",
            "action": "init",
            "storage_type": "cloud" if self.use_cloud else "local",
            "data_location": bucket_name if self.use_cloud else str(self.data_dir)
        })
        
        # Initialize with default data if needed
        self._ensure_default_data()
    
    def _read_json(self, file_path: str) -> Optional[dict]:
        """Read JSON data from storage
        
        Args:
            file_path: Path to the JSON file (cloud or local)
            
        Returns:
            Dict containing the JSON data, or None if file doesn't exist
        """
        try:
            if self.use_cloud:
                return self.storage.read_json(file_path)
            else:
                if not Path(file_path).exists():
                    return None
                with open(file_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            app_logger.log_error(f"Error reading JSON from {file_path}: {e}", e)
            return None
    
    def _write_json(self, file_path: str, data: dict) -> bool:
        """Write JSON data to storage
        
        Args:
            file_path: Path to write the JSON file
            data: Data to write
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.use_cloud:
                return self.storage.write_json(file_path, data)
            else:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2, default=self._serialize_datetime)
                return True
        except Exception as e:
            app_logger.log_error(f"Error writing JSON to {file_path}: {e}", e)
            return False