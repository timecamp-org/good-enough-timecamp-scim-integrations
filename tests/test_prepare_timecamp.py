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
    get_users_to_exclude,
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

    def test_process_group_path_regex_change(self, mock_timecamp_config):
        """Test regex group path transformation."""
        mock_timecamp_config.change_groups_regex = "Old Group|||New Group"
        department = "Old Group/Subgroup"
        result = process_group_path(department, mock_timecamp_config)
        assert result == "New Group/Subgroup"

    def test_process_group_path_regex_no_match(self, mock_timecamp_config):
        """Test regex group path transformation with no match."""
        mock_timecamp_config.change_groups_regex = "Old Group|||New Group"
        department = "Different Group"
        result = process_group_path(department, mock_timecamp_config)
        assert result == "Different Group"

    def test_process_group_path_regex_complex(self, mock_timecamp_config):
        """Test regex group path transformation with complex regex."""
        # Swap: "A [B]/C [D]" -> "X [Y]/C [D]"
        mock_timecamp_config.change_groups_regex = r"A \[B\]|||X [Y]"
        department = "A [B]/C [D]"
        result = process_group_path(department, mock_timecamp_config)
        assert result == "X [Y]/C [D]"

    def test_process_group_path_regex_invalid_format(self, mock_timecamp_config):
        """Test invalid regex format (missing separator)."""
        mock_timecamp_config.change_groups_regex = "InvalidFormat"
        department = "Group"
        result = process_group_path(department, mock_timecamp_config)
        assert result == "Group"

    def test_process_group_path_regex_invalid_regex(self, mock_timecamp_config):
        """Test invalid regex pattern."""
        mock_timecamp_config.change_groups_regex = r"[Invalid|||Replacement"
        department = "Group"
        result = process_group_path(department, mock_timecamp_config)
        assert result == "Group"

    def test_process_group_path_multiple_regex_rules(self, mock_timecamp_config):
        """Test multiple regex rules separated by ;;;."""
        # Rule 1: "A" -> "B"
        # Rule 2: "B" -> "C"
        # Result should be "C"
        mock_timecamp_config.change_groups_regex = "A|||B;;;B|||C"
        department = "A"
        result = process_group_path(department, mock_timecamp_config)
        assert result == "C"

    def test_process_group_path_multiple_regex_rules_partial_match(self, mock_timecamp_config):
        """Test multiple regex rules where only some match."""
        # Rule 1: "X" -> "Y" (No match)
        # Rule 2: "A" -> "B" (Match)
        mock_timecamp_config.change_groups_regex = "X|||Y;;;A|||B"
        department = "A"
        result = process_group_path(department, mock_timecamp_config)
        assert result == "B"

    def test_process_group_path_multiple_regex_rules_with_empty_segments(self, mock_timecamp_config):
        """Test multiple regex rules with empty segments (extra separators)."""
        mock_timecamp_config.change_groups_regex = "A|||B;;;;;;B|||C"
        department = "A"
        result = process_group_path(department, mock_timecamp_config)
        assert result == "C"


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

    def test_prepare_users_with_transform_config(self, mock_timecamp_config, tmp_path):
        """Test applying prepare transform config before processing."""
        transform_config = {
            "filter": {
                "and": [
                    {
                        "property": "department",
                        "string": {"starts_with": "IT/"}
                    },
                    {
                        "property": "raw_data.customField4932",
                        "string": {"equals": "yes"}
                    }
                ]
            },
            "transform": [
                {
                    "property": "department",
                    "action": "replace_all",
                    "value": ""
                }
            ]
        }
        config_path = tmp_path / "transform.json"
        config_path.write_text(json.dumps(transform_config))
        mock_timecamp_config.prepare_transform_config = str(config_path)

        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'Match User',
                    'email': 'match@test.com',
                    'status': 'active',
                    'department': 'IT/Recruiting',
                    'job_title': '',
                    'supervisor_id': '',
                    'raw_data': {'customField4932': 'yes'}
                },
                {
                    'external_id': 'user-2',
                    'name': 'No Match',
                    'email': 'nomatch@test.com',
                    'status': 'active',
                    'department': 'IT/Recruiting',
                    'job_title': '',
                    'supervisor_id': '',
                    'raw_data': {'customField4932': 'no'}
                }
            ]
        }

        result = prepare_timecamp_users(source_data, mock_timecamp_config)

        matched_user = next(u for u in result if u['timecamp_email'] == 'match@test.com')
        unmatched_user = next(u for u in result if u['timecamp_email'] == 'nomatch@test.com')

        assert matched_user['timecamp_groups_breadcrumb'] == ''
        assert unmatched_user['timecamp_groups_breadcrumb'] == 'IT/Recruiting'

    def test_prepare_users_puts_entire_object_in_raw_data(self, mock_timecamp_config):
        """Test that the entire source object is put inside raw_data field."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'Test User',
                    'email': 'test@example.com',
                    'status': 'active',
                    'department': 'IT',
                    'job_title': 'Developer',
                    'custom_field': 'custom_value',
                    'supervisor_id': '',
                    'original_raw': {'id': 123}
                }
            ]
        }
        
        result = prepare_timecamp_users(source_data, mock_timecamp_config)
        
        user = result[0]
        # Check standard TimeCamp fields
        assert user['timecamp_email'] == 'test@example.com'
        
        # Check that extra fields are NOT at the top level anymore
        assert 'custom_field' not in user
        assert 'original_raw' not in user
        
        # Check that entire object is in raw_data
        assert 'raw_data' in user
        raw_data = user['raw_data']
        assert raw_data['external_id'] == 'user-1'
        assert raw_data['name'] == 'Test User'
        assert raw_data['custom_field'] == 'custom_value'
        assert raw_data['original_raw'] == {'id': 123}


class TestRegexExclusion:
    """Tests for regex exclusion logic."""

    def test_no_regex_configured(self, mock_timecamp_config):
        """Test that users are not filtered when no regex is configured."""
        mock_timecamp_config.exclude_regex = ""
        users = [
            {'email': 'keep@test.com', 'department': 'Dept', 'job_title': 'Title'}
        ]
        
        result = get_users_to_exclude(users, mock_timecamp_config)
        assert len(result) == 0

    def test_regex_matching_department(self, mock_timecamp_config):
        """Test exclusion based on department match."""
        mock_timecamp_config.exclude_regex = r'department="ExcludeMe"'
        users = [
            {'email': 'exclude@test.com', 'department': 'ExcludeMe', 'job_title': 'Title'},
            {'email': 'keep@test.com', 'department': 'KeepMe', 'job_title': 'Title'}
        ]
        
        result = get_users_to_exclude(users, mock_timecamp_config)
        assert len(result) == 1
        assert 'exclude@test.com' in result

    def test_regex_matching_job_title(self, mock_timecamp_config):
        """Test exclusion based on job title match."""
        mock_timecamp_config.exclude_regex = r'job_title="ExcludeTitle"'
        users = [
            {'email': 'exclude@test.com', 'department': 'Dept', 'job_title': 'ExcludeTitle'},
            {'email': 'keep@test.com', 'department': 'Dept', 'job_title': 'KeepTitle'}
        ]
        
        result = get_users_to_exclude(users, mock_timecamp_config)
        assert len(result) == 1
        assert 'exclude@test.com' in result

    def test_regex_matching_complex_condition(self, mock_timecamp_config):
        """Test exclusion with complex regex (similar to user requirement)."""
        # Regex: Exclude if Department is "Support" AND Job Title is NOT "Manager"
        # We achieve "NOT Manager" by matching job_title="something else"
        # Let's try: department="Support" job_title="(?!Manager)[^"]*"
        mock_timecamp_config.exclude_regex = r'department="Support" job_title="(?!Manager)[^"]*"'
        
        users = [
            {'email': 'manager@test.com', 'department': 'Support', 'job_title': 'Manager'},
            {'email': 'dev@test.com', 'department': 'Support', 'job_title': 'Developer'},
            {'email': 'other@test.com', 'department': 'Other', 'job_title': 'Developer'}
        ]
        
        result = get_users_to_exclude(users, mock_timecamp_config)
        
        assert len(result) == 1
        assert 'dev@test.com' in result

    def test_invalid_regex_handling(self, mock_timecamp_config):
        """Test that invalid regex doesn't crash and preserves users."""
        mock_timecamp_config.exclude_regex = r'['  # Invalid regex
        users = [
            {'email': 'user@test.com', 'department': 'Dept', 'job_title': 'Title'}
        ]
        
        # Should catch error and return empty set (no exclusions)
        result = get_users_to_exclude(users, mock_timecamp_config)
        assert len(result) == 0

    def test_regex_context_formatting(self, mock_timecamp_config):
        """Test that context string is formatted correctly with quotes handling."""
        mock_timecamp_config.exclude_regex = r'department="DeptWith\"Quote"'
        users = [
            {'email': 'test@test.com', 'department': 'DeptWith"Quote', 'job_title': 'Title'}
        ]
        
        # The function replaces " with ' in values before checking
        # So department="DeptWith"Quote" becomes department="DeptWith'Quote" in context
        
        # Let's test that we can match what it actually produces
        mock_timecamp_config.exclude_regex = r"department=\"DeptWith'Quote\""
        
        result = get_users_to_exclude(users, mock_timecamp_config)
        assert len(result) == 1
        assert 'test@test.com' in result
