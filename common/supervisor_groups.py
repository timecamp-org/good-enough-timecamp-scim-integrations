import logging
from typing import Dict, List, Any, Set, Tuple, Optional

logger = logging.getLogger('timecamp_sync')

def prepare_user_data(user_data: Dict[str, Any], show_external_id: bool, use_job_title_name: bool = False) -> Dict[str, Any]:
    """Clean and prepare user data for processing."""
    from common.utils import clean_name
    
    user = user_data.copy()
    
    # Format name based on configuration
    base_name = user['name']
    
    # Use job title in name format if enabled and available
    if use_job_title_name and user.get('job_title'):
        base_name = f"{user['job_title']} [{user['name']}]"
    
    # Apply external_id if configured
    user['name'] = clean_name(
        f"{base_name} - {user['external_id']}" 
        if show_external_id and user.get('external_id') 
        else base_name
    )
    # Ensure email is lowercase
    if 'email' in user:
        user['email'] = user['email'].lower()
    return user

def format_supervisor_name_for_group(user_data: Dict[str, Any], config) -> str:
    """Format supervisor name for use as group name, respecting TIMECAMP_USE_JOB_TITLE_NAME_GROUPS setting."""
    from common.utils import clean_name
    
    # Get the original name (this might be already formatted if user processing happened first)
    # We need to work with the original data to apply group-specific formatting
    base_name = user_data['name']
    
    # If the name is already formatted (contains job title), extract just the name part
    # This handles cases where user processing already happened
    if ' [' in base_name and base_name.endswith(']'):
        # Extract name from "Job Title [Name]" format
        bracket_pos = base_name.rfind(' [')
        if bracket_pos > 0:
            name_in_brackets = base_name[bracket_pos + 2:-1]  # Extract "Name" from " [Name]"
            base_name = name_in_brackets
    
    # Use job title in name format if enabled for groups and available
    if config.use_job_title_name_groups and user_data.get('job_title'):
        base_name = f"{user_data['job_title']} [{base_name}]"
    
    # Apply external_id if configured
    formatted_name = clean_name(
        f"{base_name} - {user_data['external_id']}" 
        if config.show_external_id and user_data.get('external_id') 
        else base_name
    )
    
    return formatted_name

def collect_users_and_supervisors(source_data: Dict[str, Any], config) -> Tuple[Dict[str, Dict[str, Any]], Set[str]]:
    """First pass: collect all users and identify supervisors."""
    users_by_id = {}
    supervisor_ids = set()
    
    for user in source_data['users']:
        # Clean and prepare user data
        user = prepare_user_data(user, config.show_external_id, config.use_job_title_name_users)
        
        if 'external_id' in user and user['external_id']:
            users_by_id[user['external_id']] = user
            # Identify which users are supervisors
            if user.get('supervisor_id') and user['supervisor_id'].strip():
                supervisor_ids.add(user['supervisor_id'])
    
    return users_by_id, supervisor_ids

def build_supervisor_paths(source_data: Dict[str, Any], 
                        users_by_id: Dict[str, Dict[str, Any]], 
                        supervisor_ids: Set[str],
                        config) -> Dict[str, str]:
    """Second pass: build paths for supervisors (top-down approach)."""
    supervisor_paths = {}
    
    # First handle top-level supervisors (those with no supervisor)
    for user_id, user in users_by_id.items():
        if user_id not in supervisor_ids:
            continue
            
        has_supervisor = user.get('supervisor_id') and user['supervisor_id'].strip()
        if not has_supervisor:
            # Top-level supervisor gets their own group - use group name formatting
            supervisor_paths[user_id] = format_supervisor_name_for_group(user, config)
    
    # Then handle supervisors with supervisors
    more_to_process = True
    while more_to_process:
        more_to_process = False
        for user_id, user in users_by_id.items():
            if user_id not in supervisor_ids or user_id in supervisor_paths:
                continue
                
            supervisor_id = user.get('supervisor_id')
            if not supervisor_id or not supervisor_id.strip():
                continue
                
            if supervisor_id in supervisor_paths:
                # Supervisor's supervisor is already processed, add this one
                supervisor_path = supervisor_paths[supervisor_id]
                supervisor_name = format_supervisor_name_for_group(user, config)
                supervisor_paths[user_id] = f"{supervisor_path}/{supervisor_name}"
                more_to_process = True
    
    return supervisor_paths

def assign_departments_supervisor(source_data: Dict[str, Any], 
                               users_by_id: Dict[str, Dict[str, Any]], 
                               supervisor_ids: Set[str], 
                               supervisor_paths: Dict[str, str],
                               config) -> Set[str]:
    """Assign departments based on supervisor hierarchy."""
    from common.utils import clean_department_path
    
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
        
        # Set role_id based on having subordinates (2 = Supervisor, 3 = User)
        if user_id in users_with_subordinates:
            user['role_id'] = '2'  # Supervisor role
        else:
            user['role_id'] = '3'  # Regular user role
        
        # Keep isManager flag for backward compatibility
        user['isManager'] = user_id in users_with_subordinates
        
        if is_a_supervisor:
            # User is a supervisor - assign to their path in the hierarchy
            if user_id in supervisor_paths:
                # Apply skip_departments configuration to supervisor paths
                user['department'] = clean_department_path(supervisor_paths[user_id], config)
                if user['department']:
                    department_paths.add(user['department'])
                    logger.debug(f"Supervisor {user.get('name')} assigned to group: {user['department']}")
            elif not has_supervisor:
                # Fallback for top-level supervisor - use group name formatting
                supervisor_group_name = format_supervisor_name_for_group(user, config)
                user['department'] = clean_department_path(supervisor_group_name, config)
                if user['department']:
                    department_paths.add(user['department'])
                    logger.debug(f"Top-level supervisor {user.get('name')} assigned to own group: {user['department']}")
        elif has_supervisor:
            # Regular user with supervisor
            supervisor_id = user.get('supervisor_id')
            if supervisor_id in supervisor_paths:
                # Assign to the same group as their supervisor with skip_departments applied
                user['department'] = clean_department_path(supervisor_paths[supervisor_id], config)
                logger.debug(f"User {user.get('name')} assigned to supervisor's group: {user['department']}")
                if user['department']:
                    department_paths.add(user['department'])
            else:
                # Fallback: direct supervisor's name with group formatting
                supervisor = users_by_id.get(supervisor_id)
                if supervisor:
                    supervisor_group_name = format_supervisor_name_for_group(supervisor, config)
                    user['department'] = clean_department_path(supervisor_group_name, config)
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

def assign_departments_hybrid(source_data: Dict[str, Any], 
                            users_by_id: Dict[str, Dict[str, Any]], 
                            supervisor_ids: Set[str], 
                            supervisor_paths: Dict[str, str],
                            config) -> Set[str]:
    """
    Assign departments using hybrid approach: department + supervisor hierarchy.
    
    This function creates a hierarchical group structure where departments are the top level,
    and supervisors create subgroups within those departments.
    
    Examples of resulting group structure:
    
    Input data:
    - John Doe (external_id: 123, department: "Engineering", job_title: "Engineering Manager", supervisor_id: "")
    - Jane Smith (external_id: 124, department: "Engineering/Frontend", job_title: "Frontend Developer", supervisor_id: "123")
    - Bob Wilson (external_id: 125, department: "Sales/EMEA", job_title: "Sales Manager", supervisor_id: "")
    - Alice Johnson (external_id: 126, department: "Sales/EMEA", job_title: "Sales Rep", supervisor_id: "125")
    
    With hybrid mode and job titles enabled (TIMECAMP_USE_SUPERVISOR_GROUPS=true, TIMECAMP_USE_DEPARTMENT_GROUPS=true, TIMECAMP_USE_JOB_TITLE_NAME=true):
    - John Doe → "Engineering/Engineering Manager [John Doe]" (supervisor gets their own subgroup)
    - Jane Smith → "Engineering/Frontend/Engineering Manager [John Doe]" (user assigned to supervisor's subgroup within their department)
    - Bob Wilson → "Sales/EMEA/Sales Manager [Bob Wilson]" (supervisor gets their own subgroup)
    - Alice Johnson → "Sales/EMEA/Sales Manager [Bob Wilson]" (user assigned to supervisor's subgroup)
    
    This creates TimeCamp groups:
    - Engineering/Engineering Manager [John Doe]
    - Engineering/Frontend/Engineering Manager [John Doe]  
    - Sales/EMEA/Sales Manager [Bob Wilson]
    
    Args:
        source_data: The source data containing users information
        users_by_id: Dictionary mapping external_id to user data
        supervisor_ids: Set of external_ids that are supervisors (have subordinates)
        supervisor_paths: Dictionary mapping supervisor external_id to their path in hierarchy
        config: The TimeCampConfig object containing configuration settings
        
    Returns:
        A set of department paths to be created in TimeCamp
    """
    from common.utils import clean_department_path
    
    department_paths = set()
    
    # First pass: identify users with subordinates
    users_with_subordinates = set()
    for user in source_data['users']:
        supervisor_id = user.get('supervisor_id')
        if supervisor_id and supervisor_id.strip():
            users_with_subordinates.add(supervisor_id)
    
    # Second pass: build department-supervisor paths
    for user in source_data['users']:
        user_id = user.get('external_id')
        if not user_id:
            continue
            
        # Clean the original department path
        original_department = clean_department_path(user.get('department', ''), config)
        
        # Check if user is a supervisor
        is_a_supervisor = user_id in supervisor_ids
        has_supervisor = user.get('supervisor_id') and user['supervisor_id'].strip()
        
        # Set role_id based on having subordinates (2 = Supervisor, 3 = User)
        if user_id in users_with_subordinates:
            user['role_id'] = '2'  # Supervisor role
        else:
            user['role_id'] = '3'  # Regular user role
        
        # Keep isManager flag for backward compatibility
        user['isManager'] = user_id in users_with_subordinates
        
        if original_department:
            # User has a department
            if is_a_supervisor and user_id in supervisor_paths:
                # Supervisor: combine department with supervisor path
                supervisor_name = supervisor_paths[user_id].split('/')[-1]  # Get the last part (supervisor's own name)
                user['department'] = f"{original_department}/{supervisor_name}"
                logger.debug(f"Supervisor {user.get('name')} assigned to hybrid group: {user['department']}")
            elif has_supervisor:
                # Regular user with supervisor: combine department with supervisor's name
                supervisor_id = user.get('supervisor_id')
                supervisor = users_by_id.get(supervisor_id)
                if supervisor:
                    supervisor_name = format_supervisor_name_for_group(supervisor, config)  # Use group formatting
                    user['department'] = f"{original_department}/{supervisor_name}"
                    logger.debug(f"User {user.get('name')} assigned to hybrid group: {user['department']}")
                else:
                    # Fallback: just use department
                    user['department'] = original_department
                    logger.debug(f"User {user.get('name')} assigned to department group (supervisor not found): {user['department']}")
            else:
                # User without supervisor: just use department
                user['department'] = original_department
                logger.debug(f"User {user.get('name')} assigned to department group: {user['department']}")
        else:
            # User has no department - fall back to supervisor-only logic
            if is_a_supervisor and user_id in supervisor_paths:
                user['department'] = supervisor_paths[user_id]
                logger.debug(f"Supervisor {user.get('name')} (no dept) assigned to group: {user['department']}")
            elif has_supervisor:
                supervisor_id = user.get('supervisor_id')
                if supervisor_id in supervisor_paths:
                    user['department'] = supervisor_paths[supervisor_id]
                    logger.debug(f"User {user.get('name')} (no dept) assigned to supervisor's group: {user['department']}")
                else:
                    supervisor = users_by_id.get(supervisor_id)
                    if supervisor:
                        supervisor_group_name = format_supervisor_name_for_group(supervisor, config)
                        user['department'] = supervisor_group_name
                        logger.debug(f"User {user.get('name')} (no dept) assigned to supervisor's group: {user['department']}")
                    else:
                        user['department'] = ""  # Root group
                        logger.debug(f"User {user.get('name')} (no dept, no supervisor) placed in root group")
            else:
                # No department, no supervisor - place in root group
                user['department'] = ""
                logger.debug(f"User {user.get('name')} (no dept, no supervisor) placed in root group")
        
        # Add to department paths if not empty
        if user.get('department'):
            department_paths.add(user['department'])
    
    return department_paths

def process_source_data(source_data: Dict[str, Any], config) -> Tuple[Dict[str, Dict[str, Any]], Set[str]]:
    """
    Process source data to build supervisor-based groups, standard department groups, or hybrid structure.
    
    Args:
        source_data: The source data containing users information
        config: The TimeCampConfig object containing configuration settings
        
    Returns:
        A tuple containing:
        - A dictionary mapping emails to user data
        - A set of department paths to be created
    """
    # First pass: collect users and identify supervisors
    users_by_id, supervisor_ids = collect_users_and_supervisors(source_data, config)
    
    department_paths = set()
    
    if config.use_supervisor_groups and config.use_department_groups:
        # Hybrid approach: combine departments with supervisor hierarchy
        logger.debug("Using hybrid approach: departments + supervisors")
        
        # Second pass: build supervisor paths
        supervisor_paths = build_supervisor_paths(source_data, users_by_id, supervisor_ids, config)
        
        # Third pass: assign departments using hybrid approach
        department_paths = assign_departments_hybrid(
            source_data, users_by_id, supervisor_ids, supervisor_paths, config
        )
    elif config.use_supervisor_groups:
        # Pure supervisor-based groups
        logger.debug("Using supervisor-based groups only")
        
        # Second pass: build supervisor paths
        supervisor_paths = build_supervisor_paths(source_data, users_by_id, supervisor_ids, config)
        
        # Third pass: assign departments based on supervisor hierarchy
        department_paths = assign_departments_supervisor(
            source_data, users_by_id, supervisor_ids, supervisor_paths, config
        )
    else:
        # Traditional department-based structure
        logger.debug("Using traditional department-based structure")
        # Still process users to get formatted names and set up emails correctly
        for user in source_data['users']:
            user = prepare_user_data(user, config.show_external_id, config.use_job_title_name_users)
            if 'external_id' in user and user['external_id']:
                users_by_id[user['external_id']] = user
        department_paths = assign_departments_standard(source_data, config)

    # IMPORTANT: Sync the updated departments back to users_by_id
    # The assign_departments_* functions update source_data['users'], but we need
    # to sync those changes back to our users_by_id dictionary
    for user in source_data['users']:
        user_id = user.get('external_id')
        if user_id and user_id in users_by_id:
            # Update the department and role information
            users_by_id[user_id]['department'] = user.get('department', '')
            users_by_id[user_id]['role_id'] = user.get('role_id', '3')
            users_by_id[user_id]['isManager'] = user.get('isManager', False)

    # Return processed users by email instead of original source data
    return {user['email'].lower(): user for user in users_by_id.values()}, department_paths 