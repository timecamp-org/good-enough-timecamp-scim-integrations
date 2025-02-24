import os
import json
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key, find_dotenv
from common.logger import setup_logger

logger = setup_logger()

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
        
        # Required scopes for SCIM API
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
    
    def get_valid_token(self):
        """Get a valid access token, refreshing or fetching new ones as needed."""
        try:
            # Try to load existing tokens
            tokens = self._load_tokens()
            current_time = time.time()
            
            if tokens:
                # Check if access token is still valid
                if tokens.get('expires_at', 0) > current_time + 300:  # 5-minute buffer
                    logger.debug("Using existing access token")
                    return tokens['access_token']
                
                # Check if we can use refresh token
                if 'refresh_token' in tokens:
                    if tokens.get('refresh_token_expires_at', 0) > current_time:
                        logger.info("Refreshing access token")
                        new_tokens = self._refresh_token(tokens['refresh_token'])
                        return new_tokens['access_token']
            
            # Get new tokens if we couldn't refresh
            logger.info("Getting new tokens")
            new_tokens = self._get_new_tokens()
            return new_tokens['access_token']
            
        except Exception as e:
            logger.error(f"Error getting valid token: {str(e)}")
            raise

def update_env_token():
    """Update the AZURE_BEARER_TOKEN in .env file with a valid token."""
    try:
        # Get valid token
        token_manager = AzureTokenManager()
        valid_token = token_manager.get_valid_token()
        
        logger.info("Successfully updated Azure tokens in .env")
        
    except Exception as e:
        logger.error(f"Error updating token in .env: {str(e)}")
        raise

if __name__ == "__main__":
    update_env_token() 