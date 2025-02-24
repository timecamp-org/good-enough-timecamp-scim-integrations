import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from common.logger import setup_logger

logger = setup_logger()

def fetch_azure_users_and_groups():
    """Fetch users and groups from Azure AD via SCIM API and save them to JSON files."""
    try:
        load_dotenv()
        
        # Get environment variables
        scim_endpoint = os.getenv('AZURE_SCIM_ENDPOINT')
        bearer_token = os.getenv('AZURE_BEARER_TOKEN')
        
        if not all([scim_endpoint, bearer_token]):
            raise ValueError("Missing required environment variables")
        
        # Setup headers
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/scim+json',
            'Authorization': f'Bearer {bearer_token}'
        }
        
        # Fetch Users
        logger.info("Fetching users from Azure AD...")
        users = []
        start_index = 1
        
        while True:
            # SCIM API endpoint for users with pagination
            users_url = f"{scim_endpoint}/Users"
            params = {
                'startIndex': start_index,
                'count': 100  # Standard SCIM page size
            }
            
            response = requests.get(users_url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            resources = data.get('Resources', [])
            
            # Transform to our schema
            for user in resources:
                transformed_user = {
                    "external_id": user.get('id'),
                    "name": user.get('displayName', '').strip(),
                    "email": next((email.get('value') for email in user.get('emails', []) if email.get('primary')), ''),
                    "department": user.get('department', ''),
                    "status": "active" if user.get('active', True) else "inactive",
                    "supervisor_id": user.get('manager', {}).get('value', '')
                }
                users.append(transformed_user)
            
            total_results = data.get('totalResults', 0)
            if start_index + len(resources) > total_results:
                break
                
            start_index += len(resources)
            logger.info(f"Fetched {len(users)} users so far...")
        
        # Fetch Groups
        logger.info("Fetching groups from Azure AD...")
        groups = []
        start_index = 1
        
        while True:
            # SCIM API endpoint for groups with pagination
            groups_url = f"{scim_endpoint}/Groups"
            params = {
                'startIndex': start_index,
                'count': 100
            }
            
            response = requests.get(groups_url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            resources = data.get('Resources', [])
            
            # Transform to our schema
            for group in resources:
                transformed_group = {
                    "external_id": group.get('id'),
                    "display_name": group.get('displayName', '').strip(),
                    "members": [member.get('value') for member in group.get('members', [])]
                }
                groups.append(transformed_group)
            
            total_results = data.get('totalResults', 0)
            if start_index + len(resources) > total_results:
                break
                
            start_index += len(resources)
            logger.info(f"Fetched {len(groups)} groups so far...")
        
        # Save users to file
        users_output = {"users": users}
        with open("users.json", 'w') as f:
            json.dump(users_output, f, indent=2)
        
        # Save groups to file
        groups_output = {"groups": groups}
        with open("groups.json", 'w') as f:
            json.dump(groups_output, f, indent=2)
        
        logger.info(f"Successfully saved {len(users)} users to users.json and {len(groups)} groups to groups.json")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching from Azure AD SCIM: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error processing Azure AD data: {str(e)}")
        raise

if __name__ == "__main__":
    fetch_azure_users_and_groups() 