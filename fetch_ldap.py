import os
import json
import ldap
import uuid
from dotenv import load_dotenv
from common.logger import setup_logger
from ldap.controls import SimplePagedResultsControl

logger = setup_logger()


def obfuscate_secret(value):
    """Obfuscate a secret value, showing only first and last 2 characters."""
    if not value:
        return "(not set)"
    value = str(value)
    if len(value) <= 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def obfuscate_email(email):
    """Obfuscate the middle part of an email address. E.g. jo***oe@example.com"""
    if not email or '@' not in email:
        return email or ""
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        local_obfuscated = local[0] + "***"
    else:
        local_obfuscated = local[0] + "***" + local[-1]
    return f"{local_obfuscated}@{domain}"


def log_config(config):
    """Log all environment variable values used by fetch_ldap (secrets obfuscated)."""
    logger.info("=== fetch_ldap configuration ===")
    logger.info(f"  LDAP_HOST = {config['host']}")
    logger.info(f"  LDAP_PORT = {config['port']}")
    logger.info(f"  LDAP_DOMAIN = {config['domain']}")
    logger.info(f"  LDAP_DN = {config['dn']}")
    logger.info(f"  LDAP_USERNAME = {obfuscate_secret(config['username'])}")
    logger.info(f"  LDAP_PASSWORD = {obfuscate_secret(config['password'])}")
    logger.info(f"  LDAP_FILTER = {config['filter']}")
    logger.info(f"  LDAP_PAGE_SIZE = {config['page_size']}")
    logger.info(f"  LDAP_USE_SAMACCOUNTNAME = {config['use_samaccountname']}")
    logger.info(f"  LDAP_USE_SAMACCOUNTNAME_ONLY = {config['use_samaccountname_only']}")
    logger.info(f"  LDAP_USE_OU_STRUCTURE = {config['use_ou_structure']}")
    logger.info(f"  LDAP_USE_OU_DESCRIPTION = {config['use_ou_description']}")
    logger.info(f"  LDAP_USE_REAL_EMAIL_AS_EMAIL = {config['use_real_email_as_email']}")
    logger.info(f"  LDAP_USE_WINDOWS_LOGIN_EMAIL = {config['use_windows_login_email']}")
    logger.info(f"  LDAP_EMAIL_DOMAIN = {config['email_domain'] or '(not set)'}")
    logger.info(f"  LDAP_USE_SSL = {config['use_ssl']}")
    logger.info(f"  LDAP_USE_START_TLS = {config['use_start_tls']}")
    logger.info(f"  LDAP_SSL_VERIFY = {config['ssl_verify']}")
    logger.info(f"  LDAP_SUPERVISOR_GROUP_NAME = {config['supervisor_group_name'] or '(not set)'}")
    logger.info(f"  LDAP_GLOBAL_ADMIN_GROUP_NAME = {config['global_admin_group_name'] or '(not set)'}")
    logger.info(f"  TIMECAMP_USE_SUPERVISOR_GROUPS = {config['use_supervisor_groups']}")
    logger.info(f"  TIMECAMP_REPLACE_EMAIL_DOMAIN = {config['replace_email_domain'] or '(not set)'}")
    logger.info("================================")


def normalize_text(text):
    """Ensure text has proper characters instead of escaped Unicode."""
    if not text:
        return ""
    return text

def extract_ou_path(dn, ldap_connection=None, use_description=False, ou_description_cache=None):
    """Extract OU path from distinguished name.
    
    Args:
        dn: Distinguished name to parse
        ldap_connection: LDAP connection object (required if use_description=True)
        use_description: If True, use OU description field instead of CN
        ou_description_cache: Dictionary to cache OU descriptions
    
    Returns:
        String representing the OU path
    """
    if not dn:
        return ""
    
    # Split the DN into parts
    parts = dn.split(',')
    
    # Extract OUs
    ou_parts = []
    
    for i, part in enumerate(parts):
        clean_part = part.strip()
        if clean_part.lower().startswith('ou='):
            # Extract the OU name (remove 'OU=' prefix)
            ou_name = clean_part[3:]
            final_ou_name = ou_name
            
            # If use_description is enabled, try to replace OU name with description
            if use_description and ldap_connection and ou_description_cache is not None:
                # Reconstruct the full DN for this OU
                # The DN for an OU at index i consists of parts from i to the end
                ou_dn = ','.join([p.strip() for p in parts[i:]])
                
                # Check cache first
                if ou_dn in ou_description_cache:
                    description = ou_description_cache[ou_dn]
                    if description:
                        final_ou_name = description
                else:
                    # Query LDAP for the OU's description
                    try:
                        ou_result = ldap_connection.search_s(
                            ou_dn,
                            ldap.SCOPE_BASE,
                            '(objectClass=*)',
                            ['description']
                        )
                        
                        description = ""
                        if ou_result and len(ou_result) > 0 and len(ou_result[0]) > 1:
                            ou_attrs = ou_result[0][1]
                            if 'description' in ou_attrs and ou_attrs['description']:
                                description_value = ou_attrs['description'][0]
                                if isinstance(description_value, bytes):
                                    description = description_value.decode('utf-8')
                                else:
                                    description = description_value
                        
                        # Cache the result
                        ou_description_cache[ou_dn] = description
                        
                        if description:
                            final_ou_name = description
                            
                    except Exception as e:
                        logger.warning(f"Error retrieving OU description for {ou_dn}: {str(e)}")
                        ou_description_cache[ou_dn] = ""
            
            ou_parts.append(final_ou_name)
    
    # Reverse the order to get top-level OU first (Root -> Leaf)
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
        'use_samaccountname_only': os.getenv('LDAP_USE_SAMACCOUNTNAME_ONLY', 'false').lower() == 'true',
        'use_ou_structure': os.getenv('LDAP_USE_OU_STRUCTURE', 'false').lower() == 'true',
        'use_ou_description': os.getenv('LDAP_USE_OU_DESCRIPTION', 'false').lower() == 'true',
        'use_supervisor_groups': os.getenv('TIMECAMP_USE_SUPERVISOR_GROUPS', 'false').lower() == 'true',
        'use_real_email_as_email': os.getenv('LDAP_USE_REAL_EMAIL_AS_EMAIL', 'false').lower() == 'true',
        'use_windows_login_email': os.getenv('LDAP_USE_WINDOWS_LOGIN_EMAIL', 'false').lower() == 'true',
        'email_domain': os.getenv('LDAP_EMAIL_DOMAIN', ''),
        'replace_email_domain': os.getenv('TIMECAMP_REPLACE_EMAIL_DOMAIN', ''),
        'use_ssl': os.getenv('LDAP_USE_SSL', 'false').lower() == 'true',
        'use_start_tls': os.getenv('LDAP_USE_START_TLS', 'false').lower() == 'true',
        'ssl_verify': os.getenv('LDAP_SSL_VERIFY', 'true').lower() == 'true',
        'supervisor_group_name': os.getenv('LDAP_SUPERVISOR_GROUP_NAME', ''),
        'global_admin_group_name': os.getenv('LDAP_GLOBAL_ADMIN_GROUP_NAME', '')
    }
    
    # Auto-detect SSL settings based on port if not explicitly set
    if not os.getenv('LDAP_USE_SSL') and not os.getenv('LDAP_USE_START_TLS'):
        if config['port'] == '636':
            config['use_ssl'] = True
            logger.info("Auto-detected SSL based on port 636")
    
    # Validate required configuration
    required_fields = ['host', 'domain', 'dn', 'username', 'password']
    missing_fields = [field for field in required_fields if not config[field]]
    
    if missing_fields:
        raise ValueError(f"Missing required LDAP configuration: {', '.join(missing_fields)}")
    
    # Validate SSL configuration
    if config['use_ssl'] and config['use_start_tls']:
        raise ValueError("Cannot use both LDAP_USE_SSL and LDAP_USE_START_TLS simultaneously")
    
    return config

def connect_to_ldap(config):
    """Connect to LDAP server and return connection object."""
    logger.info(f"Connecting to LDAP server {config['host']}:{config['port']}")
    
    # Globally configure SSL/TLS verification before initializing
    # This is often required for python-ldap to behave like command-line tools
    if (config['use_ssl'] or config['use_start_tls']) and not config['ssl_verify']:
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
        logger.warning("Globally disabled SSL certificate verification.")
    
    # Determine the protocol and port
    if config['use_ssl']:
        protocol = "ldaps"
        # Default to 636 for SSL if port is still 389
        port = '636' if config['port'] == '389' else config['port']
        logger.info("Using LDAPS (SSL) connection")
    else:
        protocol = "ldap"
        port = config['port']
        if config['use_start_tls']:
            logger.info("Using LDAP with StartTLS")
        else:
            logger.info("Using plain LDAP connection")
    
    # Connect to LDAP server
    ldap_uri = f"{protocol}://{config['host']}:{port}"
    ldap_connection = ldap.initialize(ldap_uri)
    ldap_connection.protocol_version = ldap.VERSION3
    
    # Set option to refer to referrals
    ldap_connection.set_option(ldap.OPT_REFERRALS, 0)
    
    # Set size limit and time limit to avoid server-side restrictions
    ldap_connection.set_option(ldap.OPT_SIZELIMIT, 0)  # No client-side size limit
    ldap_connection.set_option(ldap.OPT_TIMELIMIT, 0)  # No client-side time limit
    
    # The global option above should be sufficient, but we can also set it on the
    # connection object just in case, for older versions of python-ldap.
    if (config['use_ssl'] or config['use_start_tls']) and not config['ssl_verify']:
        ldap_connection.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)

    # Use StartTLS if configured
    if config['use_start_tls']:
        try:
            ldap_connection.start_tls_s()
            logger.info("StartTLS established successfully")
        except ldap.LDAPError as e:
            logger.error(f"StartTLS failed: {str(e)}")
            raise
    
    # Construct the bind DN (distinguished name)
    bind_dn = f"{config['username']}@{config['domain']}" if '@' not in config['username'] else config['username']
    
    # Bind to the server
    try:
        ldap_connection.simple_bind_s(bind_dn, config['password'])
        logger.info("Successfully authenticated with LDAP server")
    except ldap.LDAPError as e:
        logger.error(f"LDAP authentication failed: {str(e)}")
        raise
    
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
        elif key == 'memberOf':
            # memberOf can have multiple values (multiple group memberships)
            # Join them with a semicolon for easier processing
            if isinstance(value, list):
                decoded_groups = []
                for group_dn in value:
                    if isinstance(group_dn, bytes):
                        decoded_groups.append(group_dn.decode('utf-8'))
                    else:
                        decoded_groups.append(group_dn)
                user_attrs[key] = ';'.join(decoded_groups)
            else:
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

def select_email_from_domain(email_string, preferred_domain):
    """
    Select email from preferred domain when multiple emails are present.
    
    Args:
        email_string: String containing one or more emails, possibly separated by commas
        preferred_domain: Domain to prefer when multiple emails are available
        
    Returns:
        Selected email address, or the first email if no domain match found
    """
    if not email_string:
        return ""
    
    # Handle single email case
    if ',' not in email_string:
        return email_string.strip().lower()
    
    # Split emails by comma and clean them
    emails = [email.strip().lower() for email in email_string.split(',') if email.strip()]
    
    if not emails:
        return ""
    
    # If no preferred domain specified, return the first email
    if not preferred_domain:
        return emails[0]
    
    # Look for email matching the preferred domain
    preferred_domain = preferred_domain.lower()
    for email in emails:
        if email.endswith(f'@{preferred_domain}'):
            logger.debug(f"Selected email {email} from domain {preferred_domain}")
            return email
    
    # If no match found, return the first email
    logger.debug(f"No email found for domain {preferred_domain}, using first email: {emails[0]}")
    return emails[0]

def get_department_value(user_attrs, dn, use_ou_structure, ldap_connection=None, use_ou_description=False, ou_description_cache=None):
    """Determine department value based on configuration."""
    if use_ou_structure:
        # Use OU path from DN as department
        department = extract_ou_path(dn, ldap_connection, use_ou_description, ou_description_cache)
    else:
        # Use department attribute
        department = normalize_text(user_attrs.get('department', ''))
    
    return department

def check_group_membership(user_attrs, group_name):
    """Check if user belongs to a specific group."""
    if not group_name:
        return False
    
    member_of = user_attrs.get('memberOf', '')
    if not member_of:
        return False
    
    # memberOf is a semicolon-separated list of group DNs
    # Format is typically: CN=groupname,OU=...
    group_name_lower = group_name.lower()
    member_of_lower = member_of.lower()
    
    # Check if the group name is in any of the group DNs
    return f'cn={group_name_lower},' in member_of_lower

def create_user_object(user_attrs, manager_id, department, config):
    """Create transformed user object from LDAP attributes."""
    # Process email from LDAP, selecting from preferred domain if multiple emails exist
    raw_email = user_attrs.get('mail', '')
    selected_email = select_email_from_domain(raw_email, config['replace_email_domain'])
    
    transformed_user = {
        "external_id": user_attrs.get('objectGUID', ''),
        "name": normalize_text(user_attrs.get('displayName', '')),
        "email": selected_email,
        "department": department,
        "job_title": normalize_text(user_attrs.get('title', '')),
        "status": "active",
        "supervisor_id": manager_id,
    }
    
    # Check if user belongs to supervisor group
    if config.get('supervisor_group_name'):
        is_supervisor = check_group_membership(user_attrs, config['supervisor_group_name'])
        if is_supervisor:
            transformed_user["force_supervisor_role"] = True
    
    # Check if user belongs to global admin group
    if config.get('global_admin_group_name'):
        is_global_admin = check_group_membership(user_attrs, config['global_admin_group_name'])
        if is_global_admin:
            transformed_user["force_global_admin_role"] = True
    
    # If display name is not available, try to construct from first and last name
    if not transformed_user["name"]:
        first_name = user_attrs.get('givenName', '')
        last_name = user_attrs.get('sn', '')
        if first_name or last_name:
            transformed_user["name"] = normalize_text(f"{first_name} {last_name}".strip())
    
    # Handle email generation based on configuration
    original_mail = selected_email
    
    if config['use_samaccountname_only']:
        # Use only sAMAccountName without any domain
        if user_attrs.get('sAMAccountName'):
            transformed_user["email"] = user_attrs['sAMAccountName'].lower()
            # Always store original mail as real_email if available
            if raw_email:
                transformed_user["real_email"] = raw_email.lower()
    elif config['use_windows_login_email']:
        # Use Windows login (sAMAccountName) with specified or LDAP domain
        if user_attrs.get('sAMAccountName'):
            email_domain = config['email_domain'] if config['email_domain'] else config['domain']
            transformed_user["email"] = f"{user_attrs['sAMAccountName']}@{email_domain}".lower()
            # Always store original mail as real_email if available
            if raw_email:
                transformed_user["real_email"] = raw_email.lower()
    elif config['use_samaccountname']:
        # Prioritize sAMAccountName for email
        if user_attrs.get('sAMAccountName'):
            transformed_user["email"] = f"{user_attrs['sAMAccountName']}@{config['domain']}".lower()
            # Always store original mail as real_email if available
            if raw_email:
                transformed_user["real_email"] = raw_email.lower()
    # If email is still missing, fall back to sAMAccountName
    elif not transformed_user["email"] and user_attrs.get('sAMAccountName'):
        transformed_user["email"] = f"{user_attrs['sAMAccountName']}@{config['domain']}".lower()
        # Always store original mail as real_email if available
        if raw_email:
            transformed_user["real_email"] = raw_email.lower()
    
    # If configured to use real_email as email, swap them and clear real_email
    if config['use_real_email_as_email'] and transformed_user.get('real_email'):
        transformed_user["email"] = transformed_user["real_email"]
        transformed_user["real_email"] = ""
    
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
        'telephoneNumber', 'streetAddress', 'postalCode', 'manager',
        'memberOf'
    ]
    
    # Initialize the pagination control
    page_control = SimplePagedResultsControl(True, size=config['page_size'], cookie='')
    
    users = []
    manager_guid_cache = {}  # Cache to store manager GUIDs
    ou_description_cache = {}  # Cache to store OU descriptions
    
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
                department = get_department_value(
                    user_attrs, dn, config['use_ou_structure'],
                    ldap_connection, config['use_ou_description'], ou_description_cache
                )
                
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
    
    return users, manager_guid_cache, ou_description_cache

def fetch_missing_supervisors(ldap_connection, config, users, manager_guid_cache, ou_description_cache):
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
                        'userAccountControl', 'memberOf'
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
                        department = get_department_value(
                            processed_attrs, supervisor_dn, config['use_ou_structure'],
                            ldap_connection, config['use_ou_description'], ou_description_cache
                        )
                        
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
    from common.storage import save_json_file
    
    users_output = {"users": users}
    save_json_file(users_output, "var/users.json", encoding='utf-8')
    
    logger.info(f"Successfully saved {len(users)} users to var/users.json")

def fetch_ldap_users():
    """Fetch users from LDAP server and save them to JSON file."""
    try:
        # Get configuration
        config = get_ldap_config()
        log_config(config)

        # Connect to LDAP server
        ldap_connection = connect_to_ldap(config)
        
        try:
            # Search for users
            users, manager_guid_cache, ou_description_cache = search_ldap_users(ldap_connection, config)
            
            logger.info(f"Initial users fetched: {len(users)}")
            
            # Fetch missing supervisors if supervisor groups are enabled
            if config['use_supervisor_groups']:
                missing_supervisors = fetch_missing_supervisors(
                    ldap_connection, config, users, manager_guid_cache, ou_description_cache
                )
                
                # Add missing supervisors to users list
                users.extend(missing_supervisors)
                logger.info(f"Total users including missing supervisors: {len(users)}")
            
            # Log summary with first 2 users as JSON (email obfuscated)
            logger.info(f"=== LDAP fetch results: {len(users)} users total ===")
            for i, user in enumerate(users[:2]):
                preview = dict(user)
                preview['email'] = obfuscate_email(preview.get('email', ''))
                if preview.get('real_email'):
                    preview['real_email'] = obfuscate_email(preview['real_email'])
                logger.info(f"  User {i+1}: {json.dumps(preview, ensure_ascii=False)}")
            if len(users) > 2:
                logger.info(f"  ... and {len(users) - 2} more users")

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