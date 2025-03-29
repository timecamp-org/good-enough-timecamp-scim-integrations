import time
import requests
from typing import Dict, List, Any, Optional
from common.logger import setup_logger
from common.utils import TimeCampConfig

logger = setup_logger('timecamp_sync')

class TimeCampAPI:
    def __init__(self, config: TimeCampConfig):
        self.base_url = f"https://{config.domain}/third_party/api"
        self.headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {config.api_key}"}

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        max_retries, retry_delay = 5, 5
        
        logger.debug(f"API Request: {method} {url}")
        # logger.debug(f"Headers: {self.headers}")
        # if 'json' in kwargs:
        #     logger.debug(f"Request JSON: {kwargs['json']}")
        # if 'params' in kwargs:
        #     logger.debug(f"Request params: {kwargs['params']}")
        
        for attempt in range(max_retries):
            try:
                response = requests.request(method, url, headers=self.headers, **kwargs)
                logger.debug(f"Response status: {response.status_code}")
                # logger.debug(f"Response headers: {dict(response.headers)}")
                # logger.debug(f"Response content: {response.text[:1000]}")  # First 1000 chars to avoid huge logs
                
                if response.status_code == 429 and attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if getattr(e.response, 'status_code', None) == 429 and attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                logger.error(f"API Error: {method} {url} - Status: {getattr(e.response, 'status_code', 'N/A')}")
                if hasattr(e.response, 'text'):
                    logger.error(f"Error response: {e.response.text}")
                raise
        raise requests.exceptions.RequestException(f"Failed after {max_retries} retries")

    def get_users(self) -> List[Dict[str, Any]]:
        """Get all users with their enabled status."""
        users = self._make_request('GET', "users").json()
        # logger.debug(f"Users: {users}")

        # Get enabled status for all users in bulk
        user_ids = [int(user['user_id']) for user in users]
        enabled_statuses = self.are_users_enabled(user_ids)
        
        # Add enabled status to each user
        for user in users:
            user['is_enabled'] = enabled_statuses.get(int(user['user_id']), True)
        
        return users

    def get_groups(self) -> List[Dict[str, Any]]:
        return self._make_request('GET', "group").json()

    def get_group_users(self, group_id: int) -> List[Dict[str, Any]]:
        return self._make_request('GET', f"group/{group_id}/user").json()

    def add_group(self, name: str, parent_id: int) -> str:
        """Add a new group with retries for 403 errors."""
        data = {"name": str(name), "parent_id": str(parent_id)}
        max_retries = 10  # More retries for group creation
        retry_delay = 15  # Longer delay between retries
        
        for attempt in range(max_retries):
            try:
                response = self._make_request('PUT', "group", json=data)
                return str(response.json()["group_id"])
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403 and attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    logger.warning(f"Got 403 error when creating group '{name}'. Attempt {attempt + 1}/{max_retries}. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                raise
            except Exception as e:
                logger.error(f"Error creating group '{name}': {str(e)}")
                raise
        
        raise requests.exceptions.HTTPError(f"Failed to create group '{name}' after {max_retries} retries")

    def add_user(self, email: str, name: str, group_id: int) -> Dict[str, Any]:
        data = {"email": [email], "tt_global_admin": "0", "tt_can_create_level_1_tasks": "0", 
                "can_view_rates": "0", "add_to_all_projects": "0", "send_email": "0"}
        return self._make_request('POST', f"group/{group_id}/user", json=data).json()

    def update_user(self, user_id: int, updates: Dict[str, Any], group_id: int) -> None:
        if 'fullName' in updates:
            self._make_request('POST', "user", json={"display_name": updates['fullName'], "user_id": str(user_id)})
        if 'groupId' in updates:
            self._make_request('PUT', f"group/{group_id}/user", json={"group_id": str(updates['groupId']), "user_id": str(user_id)})
        if 'isManager' in updates:
            self._make_request('PUT', f"group/{group_id}/user", 
                             json={"role_id": "2" if updates['isManager'] else "3", "user_id": str(user_id)})

    def update_user_setting(self, user_id: int, name: str, value: str) -> None:
        self._make_request('PUT', f"user/{user_id}/setting", json={"name": name, "value": value})

    def set_additional_email(self, user_id: int, email: str) -> None:
        """Set additional email for a user."""
        self._make_request('PUT', f"user/{user_id}/setting", json={"name": "additional_email", "value": email})

    def get_additional_emails(self, user_ids: List[int], batch_size: int = 50) -> Dict[int, Optional[str]]:
        """Get additional email settings for multiple users in bulk."""
        result = {}
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i:i + batch_size]
            response = self._make_request('GET', f"user/{','.join(map(str, batch))}/setting", 
                                        params={"name[]": "additional_email"})
            settings = response.json()
            
            # Handle both possible API response formats
            if isinstance(settings, dict):
                # New API format where settings is a dict with user_id keys
                for user_id in batch:
                    user_settings = settings.get(str(user_id), [])
                    if isinstance(user_settings, list):
                        additional_email = next(
                            (s.get('value') for s in user_settings 
                             if s.get('name') == 'additional_email'),
                            None
                        )
                        result[user_id] = additional_email
                    else:
                        result[user_id] = None
            else:
                # Old API format where settings is a list
                for user_id in batch:
                    user_settings = [s for s in settings 
                                   if str(s.get('userId', '')) == str(user_id) 
                                   and s.get('name') == 'additional_email']
                    result[user_id] = user_settings[0].get('value') if user_settings else None
        
        return result

    def are_users_enabled(self, user_ids: List[int], batch_size: int = 50) -> Dict[int, bool]:
        """Check if multiple users are enabled in bulk."""
        result = {}
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i:i + batch_size]
            response = self._make_request('GET', f"user/{','.join(map(str, batch))}/setting", 
                                        params={"name[]": "disabled_user"})
            settings = response.json()
            
            # Handle both possible API response formats
            if isinstance(settings, dict):
                # New API format where settings is a dict with user_id keys
                for user_id in batch:
                    user_settings = settings.get(str(user_id), [])
                    if isinstance(user_settings, list):
                        disabled = any(s.get('name') == 'disabled_user' and str(s.get('value')) == '1' 
                                     for s in user_settings)
                        result[user_id] = not disabled
                    else:
                        # If no settings or invalid format, assume user is enabled
                        result[user_id] = True
            else:
                # Old API format where settings is a list
                for user_id in batch:
                    user_settings = [s for s in settings 
                                   if str(s.get('userId', '')) == str(user_id) 
                                   and s.get('name') == 'disabled_user']
                    result[user_id] = not (user_settings and str(user_settings[0].get('value', '0')) == '1')
        
        return result 

    def get_user_roles(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get roles for all users across all groups.
        
        Returns:
            Dict mapping user_id to list of group assignments with their role_ids
            Example: {
                "1234": [{"group_id": "5678", "role_id": "2"}]
            }
        """
        response = self._make_request('GET', "people_picker")
        data = response.json()
        
        user_roles = {}
        
        # Process groups and their users
        for group_key, group_data in data.get('groups', {}).items():
            group_id = group_data.get('group_id')
            users = group_data.get('users', {})
            
            # Handle different format of users (dict vs list)
            if isinstance(users, dict):
                for user_id, user_data in users.items():
                    if user_id not in user_roles:
                        user_roles[user_id] = []
                    
                    user_roles[user_id].append({
                        'group_id': group_id,
                        'role_id': user_data.get('role_id')
                    })
            elif isinstance(users, list):
                # Empty users list or alternative format
                pass
        
        return user_roles 