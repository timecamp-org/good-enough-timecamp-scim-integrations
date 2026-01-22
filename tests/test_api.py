"""
Tests for TimeCamp API wrapper functionality.
"""
import pytest
from unittest.mock import MagicMock, Mock, patch, call
import requests
from common.api import TimeCampAPI


class TestTimeCampAPI:
    """Tests for the TimeCampAPI class."""
    
    def test_init(self, mock_timecamp_config):
        """Test API initialization."""
        api = TimeCampAPI(mock_timecamp_config)
        
        assert api.base_url == f"https://{mock_timecamp_config.domain}/third_party/api"
        assert "Authorization" in api.headers
        assert f"Bearer {mock_timecamp_config.api_key}" in api.headers["Authorization"]
    
    @patch('common.api.requests.request')
    def test_make_request_success(self, mock_request, mock_timecamp_config):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test'}
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        response = api._make_request('GET', 'users')
        
        assert response.status_code == 200
        mock_request.assert_called_once()
    
    @patch('common.api.requests.request')
    @patch('common.api.time.sleep')
    def test_make_request_retry_on_429(self, mock_sleep, mock_request, mock_timecamp_config):
        """Test retry logic on 429 rate limit."""
        # First call returns 429, second call succeeds
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.raise_for_status.side_effect = requests.exceptions.HTTPError()
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'data': 'test'}
        
        mock_request.side_effect = [mock_response_429, mock_response_200]
        
        api = TimeCampAPI(mock_timecamp_config)
        response = api._make_request('GET', 'users')
        
        assert response.status_code == 200
        assert mock_request.call_count == 2
        assert mock_sleep.called
    
    @patch('common.api.requests.request')
    def test_make_request_logs_debug_info(self, mock_request, mock_timecamp_config):
        """Test that request details are logged."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        api._make_request('POST', 'users', json={'email': 'test@test.com'})
        
        # Should have made request with JSON body
        call_kwargs = mock_request.call_args[1]
        assert 'json' in call_kwargs
    
    @patch('common.api.requests.request')
    def test_get_users(self, mock_request, mock_timecamp_config):
        """Test getting users."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'user_id': '1001', 'email': 'user1@test.com'},
            {'user_id': '1002', 'email': 'user2@test.com'}
        ]
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        
        # Mock are_users_enabled to return enabled status
        with patch.object(api, 'are_users_enabled', return_value={1001: True, 1002: True}):
            users = api.get_users()
        
        assert len(users) == 2
        assert users[0]['is_enabled'] is True
    
    @patch('common.api.requests.request')
    def test_get_groups(self, mock_request, mock_timecamp_config):
        """Test getting groups."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'group_id': '100', 'name': 'Root'},
            {'group_id': '101', 'name': 'Engineering'}
        ]
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        groups = api.get_groups()
        
        assert len(groups) == 2
        assert groups[0]['name'] == 'Root'
    
    @patch('common.api.requests.request')
    @patch('common.api.time.sleep')
    def test_add_group_with_retry_on_403(self, mock_sleep, mock_request, mock_timecamp_config):
        """Test add_group retries on 403 errors."""
        # First call returns 403, second call succeeds
        mock_response_403 = Mock()
        mock_response_403.status_code = 403
        error = requests.exceptions.HTTPError()
        error.response = mock_response_403
        mock_response_403.raise_for_status.side_effect = error
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'group_id': '101'}
        
        mock_request.side_effect = [mock_response_403, mock_response_200]
        
        api = TimeCampAPI(mock_timecamp_config)
        group_id = api.add_group('Test Group', 100)
        
        assert group_id == '101'
        assert mock_request.call_count == 2
        assert mock_sleep.called
    
    @patch('common.api.requests.request')
    def test_add_user(self, mock_request, mock_timecamp_config):
        """Test adding a user."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'user_id': '1003'}
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        result = api.add_user('newuser@test.com', 'New User', 101)
        
        assert result['user_id'] == '1003'
        
        # Check request payload
        call_kwargs = mock_request.call_args[1]
        json_data = call_kwargs['json']
        assert 'newuser@test.com' in json_data['email']
    
    @patch('common.api.requests.request')
    def test_update_user_name(self, mock_request, mock_timecamp_config):
        """Test updating user name."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        api.update_user(1001, {'fullName': 'Updated Name'}, 100)
        
        # Should make POST request to update display_name
        assert mock_request.called
        call_kwargs = mock_request.call_args[1]
        assert 'display_name' in call_kwargs['json']
    
    @patch('common.api.requests.request')
    def test_update_user_group(self, mock_request, mock_timecamp_config):
        """Test updating user group."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        api.update_user(1001, {'groupId': 101}, 100)
        
        # Should make PUT request to update group
        assert mock_request.called
    
    @patch('common.api.requests.request')
    def test_update_user_role(self, mock_request, mock_timecamp_config):
        """Test updating user role."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        api.update_user(1001, {'role_id': '2'}, 100)
        
        # Should make PUT request with role_id
        assert mock_request.called
        call_kwargs = mock_request.call_args[1]
        assert 'role_id' in call_kwargs['json']
        assert call_kwargs['json']['role_id'] == '2'
    
    @patch('common.api.requests.request')
    def test_update_user_setting(self, mock_request, mock_timecamp_config):
        """Test updating user setting."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        api.update_user_setting(1001, 'external_id', 'ext-123')
        
        call_kwargs = mock_request.call_args[1]
        json_data = call_kwargs['json']
        assert json_data['name'] == 'external_id'
        assert json_data['value'] == 'ext-123'
    
    @patch('common.api.requests.request')
    def test_set_additional_email(self, mock_request, mock_timecamp_config):
        """Test setting additional email."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        api.set_additional_email(1001, 'additional@test.com')
        
        call_kwargs = mock_request.call_args[1]
        json_data = call_kwargs['json']
        assert json_data['name'] == 'additional_email'
        assert json_data['value'] == 'additional@test.com'
    
    @patch('common.api.requests.request')
    def test_get_user_settings_batch(self, mock_request, mock_timecamp_config):
        """Test getting user settings in batch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            '1001': [
                {'name': 'external_id', 'value': 'ext-123'}
            ],
            '1002': [
                {'name': 'external_id', 'value': 'ext-456'}
            ]
        }
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        settings = api.get_user_settings([1001, 1002], 'external_id')
        
        assert settings[1001] == 'ext-123'
        assert settings[1002] == 'ext-456'
    
    @patch('common.api.requests.request')
    def test_get_additional_emails(self, mock_request, mock_timecamp_config):
        """Test getting additional emails."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            '1001': [{'name': 'additional_email', 'value': 'add1@test.com'}],
            '1002': [{'name': 'additional_email', 'value': 'add2@test.com'}]
        }
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        emails = api.get_additional_emails([1001, 1002])
        
        assert emails[1001] == 'add1@test.com'
        assert emails[1002] == 'add2@test.com'
    
    @patch('common.api.requests.request')
    def test_get_external_ids(self, mock_request, mock_timecamp_config):
        """Test getting external IDs."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            '1001': [{'name': 'external_id', 'value': 'ext-123'}]
        }
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        ext_ids = api.get_external_ids([1001])
        
        assert ext_ids[1001] == 'ext-123'
    
    @patch('common.api.requests.request')
    def test_get_manually_added_statuses(self, mock_request, mock_timecamp_config):
        """Test getting manually added statuses."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            '1001': [{'name': 'added_manually', 'value': '0'}],
            '1002': [{'name': 'added_manually', 'value': '1'}]
        }
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        statuses = api.get_manually_added_statuses([1001, 1002])
        
        assert statuses[1001] is False
        assert statuses[1002] is True
    
    @patch('common.api.requests.request')
    def test_are_users_enabled(self, mock_request, mock_timecamp_config):
        """Test checking if users are enabled."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            '1001': [{'name': 'disabled_user', 'value': '0'}],
            '1002': [{'name': 'disabled_user', 'value': '1'}]
        }
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        enabled_statuses = api.are_users_enabled([1001, 1002])
        
        assert enabled_statuses[1001] is True
        assert enabled_statuses[1002] is False
    
    @patch('common.api.requests.request')
    def test_get_user_roles(self, mock_request, mock_timecamp_config):
        """Test getting user roles."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'groups': {
                '100': {
                    'group_id': '100',
                    'users': {
                        '1001': {'role_id': '3'},
                        '1002': {'role_id': '2'}
                    }
                }
            }
        }
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        roles = api.get_user_roles()
        
        assert '1001' in roles
        assert roles['1001'][0]['role_id'] == '3'
        assert roles['1002'][0]['role_id'] == '2'
    
    @patch('common.api.requests.request')
    def test_add_vacation(self, mock_request, mock_timecamp_config):
        """Test adding vacation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        api.add_vacation(
            user_id=1001,
            start_date='2024-01-15',
            end_date='2024-01-17',
            leave_type_id='1',
            shouldBe=480,
            vacationTime=480
        )
        
        # Should make multiple calls (one per day)
        assert mock_request.call_count == 3
    
    @patch('common.api.requests.request')
    def test_get_day_types(self, mock_request, mock_timecamp_config):
        """Test getting day types."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                '1': {'id': '1', 'name': 'Vacation', 'isDayOff': False},
                '2': {'id': '2', 'name': 'Sick Leave', 'isDayOff': True}
            }
        }
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        day_types = api.get_day_types()
        
        assert '1' in day_types
        assert day_types['1']['name'] == 'Vacation'
    
    @patch('common.api.requests.request')
    def test_delete_group(self, mock_request, mock_timecamp_config):
        """Test deleting a group."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        api = TimeCampAPI(mock_timecamp_config)
        api.delete_group(101)
        
        # Should make DELETE request
        assert mock_request.call_args[0][0] == 'DELETE'

    def test_init_with_protocol(self, mock_timecamp_config):
        """Test API initialization with protocol in domain."""
        mock_timecamp_config.domain = "http://example.com"
        api = TimeCampAPI(mock_timecamp_config)
        assert api.base_url == "http://example.com/third_party/api"

        mock_timecamp_config.domain = "https://example.com"
        api = TimeCampAPI(mock_timecamp_config)
        assert api.base_url == "https://example.com/third_party/api"

    def test_init_ssl_verify(self, mock_timecamp_config):
        """Test API initialization with SSL verify configuration."""
        mock_timecamp_config.ssl_verify = True
        api = TimeCampAPI(mock_timecamp_config)
        assert api.ssl_verify is True
        
        mock_timecamp_config.ssl_verify = False
        api = TimeCampAPI(mock_timecamp_config)
        assert api.ssl_verify is False

    @patch('common.api.requests.request')
    def test_make_request_ssl_verify(self, mock_request, mock_timecamp_config):
        """Test that SSL verification setting is passed to requests."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response
        
        # Test with ssl_verify=True
        mock_timecamp_config.ssl_verify = True
        api = TimeCampAPI(mock_timecamp_config)
        api._make_request('GET', 'users')
        
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs['verify'] is True
        
        # Test with ssl_verify=False
        mock_timecamp_config.ssl_verify = False
        api = TimeCampAPI(mock_timecamp_config)
        api._make_request('GET', 'users')
        
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs['verify'] is False

