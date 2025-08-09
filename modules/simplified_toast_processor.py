"""
Simplified Toast Inventory Processor using Standardized Item Name Mapping

This processor uses the standardized_item_name field in inventory items to directly
map Toast POS menu items to inventory items, eliminating complex matching logic.
"""

import pandas as pd
import json
from datetime import datetime
from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logging_config import app_logger, log_function_errors
from modules.inventory_data import InventoryDataManager, Transaction


class SimplifiedToastProcessor:
    """Simplified processor using standardized item name mapping"""
    
    def __init__(self):
        self.data_manager = InventoryDataManager()
    
    @log_function_errors("toast_processor", "process_daily_data")
    def process_daily_data(self, items_file: str, date_str: str) -> Dict:
        """Process Toast POS data using standardized name mapping"""
        
        app_logger.log_info("Processing Toast POS data with standardized mapping", {
            "app_module": "simplified_toast_processor",
            "action": "process_daily_data",
            "date": date_str,
            "file": items_file
        })
        
        # Load POS data
        try:
            pos_df = pd.read_csv(items_file)
        except Exception as e:
            return {"success": False, "error": f"Failed to load POS data: {str(e)}"}
        
        # Filter out voided items
        pos_df = pos_df[pos_df['Void?'] == False]
        
        # Load inventory items
        inventory_items = self.data_manager.load_items()
        
        # Group POS data by menu item
        grouped_pos = pos_df.groupby(['Item', 'Menu Group'], as_index=False)['Qty'].sum()
        
        results = {
            "success": True,
            "date": date_str,
            "total_pos_items": len(grouped_pos),
            "matched_items": [],
            "unmatched_items": [],
            "transactions_logged": 0
        }
        
        # Process each POS item
        for _, row in grouped_pos.iterrows():
            menu_item = row['Item']
            menu_group = row.get('Menu Group', '')
            quantity = row['Qty']
            
            # Generate standardized name for this POS item
            standardized_name = self._generate_standardized_name(menu_item, menu_group)
            
            if standardized_name:
                # Find inventory item with this standardized name
                matched_item_id = self._find_inventory_item_by_standardized_name(
                    standardized_name, inventory_items
                )
                
                if matched_item_id:
                    # Log transaction
                    success = self._log_usage_transaction(
                        matched_item_id, quantity, date_str, menu_item, menu_group
                    )
                    
                    if success:
                        results["matched_items"].append({
                            "menu_item": menu_item,
                            "menu_group": menu_group,
                            "quantity": quantity,
                            "standardized_name": standardized_name,
                            "inventory_item_id": matched_item_id,
                            "inventory_item_name": inventory_items[matched_item_id].name
                        })
                        results["transactions_logged"] += 1
                    else:
                        results["unmatched_items"].append({
                            "menu_item": menu_item,
                            "menu_group": menu_group,
                            "quantity": quantity,
                            "reason": "Transaction logging failed"
                        })
                else:
                    results["unmatched_items"].append({
                        "menu_item": menu_item,
                        "menu_group": menu_group,
                        "quantity": quantity,
                        "standardized_name": standardized_name,
                        "reason": "No inventory item with matching standardized name"
                    })
            else:
                results["unmatched_items"].append({
                    "menu_item": menu_item,
                    "menu_group": menu_group,
                    "quantity": quantity,
                    "reason": "Could not generate standardized name"
                })
        
        app_logger.log_info("Toast POS processing complete", {
            "app_module": "simplified_toast_processor",
            "action": "processing_complete",
            "matched_items": len(results["matched_items"]),
            "unmatched_items": len(results["unmatched_items"]),
            "transactions_logged": results["transactions_logged"]
        })
        
        return results
    
    def _find_inventory_item_by_standardized_name(self, standardized_name: str, 
                                                 items: Dict) -> Optional[str]:
        """Find inventory item with matching standardized_item_name"""
        
        for item_id, item in items.items():
            if item.standardized_item_name == standardized_name:
                return item_id
        
        return None
    
    def _log_usage_transaction(self, item_id: str, quantity: float, date_str: str,
                              menu_item: str, menu_group: str) -> bool:
        """Log a usage transaction for inventory item"""
        
        try:
            transaction = Transaction(
                item_id=item_id,
                transaction_type="usage",
                quantity=quantity,
                timestamp=datetime.strptime(date_str, "%Y%m%d").replace(hour=23, minute=59),
                user="pos_automation",
                notes=f"POS usage: {menu_item} ({menu_group})",
                source="simplified_pos_integration"
            )
            
            self.data_manager.log_transaction(transaction)
            return True
            
        except Exception as e:
            app_logger.log_error(f"Failed to log transaction for {item_id}", e)
            return False
    
    def _generate_standardized_name(self, menu_item: str, menu_group: str) -> Optional[str]:
        """
        Generate standardized name from menu item and group.
        This maps Toast POS menu items to our standardized naming scheme.
        """
        
        menu_item_lower = menu_item.lower().strip()
        menu_group_lower = menu_group.lower().strip()
        
        # Direct mappings for common items
        direct_mappings = {
            # Coffee items
            "americano": "coffee_americano",
            "cappuccino": "coffee_cappuccino",
            "latte": "coffee_latte", 
            "espresso": "coffee_espresso",
            "macchiato": "coffee_macchiato",
            "cortado": "coffee_cortado",
            "mocha": "coffee_mocha",
            
            # Beverages
            "coca cola": "soda_coca_cola",
            "sprite": "soda_sprite",
            "pellegrino 500ml": "pellegrino_500ml",
            "pellegrino 750ml": "pellegrino_750ml",
            
            # Pastries - exact name matches
            "cornetto cioccolato": "cornetto_chocolate",
            "cornetto crema": "cornetto_cream", 
            "cornetto nutella": "cornetto_nutella",
            "cornetto pistacchio": "cornetto_pistachio",
            "bombolone crema": "bombolone_cream",
            "conchiglia choc": "conchiglia_chocolate",
            
            # Panini
            "panini prosciutto": "panini_prosciutto",
            "panini salami": "panini_salami",
        }
        
        # Check direct mappings first
        if menu_item_lower in direct_mappings:
            return direct_mappings[menu_item_lower]
        
        # Wine bottle logic
        if "wine" in menu_group_lower and "bottle" in menu_group_lower:
            return self._map_wine_to_standardized(menu_item_lower, is_bottle=True)
        
        # Wine glass logic  
        if "wine" in menu_group_lower and "glass" in menu_group_lower:
            return self._map_wine_to_standardized(menu_item_lower, is_bottle=False)
        
        # Beer logic
        if "beer" in menu_group_lower:
            return self._map_beer_to_standardized(menu_item_lower)
        
        # Food items with keyword matching
        if menu_group_lower in ["cornetti/bombolone", "food"]:
            return self._map_food_to_standardized(menu_item_lower)
        
        return None
    
    def _map_wine_to_standardized(self, menu_item: str, is_bottle: bool) -> Optional[str]:
        """Map wine items to standardized names"""
        
        # Common wine type keywords
        wine_types = {
            "prosecco": "prosecco",
            "chianti": "chianti", 
            "pinot grigio": "pinot_grigio",
            "pinot noir": "pinot_noir", 
            "chardonnay": "chardonnay",
            "merlot": "merlot",
            "cabernet": "cabernet",
            "sauvignon blanc": "sauvignon_blanc"
        }
        
        suffix = "_bottle" if is_bottle else "_glass"
        
        for wine_name, standardized in wine_types.items():
            if wine_name in menu_item:
                return f"wine_{standardized}{suffix}"
        
        # Fallback for unrecognized wines
        if "red" in menu_item:
            return f"wine_red_blend{suffix}"
        elif "white" in menu_item:
            return f"wine_white_blend{suffix}" 
        elif "rosé" in menu_item or "rose" in menu_item:
            return f"wine_rose{suffix}"
        
        return None
    
    def _map_beer_to_standardized(self, menu_item: str) -> Optional[str]:
        """Map beer items to standardized names"""
        
        if "lager" in menu_item:
            return "beer_lager"
        elif "ipa" in menu_item:
            return "beer_ipa"
        elif "wheat" in menu_item:
            return "beer_wheat"
        elif "stout" in menu_item:
            return "beer_stout"
        elif "pilsner" in menu_item:
            return "beer_pilsner"
        
        # Default beer mapping
        return "beer_lager"
    
    def _map_food_to_standardized(self, menu_item: str) -> Optional[str]:
        """Map food items to standardized names"""
        
        # Check for specific food items
        if "cornetto" in menu_item:
            if "cioccolato" in menu_item or "chocolate" in menu_item:
                return "cornetto_chocolate"
            elif "crema" in menu_item or "cream" in menu_item:
                return "cornetto_cream"
            elif "nutella" in menu_item:
                return "cornetto_nutella"
            elif "pistacchio" in menu_item:
                return "cornetto_pistachio"
            else:
                return "cornetto_plain"
        
        elif "bombolone" in menu_item:
            if "crema" in menu_item:
                return "bombolone_cream"
            else:
                return "bombolone_plain"
        
        elif "conchiglia" in menu_item:
            if "choc" in menu_item:
                return "conchiglia_chocolate"
            else:
                return "conchiglia_plain"
        
        elif "panini" in menu_item:
            if "prosciutto" in menu_item:
                return "panini_prosciutto"
            elif "salami" in menu_item:
                return "panini_salami"
            else:
                return "panini_prosciutto"  # Default
        
        return None


# Main function for processing
@log_function_errors("toast_processor", "process_daily_toast_data")
def process_daily_toast_data(date_str: str, items_file: str = None) -> Dict:
    """Process Toast POS data for a specific date"""
    
    if not items_file:
        items_file = f"Test_Data/ItemSelectionDetails_{date_str}.csv"
    
    processor = SimplifiedToastProcessor()
    return processor.process_daily_data(items_file, date_str)
