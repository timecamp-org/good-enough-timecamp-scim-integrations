import os
import json
import argparse
import requests
from dotenv import load_dotenv
from common.logger import setup_logger

logger = setup_logger()

class TimeCampAPI:
    def __init__(self, api_key, domain):
        self.api_key = api_key
        self.base_url = f"https://{domain}/third_party/api"
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def get_users(self):
        response = requests.get(f"{self.base_url}/users", headers=self.headers)
        response.raise_for_status()
        return response.json()

    def create_user(self, email, name, department=None, dry_run=False):
        if dry_run:
            logger.info(f"[DRY RUN] Would create user: {email}")
            return

        data = {
            "email": email,
            "name": name,
            "group_id": None  # You might want to map departments to group_ids
        }
        response = requests.post(f"{self.base_url}/users", headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def update_user(self, user_id, email, name, department=None, dry_run=False):
        if dry_run:
            logger.info(f"[DRY RUN] Would update user {user_id}: {email}")
            return

        data = {
            "email": email,
            "name": name,
            "group_id": None  # You might want to map departments to group_ids
        }
        response = requests.put(f"{self.base_url}/users/{user_id}", headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def deactivate_user(self, user_id, dry_run=False):
        if dry_run:
            logger.info(f"[DRY RUN] Would deactivate user: {user_id}")
            return

        response = requests.delete(f"{self.base_url}/users/{user_id}", headers=self.headers)
        response.raise_for_status()
        return response.json()

def get_users_file():
    """Get the users JSON file path."""
    if not os.path.exists("users.json"):
        raise FileNotFoundError("users.json file not found. Please run the integration script first.")
    return "users.json"

def sync_users(dry_run=False):
    """Synchronize users with TimeCamp."""
    try:
        load_dotenv()
        
        # Get environment variables
        api_key = os.getenv('TIMECAMP_API_KEY')
        domain = os.getenv('TIMECAMP_DOMAIN', 'app.timecamp.com')
        
        if not api_key:
            raise ValueError("Missing TIMECAMP_API_KEY environment variable")
        
        # Initialize TimeCamp client
        timecamp = TimeCampAPI(api_key, domain)
        
        # Get users file
        users_file = get_users_file()
        logger.info(f"Using users file: {users_file}")
        
        # Read source users
        with open(users_file, 'r') as f:
            source_data = json.load(f)
        
        source_users = {user['email']: user for user in source_data['users']}
        
        # Get current TimeCamp users
        timecamp_users = timecamp.get_users()
        timecamp_users_map = {user['email']: user for user in timecamp_users}
        
        # Process users
        for email, source_user in source_users.items():
            try:
                if email in timecamp_users_map:
                    # Update existing user
                    tc_user = timecamp_users_map[email]
                    if tc_user['name'] != source_user['name']:
                        logger.info(f"Updating user: {email}")
                        timecamp.update_user(
                            tc_user['user_id'],
                            email,
                            source_user['name'],
                            source_user['department'],
                            dry_run
                        )
                else:
                    # Create new user
                    logger.info(f"Creating new user: {email}")
                    timecamp.create_user(
                        email,
                        source_user['name'],
                        source_user['department'],
                        dry_run
                    )
            except requests.exceptions.RequestException as e:
                logger.error(f"Error processing user {email}: {str(e)}")
        
        # Deactivate users that are not in source
        for email, tc_user in timecamp_users_map.items():
            if email not in source_users:
                logger.info(f"Deactivating user: {email}")
                try:
                    timecamp.deactivate_user(tc_user['user_id'], dry_run)
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error deactivating user {email}: {str(e)}")
        
        logger.info("Synchronization completed successfully")
        
    except Exception as e:
        logger.error(f"Error during synchronization: {str(e)}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synchronize users with TimeCamp")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without making changes")
    args = parser.parse_args()
    
    sync_users(dry_run=args.dry_run) 