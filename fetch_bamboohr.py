import os
import json
import base64
import requests
from datetime import datetime
from dotenv import load_dotenv
from common.logger import setup_logger

logger = setup_logger()

# Cache for not-found employee IDs to avoid repeated requests
NOT_FOUND_EMPLOYEES_CACHE = set()

def fetch_employees_by_ids(subdomain, headers, employee_ids, supervisor_field=None):
    """Fetch multiple employees by their IDs using the dataset endpoint."""
    if not employee_ids:
        return []
    
    try:
        url = f'https://api.bamboohr.com/api/gateway.php/{subdomain}/v1/datasets/employee'
        
        # Prepare fields - same as main fetch
        fields = [
            "employeeNumber",
            "name",
            "email",
            "jobInformationDepartment",
            "jobInformationDivision",
            "jobInformationJobTitle",
            "isSupervisor",
            "supervisorId",
            "employmentStatus",
            "hireDate",
            "status",
            "supervisorEid"
        ]
        
        # Add supervisor field dynamically if configured
        if supervisor_field:
            fields.append(supervisor_field)
        
        # Create individual equal filters for each employee ID
        employee_filters = []
        for emp_id in employee_ids:
            employee_filters.append({
                "field": "employeeNumber",
                "operator": "equal",
                "value": str(emp_id)
            })
        
        # Create filter with "any" match for multiple employee IDs
        payload = {
            "filters": {
                "match": "any",
                "filters": employee_filters
            },
            "fields": fields
        }
        
        logger.info(f"Fetching {len(employee_ids)} employees by ID...")
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        return data.get('data', [])
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching employees by IDs: {str(e)}")
        return []

def fetch_missing_supervisors(subdomain, headers, users, excluded_departments, supervisor_field=None, supervisor_value=None):
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
    employees_data = fetch_employees_by_ids(subdomain, headers, missing_supervisor_ids, supervisor_field)
    
    # Create a set of found employee IDs
    found_employee_ids = {emp.get('employeeNumber') for emp in employees_data if emp.get('employeeNumber')}
    
    # Update cache with not-found employees
    not_found_ids = missing_supervisor_ids - found_employee_ids
    if not_found_ids:
        NOT_FOUND_EMPLOYEES_CACHE.update(not_found_ids)
        logger.warning(f"Could not find {len(not_found_ids)} employee(s): {', '.join(not_found_ids)}")
    
    inactive_supervisors = []
    new_missing_ids = set()
    
    for emp in employees_data:
        # Transform to our schema
        division = emp.get('jobInformationDivision', '')
        department = emp.get('jobInformationDepartment', '')
        combined_department = f"{division}/{department}" if department and division else department or division or ''
        
        # Determine supervisor status based on rule
        is_supervisor = False
        if supervisor_field and supervisor_value:
            field_value = emp.get(supervisor_field, '')
            is_supervisor = str(field_value).strip() == supervisor_value
        
        user = {
            "external_id": emp.get('employeeNumber'),
            "job_title": emp.get('jobInformationJobTitle'),
            "name": emp.get('name', '').strip(),
            "email": emp.get('email', '').replace('@', '@test-') if emp.get('email') else '',
            "department": combined_department,
            "status": "inactive",  # Mark as inactive since they weren't in the active set
            "supervisor_id": emp.get('supervisorId', ''),
            "is_supervisor": is_supervisor,
        }
        
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
            # Temporarily add inactive supervisors to the list for the recursive call
            temp_users = users + inactive_supervisors
            next_level_supervisors = fetch_missing_supervisors(subdomain, headers, temp_users, excluded_departments, supervisor_field, supervisor_value)
            inactive_supervisors.extend(next_level_supervisors)
    
    return inactive_supervisors

def fetch_bamboo_users():
    """Fetch active users from BambooHR and save them to a JSON file."""
    try:
        load_dotenv()
        
        # Get environment variables
        subdomain = os.getenv('BAMBOOHR_SUBDOMAIN')
        api_key = os.getenv('BAMBOOHR_API_KEY')
        
        # Get exclude filter configuration
        exclude_filter_str = os.getenv('BAMBOOHR_EXCLUDE_FILTER')
        exclude_filter = None
        if exclude_filter_str:
            try:
                exclude_filter = json.loads(exclude_filter_str)
            except json.JSONDecodeError:
                logger.warning("Invalid BAMBOOHR_EXCLUDE_FILTER format, filter will be skipped")
        
        # Get excluded departments
        excluded_departments_str = os.getenv('BAMBOOHR_EXCLUDED_DEPARTMENTS', '')
        excluded_departments = [dept.strip() for dept in excluded_departments_str.split(',') if dept.strip()]
        
        # Get supervisor rule configuration
        supervisor_rule_str = os.getenv('BAMBOOHR_SUPERVISOR_RULE', '')
        supervisor_field = None
        supervisor_value = None
        if supervisor_rule_str and ':' in supervisor_rule_str:
            try:
                supervisor_field, supervisor_value = supervisor_rule_str.split(':', 1)
                supervisor_field = supervisor_field.strip()
                supervisor_value = supervisor_value.strip()
                logger.info(f"Using supervisor rule: {supervisor_field} = '{supervisor_value}'")
            except ValueError:
                logger.warning("Invalid BAMBOOHR_SUPERVISOR_RULE format, should be 'field_name:field_value'")
                supervisor_field = None
                supervisor_value = None
        
        if not all([subdomain, api_key]):
            raise ValueError("Missing required environment variables")
        
        # Setup authentication and headers
        auth_string = base64.b64encode(f"{api_key}:x".encode()).decode()
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth_string}'
        }
        
        # BambooHR API endpoint for employee dataset
        url = f'https://api.bamboohr.com/api/gateway.php/{subdomain}/v1/datasets/employee'
        
        # Prepare base filters
        base_filters = [
            {
                "field": "employmentStatus",
                "operator": "does_not_include",
                "value": ["Terminated"],
            }
        ]
        
        # Add exclude filter if configured
        if exclude_filter:
            base_filters.insert(0, exclude_filter)
            logger.info("Using exclude filter from configuration")
        
        # Prepare base fields
        fields = [
            "employeeNumber",
            "name",
            "email",
            "jobInformationDepartment",
            "jobInformationDivision",
            "jobInformationJobTitle",
            "isSupervisor",
            "supervisorId",
            "employmentStatus",
            "hireDate",
            "status",
            "supervisorEid"
        ]
        
        # Add supervisor field dynamically if configured
        if supervisor_field:
            fields.append(supervisor_field)
        
        # Prepare request payload
        payload = {
            "filters": {
                "match": "all",
                "filters": base_filters
            },
            "fields": fields
        }
        
        logger.info("Fetching employees from BambooHR...")
        
        all_employees = []
        current_page = 1
        
        while True:
            # Add pagination parameters to payload
            payload['page'] = current_page
            
            # Get employees for current page
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            employees = data.get('data', [])
            pagination = data.get('pagination', {})
            # logger.info(f"Page {current_page} employees: {json.dumps(employees, indent=2)}")
            
            all_employees.extend(employees)
            
            # Check if there are more pages
            if not pagination.get('next_page'):
                break
                
            current_page += 1
            logger.info(f"Fetching page {current_page}...")
        
        # Transform to our schema
        users = []
        today = datetime.today().strftime('%Y-%m-%d')
        
        for emp in all_employees:
            # Filter out terminated employees, future employees, and users with no email
            employment_status = emp.get('employmentStatus', '')
            hire_date = emp.get('hireDate', '')
            department = emp.get('jobInformationDepartment', '')
            
            if (employment_status == 'Terminated' or
                (hire_date and hire_date > today) or
                not emp.get('email') or
                department in excluded_departments):
                continue
                
            # Join department and division with a forward slash if both exist
            division = emp.get('jobInformationDivision', '')
            combined_department = f"{division}/{department}" if department and division else department or division or ''
            
            # Determine supervisor status based on rule
            is_supervisor = False
            if supervisor_field and supervisor_value:
                field_value = emp.get(supervisor_field, '')
                is_supervisor = str(field_value).strip() == supervisor_value
            
            user = {
                "external_id": emp.get('employeeNumber'),
                "job_title": emp.get('jobInformationJobTitle'),
                "name": emp.get('name', '').strip(),
                "email": emp.get('email').replace('@', '@test-'),
                "department": combined_department,
                "status": "active",
                "supervisor_id": emp.get('supervisorId', ''),
                "is_supervisor": is_supervisor,
            }
            users.append(user)
        
        # Fetch missing supervisors recursively
        logger.info("Checking for missing supervisors in the hierarchy...")
        inactive_supervisors = fetch_missing_supervisors(subdomain, headers, users, excluded_departments, supervisor_field, supervisor_value)
        
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
        logger.error(f"Error fetching BambooHR users: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error processing BambooHR users: {str(e)}")
        raise

if __name__ == "__main__":
    fetch_bamboo_users() 