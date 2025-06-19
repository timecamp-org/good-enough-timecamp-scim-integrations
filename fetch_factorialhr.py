import os
import json
import base64
import requests
from datetime import datetime
from dotenv import load_dotenv
from common.logger import setup_logger

logger = setup_logger()

class FactorialHRSynchronizer:
    """Class to handle synchronization of users from FactorialHR."""
    
    def __init__(self):
        """Initialize the synchronizer with necessary configurations."""
        self.api_url = os.getenv("FACTORIAL_API_URL")  # Base URL for FactorialHR API
        self.api_key = os.getenv("FACTORIAL_API_KEY")  # API key for authentication

    def _call_api(self, endpoint, method='GET', data=None, params=None):
        """Generic method to call the FactorialHR API."""
        url = f"{self.api_url}/{endpoint}"
        headers = {
            "accept": "application/json",
            "x-api-key": self.api_key,
        }
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            else:
                raise ValueError("Unsupported HTTP method")
            
            response.raise_for_status()  # Raise an error for bad responses
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API call failed: {e}")
            raise e
    
    def fetch_users(self):
        """Fetch users from FactorialHR."""
        endpoint = "resources/employees/employees"
        params = {
            'only_active': 'true',
            'only_managers': 'false'
        }
        try:
            response = self._call_api(endpoint, params=params)
            logger.info("Fetched users successfully")
            print(response)  # For debugging purposes
            self.uid_email_map = {q['id']: q['email'] for q in response['data']}
            self.uid_lemail_map = {q['id']: q['login_email'] for q in response['data']}
            return response
        except Exception as e:
            logger.error(f"Failed to fetch users: {e}")
            return None
    
    def fetch_vacation(self):
        """Fetch vacation data from FactorialHR."""
        endpoint = "resources/timeoff/leaves"
        params = {
            'include_leave_type': 'true',
            'include_duration': 'true'
        }
        day_type_map = json.loads(os.getenv("LeaveTypeMap"))
        print(day_type_map, type(day_type_map))  # For debugging purposes
        try:
            response = self._call_api(endpoint, params=params)
            logger.info("Fetched vacation data successfully")
            print(response)  # For debugging purposes
            result = []
            for q in response['data']:
                q['email'] = self.uid_email_map.get(q['employee_id'])
                if q['email'] is None:
                    q['email'] = self.uid_lemail_map.get(q['employee_id'])
                q['tc_leave_type'] = day_type_map.get(q['leave_type_name'], day_type_map.get('Default'))
                result.append({'email': q['email'], 'start_on': q['start_on'], 'finish_on': q['finish_on'], 'tc_leave_type': q['tc_leave_type']})
            with open("vacation.json", 'w') as f:
                json.dump({'vacation': result}, f, indent=2)
            return result
        except Exception as e:
            logger.error(f"Failed to fetch vacation data: {e}")
            return None

    
    def synchronize(self):
        """Perform the full synchronization process."""
        logger.info("Starting synchronization process")
        self.fetch_users()
        self.fetch_vacation()
        
        logger.info("Synchronization process completed")

def fetch_factorialhr_vacation():
    """Fetch and synchronize users from FactorialHR."""
    synchronizer = FactorialHRSynchronizer()
    synchronizer.synchronize()

if __name__ == "__main__":
    fetch_factorialhr_vacation()
