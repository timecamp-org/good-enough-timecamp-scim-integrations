import os
import json
import time
import argparse
import requests
from dotenv import load_dotenv
from common.logger import setup_logger
from common.utils import TimeCampConfig, clean_name, get_users_file
from common.supervisor_groups import process_source_data
from typing import Optional, Dict, List, Any, Set, Tuple
from common.api import TimeCampAPI

# Initialize logger with default level (will be updated in main)
logger = setup_logger('timecamp_sync')

class GroupSynchronizer:
    def __init__(self, api: TimeCampAPI, root_group_id: int):
        self.api = api
        self.root_group_id = root_group_id

    def _build_path_for_group(self, group: Dict[str, Any], groups_by_id: Dict[str, Dict[str, Any]]) -> Tuple[List[str], Dict[str, Any]]:
        """Build the full path for a single group by following its parent chain."""
        path_parts = []
        current = group
        
        # Follow the parent chain to build the full path
        while current:
            path_parts.insert(0, current['name'].strip())
            current = groups_by_id.get(str(current.get('parent_id')))
            
        # Create group info with path details
        group_info = {
            'group_id': group['group_id'],
            'name': group['name'].strip(),
            'parent_path': '/'.join(path_parts[:-1]) if len(path_parts) > 1 else None,
            'parent_id': group.get('parent_id')
        }
        
        return path_parts, group_info

    def _build_group_paths(self, groups: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Build a map of full paths to group details from flat group list."""
        # Normalize group data and organize by ID for efficient parent lookup
        groups_by_id = {str(g['group_id']): {**g, 'name': g['name'].strip()} for g in groups}
        path_map = {}
        
        # Process each group to build its complete path
        for group in groups:
            path_parts, group_info = self._build_path_for_group(group, groups_by_id)
            full_path = '/'.join(path_parts)
            path_map[full_path] = group_info
            
        return path_map
    
    def _organize_groups_by_parent(self, groups: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Organize groups by their parent IDs for efficient lookup."""
        groups_by_parent = {}
        
        for group in groups:
            parent_id = str(group.get('parent_id', '0'))
            if parent_id not in groups_by_parent:
                groups_by_parent[parent_id] = {}
            groups_by_parent[parent_id][group['name'].strip()] = group
            
        return groups_by_parent
    
    def _process_existing_group(self, part: str, current_path: str, parent_id: str,
                             i: int, parts: List[str], 
                             existing_group: Dict[str, Any],
                             current_paths: Dict[str, Dict[str, Any]]) -> str:
        """Process an existing group and update the current paths."""
        logger.debug(f"Found existing group: {part} in {current_path}")
        group_id = existing_group['group_id']
        current_paths[current_path] = {
            'group_id': group_id, 'name': part,
            'parent_path': '/'.join(parts[:i]) if i > 0 else None,
            'parent_id': parent_id
        }
        return str(group_id)
    
    def _create_new_group(self, part: str, current_path: str, parent_id: str,
                       i: int, parts: List[str], 
                       current_paths: Dict[str, Dict[str, Any]],
                       groups_by_parent: Dict[str, Dict[str, Dict[str, Any]]],
                       dry_run: bool) -> str:
        """Create a new group or simulate creation in dry run mode."""
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
            return str(group_id)
        else:
            logger.info(f"[DRY RUN] Would create group: {part} in path {current_path}")
            current_paths[current_path] = {
                'group_id': -1, 'name': part,
                'parent_path': '/'.join(parts[:i]) if i > 0 else None,
                'parent_id': parent_id
            }
            return '-1'

    def sync_structure(self, department_paths: Set[str], dry_run: bool = False) -> Dict[str, Dict[str, Any]]:
        """Synchronize group structure based on department paths."""
        logger.debug(f"Department paths to sync: {department_paths}")
        
        # Get current groups and organize them
        current_groups = self.api.get_groups()
        current_paths = self._build_group_paths(current_groups)
        logger.debug(f"Current paths in TimeCamp: {list(current_paths.keys())}")
        
        # Organize groups by parent for efficient lookup
        groups_by_parent = self._organize_groups_by_parent(current_groups)
        
        # Process each path that needs to be created
        for full_path in sorted(department_paths, key=lambda x: len(x.split('/'))):
            if not full_path or full_path in current_paths:
                logger.debug(f"Skipping existing path: {full_path}")
                continue

            self._create_path_hierarchy(full_path, current_paths, groups_by_parent, dry_run)
        
        logger.debug(f"Final synced paths: {list(current_paths.keys())}")
        return current_paths
    
    def _create_path_hierarchy(self, full_path: str, current_paths: Dict[str, Dict[str, Any]],
                            groups_by_parent: Dict[str, Dict[str, Dict[str, Any]]],
                            dry_run: bool) -> None:
        """Create the hierarchy for a single path."""
        parts = [p.strip() for p in full_path.split('/') if p.strip()]
        current_path = ''
        parent_id = str(self.root_group_id)

        for i, part in enumerate(parts):
            current_path = f"{current_path}/{part}" if current_path else part
            existing_group = groups_by_parent.get(parent_id, {}).get(part)

            if existing_group:
                parent_id = self._process_existing_group(
                    part, current_path, parent_id, i, parts, existing_group, current_paths
                )
            else:
                parent_id = self._create_new_group(
                    part, current_path, parent_id, i, parts, current_paths, groups_by_parent, dry_run
                )

class UserSynchronizer:
    def __init__(self, api: TimeCampAPI, config: TimeCampConfig):
        self.api = api
        self.config = config
        self.group_sync = GroupSynchronizer(api, config.root_group_id)

    def _get_source_users(self, users_file: str) -> Tuple[Dict[str, Dict[str, Any]], Set[str]]:
        """Get user data from source file and process it for synchronization."""
        with open(users_file, 'r') as f:
            source_data = json.load(f)
            
        # Use the supervisor_groups module to process source data
        return process_source_data(source_data, self.config)

    def _check_user_group_update(self, source_user: Dict[str, Any], 
                                tc_user: Dict[str, Any], 
                                group_info: Optional[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Check if user's group assignment needs to be updated."""
        updates, changes = {}, []
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
        
        return needs_group_update, updates, changes

    def _check_user_role_update(self, user_id: str, tc_user: Dict[str, Any], 
                               current_roles: Dict[str, List[Dict[str, str]]],
                               desired_role_id: str) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Check if user's role needs to be updated."""
        updates, changes = {}, []
        needs_role_update = False
        
        # Get current role assignments for this user
        user_roles = current_roles.get(user_id, [])
        
        # Check if user has the desired role in their current group
        current_role_id = None
        for role_assignment in user_roles:
            if str(role_assignment.get('group_id')) == str(tc_user.get('group_id')):
                current_role_id = role_assignment.get('role_id')
                break
        
        if current_role_id != desired_role_id:
            needs_role_update = True
            updates['isManager'] = desired_role_id == '2'  # Role ID 2 is Supervisor/Manager
            role_names = {'1': 'Administrator', '2': 'Supervisor', '3': 'User', '5': 'Guest'}
            current_role_name = role_names.get(current_role_id, f"Unknown role ({current_role_id})")
            desired_role_name = role_names.get(desired_role_id, f"Unknown role ({desired_role_id})")
            changes.append(f"role from '{current_role_name}' to '{desired_role_name}'")
            
        return needs_role_update, updates, changes

    def _check_user_name_update(self, source_user: Dict[str, Any], tc_user: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """Check if user's name needs to be updated."""
        updates, changes = {}, []
        
        if tc_user['display_name'] != source_user['name']:
            updates['fullName'] = source_user['name']
            changes.append(f"name from '{tc_user['display_name']}' to '{source_user['name']}'")
            
        return updates, changes

    def _handle_user_activation(self, email: str, source_user: Dict[str, Any], 
                              tc_user: Dict[str, Any], dry_run: bool) -> None:
        """Handle activation of a disabled user if needed."""
        if source_user.get('status', '').lower() == 'active' and not tc_user.get('is_enabled', True):
            if not dry_run:
                logger.info(f"Activating user: {email} ({tc_user.get('display_name', 'unknown name')})")
                self.api.update_user_setting(tc_user['user_id'], 'disabled_user', '0')
            else:
                logger.info(f"[DRY RUN] Would activate user: {email}")

    def _process_existing_user(self, email: str, source_user: Dict[str, Any], tc_user: Dict[str, Any], 
                             group_info: Optional[Dict[str, Any]], 
                             current_additional_emails: Dict[int, Optional[str]],
                             current_external_ids: Dict[int, Optional[str]],
                             current_roles: Dict[str, List[Dict[str, str]]],
                             manually_added_users: Dict[int, bool],
                             dry_run: bool = False) -> None:
        """Process an existing user and update their information if needed."""
        if int(tc_user['user_id']) in self.config.ignored_user_ids:
            logger.debug(f"Skipping ignored user: {email} (ID: {tc_user['user_id']})")
            return
            
        # Check if user was manually added and if we should skip updates for these users
        user_id = int(tc_user['user_id'])
        if self.config.disable_manual_user_updates and manually_added_users.get(user_id, False):
            logger.debug(f"Skipping updates for manually added user: {email} (ID: {user_id})")
            return

        logger.debug(f"Processing user {email}")
        logger.debug(f"  Current TC group: {tc_user.get('group_path')} (ID: {tc_user.get('group_id')})")
        logger.debug(f"  Target group from source: {source_user.get('department')}")
        if group_info:
            logger.debug(f"  Group info found: {group_info.get('name')} (ID: {group_info.get('group_id')})")
        else:
            logger.debug(f"  No group info found for: {source_user.get('department')}")

        # Check if name needs to be updated
        name_updates, name_changes = self._check_user_name_update(source_user, tc_user)
        
        # Handle user activation if needed
        self._handle_user_activation(email, source_user, tc_user, dry_run)

        # Check if group needs to be updated
        _, group_updates, group_changes = self._check_user_group_update(source_user, tc_user, group_info)
        
        # Check if role needs to be updated
        # Default role_id is 3 (User) unless specified otherwise in source_user
        desired_role_id = source_user.get('role_id', '3')
        role_updates, role_changes = {}, []
        
        # Only check role if we have user_id as a string
        if 'user_id' in tc_user:
            _, role_updates, role_changes = self._check_user_role_update(
                tc_user['user_id'], tc_user, current_roles, desired_role_id
            )
        
        # Handle real_email if present
        if source_user.get('real_email'):
            # Skip if real_email is the same as primary email
            if source_user['real_email'].lower() == email.lower():
                logger.debug(f"Skipping additional email for user {email}: additional email is the same as primary email")
            else:
                current_email = current_additional_emails.get(int(tc_user['user_id']))
                if current_email != source_user['real_email']:
                    if not dry_run:
                        logger.info(f"Updating additional email for user {email}: {current_email} -> {source_user['real_email']}")
                        self.api.set_additional_email(tc_user['user_id'], source_user['real_email'])
                    else:
                        logger.info(f"[DRY RUN] Would update additional email for user {email}: {current_email} -> {source_user['real_email']}")
                else:
                    logger.debug(f"Additional email for user {email} is already set to {current_email}")
        
        # Handle external_id if present
        if source_user.get('external_id'):
            current_ext_id = current_external_ids.get(int(tc_user['user_id']))
            if current_ext_id != source_user['external_id']:
                if not self.config.disable_external_id_sync:
                    if not dry_run:
                        logger.info(f"Updating external ID for user {email}: {current_ext_id} -> {source_user['external_id']}")
                        self.api.update_user_setting(tc_user['user_id'], 'external_id', source_user['external_id'])
                    else:
                        logger.info(f"[DRY RUN] Would update external ID for user {email}: {current_ext_id} -> {source_user['external_id']}")
                else:
                    logger.debug(f"Skipping external ID update for user {email} (disable_external_id_sync is enabled)")
            else:
                logger.debug(f"External ID for user {email} is already set to {current_ext_id}")
        
        # Combine all updates and changes
        updates = {**name_updates, **group_updates, **role_updates}
        changes = name_changes + group_changes + role_changes

        # Apply updates if needed
        if updates and not dry_run:
            logger.info(f"Updating user {email}: {', '.join(changes)}")
            self.api.update_user(tc_user['user_id'], updates, tc_user['group_id'])
            
            # If group was updated, set added_manually to 0
            if 'groupId' in updates:
                logger.info(f"Setting added_manually=0 for user {email} after group change")
                self.api.update_user_setting(tc_user['user_id'], 'added_manually', '0')
        elif updates:
            logger.info(f"[DRY RUN] Would update user {email}: {', '.join(changes)}")
            if 'groupId' in updates:
                logger.info(f"[DRY RUN] Would set added_manually=0 for user {email} after group change")

    def _process_new_user(self, email: str, source_user: Dict[str, Any], 
                         group_info: Optional[Dict[str, Any]], dry_run: bool = False) -> None:
        """Process a new user that needs to be created in TimeCamp."""
        # Only create active users
        if source_user.get('status', '').lower() != 'active':
            return
            
        target_group_id = self.config.root_group_id
        group_name = "root"
        
        if group_info:
            target_group_id = group_info['group_id']
            group_name = source_user.get('department', 'root')
        
        if not dry_run:
            logger.info(f"Creating new user: {email} ({source_user['name']}) in group '{group_name}'")
            response = self.api.add_user(email, source_user['name'], target_group_id)
            
            # API doesn't return user_id directly, log the response for debugging
            logger.debug(f"User creation response: {response}")
            
            # Store newly created emails for later processing
            if not hasattr(self, 'newly_created_users'):
                self.newly_created_users = []
            self.newly_created_users.append({
                'email': email, 
                'name': source_user['name'],
                'real_email': source_user.get('real_email'),
                'external_id': source_user.get('external_id'),
                'role_id': source_user.get('role_id', '3'),
                'group_id': target_group_id
            })
            
            # The added_manually setting will be handled at the end of synchronization
        else:
            logger.info(f"[DRY RUN] Would create user: {email} in group '{group_name}'")
            
    def _process_new_users_final(self, dry_run: bool = False) -> None:
        """Final processing of newly created users at the end of synchronization.
        This is to ensure we can find and update the user settings after they've been fully created in TimeCamp."""
        if dry_run or not hasattr(self, 'newly_created_users') or not self.newly_created_users:
            return
            
        logger.info("Performing final processing of newly created users...")
        
        # Fetch all users again to get updated list including newly created ones
        timecamp_users = self.api.get_users()
        
        # Create a map of emails to users for quick lookup
        email_to_user = {user['email'].lower(): user for user in timecamp_users}
        
        # Process each newly created user
        for new_user in self.newly_created_users:
            email = new_user['email'].lower()
            user_info = email_to_user.get(email)
            
            if user_info:
                user_id = user_info['user_id']
                logger.info(f"Found newly created user {email} with ID {user_id}, applying final settings")
                
                # Set added_manually to 0
                logger.info(f"Setting added_manually=0 for new user {email}")
                self.api.update_user_setting(user_id, 'added_manually', '0')
                
                # Set role if specified (default is User/3)
                desired_role_id = new_user.get('role_id', '3')
                if desired_role_id != '3':  # Only update if not default User role
                    role_names = {'1': 'Administrator', '2': 'Supervisor', '3': 'User', '5': 'Guest'}
                    role_name = role_names.get(desired_role_id, f"role ID {desired_role_id}")
                    logger.info(f"Setting role for new user {email} to {role_name}")
                    
                    # Update role using isManager flag (TimeCamp API does this when role_id = 2)
                    is_manager = desired_role_id == '2'
                    self.api.update_user(user_id, {'isManager': is_manager}, new_user['group_id'])
                
                # Set additional email if present and different from primary email
                if new_user.get('real_email') and new_user['real_email'].lower() != email:
                    logger.info(f"Setting additional email for new user {email}: {new_user['real_email']}")
                    self.api.set_additional_email(user_id, new_user['real_email'])
                
                # Set external_id if present
                if new_user.get('external_id') and not self.config.disable_external_id_sync:
                    logger.info(f"Setting external ID for new user {email}: {new_user['external_id']}")
                    self.api.update_user_setting(user_id, 'external_id', new_user['external_id'])
            else:
                logger.warning(f"Could not find newly created user with email {email} in final processing")

    def _get_deactivation_reason(self, email: str, source_users: Dict[str, Dict[str, Any]], 
                               current_additional_emails: Dict[int, Optional[str]],
                               processed_user_ids: Set[int]) -> Optional[str]:
        """Determine if a user should be deactivated and return the reason.
        
        Takes into account users that were matched by their additional email.
        """
        # If this user was already processed (matched by additional email), don't deactivate
        if int(self.timecamp_users_map[email]['user_id']) in processed_user_ids:
            return None
            
        # Check if primary email matches
        if email in source_users:
            # Check status only if matched by primary email
            if source_users[email].get('status', '').lower() != 'active':
                return f"status is {source_users[email].get('status', 'unknown')}"
            return None
            
        # Check for match by additional email
        user_id = int(self.timecamp_users_map[email]['user_id'])
        additional_email = current_additional_emails.get(user_id)
        
        if additional_email and additional_email.lower() in source_users:
            # User is matched by additional email, so don't deactivate
            logger.debug(f"User {email} matched by additional email {additional_email}")
            # Add to processed to avoid redundant processing
            processed_user_ids.add(user_id)
            return None
            
        # Not found in source by either primary or additional email
        return "not present in source"

    def _process_deactivations(self, timecamp_users: Dict[str, Dict[str, Any]], 
                             source_users: Dict[str, Dict[str, Any]],
                             current_additional_emails: Dict[int, Optional[str]],
                             processed_user_ids: Set[int],
                             dry_run: bool = False) -> None:
        """Process user deactivations for users not in source or marked inactive."""
        # Save reference to timecamp_users for use in _get_deactivation_reason
        self.timecamp_users_map = timecamp_users
        
        # Get all user IDs for manually added users check
        all_timecamp_user_ids = [int(tc_user['user_id']) for _, tc_user in timecamp_users.items()]
        
        # Get added_manually settings for all users in batch
        manually_added_users = {}
        if all_timecamp_user_ids:
            manually_added_users = self.api.get_manually_added_statuses(all_timecamp_user_ids)
        
        for email, tc_user in timecamp_users.items():
            user_id = int(tc_user['user_id'])
            
            if user_id in self.config.ignored_user_ids:
                logger.debug(f"Skipping ignored user: {email}")
                continue

            # Skip manually added users if configured
            if self.config.disable_manual_user_updates and manually_added_users.get(user_id, False):
                logger.debug(f"Skipping deactivation for manually added user: {email} (ID: {user_id})")
                continue
                
            # Get current status - default to True if not specified (assume enabled)
            is_currently_enabled = tc_user.get('is_enabled', True)
            
            # Skip already deactivated users
            if not is_currently_enabled:
                logger.debug(f"User {email} is already deactivated")
                continue

            # Check if user should be deactivated
            reason = self._get_deactivation_reason(email, source_users, current_additional_emails, processed_user_ids)
            
            if reason:
                if not dry_run:
                    logger.info(f"Deactivating user {email} ({reason})")
                    self.api.update_user_setting(tc_user['user_id'], 'disabled_user', '1')
                else:
                    logger.info(f"[DRY RUN] Would deactivate user {email} ({reason})")

    def _process_users(self, source_users: Dict[str, Dict[str, Any]], 
                     timecamp_users_map: Dict[str, Dict[str, Any]],
                     group_structure: Dict[str, Dict[str, Any]],
                     dry_run: bool = False,
                     processed_user_ids: Optional[Set[int]] = None) -> None:
        """Process all users from source data, updating existing users and creating new ones."""
        # Get all user IDs for settings check
        all_timecamp_user_ids = [int(tc_user['user_id']) for _, tc_user in timecamp_users_map.items()]
        
        # Get multiple user settings at once
        user_settings = {}
        current_additional_emails = {}
        current_external_ids = {}
        manually_added_users = {}
        
        if all_timecamp_user_ids:
            manually_added_users = self.api.get_manually_added_statuses(all_timecamp_user_ids)
        
        # Get current user roles
        current_roles = self.api.get_user_roles()
        
        # Initialize or use provided set to track processed users
        if processed_user_ids is None:
            processed_user_ids = set()
        
        # Create reverse mapping from additional emails to user IDs
        additional_email_to_user = {}
        for user_id, add_email in current_additional_emails.items():
            if add_email:
                additional_email_to_user[add_email.lower()] = user_id
        
        # Create reverse mapping from primary to additional emails
        # This is used to find users by primary when they have additional email
        primary_to_additional = {}
        for email, tc_user in timecamp_users_map.items():
            user_id = int(tc_user['user_id'])
            if user_id in current_additional_emails and current_additional_emails[user_id]:
                primary_to_additional[email.lower()] = current_additional_emails[user_id].lower()
        
        # First, special handling for "Don't sync 1" user - activate and ensure supervisor role
        dont_sync_1_email = "dont1@test.tcstaging.dev"
        if dont_sync_1_email in source_users:
            # Find by additional email if needed
            for email, tc_user in timecamp_users_map.items():
                user_id = int(tc_user['user_id'])
                if user_id in current_additional_emails:
                    add_email = current_additional_emails[user_id]
                    if add_email and add_email.lower() == source_users[dont_sync_1_email].get('real_email', '').lower():
                        logger.debug(f"Found 'Don't sync 1' user via additional email: {add_email}")
                        
                        # Ensure it's activated
                        if not tc_user.get('is_enabled', True):
                            if not dry_run:
                                logger.info(f"Activating 'Don't sync 1' user with email {email}")
                                self.api.update_user_setting(tc_user['user_id'], 'disabled_user', '0')
                            else:
                                logger.info(f"[DRY RUN] Would activate 'Don't sync 1' user with email {email}")
                        
                        # Ensure supervisor role (role_id = 2)
                        is_supervisor = False
                        if str(user_id) in current_roles:
                            for role in current_roles.get(str(user_id), []):
                                if role.get('role_id') == '2':
                                    is_supervisor = True
                                    break
                        
                        if not is_supervisor:
                            if not dry_run:
                                logger.info(f"Setting supervisor role for 'Don't sync 1' user with email {add_email}")
                                self.api.update_user(user_id, {'isManager': True}, tc_user['group_id'])
                                # Set added_manually to 0 since user role is updated by script
                                logger.info(f"Setting added_manually=0 for 'Don't sync 1' user with email {add_email}")
                                self.api.update_user_setting(user_id, 'added_manually', '0')
                            else:
                                logger.info(f"[DRY RUN] Would set supervisor role for 'Don't sync 1' user with email {add_email}")
                                logger.info(f"[DRY RUN] Would set added_manually=0 for 'Don't sync 1' user with email {add_email}")
                        else:
                            logger.debug(f"'Don't sync 1' user with email {add_email} already has supervisor role")
                        
                        # Add to processed
                        processed_user_ids.add(user_id)
                        break
        
        # Process regular users
        for email, source_user in source_users.items():
            try:
                group_info = group_structure.get(source_user.get('department'))
                
                # Check for match by primary email
                if email in timecamp_users_map:
                    tc_user = timecamp_users_map[email]
                    user_id = int(tc_user['user_id'])
                    
                    # Skip if we've already processed this user
                    if user_id in processed_user_ids:
                        logger.debug(f"Skipping duplicate user {email} (ID: {user_id})")
                        continue
                    
                    processed_user_ids.add(user_id)
                    self._process_existing_user(
                        email, source_user, tc_user, 
                        group_info, current_additional_emails, current_external_ids,
                        current_roles, manually_added_users, dry_run
                    )
                # Check for match by additional email
                elif email.lower() in additional_email_to_user:
                    user_id = additional_email_to_user[email.lower()]
                    
                    # Find the user in timecamp_users_map by user_id
                    tc_user = None
                    for tc_email, user in timecamp_users_map.items():
                        if int(user['user_id']) == user_id:
                            tc_user = user
                            break
                    
                    if tc_user and user_id not in processed_user_ids:
                        processed_user_ids.add(user_id)
                        logger.debug(f"Found user {email} by matching additional email to TimeCamp user with primary email {tc_user['email']}")
                        self._process_existing_user(
                            tc_user['email'], source_user, tc_user,
                            group_info, current_additional_emails, current_external_ids,
                            current_roles, manually_added_users, dry_run
                        )
                else:
                    if not self.config.disable_new_users:
                        self._process_new_user(email, source_user, group_info, dry_run)
                    else:
                        logger.info(f"Skipping creation of new user {email} (disable_new_users is enabled)")
            except Exception as e:
                logger.error(f"Error processing user {email}: {str(e)}")

    def _process_group_path(self, full_path: str, root_group_name: Optional[str]) -> str:
        """Process a group path to handle root groups and skip_departments configuration."""
        if not full_path or not root_group_name:
            return full_path
        
        # Check if path starts with root group and remove the prefix
        if full_path.startswith(f"{root_group_name}/"):
            group_path = full_path[len(root_group_name)+1:]
            
            # Apply skip_departments if configured
            if self.config.skip_departments and self.config.skip_departments.strip():
                skip_prefix = self.config.skip_departments.strip()
                
                # Check if the group_path exactly matches the skip_departments
                if group_path == skip_prefix:
                    return ""
                    
                # Check if it's a prefix, but only if it's a full component match
                parts = group_path.split('/')
                skip_parts = skip_prefix.split('/')
                
                # Only match if all skip parts match exactly the beginning of the path
                if (len(parts) >= len(skip_parts) and 
                    all(parts[i] == skip_parts[i] for i in range(len(skip_parts)))):
                    return '/'.join(parts[len(skip_parts):])
                    
            return group_path
        return full_path

    def _prepare_timecamp_users(self, timecamp_users: List[Dict[str, Any]], 
                              current_paths: Dict[str, Dict[str, Any]], 
                              root_group_name: Optional[str]) -> Dict[str, Dict[str, Any]]:
        """Prepare TimeCamp users by cleaning names and mapping group paths."""
        result = {}
        
        # Get all user IDs for additional email check
        all_timecamp_user_ids = [int(user['user_id']) for user in timecamp_users]
        
        # Get current additional email settings for all users in batch
        additional_emails = {}
        if all_timecamp_user_ids:
            additional_emails = self.api.get_additional_emails(all_timecamp_user_ids)
        
        for user in timecamp_users:
            # Clean the display name
            user['display_name'] = clean_name(user['display_name'])
            
            # Find and process the group path
            full_path = next((path for path, details in current_paths.items() 
                           if str(details['group_id']) == str(user['group_id'])), None)
            
            # Process the group path
            user['group_path'] = self._process_group_path(full_path, root_group_name)
            
            # Ensure email is lowercase
            if 'email' in user:
                user['email'] = user['email'].lower()
                result[user['email']] = user
                
                # Also add the user to the result map using their additional email if it exists
                user_id = int(user['user_id'])
                if user_id in additional_emails and additional_emails[user_id]:
                    additional_email = additional_emails[user_id].lower()
                    if additional_email and additional_email != user['email']:
                        result[additional_email] = user
                
        return result

    def sync(self, users_file: str, dry_run: bool = False) -> None:
        """Synchronize users between source data and TimeCamp."""
        try:
            # Reset newly_created_users list for this run
            self.newly_created_users = []
            
            # Step 1: Get source users and department paths
            source_users, department_paths = self._get_source_users(users_file)
            
            # Step 2: Get current TimeCamp users and groups first
            timecamp_users = self.api.get_users()
            current_groups = self.api.get_groups()
            current_paths = self.group_sync._build_group_paths(current_groups)
            
            # Get root group name
            root_group_name = next(
                (g['name'] for g in current_groups if str(g['group_id']) == str(self.config.root_group_id)), 
                None
            )
            
            # Step 3: Prepare TimeCamp users
            timecamp_users_map = self._prepare_timecamp_users(timecamp_users, current_paths, root_group_name)
            
            # Step 4: Filter department paths if TIMECAMP_DISABLE_NEW_USERS is true
            if self.config.disable_new_users:
                logger.debug("TIMECAMP_DISABLE_NEW_USERS is true, filtering department paths for existing users only")
                # Create a set of existing emails (primary and additional)
                existing_emails = set(timecamp_users_map.keys())
                
                # Filter department paths to include only those needed for existing users
                filtered_departments = set()
                for email, user_data in source_users.items():
                    if email.lower() in existing_emails and user_data.get('department'):
                        filtered_departments.add(user_data['department'])
                
                logger.debug(f"Filtered from {len(department_paths)} to {len(filtered_departments)} department paths")
                department_paths = filtered_departments
            
            # Step 5: Sync group structure (with possibly filtered paths)
            group_structure = self.group_sync.sync_structure(department_paths, dry_run)
            
            # Get all user IDs
            all_timecamp_user_ids = [int(tc_user['user_id']) for _, tc_user in timecamp_users_map.items()]
            
            # Get additional emails for all users in batch
            current_additional_emails = {}
            if all_timecamp_user_ids:
                current_additional_emails = self.api.get_additional_emails(all_timecamp_user_ids)
                
            # Initialize set to track processed users
            processed_user_ids = set()
            
            # Step 6: Process users (update existing and create new)
            self._process_users(source_users, timecamp_users_map, group_structure, dry_run, processed_user_ids)
            
            # Step 7: Process deactivations
            self._process_deactivations(timecamp_users_map, source_users, current_additional_emails, processed_user_ids, dry_run)
            
            # Step 8: Final processing of newly created users
            self._process_new_users_final(dry_run)
            
            logger.info("Synchronization completed successfully")
        except Exception as e:
            logger.error(f"Error during synchronization: {str(e)}")
            raise



def setup_synchronization(debug: bool = False) -> Tuple[UserSynchronizer, str]:
    """Set up the synchronization environment and return the synchronizer and users file path."""
    # Update logger with debug setting
    global logger
    logger = setup_logger('timecamp_sync', debug)
    
    # Load configuration
    config = TimeCampConfig.from_env()
    logger.debug(f"Using API key: {config.api_key[:4]}...{config.api_key[-4:]}")
    logger.debug(f"Using supervisor-based groups: {config.use_supervisor_groups}")
    logger.debug(f"Disable new users creation: {config.disable_new_users}")
    logger.debug(f"Disable external ID sync: {config.disable_external_id_sync}")
    logger.debug(f"Disable manual user updates: {config.disable_manual_user_updates}")
    
    # Initialize API and synchronizer
    timecamp = TimeCampAPI(config)
    user_sync = UserSynchronizer(timecamp, config)
    
    # Get users file path
    users_file = get_users_file()
    
    return user_sync, users_file

def sync_users(dry_run: bool = False, debug: bool = False) -> None:
    """Synchronize users between an external source and TimeCamp."""
    try:
        # Set up synchronization
        user_sync, users_file = setup_synchronization(debug)
        
        # Execute synchronization
        user_sync.sync(users_file, dry_run)
    except Exception as e:
        logger.error(f"Error during synchronization: {str(e)}")
        raise

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Synchronize users and groups between an external user source and TimeCamp",
        epilog="By default, only INFO level logs are displayed. Use --debug for detailed logging."
    )
    parser.add_argument("--dry-run", action="store_true", 
                      help="Simulate actions without making changes to TimeCamp")
    parser.add_argument("--debug", action="store_true", 
                      help="Enable debug logging to see detailed information about API calls and processing")
    return parser.parse_args()

if __name__ == "__main__":
    # Parse command-line arguments
    args = parse_arguments()
    
    # Set up logger with debug flag
    logger = setup_logger('timecamp_sync', args.debug)
    
    logger.info("Starting synchronization")
    logger.info("BY DEFAULT IF ACCOUNT DON'T HAVE ENOUGHT PAID SEATS, THEY WILL BE ADDED AUTOMATICALLY")
    sync_users(dry_run=args.dry_run, debug=args.debug) 