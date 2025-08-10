"""Migrate all items from POS config to a new inventory_items.json file."""

import os
import json
from pathlib import Path
from datetime import datetime
import uuid

# Import InventoryItem and POSMappingManager from the app
import sys
sys.path.append(str(Path(__file__).parent.parent))
from modules.inventory_data import InventoryItem
from modules.pos_mapping import POSMappingManager
from modules.inventory_management import load_standardized_item_names


def migrate_inventory(default_supplier_id=None):
    """
    Create a new inventory_items.json file from POS config, with sensible defaults.
    """
    data_dir = Path(__file__).parent.parent / 'data'
    inventory_file = data_dir / 'inventory_items.json'
    
    # Load POS config items
    pos_manager = POSMappingManager()
    standardized_names = load_standardized_item_names()
    
    # Load suppliers for default assignment
    suppliers_file = data_dir / 'suppliers.json'
    suppliers = {}
    if suppliers_file.exists():
        with open(suppliers_file, 'r') as f:
            suppliers = json.load(f)
    if not default_supplier_id and suppliers:
        default_supplier_id = next(iter(suppliers.keys()))
    
    # Build inventory items
    inventory_items = {}
    for category, items in standardized_names.items():
        for key, display_name in items.items():
            # Get unit from POS config
            default_unit = ""
            # For menu items, find item by standardized_key
            for menu_item in pos_manager._mappings.values():
                if menu_item.get('standardized_key') == key:
                    default_unit = menu_item.get('base_unit', '')
                    break
            # If not found in menu items, check components
            if not default_unit and key in pos_manager._components:
                default_unit = pos_manager._components[key].get('base_unit', '')
            
            item_id = f"item_{uuid.uuid4().hex[:8]}"
            migration_date = datetime.now().strftime('%Y-%m-%d')
            item = InventoryItem(
                item_id=item_id,
                name=display_name,
                category=category,
                unit=default_unit,
                par_level=20.0,
                reorder_point=5.0,
                supplier_id=default_supplier_id,
                cost_per_unit=0.0,
                standardized_item_name=key,
                notes=f"Auto-migrated from POS config on {migration_date}"
            )
            # Recursively convert any datetime objects to strings
            def make_json_serializable(obj):
                if isinstance(obj, dict):
                    return {k: make_json_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_json_serializable(v) for v in obj]
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                else:
                    return obj
            item_dict = make_json_serializable(item.__dict__)
            inventory_items[item_id] = item_dict
    
    # Write to inventory file
    data_dir.mkdir(exist_ok=True)
    with open(inventory_file, 'w') as f:
        json.dump(inventory_items, f, indent=4)
    print(f"✅ Migrated {len(inventory_items)} items to {inventory_file}")

if __name__ == "__main__":
    migrate_inventory()
