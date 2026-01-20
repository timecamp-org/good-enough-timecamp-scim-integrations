#!/usr/bin/env python3
"""
Stage 1: Prepare TimeCamp Data
This script reads the source var/users.json and generates var/timecamp_users.json
with the final structure ready for TimeCamp synchronization.
"""

import os
import json
import re
import argparse
from typing import Dict, List, Any, Set, Tuple, Optional
from dotenv import load_dotenv
from common.logger import setup_logger
from common.utils import TimeCampConfig, clean_name, get_users_file
from common.supervisor_groups import process_source_data

# Load environment variables
load_dotenv()

# Initialize logger
logger = setup_logger('prepare_timecamp_data')


def check_force_supervisor_exists(source_data: Dict[str, Any]) -> bool:
    """Check if any user has force_supervisor_role=true in the source data."""
    users = source_data.get('users', [])
    for user in users:
        if user.get('force_supervisor_role') is True:
            return True
    return False


def determine_role(source_user: Dict[str, Any], config: TimeCampConfig, force_supervisor_exists: bool = False) -> str:
    """Determine the TimeCamp role based on source user data."""
    # Priority 1: Check for force_global_admin_role (highest priority)
    if source_user.get('force_global_admin_role') is True:
        return 'administrator'
    
    # Priority 2: Check for force_supervisor_role
    if source_user.get('force_supervisor_role') is True:
        return 'supervisor'
    
    # If force_supervisor_role exists in dataset, disable other supervisor role logic
    # and return 'user' for non-forced users
    if force_supervisor_exists:
        return 'user'
    
    # Priority 3: If configured to use is_supervisor boolean field
    if config.use_is_supervisor_role:
        is_supervisor = source_user.get('is_supervisor', False)
        if isinstance(is_supervisor, bool):
            return 'supervisor' if is_supervisor else 'user'
        elif isinstance(is_supervisor, str):
            # Handle string representations of boolean
            return 'supervisor' if is_supervisor.lower() in ('true', '1', 'yes') else 'user'
        # Fall back to default if is_supervisor field is not valid
        return 'user'
    
    # Priority 4: Original behavior - Check if role_id is specified in source data
    role_id = source_user.get('role_id', '3')
    
    # Map role IDs to role names
    role_map = {
        '1': 'administrator',
        '2': 'supervisor', 
        '3': 'user',
        '5': 'guest'
    }
    
    return role_map.get(role_id, 'user')


def replace_email_domain(email: str, new_domain: str) -> str:
    """Replace the domain part of an email address with a new domain."""
    if not new_domain or not email:
        return email
    
    # Ensure the new domain starts with @
    if not new_domain.startswith('@'):
        new_domain = '@' + new_domain
    
    # Split the email at @ and replace the domain part
    email_parts = email.split('@')
    if len(email_parts) == 2:
        return email_parts[0] + new_domain
    
    return email


def process_group_path(department: Optional[str], config: TimeCampConfig) -> str:
    """
    Process the department path.
    Applies regex substitution if configured.
    Supports multiple rules separated by ;;;
    """
    if not department:
        return ""
    
    # Apply regex substitution if configured
    if config.change_groups_regex:
        # Split by ;;; for multiple rules
        rules = config.change_groups_regex.split(';;;')
        current_department = department
        
        for rule in rules:
            if not rule.strip():
                continue
                
            # Expected format: "pattern|||replacement"
            parts = rule.split('|||')
            if len(parts) == 2:
                pattern = parts[0]
                replacement = parts[1]
                try:
                    # Use re.sub to replace pattern with replacement
                    new_department = re.sub(pattern, replacement, current_department)
                    if new_department != current_department:
                        # Only log at debug level to avoid spam, but maybe info for the first few times?
                        # Using debug is safer for large datasets
                        logger.debug(f"Applied group regex transform: '{current_department}' -> '{new_department}'")
                        current_department = new_department
                except re.error as e:
                    logger.error(f"Invalid regex in TIMECAMP_CHANGE_GROUPS_REGEX rule '{rule}': {e}")
        
        return current_department
            
    return department


def get_users_to_exclude(users: List[Dict[str, Any]], config: TimeCampConfig) -> Set[str]:
    """
    Identify users to exclude based on regex.
    Returns a set of emails (lowercased) to exclude.
    """
    if not config.exclude_regex:
        return set()
        
    logger.info(f"Filtering users with regex: {config.exclude_regex}")
    
    excluded_emails = set()
    excluded_count = 0
    
    try:
        pattern = re.compile(config.exclude_regex)
    except re.error as e:
        logger.error(f"Invalid regex pattern provided: {e}")
        logger.warning("Regex filtering skipped due to invalid pattern")
        return set()

    for user in users:
        # Build context string for matching
        dept = str(user.get('department', '')).replace('"', "'")
        title = str(user.get('job_title', '')).replace('"', "'")
        email = str(user.get('email', '')).replace('"', "'")
        
        context_string = f'department="{dept}" job_title="{title}" email="{email}"'
        
        if pattern.search(context_string):
            if user.get('email'):
                excluded_emails.add(user['email'].lower())
                excluded_count += 1
                logger.debug(f"Marking user for exclusion: {email} (matched regex)")
            
    logger.info(f"Marked {excluded_count} users for exclusion matching regex")
    return excluded_emails


def prepare_timecamp_users(source_data: Dict[str, Any], config: TimeCampConfig) -> List[Dict[str, Any]]:
    """Process source data and prepare the final TimeCamp user structure."""
    # Check if force_supervisor_role exists in the source data
    force_supervisor_exists = check_force_supervisor_exists(source_data)
    
    # Identify users to exclude (but keep them for processing structure)
    excluded_emails = set()
    if config.exclude_regex and 'users' in source_data:
        excluded_emails = get_users_to_exclude(source_data['users'], config)
    
    if force_supervisor_exists:
        logger.info("Detected force_supervisor_role in dataset - other supervisor role logic will be disabled")
    
    # Process source data using the supervisor_groups module
    # This applies all the configuration options:
    # - TIMECAMP_USE_SUPERVISOR_GROUPS
    # - TIMECAMP_USE_DEPARTMENT_GROUPS  
    # - TIMECAMP_USE_JOB_TITLE_NAME_USERS
    # - TIMECAMP_USE_JOB_TITLE_NAME_GROUPS
    # - TIMECAMP_SHOW_EXTERNAL_ID
    # - TIMECAMP_SKIP_DEPARTMENTS
    processed_users, department_paths = process_source_data(source_data, config)
    
    logger.debug(f"Processed {len(processed_users)} users with {len(department_paths)} unique department paths")
    
    timecamp_users = []
    
    for email, user_data in processed_users.items():
        # Skip excluded users
        if email in excluded_emails:
            continue

        # Determine status
        status = 'active' if user_data.get('status', '').lower() == 'active' else 'inactive'
        
        # The department/group breadcrumb has already been processed with all configurations
        group_breadcrumb = user_data.get('department', '')
        
        # Apply group path transformation (regex)
        group_breadcrumb = process_group_path(group_breadcrumb, config)
        
        # Force global admins to main group (empty breadcrumb)
        if user_data.get('force_global_admin_role') is True:
            group_breadcrumb = ''
        
        # Determine role
        role = determine_role(user_data, config, force_supervisor_exists)
        
        # Apply email domain replacement if configured
        timecamp_email = replace_email_domain(email, config.replace_email_domain)
        
        # Create TimeCamp user structure
        timecamp_user = {
            'timecamp_external_id': user_data.get('external_id', ''),
            'timecamp_user_name': user_data['name'],  # Already formatted by process_source_data
            'timecamp_email': timecamp_email,
            'timecamp_groups_breadcrumb': group_breadcrumb,
            'timecamp_status': status,
            'timecamp_role': role,
            'raw_data': user_data  # Include the entire source object as raw_data
        }
        
        # Add real_email if present and different from primary email
        if user_data.get('real_email') and user_data['real_email'].lower() != email.lower():
            # Also apply domain replacement to real_email if configured
            timecamp_real_email = replace_email_domain(user_data['real_email'], config.replace_email_domain)
            timecamp_user['timecamp_real_email'] = timecamp_real_email
        
        timecamp_users.append(timecamp_user)
    
    # Sort users by email for consistent output
    timecamp_users.sort(key=lambda x: x['timecamp_email'])
    
    return timecamp_users


def main():
    """Main function to prepare TimeCamp data."""
    parser = argparse.ArgumentParser(
        description="Prepare TimeCamp user data from source var/users.json"
    )
    parser.add_argument("--debug", action="store_true", 
                      help="Enable debug logging")
    parser.add_argument("--output", default="var/timecamp_users.json",
                      help="Output file name (default: var/timecamp_users.json)")
    
    args = parser.parse_args()
    
    # Update logger with debug setting
    global logger
    logger = setup_logger('prepare_timecamp_data', args.debug)
    
    try:
        # Load configuration
        # For preparation stage, we don't strictly need API credentials as we are just processing local data
        config = TimeCampConfig.from_env(validate_auth=False)
        logger.info("Loaded configuration from environment")
        
        # Log all configuration options to show they're being considered
        logger.info("Configuration settings:")
        logger.info(f"  - TIMECAMP_USE_SUPERVISOR_GROUPS: {config.use_supervisor_groups}")
        logger.info(f"  - TIMECAMP_USE_DEPARTMENT_GROUPS: {config.use_department_groups}")
        if config.use_supervisor_groups and config.use_department_groups:
            logger.info("    → Using HYBRID mode: Department groups with supervisor subgroups")
        elif config.use_supervisor_groups:
            logger.info("    → Using SUPERVISOR-ONLY mode: Groups based on supervisor hierarchy")
        else:
            logger.info("    → Using DEPARTMENT-ONLY mode: Traditional department-based groups")
        
        logger.info(f"  - TIMECAMP_USE_JOB_TITLE_NAME_USERS: {config.use_job_title_name_users}")
        if config.use_job_title_name_users:
            logger.info("    → User names will be formatted as: 'Job Title [Name]'")
            
        logger.info(f"  - TIMECAMP_USE_JOB_TITLE_NAME_GROUPS: {config.use_job_title_name_groups}")
        if config.use_job_title_name_groups:
            logger.info("    → Supervisor group names will be formatted as: 'Job Title [Name]'")
        
        logger.info(f"  - TIMECAMP_SHOW_EXTERNAL_ID: {config.show_external_id}")
        if config.show_external_id:
            logger.info("    → External IDs will be appended to user names")
            
        logger.info(f"  - TIMECAMP_SKIP_DEPARTMENTS: '{config.skip_departments}'")
        if config.skip_departments:
            prefixes = [p.strip() for p in config.skip_departments.split(',') if p.strip()]
            if len(prefixes) == 1:
                logger.info(f"    → Will skip department prefix: '{prefixes[0]}'")
            else:
                logger.info(f"    → Will skip department prefixes: {prefixes}")
            
        logger.info(f"  - TIMECAMP_REPLACE_EMAIL_DOMAIN: '{config.replace_email_domain}'")
        if config.replace_email_domain:
            logger.info(f"    → Will replace email domains with: '{config.replace_email_domain}'")
            
        logger.info(f"  - TIMECAMP_EXCLUDE_REGEX: '{config.exclude_regex}'")
        if config.exclude_regex:
            logger.info(f"    → Will exclude users matching regex against format: department=\"DEPT\" job_title=\"TITLE\" email=\"EMAIL\"")

        logger.info(f"  - TIMECAMP_CHANGE_GROUPS_REGEX: '{config.change_groups_regex}'")
        if config.change_groups_regex:
            if '|||' in config.change_groups_regex:
                if ';;;' in config.change_groups_regex:
                    logger.info(f"    → Will transform group paths using multiple regex rules separated by ;;;")
                else:
                    logger.info(f"    → Will transform group paths using regex substitution (pattern|||replacement)")
            else:
                logger.warning(f"    → TIMECAMP_CHANGE_GROUPS_REGEX format seems invalid (missing '|||' separator)")

        logger.info(f"  - TIMECAMP_USE_IS_SUPERVISOR_ROLE: {config.use_is_supervisor_role}")
        if config.use_is_supervisor_role:
            logger.info("    → Will determine supervisor role from 'is_supervisor' boolean field")
        else:
            logger.info("    → Will determine role from 'role_id' field (default behavior)")
        
        logger.info("  - Force role fields:")
        logger.info("    → force_global_admin_role=true → Administrator role (highest priority)")
        logger.info("    → force_supervisor_role=true → Supervisor role (if any exist, disables other supervisor logic)")
            
        # Get source users file
        users_file = get_users_file()
        logger.info(f"Reading source data from: {users_file}")
        
        # Load source data
        from common.storage import load_json_file
        source_data = load_json_file(users_file)
        
        logger.info(f"Loaded {len(source_data.get('users', []))} users from source")
        
        # Process and prepare TimeCamp users
        timecamp_users = prepare_timecamp_users(source_data, config)
        
        logger.info(f"Prepared {len(timecamp_users)} users for TimeCamp")
        
        # Count active/inactive users
        active_count = sum(1 for u in timecamp_users if u['timecamp_status'] == 'active')
        inactive_count = len(timecamp_users) - active_count
        logger.info(f"Active users: {active_count}, Inactive users: {inactive_count}")
        
        # Count users by role
        role_counts = {}
        for user in timecamp_users:
            role = user['timecamp_role']
            role_counts[role] = role_counts.get(role, 0) + 1
        
        for role, count in sorted(role_counts.items()):
            logger.info(f"{role.capitalize()} users: {count}")
        
        # Count users with forced roles from source data
        force_admin_count = sum(1 for u in source_data.get('users', []) if u.get('force_global_admin_role') is True)
        force_supervisor_count = sum(1 for u in source_data.get('users', []) if u.get('force_supervisor_role') is True)
        
        if force_admin_count > 0:
            logger.info(f"Users with force_global_admin_role: {force_admin_count}")
        if force_supervisor_count > 0:
            logger.info(f"Users with force_supervisor_role: {force_supervisor_count}")
        
        # Count unique group paths
        unique_groups = {u['timecamp_groups_breadcrumb'] for u in timecamp_users if u['timecamp_groups_breadcrumb']}
        logger.info(f"Unique group paths: {len(unique_groups)}")
        
        # Write output
        from common.storage import save_json_file
        save_json_file(timecamp_users, args.output)
        
        logger.info(f"Successfully wrote TimeCamp data to: {args.output}")
        
        # Show some sample data in debug mode
        if args.debug and timecamp_users:
            logger.debug("Sample user data:")
            logger.debug(json.dumps(timecamp_users[0], indent=2))
            
    except Exception as e:
        logger.error(f"Error preparing TimeCamp data: {str(e)}")
        raise


if __name__ == "__main__":
    main() 