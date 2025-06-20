import os
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from .logger import setup_logger

# Load environment variables
load_dotenv()

# Initialize logger
logger = setup_logger('storage')


class StorageService:
    """
    Storage service that supports both local file storage and S3-compatible storage.
    Automatically switches between local and S3 based on USE_S3_STORAGE environment variable.
    """
    
    def __init__(self):
        """Initialize the storage service with configuration from environment variables."""
        self.use_s3 = os.getenv('USE_S3_STORAGE', 'false').lower() == 'true'
        
        if self.use_s3:
            self._init_s3_config()
            logger.info("Storage service initialized with S3-compatible storage")
        else:
            logger.info("Storage service initialized with local file storage")
    
    def _init_s3_config(self):
        """Initialize S3 configuration from environment variables."""
        # Import boto3 only when S3 storage is enabled
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 storage. Install it with: pip install boto3"
            )
        
        # Store the imported modules as instance variables for later use
        self.boto3 = boto3
        self.ClientError = ClientError
        self.NoCredentialsError = NoCredentialsError
        
        self.s3_endpoint_url = os.getenv('S3_ENDPOINT_URL')
        self.s3_access_key_id = os.getenv('S3_ACCESS_KEY_ID')
        self.s3_secret_access_key = os.getenv('S3_SECRET_ACCESS_KEY')
        self.s3_bucket_name = os.getenv('S3_BUCKET_NAME')
        self.s3_region = os.getenv('S3_REGION', 'us-east-1')
        self.s3_path_prefix = os.getenv('S3_PATH_PREFIX', '').strip()
        self.s3_force_path_style = os.getenv('S3_FORCE_PATH_STYLE', 'false').lower() == 'true'
        
        # Validate required S3 configuration
        if not all([self.s3_access_key_id, self.s3_secret_access_key, self.s3_bucket_name]):
            raise ValueError(
                "S3 storage is enabled but missing required configuration. "
                "Please set S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, and S3_BUCKET_NAME."
            )
        
        # Initialize S3 client
        try:
            session = self.boto3.Session(
                aws_access_key_id=self.s3_access_key_id,
                aws_secret_access_key=self.s3_secret_access_key,
                region_name=self.s3_region
            )
            
            # Configure S3 client based on endpoint and path style
            s3_config = {}
            if self.s3_force_path_style:
                s3_config['s3'] = {'addressing_style': 'path'}
            
            self.s3_client = session.client(
                's3',
                endpoint_url=self.s3_endpoint_url,
                config=self.boto3.session.Config(**s3_config) if s3_config else None
            )
            
            # Test connection
            self._test_s3_connection()
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            raise
    
    def _test_s3_connection(self):
        """Test S3 connection and bucket access."""
        try:
            # Try to head the bucket to test connection
            self.s3_client.head_bucket(Bucket=self.s3_bucket_name)
            logger.debug(f"S3 connection test successful for bucket: {self.s3_bucket_name}")
        except self.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"S3 bucket '{self.s3_bucket_name}' not found")
            elif error_code == '403':
                logger.error(f"Access denied to S3 bucket '{self.s3_bucket_name}'")
            else:
                logger.error(f"S3 connection test failed: {str(e)}")
            raise
        except self.NoCredentialsError:
            logger.error("S3 credentials not found or invalid")
            raise
    
    def _get_s3_key(self, filename: str) -> str:
        """Get the full S3 key for a filename, including path prefix if configured."""
        if self.s3_path_prefix:
            # Ensure path prefix ends with / and doesn't start with /
            prefix = self.s3_path_prefix.strip('/')
            return f"{prefix}/{filename}"
        return filename
    
    def _ensure_local_dir(self, filepath: str):
        """Ensure the local directory exists for a file path."""
        directory = os.path.dirname(filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            logger.debug(f"Created local directory: {directory}")
    
    def save_json(self, data: Any, filename: str, encoding: str = 'utf-8') -> None:
        """
        Save JSON data to storage.
        
        Args:
            data: The data to save as JSON
            filename: The filename (e.g., 'var/users.json')
            encoding: Text encoding for local files (ignored for S3)
        """
        json_content = json.dumps(data, indent=2, ensure_ascii=False)
        
        if self.use_s3:
            self._save_to_s3(json_content, filename)
        else:
            self._save_to_local(json_content, filename, encoding)
    
    def _save_to_s3(self, content: str, filename: str):
        """Save content to S3."""
        try:
            s3_key = self._get_s3_key(filename)
            self.s3_client.put_object(
                Bucket=self.s3_bucket_name,
                Key=s3_key,
                Body=content.encode('utf-8'),
                ContentType='application/json'
            )
            logger.debug(f"Successfully saved {filename} to S3: s3://{self.s3_bucket_name}/{s3_key}")
        except Exception as e:
            logger.error(f"Failed to save {filename} to S3: {str(e)}")
            raise
    
    def _save_to_local(self, content: str, filename: str, encoding: str):
        """Save content to local file."""
        try:
            self._ensure_local_dir(filename)
            with open(filename, 'w', encoding=encoding) as f:
                f.write(content)
            logger.debug(f"Successfully saved {filename} to local storage")
        except Exception as e:
            logger.error(f"Failed to save {filename} to local storage: {str(e)}")
            raise
    
    def load_json(self, filename: str, encoding: str = 'utf-8') -> Any:
        """
        Load JSON data from storage.
        
        Args:
            filename: The filename (e.g., 'var/users.json')
            encoding: Text encoding for local files (ignored for S3)
            
        Returns:
            The loaded JSON data
            
        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        if self.use_s3:
            return self._load_from_s3(filename)
        else:
            return self._load_from_local(filename, encoding)
    
    def _load_from_s3(self, filename: str) -> Any:
        """Load JSON data from S3."""
        try:
            s3_key = self._get_s3_key(filename)
            response = self.s3_client.get_object(
                Bucket=self.s3_bucket_name,
                Key=s3_key
            )
            content = response['Body'].read().decode('utf-8')
            logger.debug(f"Successfully loaded {filename} from S3: s3://{self.s3_bucket_name}/{s3_key}")
            return json.loads(content)
        except self.ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"File not found in S3: {filename}")
            else:
                logger.error(f"Failed to load {filename} from S3: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Failed to load {filename} from S3: {str(e)}")
            raise
    
    def _load_from_local(self, filename: str, encoding: str) -> Any:
        """Load JSON data from local file."""
        try:
            with open(filename, 'r', encoding=encoding) as f:
                content = f.read()
            logger.debug(f"Successfully loaded {filename} from local storage")
            return json.loads(content)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {filename}")
        except Exception as e:
            logger.error(f"Failed to load {filename} from local storage: {str(e)}")
            raise
    
    def exists(self, filename: str) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            filename: The filename to check
            
        Returns:
            True if the file exists, False otherwise
        """
        if self.use_s3:
            return self._exists_in_s3(filename)
        else:
            return self._exists_locally(filename)
    
    def _exists_in_s3(self, filename: str) -> bool:
        """Check if a file exists in S3."""
        try:
            s3_key = self._get_s3_key(filename)
            self.s3_client.head_object(
                Bucket=self.s3_bucket_name,
                Key=s3_key
            )
            return True
        except self.ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.error(f"Error checking if {filename} exists in S3: {str(e)}")
                raise
    
    def _exists_locally(self, filename: str) -> bool:
        """Check if a file exists locally."""
        return os.path.exists(filename)
    
    def get_storage_info(self) -> Dict[str, Any]:
        """
        Get information about the current storage configuration.
        
        Returns:
            Dictionary with storage configuration details
        """
        if self.use_s3:
            return {
                'type': 's3',
                'bucket': self.s3_bucket_name,
                'endpoint': self.s3_endpoint_url,
                'region': self.s3_region,
                'path_prefix': self.s3_path_prefix,
                'force_path_style': self.s3_force_path_style
            }
        else:
            return {
                'type': 'local',
                'base_path': os.getcwd()
            }


# Global storage service instance
_storage_service = None


def get_storage_service() -> StorageService:
    """Get the global storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


def save_json_file(data: Any, filename: str, encoding: str = 'utf-8') -> None:
    """
    Convenience function to save JSON data using the global storage service.
    
    Args:
        data: The data to save as JSON
        filename: The filename (e.g., 'var/users.json')
        encoding: Text encoding for local files (ignored for S3)
    """
    storage = get_storage_service()
    storage.save_json(data, filename, encoding)


def load_json_file(filename: str, encoding: str = 'utf-8') -> Any:
    """
    Convenience function to load JSON data using the global storage service.
    
    Args:
        filename: The filename (e.g., 'var/users.json')
        encoding: Text encoding for local files (ignored for S3)
        
    Returns:
        The loaded JSON data
    """
    storage = get_storage_service()
    return storage.load_json(filename, encoding)


def file_exists(filename: str) -> bool:
    """
    Convenience function to check if a file exists using the global storage service.
    
    Args:
        filename: The filename to check
        
    Returns:
        True if the file exists, False otherwise
    """
    storage = get_storage_service()
    return storage.exists(filename) 