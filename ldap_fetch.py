import os
import json
import ldap
import uuid
from dotenv import load_dotenv
from common.logger import setup_logger
from ldap.controls import SimplePagedResultsControl

logger = setup_logger()

def normalize_text(text):
    """Ensure text has proper characters instead of escaped Unicode."""
    if not text:
        return ""
    return text

def extract_ou_path(dn):
    """Extract OU path from distinguished name."""
    if not dn:
        return ""
    
    # Split the DN into parts
    parts = dn.split(',')
    
    # Extract OUs (skip the first part as it's the user CN)
    ou_parts = []
    for part in parts:
        if part.strip().lower().startswith('ou='):
            # Remove the 'OU=' prefix and extract the OU name
            ou_name = part.strip()[3:]
            ou_parts.append(ou_name)
    
    # Reverse the order to get top-level OU first
    ou_parts.reverse()
    
    # Join OUs with forward slash
    return '/'.join(ou_parts)

def get_ldap_config():
    """Load and validate LDAP configuration from environment variables."""
    load_dotenv()
    
    config = {
        'host': os.getenv('LDAP_HOST'),
        'port': os.getenv('LDAP_PORT', '389'),
        'domain': os.getenv('LDAP_DOMAIN'),
        'dn': os.getenv('LDAP_DN'),
        'username': os.getenv('LDAP_USERNAME'),
        'password': os.getenv('LDAP_PASSWORD'),
        'filter': os.getenv('LDAP_FILTER', '(&(objectClass=person)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))'),
        'page_size': int(os.getenv('LDAP_PAGE_SIZE', '1000')),
        'use_samaccountname': os.getenv('LDAP_USE_SAMACCOUNTNAME', 'false').lower() == 'true',
        'use_ou_structure': os.getenv('LDAP_USE_OU_STRUCTURE', 'false').lower() == 'true',
        'use_supervisor_groups': os.getenv('TIMECAMP_USE_SUPERVISOR_GROUPS', 'false').lower() == 'true'
    }
    
    # Validate required configuration
    required_fields = ['host', 'domain', 'dn', 'username', 'password']
    missing_fields = [field for field in required_fields if not config[field]]
    
    if missing_fields:
        raise ValueError(f"Missing required LDAP configuration: {', '.join(missing_fields)}")
    
    return config

def connect_to_ldap(config):
    """Connect to LDAP server and return connection object."""
    logger.info(f"Connecting to LDAP server {config['host']}:{config['port']}")
    
    # Connect to LDAP server
    ldap_uri = f"ldap://{config['host']}:{config['port']}"
    ldap_connection = ldap.initialize(ldap_uri)
    ldap_connection.protocol_version = ldap.VERSION3
    
    # Set option to refer to referrals
    ldap_connection.set_option(ldap.OPT_REFERRALS, 0)
    
    # Set size limit and time limit to avoid server-side restrictions
    ldap_connection.set_option(ldap.OPT_SIZELIMIT, 0)  # No client-side size limit
    ldap_connection.set_option(ldap.OPT_TIMELIMIT, 0)  # No client-side time limit
    
    # Construct the bind DN (distinguished name)
    bind_dn = f"{config['username']}@{config['domain']}" if '@' not in config['username'] else config['username']
    
    # Bind to the server
    ldap_connection.simple_bind_s(bind_dn, config['password'])
    logger.info("Successfully authenticated with LDAP server")
    
    return ldap_connection

def convert_guid(guid_bytes):
    """Convert binary GUID to string format."""
    try:
        guid = uuid.UUID(bytes_le=guid_bytes)
        return str(guid)
    except Exception as e:
        logger.warning(f"Error converting GUID: {str(e)}")
        return "unknown"

def decode_attribute(value):
    """Decode binary attribute value."""
    if isinstance(value[0], bytes):
        return value[0].decode('utf-8')
    return value[0]

def process_attributes(attributes):
    """Process LDAP attributes and handle binary data."""
    user_attrs = {}
    
    # Handle the case where attributes could be a list
    if isinstance(attributes, list):
        logger.debug(f"Attributes returned as list")
        return None
    
    # Process attributes as dictionary
    for key, value in attributes.items():
        if not value:
            user_attrs[key] = ""
            continue
            
        if key == 'objectGUID':
            user_attrs[key] = convert_guid(value[0])
        elif key == 'manager':
            user_attrs[key] = decode_attribute(value)
        else:
            user_attrs[key] = decode_attribute(value)
    
    return user_attrs

def get_manager_guid(ldap_connection, manager_dn, manager_guid_cache):
    """Get manager's GUID from DN, using cache if available."""
    # Check if we've already retrieved this manager's GUID
    if manager_dn in manager_guid_cache:
        return manager_guid_cache[manager_dn]
    
    # We need to search for the manager's objectGUID based on their DN
    try:
        manager_result = ldap_connection.search_s(
            manager_dn, 
            ldap.SCOPE_BASE,
            '(objectClass=*)',
            ['objectGUID']
        )
        
        if manager_result and len(manager_result) > 0 and len(manager_result[0]) > 1:
            manager_guid = manager_result[0][1].get('objectGUID', [None])[0]
            if manager_guid:
                manager_id = convert_guid(manager_guid)
                # Cache the result
                manager_guid_cache[manager_dn] = manager_id
                return manager_id
    except Exception as e:
        logger.warning(f"Error retrieving manager's GUID for {manager_dn}: {str(e)}")
    
    return ""

def get_department_value(user_attrs, dn, use_ou_structure):
    """Determine department value based on configuration."""
    if use_ou_structure:
        # Use OU path from DN as department
        department = extract_ou_path(dn)
    else:
        # Use department attribute
        department = normalize_text(user_attrs.get('department', ''))
    
    return department

def create_user_object(user_attrs, manager_id, department, config):
    """Create transformed user object from LDAP attributes."""
    transformed_user = {
        "external_id": user_attrs.get('objectGUID', ''),
        "name": normalize_text(user_attrs.get('displayName', '')),
        "email": user_attrs.get('mail', '').lower(),
        "department": department,
        "status": "active",
        "supervisor_id": manager_id,
    }
    
    # If display name is not available, try to construct from first and last name
    if not transformed_user["name"]:
        first_name = user_attrs.get('givenName', '')
        last_name = user_attrs.get('sn', '')
        if first_name or last_name:
            transformed_user["name"] = normalize_text(f"{first_name} {last_name}".strip())
    
    # Handle email generation based on configuration
    original_mail = user_attrs.get('mail', '').lower()
    
    if config['use_samaccountname']:
        # Prioritize sAMAccountName for email
        if user_attrs.get('sAMAccountName'):
            transformed_user["email"] = f"{user_attrs['sAMAccountName']}@{config['domain']}".lower()
            # Always store original mail as real_email if available
            if original_mail:
                transformed_user["real_email"] = original_mail
    # If email is still missing, fall back to sAMAccountName
    elif not transformed_user["email"] and user_attrs.get('sAMAccountName'):
        transformed_user["email"] = f"{user_attrs['sAMAccountName']}@{config['domain']}".lower()
        # Always store original mail as real_email if available
        if original_mail:
            transformed_user["real_email"] = original_mail
    
    return transformed_user

def search_ldap_users(ldap_connection, config):
    """Search LDAP for users and process results with pagination."""
    # Define search parameters
    search_base = config['dn']
    search_scope = ldap.SCOPE_SUBTREE
    
    # Define attributes to retrieve
    retrieve_attributes = [
        'objectGUID', 'sAMAccountName', 'mail', 'displayName', 
        'department', 'title', 'givenName', 'sn', 'mobile',
        'telephoneNumber', 'streetAddress', 'postalCode', 'manager'
    ]
    
    # Initialize the pagination control
    page_control = SimplePagedResultsControl(True, size=config['page_size'], cookie='')
    
    users = []
    manager_guid_cache = {}  # Cache to store manager GUIDs
    
    while True:
        # Search with the pagination control
        logger.info(f"Searching LDAP with filter: {config['filter']} (page size: {config['page_size']})")
        try:
            msgid = ldap_connection.search_ext(
                search_base,
                search_scope,
                config['filter'],
                retrieve_attributes,
                serverctrls=[page_control]
            )
            
            # Get the results
            result_type, result_data, msgid, server_controls = ldap_connection.result3(msgid, all=1)
            
            # Process the results
            for entry in result_data:
                # Skip non-user entries
                if not entry or len(entry) < 2:
                    continue
                    
                dn, attributes = entry
                
                # Process user attributes
                user_attrs = process_attributes(attributes)
                if not user_attrs:
                    continue
                
                # Get manager ID if available
                manager_id = ""
                if user_attrs.get('manager'):
                    manager_id = get_manager_guid(ldap_connection, user_attrs['manager'], manager_guid_cache)
                
                # Determine department value based on configuration
                department = get_department_value(user_attrs, dn, config['use_ou_structure'])
                
                # Create transformed user object
                transformed_user = create_user_object(user_attrs, manager_id, department, config)
                
                users.append(transformed_user)
            
            # Check if there are more pages
            page_controls = [
                control 
                for control in server_controls 
                if control.controlType == SimplePagedResultsControl.controlType
            ]
            
            if not page_controls or not page_controls[0].cookie:
                # End of pages
                break
            
            # Set cookie for next page
            page_control.cookie = page_controls[0].cookie
            
            logger.info(f"Fetched {len(users)} users so far...")
            
        except ldap.LDAPError as e:
            logger.error(f"LDAP search error: {str(e)}")
            if 'desc' in e.args[0] and e.args[0]['desc'] == 'Size limit exceeded':
                logger.warning("Size limit exceeded. Consider reducing LDAP_PAGE_SIZE in .env")
            raise
    
    return users, manager_guid_cache

def fetch_missing_supervisors(ldap_connection, config, users, manager_guid_cache):
    """Fetch supervisors that are referenced but not downloaded in the initial search."""
    if not config['use_supervisor_groups']:
        return []

    logger.info("Checking for missing supervisors...")

    # Collect all supervisor IDs that are referenced
    referenced_supervisor_ids = {user.get('supervisor_id') for user in users if user.get('supervisor_id')}
    
    # Identify which supervisor IDs are not in our fetched users
    existing_ids = {user.get('external_id') for user in users}
    missing_supervisor_ids = {sid for sid in referenced_supervisor_ids if sid and sid not in existing_ids}
    
    if not missing_supervisor_ids:
        logger.info("No missing supervisors found.")
        return []

    logger.info(f"Found {len(missing_supervisor_ids)} missing supervisors. Fetching them...")
    
    # Invert the manager_guid_cache to get DN from GUID
    manager_dn_by_guid = {}
    for dn, guid in manager_guid_cache.items():
        if guid in missing_supervisor_ids:
            manager_dn_by_guid[guid] = dn
    
    missing_supervisors = []
    
    # Fetch each missing supervisor individually
    for supervisor_id in missing_supervisor_ids:
        if supervisor_id in manager_dn_by_guid:
            dn = manager_dn_by_guid[supervisor_id]
            try:
                # Use a broader filter to find the supervisor even if they're disabled
                supervisor_result = ldap_connection.search_s(
                    dn,
                    ldap.SCOPE_BASE,
                    '(objectClass=*)',
                    [
                        'objectGUID', 'sAMAccountName', 'mail', 'displayName', 
                        'department', 'title', 'givenName', 'sn', 'mobile',
                        'telephoneNumber', 'streetAddress', 'postalCode', 'manager',
                        'userAccountControl'
                    ]
                )
                
                if supervisor_result and len(supervisor_result) > 0 and len(supervisor_result[0]) > 1:
                    supervisor_dn, supervisor_attrs = supervisor_result[0]
                    processed_attrs = process_attributes(supervisor_attrs)
                    
                    if processed_attrs:
                        # Check if the supervisor has their own manager
                        manager_id = ""
                        if processed_attrs.get('manager'):
                            manager_id = get_manager_guid(ldap_connection, processed_attrs['manager'], manager_guid_cache)
                        
                        # Determine department
                        department = get_department_value(processed_attrs, supervisor_dn, config['use_ou_structure'])
                        
                        # Create supervisor object
                        supervisor = create_user_object(processed_attrs, manager_id, department, config)
                        
                        # Mark as inactive if it was filtered out in the main search
                        # This likely means they have a userAccountControl value indicating they're disabled
                        supervisor["status"] = "inactive"
                        
                        missing_supervisors.append(supervisor)
                        logger.info(f"Added missing supervisor: {supervisor.get('name')} ({supervisor.get('email')})")
            except Exception as e:
                logger.warning(f"Error fetching supervisor with ID {supervisor_id}: {str(e)}")
    
    logger.info(f"Successfully fetched {len(missing_supervisors)} missing supervisors.")
    return missing_supervisors

def save_users_to_file(users):
    """Save users to JSON file."""
    users_output = {"users": users}
    with open("users.json", 'w', encoding='utf-8') as f:
        json.dump(users_output, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Successfully saved {len(users)} users to users.json")

def fetch_ldap_users():
    """Fetch users from LDAP server and save them to JSON file."""
    try:
        # Get configuration
        config = get_ldap_config()
        
        # Connect to LDAP server
        ldap_connection = connect_to_ldap(config)
        
        try:
            # Search for users
            users, manager_guid_cache = search_ldap_users(ldap_connection, config)
            
            logger.info(f"Initial users fetched: {len(users)}")
            
            # Fetch missing supervisors if supervisor groups are enabled
            if config['use_supervisor_groups']:
                missing_supervisors = fetch_missing_supervisors(
                    ldap_connection, config, users, manager_guid_cache
                )
                
                # Add missing supervisors to users list
                users.extend(missing_supervisors)
                logger.info(f"Total users including missing supervisors: {len(users)}")
            
            # Save users to file
            save_users_to_file(users)
            
        finally:
            # Ensure connection is closed even if there's an error
            ldap_connection.unbind_s()
        
    except ldap.LDAPError as e:
        logger.error(f"LDAP Error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error processing LDAP data: {str(e)}")
        raise

if __name__ == "__main__":
    fetch_ldap_users() 