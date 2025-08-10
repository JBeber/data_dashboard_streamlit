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
from modules.inventory_data import InventoryDataManager, Transaction
from modules.pos_mapping import POSMappingManager


class SimplifiedToastProcessor:
    """Integrated processor using both standardized mapping and specialized espresso tracking"""

    def __init__(self, mapping_file: str = None):
        self.data_manager = InventoryDataManager()
        self.mapping_manager = POSMappingManager(mapping_file) if mapping_file else POSMappingManager()
        
        # Initialize espresso inventory manager
        from modular_espresso_inventory import ModularEspressoInventoryManager
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
        
        # Add espresso component usage to overall results
        for cup_type, quantity in espresso_results['cups'].items():
            if quantity > 0:
                self._add_component_usage(
                    results["component_usage"],
                    f"cups_{cup_type}",
                    quantity,
                    "cup"
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
        for _, row in items_df.iterrows():
            menu_item = row['Menu Item']
            quantity = row['Qty']
            
            # Skip espresso drinks - already handled
            if menu_item in self.espresso_manager.drink_specs:
                continue
                
            # Get component mappings for non-espresso items
            item_mapping = self.mapping_manager.get_mapping_for_item(menu_item)
            if not item_mapping:
                continue
            
            # Add components from mapping
            for component in item_mapping.get('components', []):
                self._add_component_usage(
                    results["component_usage"],
                    component['key'],
                    quantity * component['quantity'],
                    component['unit']
                )
                
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
        timestamp = datetime.strptime(date_str, "%Y%m%d").replace(hour=23, minute=59)
        
        for component_key, usage in component_usage.items():
            transaction = Transaction(
                item_id=component_key,  # Using standardized_key as item_id
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
