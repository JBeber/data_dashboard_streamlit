"""Environment detection utilities"""

import os
from pathlib import Path

def is_running_in_docker():
    """Check if we're running inside a Docker container"""
    return os.path.exists('/.dockerenv')

def get_data_directory():
    """Get the appropriate data directory based on environment"""
    if is_running_in_docker():
        return Path("/var/data/inventory")
    else:
        # Use a directory relative to the application root for local development
        app_root = Path(__file__).parent.parent
        return app_root / "data" / "inventory"