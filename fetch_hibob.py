import os
import json
import base64
import argparse
import requests
from datetime import datetime
from dotenv import load_dotenv
from common.logger import setup_logger

logger = None  # Global logger placeholder

# Cache for not-found employee IDs to avoid repeated requests
NOT_FOUND_EMPLOYEES_CACHE = set()

# Default fields to fetch from HiBob
HIBOB_FIELDS = [
    "root.id",
    "root.firstName",
    "root.surname",
    "root.fullName",
    "root.displayName",
    "root.email",
    "work.department",
    "work.title",
    "work.reportsTo",
    "work.isManager",
    "work.startDate",
    "work.site",
    "work.employeeIdInCompany",
    "internal.status",
    "internal.lifecycleStatus",
]


def build_headers(service_user_id, service_user_token):
    """Build authentication headers for HiBob API."""
    auth_string = base64.b64encode(f"{service_user_id}:{service_user_token}".encode()).decode()
    return {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'Basic {auth_string}'
    }


def fetch_employees_by_ids(headers, employee_ids, fields):
    """Fetch specific employees by their IDs using the search endpoint."""
    if not employee_ids:
        return []

    try:
        url = 'https://api.hibob.com/v1/people/search'

        payload = {
            "fields": fields,
            "filters": [{
                "fieldPath": "root.id",
                "operator": "equals",
                "values": list(employee_ids)
            }],
            "showInactive": True,
            "humanReadable": "APPEND"
        }

        logger.info(f"Fetching {len(employee_ids)} employees by ID...")

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        data = response.json()
        return data.get('employees', [])

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching employees by IDs: {str(e)}")
        return []


def transform_hibob_employee(emp, supervisor_field=None, supervisor_value=None):
    """Transform a HiBob employee record into our common schema."""
    work = emp.get('work', {})
    internal = emp.get('internal', {})

    # Prefer humanReadable versions (resolves numeric IDs to names)
    human_readable = emp.get('humanReadable', {})
    hr_work = human_readable.get('work', {}) if isinstance(human_readable, dict) else {}
    department = hr_work.get('department', '') or work.get('department', '') or ''
    job_title = hr_work.get('title', '') or work.get('title', '') or ''

    # Get supervisor ID from reportsTo
    # With humanReadable: "APPEND", reportsTo keeps original structure with id
    reports_to = work.get('reportsTo', {}) or {}
    supervisor_id = ''
    if isinstance(reports_to, dict):
        supervisor_id = reports_to.get('id', '') or ''
    elif isinstance(reports_to, str):
        # Fallback: if humanReadable: "REPLACE" was used, reportsTo becomes a name string
        # In this case we can't resolve the supervisor - skip it
        supervisor_id = ''

    # Build display name
    display_name = emp.get('fullName', '') or emp.get('displayName', '')
    if not display_name:
        first_name = emp.get('firstName', '') or ''
        surname = emp.get('surname', '') or ''
        display_name = f"{first_name} {surname}".strip()

    # Determine supervisor status
    is_supervisor = bool(work.get('isManager', False))
    if supervisor_field and supervisor_value:
        # Navigate nested field path (e.g., "work.customField")
        field_value = emp
        for part in supervisor_field.split('.'):
            if isinstance(field_value, dict):
                field_value = field_value.get(part, '')
            else:
                field_value = ''
                break
        is_supervisor = str(field_value).strip() == supervisor_value

    return {
        "external_id": emp.get('id', ''),
        "name": display_name,
        "email": emp.get('email', '') or '',
        "department": department,
        "job_title": job_title,
        "status": "active",
        "supervisor_id": supervisor_id,
        "is_supervisor": is_supervisor,
        "raw_data": emp,
    }


def fetch_missing_supervisors(headers, users, excluded_departments, fields, supervisor_field=None, supervisor_value=None):
    """Recursively fetch supervisors that are not in the current user set."""
    global NOT_FOUND_EMPLOYEES_CACHE

    # Create a set of existing employee IDs
    existing_ids = {user['external_id'] for user in users if user.get('external_id')}

    # Create a set of all supervisor IDs mentioned
    supervisor_ids = {user.get('supervisor_id') for user in users if user.get('supervisor_id')}

    # Find missing supervisor IDs (excluding ones we already know don't exist)
    missing_supervisor_ids = (supervisor_ids - existing_ids) - NOT_FOUND_EMPLOYEES_CACHE

    if not missing_supervisor_ids:
        return []

    logger.info(f"Found {len(missing_supervisor_ids)} missing supervisors, fetching...")

    # Fetch all missing supervisors in batch
    employees_data = fetch_employees_by_ids(headers, missing_supervisor_ids, fields)

    # Create a set of found employee IDs
    found_employee_ids = {emp.get('id') for emp in employees_data if emp.get('id')}

    # Update cache with not-found employees
    not_found_ids = missing_supervisor_ids - found_employee_ids
    if not_found_ids:
        NOT_FOUND_EMPLOYEES_CACHE.update(not_found_ids)
        logger.warning(f"Could not find {len(not_found_ids)} employee(s): {', '.join(not_found_ids)}")

    inactive_supervisors = []
    new_missing_ids = set()

    for emp in employees_data:
        user = transform_hibob_employee(emp, supervisor_field, supervisor_value)
        user['status'] = 'inactive'  # Mark as inactive since they weren't in the active set

        inactive_supervisors.append(user)

        # Check if this supervisor has a supervisor
        if user.get('supervisor_id') and user['supervisor_id'] not in existing_ids:
            new_missing_ids.add(user['supervisor_id'])

    # Update existing IDs with the new supervisors we just fetched
    existing_ids.update(user['external_id'] for user in inactive_supervisors if user.get('external_id'))

    # Recursively fetch the next level of supervisors if needed
    if new_missing_ids:
        # Remove already processed IDs and cached not-found IDs
        new_missing_ids = (new_missing_ids - existing_ids) - NOT_FOUND_EMPLOYEES_CACHE
        if new_missing_ids:
            temp_users = users + inactive_supervisors
            next_level_supervisors = fetch_missing_supervisors(headers, temp_users, excluded_departments, fields, supervisor_field, supervisor_value)
            inactive_supervisors.extend(next_level_supervisors)

    return inactive_supervisors


def fetch_hibob_users(debug=False):
    """Fetch active users from HiBob and save them to a JSON file."""
    global logger

    # Initialize logger if not already initialized
    if logger is None:
        logger = setup_logger(debug=debug)

    try:
        load_dotenv()

        # Override debug if env var is set
        if os.getenv('DEBUG', 'false').lower() == 'true':
            logger = setup_logger(debug=True)

        # Get environment variables
        service_user_id = os.getenv('HIBOB_SERVICE_USER_ID')
        service_user_token = os.getenv('HIBOB_SERVICE_USER_TOKEN')

        # Get exclude filter configuration
        exclude_filter_str = os.getenv('HIBOB_EXCLUDE_FILTER')
        exclude_filter = None
        if exclude_filter_str:
            try:
                exclude_filter = json.loads(exclude_filter_str)
            except json.JSONDecodeError:
                logger.warning("Invalid HIBOB_EXCLUDE_FILTER format, filter will be skipped")

        # Get excluded departments
        excluded_departments_str = os.getenv('HIBOB_EXCLUDED_DEPARTMENTS', '')
        excluded_departments = [dept.strip() for dept in excluded_departments_str.split(',') if dept.strip()]

        # Get supervisor rule configuration
        supervisor_rule_str = os.getenv('HIBOB_SUPERVISOR_RULE', '')
        supervisor_field = None
        supervisor_value = None
        if supervisor_rule_str and ':' in supervisor_rule_str:
            try:
                supervisor_field, supervisor_value = supervisor_rule_str.split(':', 1)
                supervisor_field = supervisor_field.strip()
                supervisor_value = supervisor_value.strip()
                logger.info(f"Using supervisor rule: {supervisor_field} = '{supervisor_value}'")
            except ValueError:
                logger.warning("Invalid HIBOB_SUPERVISOR_RULE format, should be 'field_name:field_value'")
                supervisor_field = None
                supervisor_value = None

        # Get additional custom fields to fetch
        custom_fields_str = os.getenv('HIBOB_CUSTOM_FIELDS', '')
        custom_fields = [f.strip() for f in custom_fields_str.split(',') if f.strip()]

        if not all([service_user_id, service_user_token]):
            raise ValueError("Missing required environment variables: HIBOB_SERVICE_USER_ID and HIBOB_SERVICE_USER_TOKEN")

        # Setup authentication headers
        headers = build_headers(service_user_id, service_user_token)

        # Build fields list
        fields = list(HIBOB_FIELDS)
        if supervisor_field:
            fields.append(supervisor_field)
        if custom_fields:
            fields.extend(custom_fields)

        # HiBob People Search API endpoint
        url = 'https://api.hibob.com/v1/people/search'

        # Prepare request payload
        # Use "APPEND" to keep original field values (needed for reportsTo.id)
        # while also getting human-readable versions (e.g., department names)
        payload = {
            "fields": fields,
            "showInactive": False,
            "humanReadable": "APPEND"
        }

        # Add exclude filter if configured
        if exclude_filter:
            payload["filters"] = [exclude_filter]
            logger.info("Using exclude filter from configuration")

        logger.info("Fetching employees from HiBob...")

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        data = response.json()
        employees = data.get('employees', [])

        logger.info(f"Received {len(employees)} employees from HiBob")

        users = []
        today = datetime.today().strftime('%Y-%m-%d')

        for emp in employees:
            work = emp.get('work', {}) or {}
            internal = emp.get('internal', {}) or {}

            # Skip employees with no email
            if not emp.get('email'):
                continue

            # Skip future hires
            start_date = work.get('startDate', '')
            if start_date and start_date > today:
                continue

            # Skip excluded departments (check both raw and human-readable)
            human_readable = emp.get('humanReadable', {})
            hr_work = human_readable.get('work', {}) if isinstance(human_readable, dict) else {}
            department = hr_work.get('department', '') or work.get('department', '') or ''
            if department in excluded_departments:
                continue

            # Skip terminated employees (safety check)
            lifecycle_status = internal.get('lifecycleStatus', '')
            if lifecycle_status == 'terminated':
                continue

            user = transform_hibob_employee(emp, supervisor_field, supervisor_value)
            logger.debug(f"Processed user: {json.dumps(user, indent=2)}")
            users.append(user)

        # Fetch missing supervisors recursively
        logger.info("Checking for missing supervisors in the hierarchy...")
        inactive_supervisors = fetch_missing_supervisors(headers, users, excluded_departments, fields, supervisor_field, supervisor_value)

        if inactive_supervisors:
            logger.info(f"Found {len(inactive_supervisors)} inactive supervisors to complete the hierarchy")
            users.extend(inactive_supervisors)

        # Prepare output data
        output_data = {"users": users}

        # Save to file in var directory
        from common.storage import save_json_file

        save_json_file(output_data, "var/users.json")

        logger.info(f"Successfully saved {len(users)} users to var/users.json ({len(users) - len(inactive_supervisors)} active, {len(inactive_supervisors)} inactive supervisors)")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching HiBob users: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error processing HiBob users: {str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch users from HiBob')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    fetch_hibob_users(debug=args.debug)
