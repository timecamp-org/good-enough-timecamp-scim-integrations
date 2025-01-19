import os
import json
import time
import argparse
import requests
import demjson3
from dotenv import load_dotenv
from common.logger import setup_logger
from typing import Optional, Dict, List, Any

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

    def get_group_users(self, group_id: int) -> List[Dict[str, Any]]:
        """Get users in a specific group."""
        response = requests.get(
            f"{self.base_url}/group/{group_id}/user",
            headers=self.headers,
            params=self.params
        )
        response.raise_for_status()
        return response.json()

    def is_user_enabled(self, user_id: int) -> bool:
        """Check if a user is enabled."""
        params = {**self.params, "name[]": "disabled_user"}
        response = requests.get(
            f"{self.base_url}/user/{user_id}/setting",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        settings = response.json()
        return not (
            int(settings['userId']) == user_id and 
            str(settings['name']) == "disabled_user" and 
            str(settings['value']) == "1"
        )

    def get_users(self) -> List[Dict[str, Any]]:
        """Get all users with their group information."""
        logger.debug(f"Fetching users from {self.base_url}/users")
        response = requests.get(
            f"{self.base_url}/users",
            headers=self.headers,
            params=self.params
        )
        # logger.debug(f"API Response Status: {response.status_code}")
        # logger.debug(f"API Response Content: {response.content}")
        response.raise_for_status()
        entries = response.json()

        # Get group information for each user
        groups = {}
        for entry in entries:
            groups[entry['group_id']] = {}

        for group_id in groups:
            group_users = self.get_group_users(group_id)
            for group_user in group_users:
                groups[group_id][group_user['user_id']] = group_user

        # Enrich user data with group information
        for entry in entries:
            group_id = entry['group_id']
            user_id = entry['user_id']
            if group_id in groups and user_id in groups[group_id]:
                group_info = groups[group_id][user_id]
                role = group_info['role_id']
                entry['is_manager'] = role in [1, 2]
                entry['is_enabled'] = self.is_user_enabled(int(user_id))

        return entries

    def get_groups(self) -> List[Dict[str, Any]]:
        """Get all groups."""
        response = requests.get(
            f"{self.base_url}/group",
            headers=self.headers,
            params=self.params
        )
        response.raise_for_status()
        return response.json()

    def add_user(self, email: str, name: str, group_id: int) -> Dict[str, Any]:
        """Add a new user to TimeCamp."""
        data = {
            "tt_global_admin": "0",
            "tt_can_create_level_1_tasks": "0",
            "can_view_rates": "0",
            "add_to_all_projects": "0",
            "send_email": "0",
            "email[]": str(email)
        }
        response = requests.post(
            f"{self.base_url}/group/{group_id}/user",
            headers=self.headers,
            params=self.params,
            json=data
        )
        response.raise_for_status()
        return response.json()

    def update_group_parent(self, group_id: int, parent_id: int) -> None:
        """Update a group's parent."""
        data = {
            "group_id": str(group_id),
            "parent_id": str(parent_id)
        }
        response = requests.post(
            f"{self.base_url}/group",
            headers=self.headers,
            params=self.params,
            json=data
        )
        response.raise_for_status()

    def update_user_setting(self, user_id: int, name: str, value: str) -> None:
        """Update a user setting."""
        data = {
            "name": str(name),
            "value": str(value)
        }
        response = requests.put(
            f"{self.base_url}/user/{user_id}/setting",
            headers=self.headers,
            params=self.params,
            json=data
        )
        response.raise_for_status()

    def update_user(self, user_id: int, fields: Dict[str, Any], group_id: Optional[int] = None) -> None:
        """Update user information."""
        if 'fullName' in fields:
            data = {
                "display_name": str(fields['fullName']),
                "user_id": str(user_id)
            }
            response = requests.post(
                f"{self.base_url}/user",
                headers=self.headers,
                params=self.params,
                json=data
            )
            response.raise_for_status()

        if 'isManager' in fields and group_id:
            role_id = "2" if fields['isManager'] else "3"  # 2 for manager, 3 for user
            data = {
                "role_id": role_id,
                "user_id": str(user_id)
            }
            response = requests.put(
                f"{self.base_url}/group/{group_id}/user",
                headers=self.headers,
                params=self.params,
                json=data
            )
            response.raise_for_status()

        if 'groupId' in fields and group_id:
            data = {
                "group_id": str(fields['groupId']),
                "user_id": str(user_id)
            }
            response = requests.put(
                f"{self.base_url}/group/{group_id}/user",
                headers=self.headers,
                params=self.params,
                json=data
            )
            response.raise_for_status()

    def add_group(self, name: str, parent_id: int) -> str:
        """Add a new group."""
        data = {
            "name": str(name),
            "parent_id": str(parent_id)
        }
        json_data = demjson3.encode(data)  # This ensures proper JSON formatting
        logger.debug(f"Adding group with data: {json_data}")
        logger.debug(f"Request URL: {self.base_url}/group")
        # logger.debug(f"Request headers: {self.headers}")
        logger.debug(f"Request params: {self.params}")
        
        max_retries = 5
        retry_delay = 15  # seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.put(
                    f"{self.base_url}/group",
                    headers=self.headers,
                    params=self.params,
                    data=json_data  # Send the properly formatted JSON string
                )
                
                logger.debug(f"Response status: {response.status_code}")
                # logger.debug(f"Response headers: {dict(response.headers)}")
                logger.debug(f"Response content: {response.text}")
                
                response.raise_for_status()
                response_data = response.json()
                group_id = str(response_data.get("group_id"))
                return group_id
            except requests.exceptions.HTTPError as e:
                if attempt < max_retries - 1:
                    logger.debug(f"Attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise

def get_users_file():
    """Get the users JSON file path."""
    if not os.path.exists("users.json"):
        raise FileNotFoundError("users.json file not found. Please run the integration script first.")
    return "users.json"

def sync_users(dry_run=False):
    """Synchronize users with TimeCamp."""
    try:
        load_dotenv()
        
        # Get environment variables
        api_key = os.getenv('TIMECAMP_API_KEY')
        domain = os.getenv('TIMECAMP_DOMAIN', 'app.timecamp.com')
        ignored_user_ids_str = os.getenv('TIMECAMP_IGNORED_USER_IDS', '')
        root_group_id = int(os.getenv('TIMECAMP_ROOT_GROUP_ID'))
        
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
        
        # Initialize TimeCamp client
        timecamp = TimeCampAPI(api_key, domain)
        
        # Get users file
        users_file = get_users_file()
        logger.info(f"Using users file: {users_file}")
        
        # Read source users
        with open(users_file, 'r') as f:
            source_data = json.load(f)
        
        source_users = {user['email']: user for user in source_data['users']}
        
        # Get current TimeCamp users and groups
        timecamp_users = timecamp.get_users()
        timecamp_users_map = {user['email']: user for user in timecamp_users}
        
        logger.debug("Fetching TimeCamp groups")
        timecamp_groups = timecamp.get_groups()
        logger.debug(f"Found {len(timecamp_groups)} existing groups")
        timecamp_groups_map = {group['name']: group for group in timecamp_groups}
        logger.debug(f"Existing groups: {', '.join(timecamp_groups_map.keys())}")
        
        # Create department hierarchy
        department_hierarchy = {}
        logger.debug("Processing departments from source users")
        
        # Create a map of group names to their IDs
        group_name_to_id = {group['name']: group['group_id'] for group in timecamp_groups}
        logger.debug(f"Existing group names: {list(group_name_to_id.keys())}")
        
        for email, source_user in source_users.items():
            if source_user['department']:
                logger.debug(f"Processing department: {source_user['department']} for user {email}")
                parts = source_user['department'].split('/')
                current_path = ''
                parent_id = None
                
                for part in parts:
                    if current_path:
                        current_path += '/'
                    current_path += part
                    
                    if current_path not in department_hierarchy:
                        # Check if group exists by its name (not full path)
                        if part in group_name_to_id:
                            logger.debug(f"Group '{part}' already exists with ID {group_name_to_id[part]}")
                            department_hierarchy[current_path] = int(group_name_to_id[part])
                            parent_id = department_hierarchy[current_path]
                            continue
                            
                        # Check if parent exists before creating new group
                        parent_path = '/'.join(current_path.split('/')[:-1])
                        if parent_path and parent_path not in department_hierarchy:
                            logger.debug(f"Parent path {parent_path} not found in hierarchy, skipping")
                            continue
                                
                        if not dry_run:
                            logger.info(f"Creating group: {part}")
                            # Convert parent_id to int or use root_group_id
                            effective_parent_id = int(parent_id) if parent_id is not None else root_group_id
                            group_id = timecamp.add_group(part, effective_parent_id)
                            group_name_to_id[part] = group_id
                            department_hierarchy[current_path] = int(group_id)
                        else:
                            logger.info(f"[DRY RUN] Would create group: {part}")
                            department_hierarchy[current_path] = -1
                            
                    parent_id = department_hierarchy[current_path]

        # Process users
        for email, source_user in source_users.items():
            try:
                department = source_user['department']
                group_id = department_hierarchy.get(department) if department else None
                
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
                            try:
                                timecamp.update_user_setting(tc_user['user_id'], 'disabled_user', '0')
                            except requests.exceptions.RequestException as e:
                                logger.error(f"Error activating user {email}: {str(e)}")
                        else:
                            logger.info(f"[DRY RUN] Would activate user: {email} ({tc_user.get('display_name', 'unknown name')})")
                    
                    # Check if group needs updating
                    if group_id:
                        current_group_name = next((g['name'] for g in timecamp_groups if str(g['group_id']) == str(tc_user['group_id'])), 'unknown')
                        # Get full path for current group
                        current_full_path = next((path for path, gid in department_hierarchy.items() if str(gid) == str(tc_user['group_id'])), current_group_name)
                        new_full_path = source_user['department'] or 'root'
                        
                        if current_full_path != new_full_path:
                            updates['groupId'] = group_id
                            changes.append(f"group from '{current_full_path}' to '{new_full_path}'")
                    
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
                            logger.info(f"Creating new user: {email} ({source_user['name']}) in group '{source_user['department'] or 'root'}'")
                            timecamp.add_user(email, source_user['name'], group_id or root_group_id)
                        else:
                            logger.info(f"[DRY RUN] Would create user: {email} ({source_user['name']}) in group '{source_user['department'] or 'root'}'")
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
                    try:
                        timecamp.update_user_setting(tc_user['user_id'], 'disabled_user', '1')
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Error deactivating user {email}: {str(e)}")
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