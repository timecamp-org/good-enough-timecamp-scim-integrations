import os
import json
import time
import argparse
import requests
from dotenv import load_dotenv
from common.logger import setup_logger
from typing import Optional, Dict, List, Any, Set

logger = setup_logger()

class TimeCampAPI:
    def __init__(self, api_key: str, domain: str = "app.timecamp.com"):
        self.api_key = api_key
        self.base_url = f"https://{domain}/third_party/api"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        self.params = {}

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an API request with universal error handling."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Merge default params with custom params if provided
        if 'params' in kwargs:
            params = {**self.params, **kwargs.pop('params')}
        else:
            params = self.params
            
        max_retries = 5
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=self.headers,
                    params=params,
                    **kwargs
                )
                logger.debug(f"API {method} {url}")
                # logger.debug(f"Request params: {params}")
                # logger.debug(f"Request data: {kwargs.get('data', kwargs.get('json', {}))}")
                # logger.debug(f"Response status: {response.status_code}")
                # logger.debug(f"Response content: {response.text}")
                
                if response.status_code == 429:  # Rate limit exceeded
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)  # Exponential backoff
                        logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                if getattr(e.response, 'status_code', None) == 429 and attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)  # Exponential backoff
                    logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}")
                    time.sleep(wait_time)
                    continue
                    
                logger.error(f"API Error: {method} {url}")
                logger.error(f"Status code: {getattr(e.response, 'status_code', 'N/A')}")
                logger.error(f"Response content: {getattr(e.response, 'text', str(e))}")
                raise
        
        # If we get here, we've exhausted all retries
        raise requests.exceptions.RequestException(f"Failed after {max_retries} retries due to rate limiting")

    def get_group_users(self, group_id: int) -> List[Dict[str, Any]]:
        """Get users in a specific group."""
        response = self._make_request('GET', f"group/{group_id}/user")
        return response.json()

    def _batch_user_ids(self, user_ids: List[int], batch_size: int = 50) -> List[List[int]]:
        """Split user IDs into batches."""
        return [user_ids[i:i + batch_size] for i in range(0, len(user_ids), batch_size)]

    def is_user_enabled(self, user_id: int) -> bool:
        """Check if a user is enabled (single user version)."""
        return self.are_users_enabled([user_id])[user_id]

    def are_users_enabled(self, user_ids: List[int]) -> Dict[int, bool]:
        """Check if multiple users are enabled in bulk.
        
        Args:
            user_ids: List of user IDs to check
            
        Returns:
            Dictionary mapping user IDs to their enabled status
        """
        result = {}
        batches = self._batch_user_ids(user_ids)
        
        for batch in batches:
            params = {
                **self.params,
                "name[]": "disabled_user"
            }
            batch_ids = ",".join(str(uid) for uid in batch)
            response = self._make_request('GET', f"user/{batch_ids}/setting", params=params)
            settings = response.json()
            
            # Process the batch response
            for user_id in batch:
                user_settings = [
                    s for s in settings 
                    if int(s['userId']) == user_id 
                    and str(s['name']) == "disabled_user"
                ]
                # User is enabled if there's no disabled_user setting or if it's not set to "1"
                result[user_id] = not (user_settings and str(user_settings[0]['value']) == "1")
        
        return result

    def get_users(self) -> List[Dict[str, Any]]:
        """Get all users with their group information."""
        logger.debug(f"Fetching users from {self.base_url}/users")
        response = self._make_request('GET', "users")
        entries = response.json()

        # Get group information for each user
        groups = {}
        for entry in entries:
            groups[entry['group_id']] = {}

        for group_id in groups:
            group_users = self.get_group_users(group_id)
            for group_user in group_users:
                groups[group_id][group_user['user_id']] = group_user

        # Enrich user data with group information and check enabled status in bulk
        user_ids = [int(entry['user_id']) for entry in entries]
        enabled_statuses = self.are_users_enabled(user_ids)

        for entry in entries:
            group_id = entry['group_id']
            user_id = int(entry['user_id'])
            
            if group_id in groups and str(user_id) in groups[group_id]:
                group_info = groups[group_id][str(user_id)]
                role = group_info['role_id']
                entry['is_manager'] = role in [1, 2]
                entry['is_enabled'] = enabled_statuses[user_id]

        return entries

    def get_groups(self) -> List[Dict[str, Any]]:
        """Get all groups."""
        response = self._make_request('GET', "group")
        return response.json()

    def add_user(self, email: str, name: str, group_id: int) -> Dict[str, Any]:
        """Add a new user to TimeCamp."""
        data = {
            "tt_global_admin": "0",
            "tt_can_create_level_1_tasks": "0",
            "can_view_rates": "0",
            "add_to_all_projects": "0",
            "send_email": "0",
            "email": [str(email)]
        }
        response = self._make_request('POST', f"group/{group_id}/user", json=data)
        return response.json()

    def update_group_parent(self, group_id: int, parent_id: int) -> None:
        """Update a group's parent."""
        data = {
            "group_id": str(group_id),
            "parent_id": str(parent_id)
        }
        self._make_request('POST', "group", json=data)

    def update_user_setting(self, user_id: int, name: str, value: str) -> None:
        """Update a user setting."""
        data = {
            "name": str(name),
            "value": str(value)
        }
        self._make_request('PUT', f"user/{user_id}/setting", json=data)

    def update_user(self, user_id: int, fields: Dict[str, Any], current_group_id: Optional[int] = None) -> None:
        """Update user information."""
        if 'fullName' in fields:
            data = {
                "display_name": str(fields['fullName']),
                "user_id": str(user_id)
            }
            self._make_request('POST', "user", json=data)

        if 'isManager' in fields and current_group_id:
            role_id = "2" if fields['isManager'] else "3"  # 2 for manager, 3 for user
            data = {
                "role_id": role_id,
                "user_id": str(user_id)
            }
            self._make_request('PUT', f"group/{current_group_id}/user", json=data)

        if 'groupId' in fields and current_group_id:
            data = {
                "group_id": str(fields['groupId']),
                "user_id": str(user_id)
            }
            self._make_request('PUT', f"group/{current_group_id}/user", json=data)

    def add_group(self, name: str, parent_id: int) -> str:
        """Add a new group."""
        data = {
            "name": str(name),
            "parent_id": str(parent_id)
        }
        max_retries = 5
        retry_delay = 15  # seconds
        
        for attempt in range(max_retries):
            try:
                response = self._make_request('PUT', "group", data=json.dumps(data))
                response_data = response.json()
                return str(response_data.get("group_id"))
            except requests.exceptions.HTTPError:
                if attempt < max_retries - 1:
                    logger.debug(f"Attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise

class GroupSynchronizer:
    def __init__(self, api: TimeCampAPI, root_group_id: int):
        self.api = api
        self.root_group_id = root_group_id

    def _build_group_paths(self, groups: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Build a map of full group paths and their details.
        
        Returns:
            Dictionary mapping full paths to group details including:
            - group_id: TimeCamp group ID
            - name: Group name (last part of path)
            - parent_path: Full path of parent group
            - parent_id: TimeCamp parent group ID
        """
        # First, create a map of group IDs to their details
        groups_by_id = {str(g['group_id']): {**g, 'name': g['name'].strip()} for g in groups}
        path_map = {}
        
        for group in groups:
            # Build full path by traversing up the parent chain
            path_parts = []
            current = group
            while current:
                path_parts.insert(0, current['name'].strip())
                parent_id = current.get('parent_id')
                current = groups_by_id.get(str(parent_id))
            
            full_path = '/'.join(path_parts)
            parent_path = '/'.join(path_parts[:-1]) if len(path_parts) > 1 else None
            
            path_map[full_path] = {
                'group_id': group['group_id'],
                'name': group['name'].strip(),
                'parent_path': parent_path,
                'parent_id': group.get('parent_id')
            }
            
        return path_map

    def sync_structure(self, department_paths: Set[str], dry_run: bool = False) -> Dict[str, Dict[str, Any]]:
        """Synchronize the entire group structure.
        
        Args:
            department_paths: Set of all department paths needed
            dry_run: Whether to actually make changes
            
        Returns:
            Dictionary mapping department paths to their details
        """
        # Get current group structure
        current_groups = self.api.get_groups()
        current_paths = self._build_group_paths(current_groups)
        
        # Create a map of groups by their IDs for quick lookup
        groups_by_id = {str(g['group_id']): g for g in current_groups}
        
        # Create a map of groups by their names for each parent_id
        groups_by_parent: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for group in current_groups:
            parent_id = str(group.get('parent_id', '0'))
            if parent_id not in groups_by_parent:
                groups_by_parent[parent_id] = {}
            groups_by_parent[parent_id][group['name'].strip()] = group
        
        # Sort paths to ensure parent groups are created first
        sorted_paths = sorted(department_paths, key=lambda x: len(x.split('/')))
        
        for full_path in sorted_paths:
            if not full_path:  # Skip empty paths
                continue
                
            if full_path in current_paths:
                logger.debug(f"Group already exists: {full_path}")
                continue
                
            # Split path and get parent info
            parts = [p.strip() for p in full_path.split('/') if p.strip()]
            
            # Create each part of the path if it doesn't exist
            current_path = ''
            parent_id = str(self.root_group_id)
            
            for i, part in enumerate(parts):
                if current_path:
                    current_path += '/'
                current_path += part
                
                # Check if group exists under current parent
                existing_group = groups_by_parent.get(parent_id, {}).get(part)
                
                if existing_group:
                    # Use existing group
                    group_id = existing_group['group_id']
                    current_paths[current_path] = {
                        'group_id': group_id,
                        'name': part,
                        'parent_path': '/'.join(parts[:i]) if i > 0 else None,
                        'parent_id': parent_id
                    }
                    parent_id = str(group_id)
                else:
                    # Create new group
                    if not dry_run:
                        logger.info(f"Creating group: {part} in path {current_path}")
                        group_id = self.api.add_group(part, int(parent_id))
                        
                        # Add to our maps
                        group_info = {
                            'group_id': group_id,
                            'name': part,
                            'parent_path': '/'.join(parts[:i]) if i > 0 else None,
                            'parent_id': parent_id
                        }
                        current_paths[current_path] = group_info
                        
                        if parent_id not in groups_by_parent:
                            groups_by_parent[parent_id] = {}
                        groups_by_parent[parent_id][part] = {
                            'group_id': group_id,
                            'name': part,
                            'parent_id': parent_id
                        }
                        
                        parent_id = str(group_id)
                    else:
                        current_paths[current_path] = {
                            'group_id': -1,
                            'name': part,
                            'parent_path': '/'.join(parts[:i]) if i > 0 else None,
                            'parent_id': parent_id
                        }
                        parent_id = '-1'
            
        return current_paths

def get_users_file():
    """Get the users JSON file path."""
    if not os.path.exists("users.json"):
        raise FileNotFoundError("users.json file not found. Please run the integration script first.")
    return "users.json"

def clean_name(name: Optional[str]) -> str:
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

def sync_users(dry_run=False):
    """Synchronize users with TimeCamp."""
    try:
        load_dotenv()
        
        # Get environment variables
        api_key = os.getenv('TIMECAMP_API_KEY')
        domain = os.getenv('TIMECAMP_DOMAIN', 'app.timecamp.com')
        ignored_user_ids_str = os.getenv('TIMECAMP_IGNORED_USER_IDS', '')
        root_group_id = int(os.getenv('TIMECAMP_ROOT_GROUP_ID'))
        show_external_id = os.getenv('TIMECAMP_SHOW_EXTERNAL_ID', 'true').lower() == 'true'
        
        if not api_key:
            raise ValueError("Missing TIMECAMP_API_KEY environment variable")
        
        if not root_group_id:
            raise ValueError("Missing TIMECAMP_ROOT_GROUP_ID environment variable")
        
        # Parse ignored user IDs
        ignored_user_ids = set()
        if ignored_user_ids_str:
            ignored_user_ids = {int(uid.strip()) for uid in ignored_user_ids_str.split(',') if uid.strip()}
            logger.debug(f"Ignoring user IDs: {ignored_user_ids}")
        
        logger.debug(f"Using API key: {api_key[:4]}...{api_key[-4:]}")
        logger.debug(f"Using domain: {domain}")
        logger.debug(f"Using root group ID: {root_group_id}")
        
        # Initialize TimeCamp client and group synchronizer
        timecamp = TimeCampAPI(api_key, domain)
        group_sync = GroupSynchronizer(timecamp, root_group_id)
        
        # Get users file
        users_file = get_users_file()
        logger.info(f"Using users file: {users_file}")
        
        # Read source users
        with open(users_file, 'r') as f:
            source_data = json.load(f)
        
        # Clean up department names and collect all unique department paths
        department_paths = set()
        for user in source_data['users']:
            if user.get('department'):
                user['department'] = '/'.join(part.strip() for part in user['department'].split('/') if part.strip())
                if user['department']:  # Only add non-empty paths
                    department_paths.add(user['department'])
            # Format and clean user name
            if show_external_id and user.get('external_id'):
                user['name'] = clean_name(f"{user['name']} - {user['external_id']}")
            else:
                user['name'] = clean_name(user['name'])
        
        source_users = {user['email']: user for user in source_data['users']}
        
        # Synchronize group structure first
        logger.info("Synchronizing group structure")
        group_structure = group_sync.sync_structure(department_paths, dry_run)
        
        # Get current TimeCamp users
        timecamp_users = timecamp.get_users()
        timecamp_users_map = {user['email']: user for user in timecamp_users}
        
        # Clean display names in TimeCamp users
        for user in timecamp_users:
            user['display_name'] = clean_name(user['display_name'])
        
        # Get current groups and build path map for existing users
        current_groups = timecamp.get_groups()
        current_paths = group_sync._build_group_paths(current_groups)
        
        # Find root group name
        root_group_name = next(
            (group['name'] for group in current_groups 
             if str(group['group_id']) == str(root_group_id)),
            None
        )
        
        # Add group paths to users
        for user in timecamp_users:
            group_id = user['group_id']
            full_path = next(
                (path for path, details in current_paths.items() 
                 if str(details['group_id']) == str(group_id)),
                None
            )
            # Remove root group name from path if present
            if full_path and root_group_name and full_path.startswith(f"{root_group_name}/"):
                user['group_path'] = full_path[len(root_group_name)+1:]
            else:
                user['group_path'] = full_path
        
        # Process users
        for email, source_user in source_users.items():
            try:
                department = source_user['department']
                group_info = group_structure.get(department) if department else None
                
                if email in timecamp_users_map:
                    # Update existing user
                    tc_user = timecamp_users_map[email]
                    
                    # Skip if user is in ignored list
                    if int(tc_user['user_id']) in ignored_user_ids:
                        logger.debug(f"Skipping ignored user: {email} (ID: {tc_user['user_id']})")
                        continue
                        
                    updates = {}
                    changes = []
                    
                    # Check if name needs updating
                    if tc_user['display_name'] != source_user['name']:
                        updates['fullName'] = source_user['name']
                        changes.append(f"name from '{tc_user['display_name']}' to '{source_user['name']}'")
                    
                    # Check if user should be activated
                    if source_user.get('status', '').lower() == 'active' and not tc_user.get('is_enabled', True):
                        if not dry_run:
                            logger.info(f"Activating user: {email} ({tc_user.get('display_name', 'unknown name')})")
                            timecamp.update_user_setting(tc_user['user_id'], 'disabled_user', '0')
                        else:
                            logger.info(f"[DRY RUN] Would activate user: {email} ({tc_user.get('display_name', 'unknown name')})")
                    
                    # Check if group needs updating
                    if group_info:
                        current_group_path = tc_user.get('group_path')
                        if current_group_path != department:
                            logger.debug(f"User {email} current group: {current_group_path}, target group: {department}")
                            updates['groupId'] = group_info['group_id']
                            changes.append(f"group from '{current_group_path or 'unknown'}' to '{department}'")
                    
                    if updates:
                        if not dry_run:
                            logger.info(f"Updating user {email}: {', '.join(changes)}")
                            timecamp.update_user(tc_user['user_id'], updates, tc_user['group_id'])
                        else:
                            logger.info(f"[DRY RUN] Would update user {email}: {', '.join(changes)}")
                else:
                    # Create new user only if status is active
                    if source_user.get('status', '').lower() == 'active':
                        if not dry_run:
                            logger.info(f"Creating new user: {email} ({source_user['name']}) in group '{department or 'root'}'")
                            timecamp.add_user(email, source_user['name'], group_info['group_id'] if group_info else root_group_id)
                        else:
                            logger.info(f"[DRY RUN] Would create user: {email} ({source_user['name']}) in group '{department or 'root'}'")
                    else:
                        logger.debug(f"Skipping creation of inactive user: {email} (status: {source_user.get('status', 'unknown')})")

            except requests.exceptions.RequestException as e:
                logger.error(f"Error processing user {email}: {str(e)}")
        
        # Handle user deactivation
        for email, tc_user in timecamp_users_map.items():
            # Skip if user is in ignored list
            if int(tc_user['user_id']) in ignored_user_ids:
                logger.debug(f"Skipping ignored user for deactivation: {email} (ID: {tc_user['user_id']})")
                continue
                
            should_deactivate = False
            deactivation_reason = None
            
            # Check if user exists in source and is active
            if email not in source_users:
                should_deactivate = True
                deactivation_reason = "not present in users.json"
            elif source_users[email].get('status', '').lower() != 'active':
                should_deactivate = True
                deactivation_reason = f"status is {source_users[email].get('status', 'unknown')}"
            
            if should_deactivate and tc_user.get('is_enabled', True):
                if not dry_run:
                    logger.info(f"Deactivating user: {email} ({tc_user.get('display_name', 'unknown name')}) - Reason: {deactivation_reason}")
                    timecamp.update_user_setting(tc_user['user_id'], 'disabled_user', '1')
                else:
                    logger.info(f"[DRY RUN] Would deactivate user: {email} ({tc_user.get('display_name', 'unknown name')}) - Reason: {deactivation_reason}")
        
        logger.info("Synchronization completed successfully")
        
    except Exception as e:
        logger.error(f"Error during synchronization: {str(e)}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synchronize users with TimeCamp")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without making changes")
    args = parser.parse_args()
    
    logger.info("Starting synchronization")
    sync_users(dry_run=args.dry_run) 