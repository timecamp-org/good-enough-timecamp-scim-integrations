import os
import json
from datetime import datetime
from dotenv import load_dotenv
from pyBambooHR import PyBambooHR
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
        
        # Initialize BambooHR client
        bamboo = PyBambooHR(subdomain=subdomain, api_key=api_key)
        
        logger.info("Fetching employees from BambooHR...")
        
        # Get all employees
        employees = bamboo.get_employees()
        
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
        
    except Exception as e:
        logger.error(f"Error fetching BambooHR users: {str(e)}")
        raise

if __name__ == "__main__":
    fetch_bamboo_users() 