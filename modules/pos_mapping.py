"""
POS Mapping Manager for standardized inventory tracking
"""

import pandas as pd
from typing import Dict, Optional, List
from dataclasses import dataclass
from pathlib import Path

@dataclass
class POSMapping:
    """Container for POS item mapping data"""
    standardized_key: str
    base_unit: str
    menu_group: str
    notes: Optional[str] = None

class POSMappingManager:
    """Manages POS to inventory item mappings from JSON configuration"""
    
    def __init__(self, mapping_file: str = "/var/data/inventory/pos_mapping_config.json"):
        self.mapping_file = mapping_file
        self._mappings: Dict[str, Dict] = {}
        self._components: Dict[str, Dict] = {}
        self._component_relationships: Dict[str, Dict] = {}
        self.load_mappings()
    
    def load_mappings(self):
        """Load and parse the mapping JSON file"""
        # Reset our mappings at the start
        self._mappings = {}
        self._components = {}
        self._component_relationships = {}
        
        try:
            # Check if file exists
            if not Path(self.mapping_file).exists():
                raise FileNotFoundError(f"Mapping file not found: {self.mapping_file}")
                
            # Load JSON data
            import json
            with open(self.mapping_file, 'r') as f:
                config = json.load(f)
            
            # Validate basic structure
            if not isinstance(config, dict):
                raise ValueError("Invalid JSON format - root must be an object")
                
            # Load menu items
            for category, items in config.get('menu_items', {}).items():
                for item_name, details in items.items():
                    self._mappings[item_name] = {
                        'standardized_key': details['standardized_key'],
                        'base_unit': details['base_unit'],
                        'menu_group': category,
                        'display_name': details.get('display_name', item_name),
                        'notes': details.get('notes')
                    }
            
            # Load component definitions
            for category, components in config.get('components', {}).items():
                for comp_key, details in components.items():
                    self._components[comp_key] = {
                        'display_name': details['display_name'],
                        'base_unit': details['base_unit'],
                        'menu_group': category
                    }
            
            # Load component relationships
            self._component_relationships = config.get('component_relationships', {})
                    
        except (FileNotFoundError, pd.errors.EmptyDataError) as e:
            print(f"Error loading mapping file: {e}")
        except ValueError as e:
            print(f"Invalid mapping file format: {e}")
        except Exception as e:
            print(f"Unexpected error loading mappings: {e}")
    
    def get_mapping_for_item(self, item_name: str) -> Optional[Dict]:
        """Get mapping for a POS menu item name, including any component relationships"""
        base_mapping = self._mappings.get(item_name)
        if not base_mapping:
            return None
            
        # Get component relationships if they exist
        components = []
        key = base_mapping['standardized_key']
        if key in self._component_relationships:
            for use in self._component_relationships[key].get('uses', []):
                components.append({
                    'key': use['component'],
                    'quantity': use['quantity'],
                    'unit': use['unit']
                })
        
        return {
            'standardized_key': base_mapping['standardized_key'],
            'base_unit': base_mapping['base_unit'],
            'menu_group': base_mapping['menu_group'],
            'display_name': base_mapping.get('display_name', item_name),
            'components': components,
            'notes': base_mapping.get('notes')
        }
    
    def get_component(self, key: str) -> Optional[Dict]:
        """Get component definition by its key"""
        return self._components.get(key)
    
    def is_component(self, key: str) -> bool:
        """Check if a key refers to a defined component"""
        return key in self._components
    
    def get_all_components(self) -> Dict[str, Dict]:
        """Get all component definitions"""
        return self._components.copy()
        
    def get_component_relationships(self, item_key: str) -> List[Dict]:
        """Get component relationships for an item by its standardized key"""
        if item_key in self._component_relationships:
            return self._component_relationships[item_key].get('uses', [])
        return []
