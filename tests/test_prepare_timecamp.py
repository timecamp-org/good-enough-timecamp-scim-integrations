"""
Tests for TimeCamp data preparation functionality.
"""
import pytest
import json
from prepare_timecamp_json_from_fetch import (
    check_force_supervisor_exists,
    determine_role,
    replace_email_domain,
    process_group_path,
    prepare_timecamp_users,
)


class TestCheckForceSupervisorExists:
    """Tests for checking if force_supervisor_role exists in data."""
    
    def test_force_supervisor_exists(self):
        """Test when force_supervisor_role=true exists."""
        source_data = {
            'users': [
                {'name': 'User 1', 'force_supervisor_role': False},
                {'name': 'User 2', 'force_supervisor_role': True},
                {'name': 'User 3'}
            ]
        }
        
        assert check_force_supervisor_exists(source_data) is True
    
    def test_force_supervisor_not_exists(self):
        """Test when force_supervisor_role=true does not exist."""
        source_data = {
            'users': [
                {'name': 'User 1', 'force_supervisor_role': False},
                {'name': 'User 2'},
                {'name': 'User 3'}
            ]
        }
        
        assert check_force_supervisor_exists(source_data) is False
    
    def test_empty_users(self):
        """Test with empty users list."""
        source_data = {'users': []}
        assert check_force_supervisor_exists(source_data) is False


class TestDetermineRole:
    """Tests for role determination logic."""
    
    def test_force_global_admin_role_highest_priority(self, mock_timecamp_config):
        """Test that force_global_admin_role has highest priority."""
        user = {
            'force_global_admin_role': True,
            'force_supervisor_role': True,
            'is_supervisor': True,
            'role_id': '3'
        }
        
        result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
        assert result == 'administrator'
    
    def test_force_supervisor_role(self, mock_timecamp_config):
        """Test force_supervisor_role."""
        user = {
            'force_supervisor_role': True,
            'is_supervisor': False,
            'role_id': '3'
        }
        
        result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
        assert result == 'supervisor'
    
    def test_force_supervisor_exists_disables_other_logic(self, mock_timecamp_config):
        """Test that force_supervisor_exists disables other supervisor logic."""
        user = {
            'is_supervisor': True,
            'role_id': '2'
        }
        
        result = determine_role(user, mock_timecamp_config, force_supervisor_exists=True)
        assert result == 'user'
    
    def test_is_supervisor_role_boolean_true(self, mock_timecamp_config):
        """Test is_supervisor boolean field when true."""
        mock_timecamp_config.use_is_supervisor_role = True
        user = {
            'is_supervisor': True
        }
        
        result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
        assert result == 'supervisor'
    
    def test_is_supervisor_role_boolean_false(self, mock_timecamp_config):
        """Test is_supervisor boolean field when false."""
        mock_timecamp_config.use_is_supervisor_role = True
        user = {
            'is_supervisor': False
        }
        
        result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
        assert result == 'user'
    
    def test_is_supervisor_role_string_true(self, mock_timecamp_config):
        """Test is_supervisor string field."""
        mock_timecamp_config.use_is_supervisor_role = True
        
        for value in ['true', 'True', '1', 'yes', 'YES']:
            user = {'is_supervisor': value}
            result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
            assert result == 'supervisor', f"Failed for value: {value}"
    
    def test_is_supervisor_role_string_false(self, mock_timecamp_config):
        """Test is_supervisor string field as false."""
        mock_timecamp_config.use_is_supervisor_role = True
        
        for value in ['false', 'False', '0', 'no', 'NO']:
            user = {'is_supervisor': value}
            result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
            assert result == 'user', f"Failed for value: {value}"
    
    def test_role_id_administrator(self, mock_timecamp_config):
        """Test role_id mapping for administrator."""
        user = {'role_id': '1'}
        result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
        assert result == 'administrator'
    
    def test_role_id_supervisor(self, mock_timecamp_config):
        """Test role_id mapping for supervisor."""
        user = {'role_id': '2'}
        result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
        assert result == 'supervisor'
    
    def test_role_id_user(self, mock_timecamp_config):
        """Test role_id mapping for user."""
        user = {'role_id': '3'}
        result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
        assert result == 'user'
    
    def test_role_id_guest(self, mock_timecamp_config):
        """Test role_id mapping for guest."""
        user = {'role_id': '5'}
        result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
        assert result == 'guest'
    
    def test_role_id_default_fallback(self, mock_timecamp_config):
        """Test default fallback for unknown role_id."""
        user = {'role_id': '99'}
        result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
        assert result == 'user'
    
    def test_role_id_missing_defaults_to_user(self, mock_timecamp_config):
        """Test that missing role_id defaults to user."""
        user = {}
        result = determine_role(user, mock_timecamp_config, force_supervisor_exists=False)
        assert result == 'user'


class TestReplaceEmailDomain:
    """Tests for email domain replacement."""
    
    def test_replace_email_domain_basic(self):
        """Test basic email domain replacement."""
        email = "user@olddomain.com"
        new_domain = "newdomain.com"
        
        result = replace_email_domain(email, new_domain)
        assert result == "user@newdomain.com"
    
    def test_replace_email_domain_with_at_sign(self):
        """Test domain replacement when new domain has @ prefix."""
        email = "user@olddomain.com"
        new_domain = "@newdomain.com"
        
        result = replace_email_domain(email, new_domain)
        assert result == "user@newdomain.com"
    
    def test_replace_email_domain_empty_new_domain(self):
        """Test that empty new domain returns original email."""
        email = "user@domain.com"
        new_domain = ""
        
        result = replace_email_domain(email, new_domain)
        assert result == "user@domain.com"
    
    def test_replace_email_domain_empty_email(self):
        """Test that empty email returns empty string."""
        email = ""
        new_domain = "newdomain.com"
        
        result = replace_email_domain(email, new_domain)
        assert result == ""
    
    def test_replace_email_domain_invalid_email(self):
        """Test with email without @ sign."""
        email = "notanemail"
        new_domain = "newdomain.com"
        
        result = replace_email_domain(email, new_domain)
        assert result == "notanemail"
    
    def test_replace_email_domain_complex_username(self):
        """Test with complex username containing dots and numbers."""
        email = "john.doe.123@olddomain.com"
        new_domain = "newdomain.org"
        
        result = replace_email_domain(email, new_domain)
        assert result == "john.doe.123@newdomain.org"


class TestProcessGroupPath:
    """Tests for group path processing."""
    
    def test_process_group_path_basic(self, mock_timecamp_config):
        """Test basic group path processing."""
        department = "Engineering/Team A"
        result = process_group_path(department, mock_timecamp_config)
        assert result == "Engineering/Team A"
    
    def test_process_group_path_empty(self, mock_timecamp_config):
        """Test empty department path."""
        department = ""
        result = process_group_path(department, mock_timecamp_config)
        assert result == ""
    
    def test_process_group_path_none(self, mock_timecamp_config):
        """Test None department path."""
        department = None
        result = process_group_path(department, mock_timecamp_config)
        assert result == ""


class TestPrepareTimeCampUsers:
    """Tests for the main prepare_timecamp_users function."""
    
    def test_prepare_basic_users(self, mock_timecamp_config, sample_users):
        """Test basic user preparation."""
        result = prepare_timecamp_users(sample_users, mock_timecamp_config)
        
        assert len(result) > 0
        assert all('timecamp_email' in user for user in result)
        assert all('timecamp_user_name' in user for user in result)
        assert all('timecamp_status' in user for user in result)
        assert all('timecamp_role' in user for user in result)
    
    def test_prepare_users_with_job_title_formatting(self, mock_timecamp_config, sample_users):
        """Test user preparation with job title formatting."""
        mock_timecamp_config.use_job_title_name_users = True
        
        result = prepare_timecamp_users(sample_users, mock_timecamp_config)
        
        # Find a user with job title
        user_with_job = next((u for u in result if 'HR Manager' in u.get('timecamp_user_name', '')), None)
        assert user_with_job is not None
        assert '[' in user_with_job['timecamp_user_name']
    
    def test_prepare_users_with_external_id(self, mock_timecamp_config, sample_users):
        """Test that external IDs are preserved."""
        result = prepare_timecamp_users(sample_users, mock_timecamp_config)
        
        for user in result:
            assert 'timecamp_external_id' in user
            assert user['timecamp_external_id'] != ''
    
    def test_prepare_users_status_mapping(self, mock_timecamp_config):
        """Test status mapping from active/inactive."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'Active User',
                    'email': 'active@test.com',
                    'status': 'active',
                    'department': 'IT',
                    'job_title': '',
                    'supervisor_id': ''
                },
                {
                    'external_id': 'user-2',
                    'name': 'Inactive User',
                    'email': 'inactive@test.com',
                    'status': 'inactive',
                    'department': 'IT',
                    'job_title': '',
                    'supervisor_id': ''
                }
            ]
        }
        
        result = prepare_timecamp_users(source_data, mock_timecamp_config)
        
        active_user = next(u for u in result if u['timecamp_email'] == 'active@test.com')
        inactive_user = next(u for u in result if u['timecamp_email'] == 'inactive@test.com')
        
        assert active_user['timecamp_status'] == 'active'
        assert inactive_user['timecamp_status'] == 'inactive'
    
    def test_prepare_users_with_email_domain_replacement(self, mock_timecamp_config):
        """Test email domain replacement."""
        mock_timecamp_config.replace_email_domain = '@newdomain.com'
        
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'Test User',
                    'email': 'test@olddomain.com',
                    'status': 'active',
                    'department': 'IT',
                    'job_title': '',
                    'supervisor_id': ''
                }
            ]
        }
        
        result = prepare_timecamp_users(source_data, mock_timecamp_config)
        
        assert result[0]['timecamp_email'] == 'test@newdomain.com'
    
    def test_prepare_users_with_real_email(self, mock_timecamp_config):
        """Test that real_email is included when different from primary."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'Test User',
                    'email': 'test@federated.com',
                    'real_email': 'test@real.com',
                    'status': 'active',
                    'department': 'IT',
                    'job_title': '',
                    'supervisor_id': ''
                }
            ]
        }
        
        result = prepare_timecamp_users(source_data, mock_timecamp_config)
        
        assert 'timecamp_real_email' in result[0]
        assert result[0]['timecamp_real_email'] == 'test@real.com'
    
    def test_prepare_users_real_email_same_as_primary(self, mock_timecamp_config):
        """Test that real_email is not included when same as primary."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'Test User',
                    'email': 'test@example.com',
                    'real_email': 'test@example.com',
                    'status': 'active',
                    'department': 'IT',
                    'job_title': '',
                    'supervisor_id': ''
                }
            ]
        }
        
        result = prepare_timecamp_users(source_data, mock_timecamp_config)
        
        assert 'timecamp_real_email' not in result[0]
    
    def test_prepare_users_force_global_admin_empty_breadcrumb(self, mock_timecamp_config):
        """Test that force_global_admin_role users get empty breadcrumb."""
        source_data = {
            'users': [
                {
                    'external_id': 'admin-1',
                    'name': 'Admin User',
                    'email': 'admin@test.com',
                    'status': 'active',
                    'department': 'IT/Management',
                    'job_title': 'CTO',
                    'supervisor_id': '',
                    'force_global_admin_role': True
                }
            ]
        }
        
        result = prepare_timecamp_users(source_data, mock_timecamp_config)
        
        assert result[0]['timecamp_groups_breadcrumb'] == ''
        assert result[0]['timecamp_role'] == 'administrator'
    
    def test_prepare_users_sorted_by_email(self, mock_timecamp_config):
        """Test that users are sorted by email."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-3',
                    'name': 'User C',
                    'email': 'c@test.com',
                    'status': 'active',
                    'department': 'IT',
                    'job_title': '',
                    'supervisor_id': ''
                },
                {
                    'external_id': 'user-1',
                    'name': 'User A',
                    'email': 'a@test.com',
                    'status': 'active',
                    'department': 'IT',
                    'job_title': '',
                    'supervisor_id': ''
                },
                {
                    'external_id': 'user-2',
                    'name': 'User B',
                    'email': 'b@test.com',
                    'status': 'active',
                    'department': 'IT',
                    'job_title': '',
                    'supervisor_id': ''
                }
            ]
        }
        
        result = prepare_timecamp_users(source_data, mock_timecamp_config)
        
        emails = [u['timecamp_email'] for u in result]
        assert emails == sorted(emails)

