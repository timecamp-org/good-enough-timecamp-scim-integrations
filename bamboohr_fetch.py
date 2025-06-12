import os
import json
import base64
import requests
from datetime import datetime
from dotenv import load_dotenv
from common.logger import setup_logger

logger = setup_logger()

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
            "status"
        ]
        
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
            
            user = {
                "external_id": emp.get('employeeNumber'),
                "job_title": emp.get('jobInformationJobTitle'),
                "name": emp.get('name', '').strip(),
                "email": emp.get('email').replace('@', '@test-'),
                "department": combined_department,
                "status": "active",
                "supervisor_id": emp.get('supervisorId', ''),
            }
            users.append(user)
        
        # Prepare output data
        output_data = {"users": users}
        
        # Save to file in main directory
        with open("users.json", 'w') as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"Successfully saved {len(users)} users to users.json")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching BambooHR users: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error processing BambooHR users: {str(e)}")
        raise

if __name__ == "__main__":
    fetch_bamboo_users() 