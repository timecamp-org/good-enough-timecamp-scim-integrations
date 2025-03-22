import os
from typing import Optional, Set
from dotenv import load_dotenv
from dataclasses import dataclass

@dataclass
class TimeCampConfig:
    """Configuration for TimeCamp integration."""
    api_key: str
    domain: str
    root_group_id: int
    ignored_user_ids: Set[int]
    show_external_id: bool
    skip_departments: str

    @classmethod
    def from_env(cls) -> 'TimeCampConfig':
        """Create configuration from environment variables."""
        load_dotenv()
        
        api_key = os.getenv('TIMECAMP_API_KEY')
        if not api_key:
            raise ValueError("Missing TIMECAMP_API_KEY environment variable")
            
        root_group_id = os.getenv('TIMECAMP_ROOT_GROUP_ID')
        if not root_group_id:
            raise ValueError("Missing TIMECAMP_ROOT_GROUP_ID environment variable")
            
        # Parse other environment variables
        domain = os.getenv('TIMECAMP_DOMAIN', 'app.timecamp.com')
        ignored_user_ids_str = os.getenv('TIMECAMP_IGNORED_USER_IDS', '')
        show_external_id = os.getenv('TIMECAMP_SHOW_EXTERNAL_ID', 'true').lower() == 'true'
        skip_departments = os.getenv('TIMECAMP_SKIP_DEPARTMENTS', '').strip()
        
        # Parse ignored user IDs
        ignored_user_ids = {
            int(uid.strip()) 
            for uid in ignored_user_ids_str.split(',') 
            if uid.strip()
        }
        
        return cls(
            api_key=api_key,
            domain=domain,
            root_group_id=int(root_group_id),
            ignored_user_ids=ignored_user_ids,
            show_external_id=show_external_id,
            skip_departments=skip_departments
        )

def clean_name(name: Optional[str]) -> str: # bug in TimeCamp API - it doesn't accept some special characters
    """Clean special characters from name."""
    if not name:
        return ""
        
    # Replace or remove special characters
    replacements = {
        "'": "",
        "(": "",
        ")": "",
        "[": "",
        "]": "",
        "{": "",
        "}": "",
        "`": "",
        "´": "",
        """: "",
        """: "",
        "'": "",
        "'": "",
    }
    result = str(name)
    for char, replacement in replacements.items():
        result = result.replace(char, replacement)
    return result.strip()

def get_users_file() -> str:
    """Get the users JSON file path."""
    if not os.path.exists("users.json"):
        raise FileNotFoundError("users.json file not found. Please run the integration script first.")
    return "users.json"

def clean_department_path(path: Optional[str], config: Optional[TimeCampConfig] = None) -> str:
    """Clean and normalize department path. If config is provided with skip_departments, remove those prefixes."""
    if not path:
        return ""
        
    normalized_path = '/'.join(part.strip() for part in path.split('/') if part.strip())
    
    # Skip departments if config is provided and skip_departments is set
    if config and config.skip_departments and config.skip_departments.strip():
        skip_prefix = config.skip_departments.strip()
        if normalized_path.startswith(skip_prefix):
            if normalized_path == skip_prefix:
                return ""
            return normalized_path[len(skip_prefix) + 1:]  # +1 for the trailing slash
            
    return normalized_path 