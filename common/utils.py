import os
from typing import Optional, Set, Dict, Any
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
    use_supervisor_groups: bool
    use_department_groups: bool
    disable_new_users: bool
    disable_external_id_sync: bool
    disable_manual_user_updates: bool
    use_job_title_name: bool
    replace_email_domain: str
    use_is_supervisor_role: bool

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
        use_supervisor_groups = os.getenv('TIMECAMP_USE_SUPERVISOR_GROUPS', 'false').lower() == 'true'
        use_department_groups = os.getenv('TIMECAMP_USE_DEPARTMENT_GROUPS', 'true').lower() == 'true'
        disable_new_users = os.getenv('TIMECAMP_DISABLE_NEW_USERS', 'false').lower() == 'true'
        disable_external_id_sync = os.getenv('TIMECAMP_DISABLE_EXTERNAL_ID_SYNC', 'false').lower() == 'true'
        disable_manual_user_updates = os.getenv('TIMECAMP_DISABLE_MANUAL_USER_UPDATES', 'false').lower() == 'true'
        use_job_title_name = os.getenv('TIMECAMP_USE_JOB_TITLE_NAME', 'false').lower() == 'true'
        replace_email_domain = os.getenv('TIMECAMP_REPLACE_EMAIL_DOMAIN', '').strip()
        use_is_supervisor_role = os.getenv('TIMECAMP_USE_IS_SUPERVISOR_ROLE', 'false').lower() == 'true'
        
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
            skip_departments=skip_departments,
            use_supervisor_groups=use_supervisor_groups,
            use_department_groups=use_department_groups,
            disable_new_users=disable_new_users,
            disable_external_id_sync=disable_external_id_sync,
            disable_manual_user_updates=disable_manual_user_updates,
            use_job_title_name=use_job_title_name,
            replace_email_domain=replace_email_domain,
            use_is_supervisor_role=use_is_supervisor_role
        )

def clean_name(name: Optional[str]) -> str: # bug in TimeCamp API - it doesn't accept some special characters
    """Clean special characters from name."""
    if not name:
        return ""
        
    # Replace or remove special characters
    replacements = {
        "(": "",
        ")": "",
        "{": "",
        "}": "",
        "`": "",
        "´": "",
        """: "",
        """: "",
        "_": "",
    }
    result = str(name)
    for char, replacement in replacements.items():
        result = result.replace(char, replacement)
    return result.strip()

def get_users_file() -> str:
    """Get the users JSON file path and verify it exists."""
    from .storage import file_exists
    
    filename = "var/users.json"
    if not file_exists(filename):
        raise FileNotFoundError("var/users.json file not found. Please run the integration script first.")
    return filename

def clean_department_path(path: Optional[str], config: Optional[TimeCampConfig] = None) -> str:
    """Clean and normalize department path. If config is provided with skip_departments, remove those prefixes."""
    if not path:
        return ""
        
    normalized_path = '/'.join(part.strip() for part in path.split('/') if part.strip())
    
    # Skip departments if config is provided and skip_departments is set
    if config and config.skip_departments and config.skip_departments.strip():
        skip_departments_str = config.skip_departments.strip()
        
        # Parse comma-separated list of prefixes to skip
        skip_prefixes = [prefix.strip() for prefix in skip_departments_str.split(',') if prefix.strip()]
        
        # Try each skip prefix until we find a match
        for skip_prefix in skip_prefixes:
            # Check if the normalized path exactly matches the skip_departments
            if normalized_path == skip_prefix:
                return ""
                
            # Check if it's a prefix, but only if it's a full component match
            # For example: if skip is "foo" and path is "foo/bar", it will match
            # but if skip is "fo" and path is "foo/bar", it won't match
            parts = normalized_path.split('/')
            skip_parts = skip_prefix.split('/')
            
            # Only match if all skip parts match exactly the beginning of the path
            if (len(parts) >= len(skip_parts) and 
                all(parts[i] == skip_parts[i] for i in range(len(skip_parts)))):
                return '/'.join(parts[len(skip_parts):])
            
    return normalized_path 