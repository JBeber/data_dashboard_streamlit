"""
Modular Espresso Inventory Management System
Designed for automated daily background processing after data collection

Features:
- Separate focused functions for each calculation type
- Ready for tomorrow's Item Selection Id field
- Designed for automated inventory system integration
- Clean, maintainable code structure
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json, sys

class ModularEspressoInventoryManager:
    def __init__(self, config_file="data/espresso_drink_specs.json"):
        """Initialize with beverage specifications from config file"""
        self.load_drink_specifications(config_file)

        
    
    def load_drink_specifications(self, config_file):
        """Load drink specifications from JSON config file"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            self.drink_specs = config.get('drink_specifications', {})
            self.espresso_drinks = self.drink_specs.keys()
            self.milk_alternatives = config.get('milk_alternatives', [])
            self.syrups = config.get('syrups', [])
            
            print(f"✅ Loaded specifications for {len(self.drink_specs)} drinks")
            print(f"✅ Loaded {len(self.milk_alternatives)} milk alternatives and {len(self.syrups)} syrups")
            
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            self.drink_specs = {}
            self.milk_alternatives = []
            self.syrups = []
    
    def calculate_togo_cup_usage(self, items_df, mods_df):
        """
        Calculate togo cup usage based on ItemSelectionDetails and ModifiersSelectionDetails
        
        Logic:
        - Only count cups for Take Out orders
        - Use drink specifications for base cup type/size
        - Apply 'iced' modifier to determine final cup type
        - Handle multiple drinks of same type in single order
        """
        print("🥤 Calculating togo cup usage...")
        
        cup_usage = {
            'hot_4oz': 0, 'hot_8oz': 0, 'hot_12oz': 0, 'hot_16oz': 0,
            'cold_9oz': 0, 'cold_20oz': 0
        }
        
        # Filter takeout espresso drinks in Items.csv
        espresso_togo = items_df[
            (items_df['Menu Item'].isin(self.espresso_drinks)) & 
            (items_df['Dining Option'].str.lower() == 'take out') &
            (items_df['Void?'] == False)
        ]
        
        print(f"Found {len(espresso_togo)} togo espresso drinks")
        
        # Process each togo drink in Items.csv and assume all hot drinks
        for _, item in espresso_togo.iterrows():
            drink_name = item['Menu Item']
            drink_qty = item['Qty']
            spec = self.drink_specs[drink_name]
            if spec.get('hot_size_oz'):
                cup_key = f"hot_{spec['hot_size_oz']}oz"
            else:
                cup_key = f"cold_{spec['cold_size_oz']}oz"

            cup_usage[cup_key] = cup_usage.get(cup_key, 0) + drink_qty

        # Filter takeout iced espresso drinks from Mods.csv
        iced_togo = mods_df[
            (mods_df['Parent Menu Selection'].isin(self.espresso_drinks)) & 
            (mods_df['Dining Option'].str.lower() == 'take out') &
            (mods_df['Modifier'].str.lower() == 'iced') &
            (mods_df['Void?'] == False)
        ]

        # Process each iced togo drink in Mods.csv
        iced_cup_usage = { 'cold_9oz': 0, 'cold_20oz': 0 }

        for _, iced_item in iced_togo.iterrows():
            iced_drink_name = iced_item['Parent Menu Selection']
            iced_drink_qty = iced_item['Qty']
            spec = self.drink_specs[iced_drink_name]

            cup_key = f"cold_{spec['cold_size_oz']}oz"
            iced_cup_usage[cup_key] = iced_cup_usage.get(cup_key, 0) + iced_drink_qty

            # Subtract the corresponding hot cup count
            hot_cup_key = f"hot_{spec['hot_size_oz']}oz"
            cup_usage[hot_cup_key] = cup_usage.get(hot_cup_key, 0) - iced_drink_qty

        # Add cold counts to hot counts for total usage
        cup_usage['cold_9oz'] += iced_cup_usage.get('cold_9oz', 0)
        cup_usage['cold_20oz'] += iced_cup_usage.get('cold_20oz', 0)

        print(f"Cup usage calculated: {sum(cup_usage.values())} total cups")
        return cup_usage
    
    def calculate_espresso_usage(self, items_df, modifiers_df, has_item_selection_id=False):
        """
        Calculate espresso usage with proper modifier handling
        
        Parameters:
        has_item_selection_id: Set to True when tomorrow's data includes Item Selection Id field
        
        Logic:
        - Base shots from drink specifications
        - Extra shots from modifiers (with quantity)
        - Decaf modifier switches to Sereno beans
        - Handle multiple drinks of same type properly
        """
        print("☕ Calculating espresso usage...")
        
        espresso_usage = {'Barocco': 0, 'Sereno': 0}
        
        # Filter for espresso drinks only
        espresso_orders = items_df[
                                (items_df['Menu Item'].isin(self.espresso_drinks)) & 
                                (items_df['Void?'] == False)
                          ]
        print(f"Found {len(espresso_orders)} espresso drinks")
        
        if has_item_selection_id:
            # Future logic for when Item Selection Id is available
            print("Using Item Selection Id for precise modifier matching...")
            # TODO: Implement precise matching logic
        else:
            # Current logic without Item Selection Id
            print("Using Order Id + drink name for modifier matching...")
            
            # Group by order to handle modifier distribution properly
            for order_id in espresso_orders['Order Id'].unique():
                order_items = espresso_orders[espresso_orders['Order Id'] == order_id]
                order_modifiers = modifiers_df[
                                        (modifiers_df['Order Id'] == order_id) &
                                        (modifiers_df['Void?'] == False)
                                  ]
                
                # Track used modifiers to avoid double application
                used_modifier_indices = set()
                
                for _, item in order_items.iterrows():
                    drink_name = item['Menu Item']
                    
                    # Get base shots from config
                    base_shots = self.drink_specs.get(drink_name, {}).get('espresso_shots', 1)
                    
                    # Find modifiers for this specific drink
                    drink_modifiers = order_modifiers[
                        order_modifiers['Parent Menu Selection'] == drink_name
                    ]
                    
                    extra_shots = 0
                    is_decaf = False
                    
                    # Process modifiers (only use each modifier once)
                    for idx, modifier in drink_modifiers.iterrows():
                        if idx in used_modifier_indices:
                            continue
                        
                        mod_name = str(modifier.get('Modifier', '')).lower()
                        mod_qty = modifier.get('Qty', 1)
                        
                        if 'extra shot' in mod_name:
                            extra_shots += mod_qty
                            used_modifier_indices.add(idx)
                        elif 'decaf' in mod_name or 'sereno' in mod_name:
                            is_decaf = True
                            used_modifier_indices.add(idx)
                    
                    # Calculate total shots for this drink
                    drink_qty = item['Qty']
                    total_shots = (base_shots * drink_qty) + extra_shots
                    bean_type = 'Sereno' if is_decaf else 'Barocco'
                    espresso_usage[bean_type] += total_shots
        
        print(f"Espresso usage: {espresso_usage['Barocco']} Barocco, {espresso_usage['Sereno']} Sereno")
        return espresso_usage
    
    def calculate_syrup_milk_usage(self, modifiers_df):
        """
        Calculate syrup and milk alternative usage from ModifiersSelectionDetails only
        Each modifier row = 1 usage (future: update config for amounts per drink type)
        """
        print("🥛 Calculating syrup and milk usage...")
        
        syrup_usage = {}
        milk_usage = {}
        
        for _, modifier in modifiers_df.iterrows():
            modifier_name = str(modifier.get('Modifier', ''))
            if pd.isna(modifier.get('Modifier', '')):
                continue
            
            # Check if modifier is a milk alternative
            if modifier_name in self.milk_alternatives:
                milk_usage[modifier_name] = milk_usage.get(modifier_name, 0) + 1
            
            # Check if modifier is a syrup
            elif modifier_name in self.syrups:
                syrup_usage[modifier_name] = syrup_usage.get(modifier_name, 0) + 1
        
        print(f"Found {sum(syrup_usage.values())} syrup usages, {sum(milk_usage.values())} milk alternative usages")
        return syrup_usage, milk_usage
    
    def process_daily_inventory(self, items_file, modifiers_file, date_str, has_item_selection_id=False):
        """
        Main processing function for daily inventory calculation
        Returns structured data ready for inventory system integration
        """
        print(f"🚀 Processing daily inventory for {date_str}")
        print("=" * 50)
        
        try:
            # Load data files
            items_df = pd.read_csv(items_file)
            modifiers_df = pd.read_csv(modifiers_file)
            
            # Convert Order Id to string
            items_df['Order Id'] = items_df['Order Id'].astype(str)
            modifiers_df['Order Id'] = modifiers_df['Order Id'].astype(str)
            
            print(f"Loaded {len(items_df)} items and {len(modifiers_df)} modifiers")
            
            # Calculate each component separately
            cup_usage = self.calculate_togo_cup_usage(items_df, modifiers_df)
            espresso_usage = self.calculate_espresso_usage(items_df, modifiers_df, has_item_selection_id)
            syrup_usage, milk_usage = self.calculate_syrup_milk_usage(modifiers_df)
            
            # Combine results
            daily_inventory = {
                'date': date_str,
                'cups': cup_usage,
                'espresso': espresso_usage,
                'syrups': syrup_usage,
                'milk_alternatives': milk_usage,
                'metadata': {
                    'total_items': len(items_df),
                    'total_modifiers': len(modifiers_df),
                    'espresso_orders': len(items_df[items_df['Menu Item'].isin(self.espresso_drinks)]),
                    'has_item_selection_id': has_item_selection_id
                }
            }
            
            self.generate_daily_report(daily_inventory)
            return daily_inventory
            
        except Exception as e:
            import traceback
            print(f"❌ Error processing {date_str}: {e}")
            traceback.print_exc()
            return None
    
    def generate_daily_report(self, inventory_data):
        """Generate human-readable daily report"""
        print(f"\n📊 Daily Inventory Report - {inventory_data['date']}")
        print("=" * 40)
        
        metadata = inventory_data['metadata']
        print(f"Total Orders Processed: {metadata['total_items']}")
        print(f"Espresso Orders: {metadata['espresso_orders']}")
        
        # Espresso consumption
        espresso = inventory_data['espresso']
        total_shots = espresso['Barocco'] + espresso['Sereno']
        print(f"\nEspresso Shots: {total_shots} total")
        print(f"  - Barocco (Regular): {espresso['Barocco']}")
        print(f"  - Sereno (Decaf): {espresso['Sereno']}")
        
        # Cup usage
        cups = inventory_data['cups']
        total_cups = sum(cups.values())
        print(f"\nTogo Cups: {total_cups} total")
        
        hot_cups = sum(v for k, v in cups.items() if k.startswith('hot_') and v > 0)
        cold_cups = sum(v for k, v in cups.items() if k.startswith('cold_') and v > 0)
        
        if hot_cups > 0:
            print(f"  Hot cups: {hot_cups}")
            for cup_type, count in cups.items():
                if cup_type.startswith('hot_') and count > 0:
                    print(f"    - {cup_type.replace('hot_', '')}: {count}")
        
        if cold_cups > 0:
            print(f"  Cold cups: {cold_cups}")
            for cup_type, count in cups.items():
                if cup_type.startswith('cold_') and count > 0:
                    print(f"    - {cup_type.replace('cold_', '')}: {count}")
        
        # Syrups - Enhanced detailed breakdown
        syrups = inventory_data['syrups']
        if syrups:
            total_syrup_uses = sum(syrups.values())
            print(f"\n🧴 Syrups: {total_syrup_uses} total usages")
            
            # Group syrups by type for better organization
            regular_syrups = {k: v for k, v in syrups.items() if not k.startswith('SF ')}
            sugar_free_syrups = {k: v for k, v in syrups.items() if k.startswith('SF ')}
            
            if regular_syrups:
                print("  Regular Syrups:")
                for syrup, count in sorted(regular_syrups.items()):
                    percentage = (count / total_syrup_uses) * 100
                    print(f"    - {syrup}: {count} uses ({percentage:.1f}%)")
            
            if sugar_free_syrups:
                print("  Sugar-Free Syrups:")
                for syrup, count in sorted(sugar_free_syrups.items()):
                    percentage = (count / total_syrup_uses) * 100
                    print(f"    - {syrup}: {count} uses ({percentage:.1f}%)")
        else:
            print("\n🧴 Syrups: No syrup usage detected")
        
        # Milk alternatives - Enhanced detailed breakdown
        milk = inventory_data['milk_alternatives']
        if milk:
            total_milk_uses = sum(milk.values())
            print(f"\n🥛 Milk Alternatives: {total_milk_uses} total usages")
            
            # Show individual breakdown with percentages
            for milk_type, count in sorted(milk.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_milk_uses) * 100
                print(f"    - {milk_type}: {count} uses ({percentage:.1f}%)")
            
            # Show most popular milk alternative
            most_popular = max(milk.items(), key=lambda x: x[1])
            print(f"  📈 Most popular: {most_popular[0]} ({most_popular[1]} uses)")
        else:
            print("\n🥛 Milk Alternatives: No milk alternative usage detected")
        
        print("\n✅ Daily processing complete - ready for inventory system integration")
    
    def integrate_with_inventory_system(self, inventory_data):
        """
        Placeholder for inventory system integration
        This would update your actual inventory counts
        """
        print("\n🔄 Integrating with inventory system...")
        print("(This would update actual product counts in your inventory database)")
        
        # Example integration logic:
        # - Subtract cup usage from cup inventory
        # - Subtract espresso bean usage from bean inventory  
        # - Subtract syrup/milk usage from respective inventories
        # - Log all transactions with timestamps
        
        return True

def main(dt=None, has_item_selection_id=False):
    """
    Main function for automated daily processing
    """
    print("🚀 Modular Espresso Inventory Management System")
    print("Designed for automated daily background processing")
    print("=" * 60)
    
    # Initialize the manager
    manager = ModularEspressoInventoryManager()
    
    # Use provided date or default to current format
    if dt is None:
        dt = "20250806"  # Your current data format
    
    # File paths
    items_file = f"ItemSelectionDetails_{dt}.csv"
    modifiers_file = f"ModifiersSelectionDetails_{dt}.csv"
    
    # Check if files exist
    import os
    if os.path.exists(items_file) and os.path.exists(modifiers_file):
        # Process daily inventory
        inventory_data = manager.process_daily_inventory(
            items_file, 
            modifiers_file, 
            dt, 
            has_item_selection_id
        )
        
        if inventory_data:
            # Integrate with inventory system
            manager.integrate_with_inventory_system(inventory_data)
            
            # Save results for weekly analysis
            output_file = f"daily_inventory_{dt}.json"
            with open(output_file, 'w') as f:
                json.dump(inventory_data, f, indent=2)
            print(f"Results saved to {output_file}")
        
    else:
        print(f"❌ Data files for {dt} not found:")
        print(f"  Looking for: {items_file}")
        print(f"  Looking for: {modifiers_file}")

if __name__ == "__main__":
    # Parse command line arguments
    dt = sys.argv[1] if len(sys.argv) > 1 else None
    has_item_selection_id = '--with-item-id' in sys.argv
    
    main(dt, has_item_selection_id)
