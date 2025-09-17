"""
Integrated Toast Inventory Processor

This processor combines:
1. Standardized mapping for regular menu items from POS config
2. Specialized espresso drink tracking from modular espresso inventory
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logging_config import app_logger, log_function_errors
from modules.inventory_data import InventoryDataManager, Transaction, InventoryItem
from modules.pos_mapping import POSMappingManager
from modular_espresso_inventory import ModularEspressoInventoryManager


class SimplifiedToastProcessor:
    """Integrated processor using both standardized mapping and specialized espresso tracking"""

    def __init__(self, mapping_file: str = None):
        self.data_manager = InventoryDataManager()
        self.mapping_manager = POSMappingManager(mapping_file) if mapping_file else POSMappingManager()
        
        # Initialize espresso inventory manager        
        self.espresso_manager = ModularEspressoInventoryManager()
    
    @log_function_errors("toast_processor", "process_daily_data")
    def process_daily_data(self, items_file: str, modifiers_file: str, date_str: str) -> Dict:
        """Process Toast POS data focusing on modifier-based component usage"""
        
        app_logger.log_info("Processing Toast POS data with modifier tracking", {
            "app_module": "simplified_toast_processor",
            "action": "process_daily_data",
            "date": date_str,
            "items_file": items_file,
            "modifiers_file": modifiers_file
        })
        
        # Load POS data
        try:
            items_df = pd.read_csv(items_file)
            modifiers_df = pd.read_csv(modifiers_file)
        except Exception as e:
            return {"success": False, "error": f"Failed to load POS data: {str(e)}"}
        
        # Filter out voided items
        items_df = items_df[items_df['Void?'] == False]
        modifiers_df = modifiers_df[modifiers_df['Void?'] == False]
        
        results = {
            "success": True,
            "date": date_str,
            "component_usage": {},
            "processed_modifiers": 0,
            "unprocessed_modifiers": [],
            "espresso_results": {}
        }
        
        # Process espresso drinks first using modular espresso inventory
        espresso_results = {
            'cups': self.espresso_manager.calculate_togo_cup_usage(items_df, modifiers_df),
            'espresso': self.espresso_manager.calculate_espresso_usage(items_df, modifiers_df),
            'syrups_milk': self.espresso_manager.calculate_syrup_milk_usage(modifiers_df)
        }
        
        # Calculate lids based on cup usage
        espresso_results['lids'] = self.espresso_manager.calculate_lid_usage(espresso_results['cups'])
        
        # Add espresso component usage to overall results
        for cup_type, quantity in espresso_results['cups'].items():
            if quantity > 0:
                # Already formatted as "4oz_hot" or "9oz_cold" from modular_espresso_inventory.py
                cup_key = f"cups_{cup_type}"
                
                self._add_component_usage(
                    results["component_usage"],
                    cup_key,
                    quantity,
                    "cup"
                )
                
        # Add lid usage to component usage
        for lid_type, quantity in espresso_results['lids'].items():
            if quantity > 0:
                self._add_component_usage(
                    results["component_usage"],
                    lid_type,
                    quantity,
                    "lid"
                )
                
        for bean_type, shots in espresso_results['espresso'].items():
            if shots > 0:
                self._add_component_usage(
                    results["component_usage"],
                    f"espresso_{bean_type.lower()}", 
                    shots,
                    "shot"
                )
        
        syrup_usage, milk_usage = espresso_results['syrups_milk']
        for syrup_type, count in syrup_usage.items():
            if count > 0:
                self._add_component_usage(
                    results["component_usage"],
                    f"flavor_{syrup_type.lower().replace(' ', '_')}",
                    count,
                    "unit"
                )
                
        for milk_type, count in milk_usage.items():
            if count > 0:
                self._add_component_usage(
                    results["component_usage"],
                    f"milk_{milk_type.lower().replace(' ', '_')}",
                    count,
                    "unit"
                )
        
        results["espresso_results"] = espresso_results
        
        # Process remaining non-espresso items from the mapping config
        # First, check for wine and beer items and create direct usage transactions for them
        items = self.data_manager.load_items()
        
        # Create lookup dictionaries for wine and beer items by their standardized names
        wine_items = {}
        beer_items = {}
        for item_id, item in items.items():
            if item.category in ('Wine - Glasses', 'Wine - Bottle'):
                wine_items[item.standardized_item_name] = item_id
            elif item.standardized_item_name and "beer" in item.standardized_item_name:
                beer_items[item.standardized_item_name] = item_id
        
        # Process wine and beer menu items
        for _, row in items_df.iterrows():
            menu_item = row['Menu Item']
            quantity = row['Qty']
            
            # Skip espresso drinks - already handled
            if menu_item in self.espresso_manager.drink_specs:
                continue
            
            # Check if this is a wine or beer item that matches our inventory
            found_match = False
            # Try exact match first
            standardized_key = menu_item.lower().replace(" ", "_")
            
            if standardized_key.startswith("wine"):
                # Check if this menu item matches any wine inventory item
                for wine_key, item_id in wine_items.items():
                    if standardized_key in wine_key or wine_key in standardized_key:
                        self._add_component_usage(
                            results["component_usage"],
                            wine_key,
                            quantity,
                            "bottle"
                        )
                        found_match = True
                        break
            elif standardized_key.startswith("beer"):
                # Check if this menu item matches any beer inventory item
                for beer_key, item_id in beer_items.items():
                    if standardized_key in beer_key or beer_key in standardized_key:
                        self._add_component_usage(
                            results["component_usage"],
                            beer_key,
                            quantity,
                            "bottle"
                        )
                        found_match = True
                        break
            
            if found_match:
                continue

            
            # TODO: Add logic for other item tracking    
            # # Get component mappings for non-espresso items
            # item_mapping = self.mapping_manager.get_mapping_for_item(menu_item)
            # if not item_mapping:
            #     continue
            
            # # Handle Non-Alcoholic Beverages directly - they don't have components but should be tracked
            # if item_mapping.get('menu_group') == 'Non-Alcoholic':
            #     self._add_component_usage(
            #         results["component_usage"],
            #         item_mapping['standardized_key'],  # Use the standardized key like na_bev_pele_lg
            #         quantity,
            #         item_mapping['base_unit']
            #     )
            #     continue
            
            # # Add components from mapping
            # for component in item_mapping.get('components', []):
            #     self._add_component_usage(
            #         results["component_usage"],
            #         component['key'],
            #         quantity * component['quantity'],
            #         component['unit']
            #     )
                
        # Log all component usage transactions
        self._log_component_transactions(results["component_usage"], date_str)
        
        app_logger.log_info("Toast POS processing complete", {
            "app_module": "simplified_toast_processor",
            "action": "processing_complete",
            "date": date_str,
            "espresso_drinks_processed": len(espresso_results.get('espresso', {})),
            "transactions_logged": len(results["component_usage"])
        })
        
        return results
    def _add_component_usage(self, usage_dict: Dict, key: str, 
                            quantity: float, unit: str):
        """Add or update component usage tracking"""
        if key not in usage_dict:
            usage_dict[key] = {"quantity": 0.0, "unit": unit}
        usage_dict[key]["quantity"] += quantity
    
    def _log_component_transactions(self, component_usage: Dict, date_str: str):
        """Log transactions for component usage"""
        # Ensure idempotency: purge existing auto POS usage transactions for the date before logging
        target_date = datetime.strptime(date_str, "%Y%m%d").date()
        try:
            # Only purge our previously logged POS usage entries for that day
            self.data_manager.purge_transactions_by_source_date(target_date, source="simplified_pos_integration", types=["usage"])
        except Exception:
            # If purge fails, continue to avoid blocking; duplicates may occur
            pass

        timestamp = datetime.combine(target_date, datetime.min.time()).replace(hour=23, minute=59)
        
        for component_key, usage in component_usage.items():
            # Resolve or create inventory item for this component key
            resolved_item_id = self._resolve_or_create_item(component_key)

            transaction = Transaction(
                item_id=resolved_item_id,
                transaction_type="usage",
                quantity=usage["quantity"],
                timestamp=timestamp,
                user="pos_automation",
                notes=f"POS daily usage",
                source="simplified_pos_integration"
            )
            
            try:
                self.data_manager.log_transaction(transaction)
            except Exception as e:
                app_logger.log_error(f"Failed to log transaction for {component_key}", e)

    def _resolve_or_create_item(self, component_key: str) -> str:
        """Ensure an InventoryItem exists for the given component key.

        Priority:
        1) If an item exists with item_id == component_key, use it (ideal alignment).
        2) Else if an item exists with standardized_item_name == component_key, use that legacy item_id.
        3) Else create a new item using POS component definition with item_id == component_key.
        """
        items = self.data_manager.load_items()
        if component_key in items:
            return component_key

        # Look for legacy item matching standardized_item_name
        for item in items.values():
            if item.standardized_item_name == component_key:
                return item.item_id

        # Create new from POS component definition
        comp = self.mapping_manager.get_component(component_key)
        display_name = comp.get('display_name', component_key) if comp else component_key
        base_unit = comp.get('base_unit', 'unit') if comp else 'unit'
        category = comp.get('menu_group', 'supplies') if comp else 'supplies'

        # Choose a default supplier if available
        suppliers = self.data_manager.load_suppliers()
        default_supplier = None
        if 'supplier_internal_001' in suppliers:
            default_supplier = 'supplier_internal_001'
        elif suppliers:
            # Pick any supplier deterministically
            default_supplier = sorted(suppliers.keys())[0]

        new_item = InventoryItem(
            item_id=component_key,
            name=display_name,
            category=category,
            unit=base_unit,
            par_level=0.0,
            reorder_point=0.0,
            supplier_id=default_supplier,
            cost_per_unit=0.0,
            standardized_item_name=component_key,
            notes="Auto-created by POS usage processor"
        )

        items[component_key] = new_item
        self.data_manager.save_items(items)
        return component_key


# Main function for processing
@log_function_errors("toast_processor", "process_daily_toast_data")
def process_daily_toast_data(date_str: str, items_file: str = None) -> Dict:
    """Process Toast POS data for a specific date"""
    
    if not items_file:
        # Auto-detect files in Test_Data
        items_file = f"../Test_Data/ItemSelectionDetails_{date_str}.csv"
        modifiers_file = f"../Test_Data/ModifiersSelectionDetails_{date_str}.csv"
    else:
        # If manual file provided, build modifiers path
        base_path = os.path.dirname(items_file)
        base_name = os.path.basename(items_file)
        if base_name.startswith('ItemSelectionDetails'):
            modifiers_file = os.path.join(base_path, f"ModifiersSelectionDetails_{date_str}.csv")
        else:
            # Fall back to Test_Data
            modifiers_file = f"Test_Data/ModifiersSelectionDetails_{date_str}.csv"
    
    processor = SimplifiedToastProcessor()
    return processor.process_daily_data(items_file, modifiers_file, date_str)
