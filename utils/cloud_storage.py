"""Cloud Storage utilities for inventory data management"""

import json
from google.cloud import storage
from pathlib import Path
from typing import Dict, Any, Optional
from utils.logging_config import app_logger

class CloudStorageManager:
    """Manages reading and writing JSON files to Google Cloud Storage"""
    
    def __init__(self, bucket_name: str = "vv-inventory-data"):
        """Initialize the Cloud Storage manager with a bucket name"""
        self.client = storage.Client()
        self.bucket_name = bucket_name
        self.bucket = self.client.bucket(bucket_name)
        
    def read_json(self, blob_path: str) -> Optional[Dict[str, Any]]:
        """Read a JSON file from Cloud Storage
        
        Args:
            blob_path: Path to the JSON file in the bucket
            
        Returns:
            Dict containing the JSON data, or None if the file doesn't exist
        """
        try:
            blob = self.bucket.blob(blob_path)
            if not blob.exists():
                app_logger.log_info(f"Blob does not exist: {blob_path}", {
                    "app_module": "cloud_storage",
                    "action": "read_json",
                    "bucket": self.bucket_name,
                    "blob_path": blob_path
                })
                return None
                
            content = blob.download_as_string()
            return json.loads(content)
        except Exception as e:
            app_logger.log_error(f"Error reading from Cloud Storage: {str(e)}", e)
            return None
            
    def write_json(self, blob_path: str, data: Dict[str, Any]) -> bool:
        """Write a dictionary as JSON to Cloud Storage
        
        Args:
            blob_path: Path where the JSON file should be stored
            data: Dictionary to be stored as JSON
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            blob = self.bucket.blob(blob_path)
            blob.upload_from_string(
                json.dumps(data, indent=2),
                content_type='application/json'
            )
            app_logger.log_info(f"Successfully wrote to {blob_path}", {
                "app_module": "cloud_storage",
                "action": "write_json",
                "bucket": self.bucket_name,
                "blob_path": blob_path
            })
            return True
        except Exception as e:
            app_logger.log_error(f"Error writing to Cloud Storage: {str(e)}", e)
            return False
            
    def list_files(self, prefix: Optional[str] = None) -> list[str]:
        """List files in the bucket, optionally filtered by prefix
        
        Args:
            prefix: Optional prefix to filter blobs
            
        Returns:
            List of blob names
        """
        try:
            blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            app_logger.log_error(f"Error listing files in Cloud Storage: {str(e)}", e)
            return []
            
    def file_exists(self, blob_path: str) -> bool:
        """Check if a file exists in Cloud Storage
        
        Args:
            blob_path: Path to check
            
        Returns:
            bool: True if the file exists, False otherwise
        """
        try:
            blob = self.bucket.blob(blob_path)
            return blob.exists()
        except Exception as e:
            app_logger.log_error(f"Error checking file existence in Cloud Storage: {str(e)}", e)
            return False