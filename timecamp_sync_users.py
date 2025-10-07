#!/usr/bin/env python3
"""
Stage 2: TimeCamp Synchronization (Version 2)
This script reads the prepared var/timecamp_users.json and synchronizes
users and groups with TimeCamp API.
"""

import os
import json
import argparse
from typing import Dict, List, Any, Set, Tuple, Optional
from dotenv import load_dotenv
from common.logger import setup_logger
from common.utils import TimeCampConfig
from common.api import TimeCampAPI

# Load environment variables
load_dotenv()

# Initialize logger
logger = setup_logger('timecamp_sync_v2')


class TimeCampSynchronizer:
    """Handles synchronization of users and groups with TimeCamp."""
    
    def __init__(self, api: TimeCampAPI, config: TimeCampConfig):
        self.api = api
        self.config = config
        self.newly_created_users = []
        
    def _build_group_paths(self, groups: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Build a map of full paths to group details from flat group list."""
        groups_by_id = {str(g['group_id']): g for g in groups}
        path_map = {}
        
        for group in groups:
            path_parts = []
            current = group
            
            # Follow the parent chain to build the full path
            while current:
                path_parts.insert(0, current['name'].strip())
                current = groups_by_id.get(str(current.get('parent_id')))
                
            full_path = '/'.join(path_parts)
            path_map[full_path] = {
                'group_id': group['group_id'],
                'name': group['name'].strip(),
                'parent_id': group.get('parent_id')
            }
            
        return path_map
    
    def _get_required_groups(self, timecamp_users: List[Dict[str, Any]]) -> Set[str]:
        """Extract all unique group paths from TimeCamp users, but only for active users."""
        group_paths = set()
        
        for user in timecamp_users:
            # Only consider active users when determining required groups
            if user.get('timecamp_status') != 'active':
                continue
                
            breadcrumb = user.get('timecamp_groups_breadcrumb', '')
            if breadcrumb:
                # Add the full path
                group_paths.add(breadcrumb)
                
                # Also add all parent paths
                parts = breadcrumb.split('/')
                for i in range(1, len(parts)):
                    parent_path = '/'.join(parts[:i])
                    group_paths.add(parent_path)
                    
        return group_paths
    
    def _sync_groups(self, required_groups: Set[str], dry_run: bool = False) -> Dict[str, Dict[str, Any]]:
        """Synchronize required group structure with TimeCamp."""
        # Get current groups
        current_groups = self.api.get_groups()
        current_paths = self._build_group_paths(current_groups)
        
        logger.debug(f"Current group paths in TimeCamp: {list(current_paths.keys())}")
        logger.debug(f"Required group paths: {required_groups}")
        
        # Organize groups by parent for efficient lookup
        groups_by_parent = {}
        for group in current_groups:
            parent_id = str(group.get('parent_id', '0'))
            if parent_id not in groups_by_parent:
                groups_by_parent[parent_id] = {}
            groups_by_parent[parent_id][group['name'].strip()] = group
        
        # Process each required path
        for full_path in sorted(required_groups, key=lambda x: len(x.split('/'))):
            if not full_path or full_path in current_paths:
                continue
                
            # Create the path hierarchy
            parts = [p.strip() for p in full_path.split('/') if p.strip()]
            current_path = ''
            parent_id = str(self.config.root_group_id)
            
            for i, part in enumerate(parts):
                current_path = f"{current_path}/{part}" if current_path else part
                
                # Check if this part already exists under the current parent
                existing_group = groups_by_parent.get(parent_id, {}).get(part)
                
                if existing_group:
                    parent_id = str(existing_group['group_id'])
                    current_paths[current_path] = {
                        'group_id': existing_group['group_id'],
                        'name': part,
                        'parent_id': existing_group.get('parent_id')
                    }
                else:
                    # Create new group
                    if not dry_run and not self.config.disable_groups_creation:
                        logger.info(f"Creating group: {part} under parent {parent_id}")
                        group_id = self.api.add_group(part, int(parent_id))
                        
                        # Update tracking structures
                        current_paths[current_path] = {
                            'group_id': group_id,
                            'name': part,
                            'parent_id': parent_id
                        }
                        groups_by_parent.setdefault(parent_id, {})[part] = {
                            'group_id': group_id,
                            'name': part,
                            'parent_id': parent_id
                        }
                        parent_id = str(group_id)
                    elif self.config.disable_groups_creation:
                        logger.info(f"Skipping group creation: {part} under parent {parent_id} (disable_groups_creation is enabled)")
                        parent_id = '-1'  # Dummy ID when group creation is disabled
                    else:
                        logger.info(f"[DRY RUN] Would create group: {part} under parent {parent_id}")
                        parent_id = '-1'  # Dummy ID for dry run
                        
        return current_paths
    
    def _sync_users(self, timecamp_users: List[Dict[str, Any]], 
                   group_structure: Dict[str, Dict[str, Any]], 
                   dry_run: bool = False) -> None:
        """Synchronize users with TimeCamp."""
        # Get current TimeCamp users
        current_tc_users = self.api.get_users()
        tc_users_by_email = {user['email'].lower(): user for user in current_tc_users}
        
        # Get additional user data
        all_user_ids = [int(user['user_id']) for user in current_tc_users]
        additional_emails = {}
        external_ids = {}
        manually_added = {}
        current_roles = {}
        
        if all_user_ids:
            additional_emails = self.api.get_additional_emails(all_user_ids)
            external_ids = self.api.get_external_ids(all_user_ids)
            manually_added = self.api.get_manually_added_statuses(all_user_ids)
            current_roles = self.api.get_user_roles()
        
        # Build reverse mapping from additional emails
        additional_email_to_user = {}
        for user_id, add_email in additional_emails.items():
            if add_email:
                additional_email_to_user[add_email.lower()] = user_id
        
        # Track processed users to avoid duplicates
        processed_user_ids = set()
        
        # Process each user from the prepared data
        for tc_user_data in timecamp_users:
            email = tc_user_data['timecamp_email'].lower()
            
            # Skip inactive users for creation
            if tc_user_data['timecamp_status'] != 'active':
                logger.debug(f"Skipping inactive user: {email}")
                continue
            
            # Find existing user by primary email or additional email
            existing_user = None
            user_id = None
            
            if email in tc_users_by_email:
                existing_user = tc_users_by_email[email]
                user_id = int(existing_user['user_id'])
            elif email in additional_email_to_user:
                user_id = additional_email_to_user[email]
                # Find the user in tc_users_by_email
                for tc_email, tc_user in tc_users_by_email.items():
                    if int(tc_user['user_id']) == user_id:
                        existing_user = tc_user
                        break
            
            # Skip if already processed
            if user_id and user_id in processed_user_ids:
                continue
                
            if user_id:
                processed_user_ids.add(user_id)
            
            # Determine target group
            group_breadcrumb = tc_user_data.get('timecamp_groups_breadcrumb', '')
            target_group_id = self.config.root_group_id
            target_group_name = 'root'
            
            if group_breadcrumb and group_breadcrumb in group_structure:
                target_group_id = group_structure[group_breadcrumb]['group_id']
                target_group_name = group_breadcrumb
            elif group_breadcrumb and dry_run:
                # In dry run mode, show the intended breadcrumb even if group doesn't exist
                target_group_name = group_breadcrumb
            elif group_breadcrumb:
                # For actual execution, if group doesn't exist, use root
                target_group_name = 'root'
            
            if existing_user:
                # Update existing user
                self._update_existing_user(
                    existing_user, tc_user_data, target_group_id, target_group_name,
                    additional_emails, external_ids, manually_added, current_roles,
                    dry_run
                )
            else:
                # Create new user
                if not self.config.disable_new_users:
                    self._create_new_user(tc_user_data, target_group_id, target_group_name, dry_run)
                else:
                    logger.info(f"Skipping creation of new user {email} (disable_new_users is enabled)")
        
        # Handle deactivations
        self._handle_deactivations(
            timecamp_users, tc_users_by_email, additional_emails, 
            processed_user_ids, manually_added, dry_run
        )
        
        # Final processing for newly created users
        if not dry_run and self.newly_created_users:
            self._finalize_new_users()
    
    def _update_existing_user(self, existing_user: Dict[str, Any], 
                            tc_user_data: Dict[str, Any],
                            target_group_id: int, target_group_name: str,
                            additional_emails: Dict[int, Optional[str]],
                            external_ids: Dict[int, Optional[str]], 
                            manually_added: Dict[int, bool],
                            current_roles: Dict[str, List[Dict[str, str]]],
                            dry_run: bool) -> None:
        """Update an existing TimeCamp user."""
        user_id = int(existing_user['user_id'])
        email = existing_user['email']
        
        # Skip ignored users
        if user_id in self.config.ignored_user_ids:
            logger.debug(f"Skipping ignored user: {email} (ID: {user_id})")
            return
        
        # Skip manually added users if configured
        if self.config.disable_manual_user_updates and manually_added.get(user_id, False):
            logger.info(f"Skipping updates for manually added user: {email} (ID: {user_id}) due to disable_manual_user_updates config.")
            return
        
        updates = {}
        changes = []
        
        # Check name update
        if existing_user['display_name'] != tc_user_data['timecamp_user_name']:
            updates['fullName'] = tc_user_data['timecamp_user_name']
            changes.append(f"name from '{existing_user['display_name']}' to '{tc_user_data['timecamp_user_name']}'")
        
        # Check group update (only if not disabled)
        if not self.config.disable_group_updates and str(existing_user.get('group_id')) != str(target_group_id):
            updates['groupId'] = target_group_id
            changes.append(f"group to '{target_group_name}' (ID: {target_group_id})")
        elif self.config.disable_group_updates and str(existing_user.get('group_id')) != str(target_group_id):
            logger.debug(f"Skipping group update for user {email} due to disable_group_updates config")
        
        # Check role update (only if not disabled)
        if not self.config.disable_role_updates:
            desired_role = tc_user_data['timecamp_role']
            role_map = {'administrator': '1', 'supervisor': '2', 'user': '3', 'guest': '5'}
            desired_role_id = role_map.get(desired_role, '3')
            
            # Get current role for this user in their group
            user_roles = current_roles.get(str(user_id), [])
            current_role_id = None
            for role_assignment in user_roles:
                if str(role_assignment.get('group_id')) == str(existing_user.get('group_id')):
                    current_role_id = role_assignment.get('role_id')
                    break
            
            if current_role_id != desired_role_id:
                updates['role_id'] = desired_role_id
                changes.append(f"role to '{desired_role}'")
        else:
            logger.debug(f"Skipping role update for user {email} due to disable_role_updates config")
        
        # Apply updates
        if updates:
            if not dry_run:
                logger.info(f"Updating user {email}: {', '.join(changes)}")
                self.api.update_user(user_id, updates, existing_user['group_id'])
                
                # Always set added_manually to 0 after any update to ensure proper tracking
                logger.info(f"Setting added_manually=0 for user {email} after update")
                self.api.update_user_setting(user_id, 'added_manually', '0')
            else:
                logger.info(f"[DRY RUN] Would update user {email}: {', '.join(changes)}")
                logger.info(f"[DRY RUN] Would set added_manually=0 for user {email} after update")
        
        # Handle additional email
        if 'timecamp_real_email' in tc_user_data:
            current_add_email = additional_emails.get(user_id)
            if current_add_email != tc_user_data['timecamp_real_email']:
                if not dry_run:
                    logger.info(f"Updating additional email for user {email}")
                    self.api.set_additional_email(user_id, tc_user_data['timecamp_real_email'])
                    logger.info(f"Setting added_manually=0 for user {email} after additional email update")
                    self.api.update_user_setting(user_id, 'added_manually', '0')
                else:
                    logger.info(f"[DRY RUN] Would update additional email for user {email}")
                    logger.info(f"[DRY RUN] Would set added_manually=0 for user {email} after additional email update")
        
        # Handle external ID
        if tc_user_data.get('timecamp_external_id') and not self.config.disable_external_id_sync:
            current_ext_id = external_ids.get(user_id)
            if current_ext_id != tc_user_data['timecamp_external_id']:
                if not dry_run:
                    logger.info(f"Updating external ID for user {email}")
                    self.api.update_user_setting(user_id, 'external_id', tc_user_data['timecamp_external_id'])
                    logger.info(f"Setting added_manually=0 for user {email} after external ID update")
                    self.api.update_user_setting(user_id, 'added_manually', '0')
                else:
                    logger.info(f"[DRY RUN] Would update external ID for user {email}")
                    logger.info(f"[DRY RUN] Would set added_manually=0 for user {email} after external ID update")
    
    def _create_new_user(self, tc_user_data: Dict[str, Any], 
                        target_group_id: int, target_group_name: str,
                        dry_run: bool) -> None:
        """Create a new user in TimeCamp."""
        email = tc_user_data['timecamp_email']
        name = tc_user_data['timecamp_user_name']
        
        if not dry_run:
            logger.info(f"Creating new user: {email} ({name}) in group '{target_group_name}'")
            response = self.api.add_user(email, name, target_group_id)
            logger.debug(f"User creation response: {response}")
            
            # Store for later processing
            self.newly_created_users.append({
                'email': email,
                'name': name,
                'group_id': target_group_id,
                'real_email': tc_user_data.get('timecamp_real_email'),
                'external_id': tc_user_data.get('timecamp_external_id'),
                'role': tc_user_data.get('timecamp_role', 'user')
            })
        else:
            logger.info(f"[DRY RUN] Would create user: {email} in group '{target_group_name}'")
    
    def _handle_deactivations(self, timecamp_users: List[Dict[str, Any]],
                            tc_users_by_email: Dict[str, Dict[str, Any]],
                            additional_emails: Dict[int, Optional[str]],
                            processed_user_ids: Set[int],
                            manually_added: Dict[int, bool],
                            dry_run: bool) -> None:
        """Handle deactivation of users not in the prepared data or marked inactive."""
        # Create a set of all emails from prepared data (both active and inactive)
        prepared_emails = {user['timecamp_email'].lower() for user in timecamp_users}
        
        # Also create a mapping for inactive users
        inactive_users = {
            user['timecamp_email'].lower(): user 
            for user in timecamp_users 
            if user['timecamp_status'] != 'active'
        }
        
        for email, tc_user in tc_users_by_email.items():
            user_id = int(tc_user['user_id'])
            
            # Skip ignored users
            if user_id in self.config.ignored_user_ids:
                continue
            
            # Skip manually added users if configured
            if self.config.disable_manual_user_updates and manually_added.get(user_id, False):
                logger.info(f"Skipping deactivation for manually added user: {email} (ID: {user_id}) due to disable_manual_user_updates config.")
                continue
            
            # Skip if already processed (matched by additional email)
            if user_id in processed_user_ids:
                continue
            
            # Skip already deactivated users
            if not tc_user.get('is_enabled', True):
                continue
            
            # Determine if user should be deactivated
            should_deactivate = False
            reason = ""
            
            if email in inactive_users:
                # User is marked as inactive in prepared data
                should_deactivate = True
                reason = "marked as inactive"
            elif email not in prepared_emails:
                # Check if user has additional email that matches
                add_email = additional_emails.get(user_id)
                if not add_email or add_email.lower() not in prepared_emails:
                    should_deactivate = True
                    reason = "not present in source"
            
            if should_deactivate:
                if not dry_run:
                    logger.info(f"Deactivating user {email} ({reason})")
                    self.api.update_user_setting(user_id, 'disabled_user', '1')
                else:
                    logger.info(f"[DRY RUN] Would deactivate user {email} ({reason})")
    
    def _finalize_new_users(self) -> None:
        """Apply final settings to newly created users."""
        logger.info("Finalizing newly created users...")
        
        # Fetch updated user list
        current_tc_users = self.api.get_users()
        tc_users_by_email = {user['email'].lower(): user for user in current_tc_users}
        
        for new_user in self.newly_created_users:
            email = new_user['email'].lower()
            tc_user = tc_users_by_email.get(email)
            
            if tc_user:
                user_id = int(tc_user['user_id'])
                logger.info(f"Applying final settings to new user {email} (ID: {user_id})")
                
                # Set added_manually to 0
                self.api.update_user_setting(user_id, 'added_manually', '0')
                
                # Set role if not default
                role = new_user.get('role', 'user')
                if role != 'user':
                    role_map = {'administrator': '1', 'supervisor': '2', 'user': '3', 'guest': '5'}
                    role_id = role_map.get(role, '3')
                    logger.info(f"Setting {role} role for new user {email}")
                    self.api.update_user(user_id, {'role_id': role_id}, new_user['group_id'])
                
                # Set additional email if present
                if new_user.get('real_email'):
                    logger.info(f"Setting additional email for new user {email}")
                    self.api.set_additional_email(user_id, new_user['real_email'])
                
                # Set external ID if present
                if new_user.get('external_id') and not self.config.disable_external_id_sync:
                    logger.info(f"Setting external ID for new user {email}")
                    self.api.update_user_setting(user_id, 'external_id', new_user['external_id'])
            else:
                logger.warning(f"Could not find newly created user {email} in final processing")
    
    def sync(self, timecamp_users: List[Dict[str, Any]], dry_run: bool = False) -> None:
        """Main synchronization method."""
        logger.info(f"Starting synchronization with {len(timecamp_users)} users")
        
        # Step 1: Get required groups
        required_groups = self._get_required_groups(timecamp_users)
        logger.info(f"Found {len(required_groups)} unique group paths")
        
        # Step 2: Sync groups
        logger.info("Synchronizing group structure...")
        group_structure = self._sync_groups(required_groups, dry_run)
        
        # Step 3: Sync users
        logger.info("Synchronizing users...")
        self._sync_users(timecamp_users, group_structure, dry_run)
        
        logger.info("Synchronization completed successfully")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Synchronize users and groups with TimeCamp (Version 2)"
    )
    parser.add_argument("--dry-run", action="store_true",
                      help="Simulate actions without making changes")
    parser.add_argument("--debug", action="store_true",
                      help="Enable debug logging")
    parser.add_argument("--input", default="var/timecamp_users.json",
                      help="Input file name (default: var/timecamp_users.json)")
    
    args = parser.parse_args()
    
    # Update logger with debug setting
    global logger
    logger = setup_logger('timecamp_sync_v2', args.debug)
    
    try:
        # Load configuration
        config = TimeCampConfig.from_env()
        logger.info("Loaded configuration")
        logger.debug(f"Root group ID: {config.root_group_id}")
        logger.debug(f"Disable new users: {config.disable_new_users}")
        logger.debug(f"Disable external ID sync: {config.disable_external_id_sync}")
        logger.debug(f"Disable manual user updates: {config.disable_manual_user_updates}")
        logger.debug(f"Disable group updates: {config.disable_group_updates}")
        logger.debug(f"Disable role updates: {config.disable_role_updates}")
        logger.debug(f"Disable groups creation: {config.disable_groups_creation}")
        logger.debug(f"Ignored user IDs: {config.ignored_user_ids}")
        
        # Check if input file exists
        from common.storage import load_json_file, file_exists
        if not file_exists(args.input):
            logger.error(f"Input file not found: {args.input}")
            logger.error("Please run prepare_timecamp_data.py first to generate the input file")
            return 1
        
        # Load prepared TimeCamp users
        timecamp_users = load_json_file(args.input)
        
        logger.info(f"Loaded {len(timecamp_users)} users from {args.input}")
        
        # Initialize API and synchronizer
        api = TimeCampAPI(config)
        synchronizer = TimeCampSynchronizer(api, config)
        
        # Perform synchronization
        logger.info("BY DEFAULT IF ACCOUNT DOESN'T HAVE ENOUGH PAID SEATS, THEY WILL BE ADDED AUTOMATICALLY")
        synchronizer.sync(timecamp_users, args.dry_run)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error during synchronization: {str(e)}")
        raise


if __name__ == "__main__":
    exit(main()) 