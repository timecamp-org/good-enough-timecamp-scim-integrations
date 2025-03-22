import os
import json
import time
import argparse
import requests
from dotenv import load_dotenv
from common.logger import setup_logger
from common.utils import TimeCampConfig, clean_name, get_users_file, clean_department_path
from typing import Optional, Dict, List, Any, Set, Tuple
from common.api import TimeCampAPI

# Initialize logger with default level (will be updated in main)
logger = setup_logger('timecamp_sync')

class GroupSynchronizer:
    def __init__(self, api: TimeCampAPI, root_group_id: int):
        self.api = api
        self.root_group_id = root_group_id

    def _build_group_paths(self, groups: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        groups_by_id = {str(g['group_id']): {**g, 'name': g['name'].strip()} for g in groups}
        path_map = {}
        
        for group in groups:
            path_parts = []
            current = group
            while current:
                path_parts.insert(0, current['name'].strip())
                current = groups_by_id.get(str(current.get('parent_id')))
            
            path_map['/'.join(path_parts)] = {
                'group_id': group['group_id'],
                'name': group['name'].strip(),
                'parent_path': '/'.join(path_parts[:-1]) if len(path_parts) > 1 else None,
                'parent_id': group.get('parent_id')
            }
        return path_map

    def sync_structure(self, department_paths: Set[str], dry_run: bool = False) -> Dict[str, Dict[str, Any]]:
        logger.debug(f"Department paths to sync: {department_paths}")
        current_groups = self.api.get_groups()
        current_paths = self._build_group_paths(current_groups)
        logger.debug(f"Current paths in TimeCamp: {list(current_paths.keys())}")
        groups_by_parent = {}
        
        for group in current_groups:
            parent_id = str(group.get('parent_id', '0'))
            if parent_id not in groups_by_parent:
                groups_by_parent[parent_id] = {}
            groups_by_parent[parent_id][group['name'].strip()] = group

        for full_path in sorted(department_paths, key=lambda x: len(x.split('/'))):
            if not full_path or full_path in current_paths:
                logger.debug(f"Skipping existing path: {full_path}")
                continue

            parts = [p.strip() for p in full_path.split('/') if p.strip()]
            current_path = ''
            parent_id = str(self.root_group_id)

            for i, part in enumerate(parts):
                current_path = f"{current_path}/{part}" if current_path else part
                existing_group = groups_by_parent.get(parent_id, {}).get(part)

                if existing_group:
                    logger.debug(f"Found existing group: {part} in {current_path}")
                    group_id = existing_group['group_id']
                    current_paths[current_path] = {
                        'group_id': group_id, 'name': part,
                        'parent_path': '/'.join(parts[:i]) if i > 0 else None,
                        'parent_id': parent_id
                    }
                    parent_id = str(group_id)
                else:
                    if not dry_run:
                        logger.info(f"Creating group: {part} in path {current_path}")
                        group_id = self.api.add_group(part, int(parent_id))
                        group_info = {
                            'group_id': group_id, 'name': part,
                            'parent_path': '/'.join(parts[:i]) if i > 0 else None,
                            'parent_id': parent_id
                        }
                        current_paths[current_path] = group_info
                        groups_by_parent.setdefault(parent_id, {})[part] = {
                            'group_id': group_id, 'name': part, 'parent_id': parent_id
                        }
                        parent_id = str(group_id)
                    else:
                        logger.info(f"[DRY RUN] Would create group: {part} in path {current_path}")
                        current_paths[current_path] = {
                            'group_id': -1, 'name': part,
                            'parent_path': '/'.join(parts[:i]) if i > 0 else None,
                            'parent_id': parent_id
                        }
                        parent_id = '-1'
        
        logger.debug(f"Final synced paths: {list(current_paths.keys())}")
        return current_paths

class UserSynchronizer:
    def __init__(self, api: TimeCampAPI, config: TimeCampConfig):
        self.api = api
        self.config = config
        self.group_sync = GroupSynchronizer(api, config.root_group_id)

    def _get_source_users(self, users_file: str) -> Tuple[Dict[str, Dict[str, Any]], Set[str]]:
        with open(users_file, 'r') as f:
            source_data = json.load(f)

        department_paths = set()
        for user in source_data['users']:
            if user.get('department'):
                user['department'] = clean_department_path(user['department'], self.config)
                if user['department']:
                    department_paths.add(user['department'])
            user['name'] = clean_name(f"{user['name']} - {user['external_id']}" if self.config.show_external_id and user.get('external_id') else user['name'])
            # Ensure email is lowercase
            if 'email' in user:
                user['email'] = user['email'].lower()

        return {user['email'].lower(): user for user in source_data['users']}, department_paths

    def _process_existing_user(self, email: str, source_user: Dict[str, Any], tc_user: Dict[str, Any], 
                             group_info: Optional[Dict[str, Any]], dry_run: bool = False) -> None:
        if int(tc_user['user_id']) in self.config.ignored_user_ids:
            logger.debug(f"Skipping ignored user: {email} (ID: {tc_user['user_id']})")
            return

        logger.debug(f"Processing user {email}")
        logger.debug(f"  Current TC group: {tc_user.get('group_path')} (ID: {tc_user.get('group_id')})")
        logger.debug(f"  Target group from source: {source_user.get('department')}")
        if group_info:
            logger.debug(f"  Group info found: {group_info.get('name')} (ID: {group_info.get('group_id')})")
        else:
            logger.debug(f"  No group info found for: {source_user.get('department')}")

        updates, changes = {}, []
        if tc_user['display_name'] != source_user['name']:
            updates['fullName'] = source_user['name']
            changes.append(f"name from '{tc_user['display_name']}' to '{source_user['name']}'")

        if source_user.get('status', '').lower() == 'active' and not tc_user.get('is_enabled', True):
            if not dry_run:
                logger.info(f"Activating user: {email} ({tc_user.get('display_name', 'unknown name')})")
                self.api.update_user_setting(tc_user['user_id'], 'disabled_user', '0')
            else:
                logger.info(f"[DRY RUN] Would activate user: {email}")

        # Check both path and ID to determine if group change is needed
        needs_group_update = False
        
        # Handle empty department - should be in root group
        if not source_user.get('department') and str(tc_user.get('group_id')) != str(self.config.root_group_id):
            needs_group_update = True
            updates['groupId'] = self.config.root_group_id
            changes.append(f"group from '{tc_user.get('group_path', 'unknown')}' (ID: {tc_user.get('group_id')}) to 'root' (ID: {self.config.root_group_id})")
        # Handle normal department assignment
        elif group_info:
            if tc_user.get('group_path') != source_user.get('department'):
                needs_group_update = True
            elif str(tc_user.get('group_id')) != str(group_info.get('group_id')):
                needs_group_update = True
                logger.debug(f"  Group path matches but IDs differ: {tc_user.get('group_id')} vs {group_info.get('group_id')}")
                
            if needs_group_update:
                updates['groupId'] = group_info['group_id']
                changes.append(f"group from '{tc_user.get('group_path', 'unknown')}' (ID: {tc_user.get('group_id')}) to '{source_user['department']}' (ID: {group_info['group_id']})")

        if updates and not dry_run:
            logger.info(f"Updating user {email}: {', '.join(changes)}")
            self.api.update_user(tc_user['user_id'], updates, tc_user['group_id'])
        elif updates:
            logger.info(f"[DRY RUN] Would update user {email}: {', '.join(changes)}")

    def _process_new_user(self, email: str, source_user: Dict[str, Any], 
                         group_info: Optional[Dict[str, Any]], dry_run: bool = False) -> None:
        if source_user.get('status', '').lower() == 'active':
            if not dry_run:
                target_group_id = self.config.root_group_id
                group_name = "root"
                
                if group_info:
                    target_group_id = group_info['group_id']
                    group_name = source_user.get('department', 'root')
                
                logger.info(f"Creating new user: {email} ({source_user['name']}) in group '{group_name}'")
                self.api.add_user(email, source_user['name'], target_group_id)
            else:
                target_group = source_user.get('department', 'root')
                logger.info(f"[DRY RUN] Would create user: {email} in group '{target_group}'")

    def _process_deactivations(self, timecamp_users: Dict[str, Dict[str, Any]], 
                             source_users: Dict[str, Dict[str, Any]], dry_run: bool = False) -> None:
        for email, tc_user in timecamp_users.items():
            if int(tc_user['user_id']) in self.config.ignored_user_ids:
                logger.debug(f"Skipping ignored user: {email}")
                continue

            # Check if user should be deactivated
            should_deactivate = False
            if email not in source_users:
                should_deactivate = True
                reason = "not present in source"
            elif source_users[email].get('status', '').lower() != 'active':
                should_deactivate = True
                reason = f"status is {source_users[email].get('status', 'unknown')}"

            # Get current status
            is_currently_enabled = tc_user.get('is_enabled', True)
            
            if should_deactivate:
                if is_currently_enabled:
                    if not dry_run:
                        logger.info(f"Deactivating user {email} ({reason})")
                        self.api.update_user_setting(tc_user['user_id'], 'disabled_user', '1')
                    else:
                        logger.info(f"[DRY RUN] Would deactivate user {email} ({reason})")
                else:
                    logger.debug(f"User {email} is already deactivated ({reason})")

    def _prepare_timecamp_users(self, timecamp_users: List[Dict[str, Any]], 
                              current_paths: Dict[str, Dict[str, Any]], root_group_name: Optional[str]) -> Dict[str, Dict[str, Any]]:
        for user in timecamp_users:
            user['display_name'] = clean_name(user['display_name'])
            full_path = next((path for path, details in current_paths.items() 
                            if str(details['group_id']) == str(user['group_id'])), None)
            if full_path and root_group_name and full_path.startswith(f"{root_group_name}/"):
                # Remove root group prefix
                group_path = full_path[len(root_group_name)+1:]
                # Apply skip_departments if configured
                if self.config.skip_departments and self.config.skip_departments.strip() and group_path.startswith(self.config.skip_departments):
                    if group_path == self.config.skip_departments:
                        group_path = ""
                    else:
                        group_path = group_path[len(self.config.skip_departments)+1:]
                user['group_path'] = group_path
            else:
                user['group_path'] = full_path
            # Ensure email is lowercase
            if 'email' in user:
                user['email'] = user['email'].lower()
        return {user['email'].lower(): user for user in timecamp_users}

    def sync(self, users_file: str, dry_run: bool = False) -> None:
        try:
            source_users, department_paths = self._get_source_users(users_file)
            group_structure = self.group_sync.sync_structure(department_paths, dry_run)
            
            timecamp_users = self.api.get_users()
            current_groups = self.api.get_groups()
            current_paths = self.group_sync._build_group_paths(current_groups)
            root_group_name = next((g['name'] for g in current_groups if str(g['group_id']) == str(self.config.root_group_id)), None)
            
            timecamp_users_map = self._prepare_timecamp_users(timecamp_users, current_paths, root_group_name)
            
            for email, source_user in source_users.items():
                try:
                    group_info = group_structure.get(source_user.get('department'))
                    if email in timecamp_users_map:
                        self._process_existing_user(email, source_user, timecamp_users_map[email], group_info, dry_run)
                    else:
                        self._process_new_user(email, source_user, group_info, dry_run)
                except Exception as e:
                    logger.error(f"Error processing user {email}: {str(e)}")
            
            self._process_deactivations(timecamp_users_map, source_users, dry_run)
            logger.info("Synchronization completed successfully")
        except Exception as e:
            logger.error(f"Error during synchronization: {str(e)}")
            raise

def sync_users(dry_run=False, debug=False):
    try:
        # Update logger with debug setting
        global logger
        logger = setup_logger('timecamp_sync', debug)
        
        config = TimeCampConfig.from_env()
        logger.debug(f"Using API key: {config.api_key[:4]}...{config.api_key[-4:]}")
        timecamp = TimeCampAPI(config)
        user_sync = UserSynchronizer(timecamp, config)
        user_sync.sync(get_users_file(), dry_run)
    except Exception as e:
        logger.error(f"Error during synchronization: {str(e)}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Synchronize users and groups between an external user source and TimeCamp",
        epilog="By default, only INFO level logs are displayed. Use --debug for detailed logging."
    )
    parser.add_argument("--dry-run", action="store_true", 
                      help="Simulate actions without making changes to TimeCamp")
    parser.add_argument("--debug", action="store_true", 
                      help="Enable debug logging to see detailed information about API calls and processing")
    args = parser.parse_args()
    
    # Set up logger with debug flag
    logger = setup_logger('timecamp_sync', args.debug)
    
    logger.info("Starting synchronization")
    sync_users(dry_run=args.dry_run, debug=args.debug) 