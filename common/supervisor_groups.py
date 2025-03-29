import logging
from typing import Dict, List, Any, Set, Tuple, Optional

logger = logging.getLogger('timecamp_sync')

def prepare_user_data(user_data: Dict[str, Any], show_external_id: bool) -> Dict[str, Any]:
    """Clean and prepare user data for processing."""
    from common.utils import clean_name
    
    user = user_data.copy()
    user['name'] = clean_name(
        f"{user['name']} - {user['external_id']}" 
        if show_external_id and user.get('external_id') 
        else user['name']
    )
    # Ensure email is lowercase
    if 'email' in user:
        user['email'] = user['email'].lower()
    return user

def collect_users_and_supervisors(source_data: Dict[str, Any], show_external_id: bool) -> Tuple[Dict[str, Dict[str, Any]], Set[str]]:
    """First pass: collect all users and identify supervisors."""
    users_by_id = {}
    supervisor_ids = set()
    
    for user in source_data['users']:
        # Clean and prepare user data
        user = prepare_user_data(user, show_external_id)
        
        if 'external_id' in user and user['external_id']:
            users_by_id[user['external_id']] = user
            # Identify which users are supervisors
            if user.get('supervisor_id') and user['supervisor_id'].strip():
                supervisor_ids.add(user['supervisor_id'])
    
    return users_by_id, supervisor_ids

def build_supervisor_paths(source_data: Dict[str, Any], 
                        users_by_id: Dict[str, Dict[str, Any]], 
                        supervisor_ids: Set[str]) -> Dict[str, str]:
    """Second pass: build paths for supervisors (top-down approach)."""
    supervisor_paths = {}
    
    # First handle top-level supervisors (those with no supervisor)
    for user in source_data['users']:
        user_id = user.get('external_id')
        if not user_id or user_id not in supervisor_ids:
            continue
            
        has_supervisor = user.get('supervisor_id') and user['supervisor_id'].strip()
        if not has_supervisor:
            # Top-level supervisor gets their own group
            supervisor_paths[user_id] = user.get('name', '')
    
    # Then handle supervisors with supervisors
    more_to_process = True
    while more_to_process:
        more_to_process = False
        for user in source_data['users']:
            user_id = user.get('external_id')
            if not user_id or user_id not in supervisor_ids or user_id in supervisor_paths:
                continue
                
            supervisor_id = user.get('supervisor_id')
            if not supervisor_id or not supervisor_id.strip():
                continue
                
            if supervisor_id in supervisor_paths:
                # Supervisor's supervisor is already processed, add this one
                supervisor_path = supervisor_paths[supervisor_id]
                supervisor_paths[user_id] = f"{supervisor_path}/{user.get('name')}"
                more_to_process = True
    
    return supervisor_paths

def assign_departments_supervisor(source_data: Dict[str, Any], 
                               users_by_id: Dict[str, Dict[str, Any]], 
                               supervisor_ids: Set[str], 
                               supervisor_paths: Dict[str, str]) -> Set[str]:
    """Assign departments based on supervisor hierarchy."""
    department_paths = set()
    
    # First pass: identify users with subordinates
    users_with_subordinates = set()
    for user in source_data['users']:
        supervisor_id = user.get('supervisor_id')
        if supervisor_id and supervisor_id.strip():
            users_with_subordinates.add(supervisor_id)
    
    for user in source_data['users']:
        user_id = user.get('external_id')
        if not user_id:
            continue
            
        # Check if user is a supervisor
        is_a_supervisor = user_id in supervisor_ids
        has_supervisor = user.get('supervisor_id') and user['supervisor_id'].strip()
        
        # Set isManager flag based on having subordinates
        user['isManager'] = user_id in users_with_subordinates
        
        if is_a_supervisor:
            # User is a supervisor - assign to their path in the hierarchy
            if user_id in supervisor_paths:
                user['department'] = supervisor_paths[user_id]
                if user['department']:
                    department_paths.add(user['department'])
                    logger.debug(f"Supervisor {user.get('name')} assigned to group: {user['department']}")
            elif not has_supervisor:
                # Fallback for top-level supervisor
                user['department'] = user.get('name', '')
                if user['department']:
                    department_paths.add(user['department'])
                    logger.debug(f"Top-level supervisor {user.get('name')} assigned to own group: {user['department']}")
        elif has_supervisor:
            # Regular user with supervisor
            supervisor_id = user.get('supervisor_id')
            if supervisor_id in supervisor_paths:
                # Assign to the same group as their supervisor
                user['department'] = supervisor_paths[supervisor_id]
                logger.debug(f"User {user.get('name')} assigned to supervisor's group: {user['department']}")
                if user['department']:
                    department_paths.add(user['department'])
            else:
                # Fallback: direct supervisor's name
                supervisor = users_by_id.get(supervisor_id)
                if supervisor:
                    user['department'] = supervisor.get('name', '')
                    logger.debug(f"User {user.get('name')} assigned to supervisor's group: {user['department']}")
                    if user['department']:
                        department_paths.add(user['department'])
        else:
            # User is not a supervisor and has no supervisor - place in root group
            logger.debug(f"User {user.get('name')} is not a supervisor and has no supervisor, placing in root group")
            user['department'] = ""  # Empty department means root group
    
    return department_paths

def assign_departments_standard(source_data: Dict[str, Any], config) -> Set[str]:
    """Assign departments using the traditional department-based structure."""
    from common.utils import clean_department_path
    
    department_paths = set()
    for user in source_data['users']:
        if user.get('department'):
            user['department'] = clean_department_path(user['department'], config)
            if user['department']:
                department_paths.add(user['department'])
    return department_paths

def process_source_data(source_data: Dict[str, Any], config) -> Tuple[Dict[str, Dict[str, Any]], Set[str]]:
    """
    Process source data to build supervisor-based groups or standard department groups.
    
    Args:
        source_data: The source data containing users information
        config: The TimeCampConfig object containing configuration settings
        
    Returns:
        A tuple containing:
        - A dictionary mapping emails to user data
        - A set of department paths to be created
    """
    # First pass: collect users and identify supervisors
    users_by_id, supervisor_ids = collect_users_and_supervisors(source_data, config.show_external_id)
    
    # If using supervisor-based groups
    department_paths = set()
    if config.use_supervisor_groups:
        # Second pass: build supervisor paths
        supervisor_paths = build_supervisor_paths(source_data, users_by_id, supervisor_ids)
        
        # Third pass: assign departments based on supervisor hierarchy
        department_paths = assign_departments_supervisor(
            source_data, users_by_id, supervisor_ids, supervisor_paths
        )
    else:
        # Traditional department-based structure
        department_paths = assign_departments_standard(source_data, config)

    return {user['email'].lower(): user for user in source_data['users']}, department_paths 