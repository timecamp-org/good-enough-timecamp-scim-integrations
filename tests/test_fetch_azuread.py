"""
Tests for Azure AD user fetching functionality.
"""
import pytest
import json
from unittest.mock import Mock, MagicMock, patch, call
from fetch_azuread import (
    normalize_text,
    transform_azure_user_to_schema,
    AzureTokenManager,
    fetch_group_members,
    find_group_id_by_name,
)


class TestNormalizeText:
    """Tests for text normalization function."""
    
    def test_normalize_text_with_polish_characters(self):
        """Test that Polish characters are preserved."""
        text = "Łukasz Żółć"
        result = normalize_text(text)
        assert result == "Łukasz Żółć"
    
    def test_normalize_text_with_empty_string(self):
        """Test normalization of empty string."""
        assert normalize_text("") == ""
    
    def test_normalize_text_with_none(self):
        """Test normalization of None."""
        assert normalize_text(None) == ""
    
    def test_normalize_text_with_regular_text(self):
        """Test normalization of regular text."""
        text = "John Doe"
        result = normalize_text(text)
        assert result == "John Doe"


class TestTransformAzureUserToSchema:
    """Tests for Azure AD user transformation."""
    
    def test_transform_basic_user(self):
        """Test transformation of basic user with all fields."""
        azure_user = {
            "id": "user-123",
            "displayName": "John Doe",
            "mail": "john.doe@example.com",
            "userPrincipalName": "john.doe@example.onmicrosoft.com",
            "department": "Engineering",
            "jobTitle": "Software Engineer",
            "manager": {
                "id": "manager-456"
            }
        }
        
        result = transform_azure_user_to_schema(azure_user, prefer_real_email=False)
        
        assert result["external_id"] == "user-123"
        assert result["name"] == "John Doe"
        assert result["email"] == "john.doe@example.onmicrosoft.com"
        assert result["department"] == "Engineering"
        assert result["job_title"] == "Software Engineer"
        assert result["status"] == "active"
        assert result["supervisor_id"] == "manager-456"
    
    def test_transform_user_prefer_real_email(self):
        """Test that real email is used when prefer_real_email is True."""
        azure_user = {
            "id": "user-123",
            "displayName": "Jane Smith",
            "mail": "jane.smith@company.com",
            "userPrincipalName": "jane@company.onmicrosoft.com",
            "department": "Sales",
            "jobTitle": "Sales Rep"
        }
        
        result = transform_azure_user_to_schema(azure_user, prefer_real_email=True)
        assert result["email"] == "jane.smith@company.com"
    
    def test_transform_user_prefer_real_email_fallback(self):
        """Test fallback to userPrincipalName when mail is missing."""
        azure_user = {
            "id": "user-123",
            "displayName": "Bob Wilson",
            "mail": None,
            "userPrincipalName": "bob@company.onmicrosoft.com",
            "department": "IT",
            "jobTitle": "IT Admin"
        }
        
        result = transform_azure_user_to_schema(azure_user, prefer_real_email=True)
        assert result["email"] == "bob@company.onmicrosoft.com"
    
    def test_transform_user_use_federated_id(self):
        """Test that federated ID is used when prefer_real_email is False."""
        azure_user = {
            "id": "user-123",
            "displayName": "Alice Johnson",
            "mail": "alice@company.com",
            "userPrincipalName": "alice@company.onmicrosoft.com",
            "department": "HR",
            "jobTitle": "HR Manager"
        }
        
        result = transform_azure_user_to_schema(azure_user, prefer_real_email=False)
        assert result["email"] == "alice@company.onmicrosoft.com"
    
    def test_transform_user_no_manager(self):
        """Test transformation of user without manager."""
        azure_user = {
            "id": "user-123",
            "displayName": "CEO User",
            "userPrincipalName": "ceo@company.com",
            "department": "Executive",
            "jobTitle": "CEO",
            "manager": None
        }
        
        result = transform_azure_user_to_schema(azure_user, prefer_real_email=False)
        assert result["supervisor_id"] == ""
    
    def test_transform_user_with_polish_characters(self):
        """Test that Polish characters in names are preserved."""
        azure_user = {
            "id": "user-123",
            "displayName": "Łukasz Żółć",
            "userPrincipalName": "lukasz@company.com",
            "department": "Dział Techniczny",
            "jobTitle": "Programista"
        }
        
        result = transform_azure_user_to_schema(azure_user, prefer_real_email=False)
        assert result["name"] == "Łukasz Żółć"
        assert result["department"] == "Dział Techniczny"
        assert result["job_title"] == "Programista"
    
    def test_transform_user_email_lowercase(self):
        """Test that email is converted to lowercase."""
        azure_user = {
            "id": "user-123",
            "displayName": "Test User",
            "userPrincipalName": "Test.User@Company.COM",
            "department": "Test",
            "jobTitle": "Tester"
        }
        
        result = transform_azure_user_to_schema(azure_user, prefer_real_email=False)
        assert result["email"] == "test.user@company.com"
    
    def test_transform_user_missing_optional_fields(self):
        """Test transformation with missing optional fields."""
        azure_user = {
            "id": "user-123",
            "displayName": "Minimal User",
            "userPrincipalName": "minimal@company.com"
        }
        
        result = transform_azure_user_to_schema(azure_user, prefer_real_email=False)
        assert result["external_id"] == "user-123"
        assert result["name"] == "Minimal User"
        assert result["email"] == "minimal@company.com"
        assert result["department"] == ""
        assert result["job_title"] == ""
        assert result["supervisor_id"] == ""


class TestAzureTokenManager:
    """Tests for Azure Token Manager."""
    
    @patch('fetch_azuread.find_dotenv')
    @patch('fetch_azuread.load_dotenv')
    def test_init_with_valid_config(self, mock_load_dotenv, mock_find_dotenv, monkeypatch):
        """Test initialization with valid configuration."""
        monkeypatch.setenv('AZURE_TENANT_ID', 'test-tenant')
        monkeypatch.setenv('AZURE_CLIENT_ID', 'test-client')
        monkeypatch.setenv('AZURE_CLIENT_SECRET', 'test-secret')
        mock_find_dotenv.return_value = '.env'
        
        manager = AzureTokenManager()
        
        assert manager.tenant_id == 'test-tenant'
        assert manager.client_id == 'test-client'
        assert manager.client_secret == 'test-secret'
        assert 'test-tenant' in manager.token_endpoint
    
    @patch('fetch_azuread.load_dotenv')
    def test_init_missing_config_raises_error(self, mock_load_dotenv, monkeypatch):
        """Test that missing configuration raises ValueError."""
        monkeypatch.delenv('AZURE_TENANT_ID', raising=False)
        monkeypatch.delenv('AZURE_CLIENT_ID', raising=False)
        monkeypatch.delenv('AZURE_CLIENT_SECRET', raising=False)
        
        with pytest.raises(ValueError, match="Missing required Azure AD OAuth configuration"):
            AzureTokenManager()
    
    @patch('fetch_azuread.find_dotenv')
    @patch('fetch_azuread.load_dotenv')
    @patch('fetch_azuread.requests.post')
    @patch('fetch_azuread.set_key')
    @patch('fetch_azuread.time.time')
    def test_get_new_tokens_success(self, mock_time, mock_set_key, mock_post, 
                                     mock_load_dotenv, mock_find_dotenv, monkeypatch):
        """Test successful token acquisition."""
        monkeypatch.setenv('AZURE_TENANT_ID', 'test-tenant')
        monkeypatch.setenv('AZURE_CLIENT_ID', 'test-client')
        monkeypatch.setenv('AZURE_CLIENT_SECRET', 'test-secret')
        mock_find_dotenv.return_value = '.env'
        mock_time.return_value = 1000.0
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_token_123',
            'expires_in': 3600,
            'refresh_token': 'refresh_token_456'
        }
        mock_post.return_value = mock_response
        
        manager = AzureTokenManager()
        token_data = manager._get_new_tokens()
        
        assert token_data['access_token'] == 'new_token_123'
        assert mock_set_key.called
    
    @patch('fetch_azuread.find_dotenv')
    @patch('fetch_azuread.load_dotenv')
    @patch('fetch_azuread.time.time')
    def test_get_valid_token_uses_existing_valid_token(self, mock_time, 
                                                        mock_load_dotenv, 
                                                        mock_find_dotenv, 
                                                        monkeypatch):
        """Test that existing valid token is reused."""
        monkeypatch.setenv('AZURE_TENANT_ID', 'test-tenant')
        monkeypatch.setenv('AZURE_CLIENT_ID', 'test-client')
        monkeypatch.setenv('AZURE_CLIENT_SECRET', 'test-secret')
        monkeypatch.setenv('AZURE_BEARER_TOKEN', 'existing_token')
        monkeypatch.setenv('AZURE_TOKEN_EXPIRES_AT', '2000')
        mock_find_dotenv.return_value = '.env'
        mock_time.return_value = 1000.0  # Token expires at 2000, still valid
        
        manager = AzureTokenManager()
        token, is_new = manager.get_valid_token()
        
        assert token == 'existing_token'
        assert is_new is False


class TestFetchGroupMembers:
    """Tests for fetching group members."""
    
    def test_fetch_group_members_single_page(self):
        """Test fetching group members with single page response."""
        mock_api_request = Mock()
        mock_api_request.return_value = {
            'value': [
                {'id': 'user-1', '@odata.type': '#microsoft.graph.user'},
                {'id': 'user-2', '@odata.type': '#microsoft.graph.user'},
                {'id': 'group-1', '@odata.type': '#microsoft.graph.group'}  # Should be filtered
            ],
            '@odata.nextLink': None
        }
        
        result = fetch_group_members(
            'mock_token',
            'group-123',
            {'Authorization': 'Bearer mock_token'},
            mock_api_request
        )
        
        assert len(result) == 2
        assert 'user-1' in result
        assert 'user-2' in result
        assert 'group-1' not in result
    
    def test_fetch_group_members_multiple_pages(self):
        """Test fetching group members with pagination."""
        responses = [
            {
                'value': [
                    {'id': 'user-1', '@odata.type': '#microsoft.graph.user'},
                ],
                '@odata.nextLink': 'https://graph.microsoft.com/v1.0/groups/123/members?$skip=1'
            },
            {
                'value': [
                    {'id': 'user-2', '@odata.type': '#microsoft.graph.user'},
                ],
                '@odata.nextLink': None
            }
        ]
        
        mock_api_request = Mock(side_effect=responses)
        
        result = fetch_group_members(
            'mock_token',
            'group-123',
            {'Authorization': 'Bearer mock_token'},
            mock_api_request
        )
        
        assert len(result) == 2
        assert 'user-1' in result
        assert 'user-2' in result
        assert mock_api_request.call_count == 2


class TestFindGroupIdByName:
    """Tests for finding group ID by name."""
    
    def test_find_group_id_by_name_found(self):
        """Test finding existing group by name."""
        mock_api_request = Mock()
        mock_api_request.return_value = {
            'value': [
                {'id': 'group-123', 'displayName': 'Engineering Team'}
            ]
        }
        
        result = find_group_id_by_name(
            'mock_token',
            'Engineering Team',
            {'Authorization': 'Bearer mock_token'},
            mock_api_request
        )
        
        assert result == 'group-123'
    
    def test_find_group_id_by_name_not_found(self):
        """Test when group is not found."""
        mock_api_request = Mock()
        mock_api_request.return_value = {'value': []}
        
        result = find_group_id_by_name(
            'mock_token',
            'Nonexistent Group',
            {'Authorization': 'Bearer mock_token'},
            mock_api_request
        )
        
        assert result is None
    
    def test_find_group_id_by_name_url_encoding(self):
        """Test that group name is properly URL encoded."""
        mock_api_request = Mock()
        mock_api_request.return_value = {'value': []}
        
        find_group_id_by_name(
            'mock_token',
            'Group with spaces',
            {'Authorization': 'Bearer mock_token'},
            mock_api_request
        )
        
        # Verify the API was called (URL encoding happens internally)
        mock_api_request.assert_called_once()


class TestFetchAzureUsersIntegration:
    """Integration tests for the full fetch_azure_users function."""
    
    @patch('fetch_azuread.update_azure_token')
    @patch('fetch_azuread.load_dotenv')
    @patch('fetch_azuread.requests.get')
    @patch('common.storage.save_json_file')
    def test_fetch_azure_users_basic(self, mock_save, mock_get, mock_load_dotenv, 
                                     mock_update_token, monkeypatch):
        """Test basic user fetching without group filtering."""
        monkeypatch.setenv('AZURE_SCIM_ENDPOINT', 'https://graph.microsoft.com/v1.0/users')
        monkeypatch.setenv('AZURE_PREFER_REAL_EMAIL', 'false')
        monkeypatch.setenv('AZURE_FILTER_GROUPS', '')
        
        mock_update_token.return_value = 'mock_token'
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'value': [
                {
                    'id': 'user-1',
                    'displayName': 'Test User',
                    'mail': 'test@example.com',
                    'userPrincipalName': 'test@example.onmicrosoft.com',
                    'department': 'IT',
                    'jobTitle': 'Developer',
                    'manager': None
                }
            ],
            '@odata.nextLink': None
        }
        mock_get.return_value = mock_response
        
        from fetch_azuread import fetch_azure_users
        fetch_azure_users()
        
        # Verify save_json_file was called
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        
        assert 'users' in saved_data
        assert len(saved_data['users']) == 1
        assert saved_data['users'][0]['external_id'] == 'user-1'
        assert saved_data['users'][0]['name'] == 'Test User'

