import os
import json
import time
import requests
import unicodedata
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key, find_dotenv
from common.logger import setup_logger

logger = setup_logger()

def normalize_text(text):
    """Ensure text has proper Polish characters instead of escaped Unicode."""
    if not text:
        return ""
    # Convert any escaped Unicode to proper characters
    return text

class AzureTokenManager:
    def __init__(self):
        """Initialize the token manager with configuration from environment variables."""
        load_dotenv()

        # Get configuration
        self.tenant_id = os.getenv('AZURE_TENANT_ID')
        self.client_id = os.getenv('AZURE_CLIENT_ID')
        self.client_secret = os.getenv('AZURE_CLIENT_SECRET')
        
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError("Missing required Azure AD OAuth configuration")
        
        # Token endpoint
        self.token_endpoint = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        # Required scopes for Graph API
        self.scope = "https://graph.microsoft.com/.default"
        
        # Env file path
        self.dotenv_path = find_dotenv()
        if not self.dotenv_path:
            self.dotenv_path = '.env'
            logger.warning(f".env file not found, will create at {self.dotenv_path}")
    
    def _save_tokens(self, token_data):
        """Save tokens to .env file with expiration timestamps."""
        # Add absolute expiration timestamps
        current_time = time.time()
        expires_at = current_time + token_data.get('expires_in', 3600)
        
        # Save access token and expiration to .env
        set_key(self.dotenv_path, 'AZURE_BEARER_TOKEN', token_data['access_token'])
        set_key(self.dotenv_path, 'AZURE_TOKEN_EXPIRES_AT', str(int(expires_at)))
        
        # Save refresh token if available
        if 'refresh_token' in token_data:
            refresh_token_expires_at = current_time + (90 * 24 * 3600)  # 90 days
            set_key(self.dotenv_path, 'AZURE_REFRESH_TOKEN', token_data['refresh_token'])
            set_key(self.dotenv_path, 'AZURE_REFRESH_TOKEN_EXPIRES_AT', str(int(refresh_token_expires_at)))
        
        logger.debug("Saved token information to .env file")
    
    def _load_tokens(self):
        """Load tokens from .env file if they exist."""
        try:
            # Reload env to get latest values
            load_dotenv(self.dotenv_path, override=True)
            
            access_token = os.getenv('AZURE_BEARER_TOKEN')
            expires_at = os.getenv('AZURE_TOKEN_EXPIRES_AT')
            refresh_token = os.getenv('AZURE_REFRESH_TOKEN')
            refresh_token_expires_at = os.getenv('AZURE_REFRESH_TOKEN_EXPIRES_AT')
            
            if not access_token:
                return None
                
            token_data = {
                'access_token': access_token
            }
            
            if expires_at:
                token_data['expires_at'] = float(expires_at)
                
            if refresh_token:
                token_data['refresh_token'] = refresh_token
                
            if refresh_token_expires_at:
                token_data['refresh_token_expires_at'] = float(refresh_token_expires_at)
                
            return token_data
            
        except Exception as e:
            logger.warning(f"Error loading tokens from .env: {str(e)}")
            return None
    
    def _get_new_tokens(self):
        """Get new access and refresh tokens using client credentials."""
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': self.scope
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            logger.info(f"Requesting new token with scope: {self.scope}")
            response = requests.post(self.token_endpoint, data=data, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Token request failed with status {response.status_code}")
                logger.error(f"Response: {response.text}")
                response.raise_for_status()
            
            token_data = response.json()
            self._save_tokens(token_data)
            
            return token_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Error details: {e.response.text}")
            raise
    
    def _refresh_token(self, refresh_token):
        """Get new access token using refresh token."""
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = requests.post(self.token_endpoint, data=data, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Token refresh failed with status {response.status_code}")
                logger.error(f"Response: {response.text}")
                response.raise_for_status()
            
            token_data = response.json()
            self._save_tokens(token_data)
            
            return token_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Refresh request failed: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Error details: {e.response.text}")
            raise
    
    def get_valid_token(self, force_new=False):
        """Get a valid access token, refreshing or fetching new ones as needed.
        
        Returns:
            tuple: (token, is_new_token) where is_new_token is True if a new token was generated
        """
        try:
            # Try to load existing tokens
            tokens = self._load_tokens()
            current_time = time.time()
            is_new_token = False
            
            if tokens and not force_new:
                # Check if access token is still valid
                if tokens.get('expires_at', 0) > current_time + 300:  # 5-minute buffer
                    logger.debug("Using existing access token")
                    return tokens['access_token'], is_new_token
                
                # Check if we can use refresh token
                if 'refresh_token' in tokens:
                    if tokens.get('refresh_token_expires_at', 0) > current_time:
                        logger.info("Refreshing access token")
                        new_tokens = self._refresh_token(tokens['refresh_token'])
                        is_new_token = True
                        return new_tokens['access_token'], is_new_token
            
            # Get new tokens if we couldn't refresh
            logger.info("Getting new tokens")
            new_tokens = self._get_new_tokens()
            is_new_token = True
            return new_tokens['access_token'], is_new_token
            
        except Exception as e:
            logger.error(f"Error getting valid token: {str(e)}")
            raise

def update_azure_token(force_new=False):
    """Update the AZURE_BEARER_TOKEN in .env file with a valid token."""
    try:
        # Get valid token
        token_manager = AzureTokenManager()
        valid_token, is_new_token = token_manager.get_valid_token(force_new=force_new)
        
        # Only log "updated" if we actually got a new token
        if is_new_token:
            logger.info("Successfully updated Azure tokens in .env")
        else:
            logger.info("Using existing valid Azure token")
        
        return valid_token
        
    except Exception as e:
        logger.error(f"Error with Azure token: {str(e)}")
        raise

def fetch_azure_users_and_groups():
    """Fetch users and groups from Azure AD via Microsoft Graph API and save them to JSON file."""
    try:
        # First, ensure we have a valid token
        bearer_token = update_azure_token()
        
        # Get environment variables
        load_dotenv()
        graph_endpoint = os.getenv('AZURE_SCIM_ENDPOINT')
        # Get email preference setting (default is to use federated ID if mail is not available)
        prefer_real_email = os.getenv('AZURE_PREFER_REAL_EMAIL', 'false').lower() == 'true'
        
        if not graph_endpoint:
            raise ValueError("Missing required environment variable: AZURE_SCIM_ENDPOINT")
        
        # Setup headers for Graph API
        headers = {
            'Authorization': f'Bearer {bearer_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Fetch Groups first to build a mapping of users to groups
        logger.info("Fetching groups from Azure AD...")
        groups = {}
        user_to_groups = {}
        
        # Microsoft Graph API for groups
        groups_url = graph_endpoint.replace('/users', '/groups')
        params = {
            '$select': 'id,displayName',
            '$top': 100
        }
        
        next_link = None
        
        # Function to handle API requests with token refresh on 401 errors
        def make_api_request(url, params=None, retry_count=0):
            nonlocal headers
            
            if retry_count > 1:
                logger.error(f"Failed to make API request after token refresh: {url}")
                raise ValueError("Failed to authenticate with Microsoft Graph API after token refresh")
                
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401 and retry_count == 0:
                    logger.warning("Received 401 Unauthorized error. Refreshing token and retrying...")
                    # Force a new token
                    new_token = update_azure_token(force_new=True)
                    headers['Authorization'] = f'Bearer {new_token}'
                    # Retry the request with the new token
                    return make_api_request(url, params, retry_count + 1)
                else:
                    # Re-raise the exception for other errors or if we've already retried
                    raise
        
        while True:
            # If we have a next link from a previous call, use it directly
            if next_link:
                data = make_api_request(next_link)
            else:
                data = make_api_request(groups_url, params)
            
            resources = data.get('value', [])
            
            # Process each group
            for group in resources:
                group_id = group.get('id')
                group_name = normalize_text(group.get('displayName', '').strip())
                groups[group_id] = group_name
                
                # Get group members using a separate call
                members_url = f"{groups_url}/{group_id}/members"
                members_data = make_api_request(members_url)
                
                # Add each member to the user_to_groups mapping
                for member in members_data.get('value', []):
                    member_id = member.get('id')
                    if member_id not in user_to_groups:
                        user_to_groups[member_id] = []
                    user_to_groups[member_id].append(group_name)
            
            # Check if there are more pages
            next_link = data.get('@odata.nextLink')
            if not next_link:
                break
                
            logger.info(f"Fetched {len(groups)} groups so far...")
        
        # Fetch Users
        logger.info("Fetching users from Azure AD...")
        users = []
        
        # Microsoft Graph API for users
        users_url = graph_endpoint
        params = {
            '$select': 'id,displayName,mail,userPrincipalName,department,jobTitle,givenName,surname,mobilePhone,businessPhones,streetAddress,postalCode,manager',
            '$expand': 'manager',
            '$top': 100  # Graph API page size
        }
        
        next_link = None
        
        while True:
            # If we have a next link from a previous call, use it directly
            if next_link:
                data = make_api_request(next_link)
            else:
                data = make_api_request(users_url, params)
            
            resources = data.get('value', [])
            
            # Transform to our schema
            for user in resources:
                user_id = user.get('id')
                
                # Handle email based on preference setting
                mail = user.get('mail')
                user_principal_name = user.get('userPrincipalName')
                
                if prefer_real_email:
                    # Prefer mail, but fall back to userPrincipalName if mail is not available
                    email = mail if mail else user_principal_name
                else:
                    # Always use userPrincipalName (federated ID) as the primary email
                    email = user_principal_name
                
                # Properly handle Polish characters in names
                display_name = normalize_text(user.get('displayName', '').strip())
                
                # Extract manager ID correctly
                manager = user.get('manager', {})
                manager_id = manager.get('id', '') if manager else ''
                
                transformed_user = {
                    "external_id": user_id,
                    "name": display_name,
                    "email": email,
                    "department": normalize_text(user.get('department', '')),
                    "status": "active",  # Graph API doesn't directly expose this in the same way
                    "supervisor_id": manager_id,
                    "groups": user_to_groups.get(user_id, [])
                }
                users.append(transformed_user)
            
            # Check if there are more pages
            next_link = data.get('@odata.nextLink')
            if not next_link:
                break
                
            logger.info(f"Fetched {len(users)} users so far...")
        
        # Save users to file with proper encoding for Polish characters
        users_output = {"users": users}
        with open("users.json", 'w', encoding='utf-8') as f:
            json.dump(users_output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully saved {len(users)} users to users.json with group information")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching from Azure AD Graph API: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error processing Azure AD data: {str(e)}")
        raise

if __name__ == "__main__":
    fetch_azure_users_and_groups() 