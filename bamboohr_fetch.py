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
        
        if not all([subdomain, api_key]):
            raise ValueError("Missing required environment variables")
        
        # Setup authentication and headers
        auth_string = base64.b64encode(f"{api_key}:x".encode()).decode()
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Basic {auth_string}'
        }
        
        # BambooHR API endpoint for directory
        url = f'https://api.bamboohr.com/api/gateway.php/{subdomain}/v1/employees/directory'
        
        logger.info("Fetching employees from BambooHR...")
        
        # Get all employees
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        employees = response.json().get('employees', [])
        
        # Filter active employees and transform to our schema
        users = []
        for emp in employees:
            if emp.get('status') == 'Active':
                user = {
                    "external_id": emp.get('id'),
                    "name": f"{emp.get('firstName', '')} {emp.get('lastName', '')}".strip(),
                    "email": emp.get('workEmail'),
                    "department": emp.get('department', ''),
                    "status": "active"
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