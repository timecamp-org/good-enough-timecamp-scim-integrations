"""
Tests for supervisor group processing functionality.
"""
import pytest
from common.supervisor_groups import (
    prepare_user_data,
    format_supervisor_name_for_group,
    collect_users_and_supervisors,
    build_supervisor_paths,
    assign_departments_supervisor,
    assign_departments_standard,
    assign_departments_hybrid,
    process_source_data,
)


class TestPrepareUserData:
    """Tests for user data preparation."""
    
    def test_prepare_user_basic(self):
        """Test basic user data preparation."""
        user_data = {
            'name': 'John Doe',
            'email': 'John.Doe@Example.COM',
            'external_id': 'user-123',
            'job_title': 'Developer'
        }
        
        result = prepare_user_data(user_data, show_external_id=False, use_job_title_name=False)
        
        assert result['name'] == 'John Doe'
        assert result['email'] == 'john.doe@example.com'
    
    def test_prepare_user_with_external_id(self):
        """Test user preparation with external ID display."""
        user_data = {
            'name': 'Jane Smith',
            'email': 'jane@example.com',
            'external_id': 'ext-456',
            'job_title': 'Manager'
        }
        
        result = prepare_user_data(user_data, show_external_id=True, use_job_title_name=False)
        
        assert 'ext-456' in result['name']
    
    def test_prepare_user_with_job_title(self):
        """Test user preparation with job title formatting."""
        user_data = {
            'name': 'Bob Wilson',
            'email': 'bob@example.com',
            'external_id': 'user-789',
            'job_title': 'Senior Developer'
        }
        
        result = prepare_user_data(user_data, show_external_id=False, use_job_title_name=True)
        
        assert 'Senior Developer' in result['name']
        assert '[Bob Wilson]' in result['name']
    
    def test_prepare_user_email_lowercase(self):
        """Test that email is converted to lowercase."""
        user_data = {
            'name': 'Test User',
            'email': 'Test.User@DOMAIN.COM',
            'external_id': 'test-1',
            'job_title': ''
        }
        
        result = prepare_user_data(user_data, show_external_id=False, use_job_title_name=False)
        
        assert result['email'] == 'test.user@domain.com'


class TestFormatSupervisorNameForGroup:
    """Tests for supervisor name formatting for groups."""
    
    def test_format_supervisor_basic(self, mock_timecamp_config):
        """Test basic supervisor name formatting."""
        user_data = {
            'name': 'Manager Name',
            'job_title': 'Engineering Manager',
            'external_id': 'mgr-123'
        }
        
        result = format_supervisor_name_for_group(user_data, mock_timecamp_config)
        
        assert result == 'Manager Name'
    
    def test_format_supervisor_with_job_title(self, mock_timecamp_config):
        """Test supervisor formatting with job title enabled."""
        mock_timecamp_config.use_job_title_name_groups = True
        
        user_data = {
            'name': 'Alice Johnson',
            'job_title': 'VP Engineering',
            'external_id': 'vp-456'
        }
        
        result = format_supervisor_name_for_group(user_data, mock_timecamp_config)
        
        assert 'VP Engineering' in result
        assert '[Alice Johnson]' in result
    
    def test_format_supervisor_with_external_id(self, mock_timecamp_config):
        """Test supervisor formatting with external ID display."""
        mock_timecamp_config.show_external_id = True
        
        user_data = {
            'name': 'Charlie Brown',
            'job_title': 'Director',
            'external_id': 'dir-789'
        }
        
        result = format_supervisor_name_for_group(user_data, mock_timecamp_config)
        
        assert 'dir-789' in result
    
    def test_format_supervisor_extract_from_formatted_name(self, mock_timecamp_config):
        """Test extracting base name from already formatted name."""
        mock_timecamp_config.use_job_title_name_groups = True
        
        user_data = {
            'name': 'Manager Title [Original Name]',
            'job_title': 'New Title',
            'external_id': 'user-1'
        }
        
        result = format_supervisor_name_for_group(user_data, mock_timecamp_config)
        
        # Should extract "Original Name" and reformat with "New Title"
        assert 'New Title' in result
        assert '[Original Name]' in result


class TestCollectUsersAndSupervisors:
    """Tests for collecting users and identifying supervisors."""
    
    def test_collect_users_basic(self, mock_timecamp_config):
        """Test basic user collection."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'Employee 1',
                    'email': 'emp1@test.com',
                    'supervisor_id': 'mgr-1',
                    'job_title': '',
                    'department': ''
                },
                {
                    'external_id': 'mgr-1',
                    'name': 'Manager 1',
                    'email': 'mgr1@test.com',
                    'supervisor_id': '',
                    'job_title': 'Manager',
                    'department': ''
                }
            ]
        }
        
        users_by_id, supervisor_ids = collect_users_and_supervisors(source_data, mock_timecamp_config)
        
        assert len(users_by_id) == 2
        assert 'user-1' in users_by_id
        assert 'mgr-1' in users_by_id
        assert 'mgr-1' in supervisor_ids
        assert 'user-1' not in supervisor_ids
    
    def test_collect_users_chain_of_supervisors(self, mock_timecamp_config):
        """Test identifying supervisors in a chain."""
        source_data = {
            'users': [
                {
                    'external_id': 'emp-1',
                    'name': 'Employee',
                    'email': 'emp@test.com',
                    'supervisor_id': 'mgr-1',
                    'job_title': '',
                    'department': ''
                },
                {
                    'external_id': 'mgr-1',
                    'name': 'Manager',
                    'email': 'mgr@test.com',
                    'supervisor_id': 'dir-1',
                    'job_title': '',
                    'department': ''
                },
                {
                    'external_id': 'dir-1',
                    'name': 'Director',
                    'email': 'dir@test.com',
                    'supervisor_id': '',
                    'job_title': '',
                    'department': ''
                }
            ]
        }
        
        users_by_id, supervisor_ids = collect_users_and_supervisors(source_data, mock_timecamp_config)
        
        assert 'mgr-1' in supervisor_ids
        assert 'dir-1' in supervisor_ids
        assert 'emp-1' not in supervisor_ids


class TestBuildSupervisorPaths:
    """Tests for building supervisor hierarchy paths."""
    
    def test_build_paths_single_level(self, mock_timecamp_config):
        """Test building paths for single-level hierarchy."""
        source_data = {'users': []}
        users_by_id = {
            'mgr-1': {
                'name': 'Manager One',
                'supervisor_id': '',
                'job_title': 'Manager'
            }
        }
        supervisor_ids = {'mgr-1'}
        
        paths = build_supervisor_paths(source_data, users_by_id, supervisor_ids, mock_timecamp_config)
        
        assert 'mgr-1' in paths
        assert paths['mgr-1'] == 'Manager One'
    
    def test_build_paths_multi_level(self, mock_timecamp_config):
        """Test building paths for multi-level hierarchy."""
        source_data = {'users': []}
        users_by_id = {
            'dir-1': {
                'name': 'Director',
                'supervisor_id': '',
                'job_title': 'Director'
            },
            'mgr-1': {
                'name': 'Manager',
                'supervisor_id': 'dir-1',
                'job_title': 'Manager'
            },
            'lead-1': {
                'name': 'Team Lead',
                'supervisor_id': 'mgr-1',
                'job_title': 'Lead'
            }
        }
        supervisor_ids = {'dir-1', 'mgr-1', 'lead-1'}
        
        paths = build_supervisor_paths(source_data, users_by_id, supervisor_ids, mock_timecamp_config)
        
        assert paths['dir-1'] == 'Director'
        assert paths['mgr-1'] == 'Director/Manager'
        assert paths['lead-1'] == 'Director/Manager/Team Lead'
    
    def test_build_paths_supervisor_not_in_dataset(self, mock_timecamp_config):
        """Test handling supervisor not present in dataset."""
        source_data = {'users': []}
        users_by_id = {
            'mgr-1': {
                'name': 'Manager',
                'supervisor_id': 'external-boss',  # Not in dataset
                'job_title': 'Manager'
            }
        }
        supervisor_ids = {'mgr-1'}
        
        paths = build_supervisor_paths(source_data, users_by_id, supervisor_ids, mock_timecamp_config)
        
        # Should treat as top-level since supervisor not in dataset
        assert paths['mgr-1'] == 'Manager'


class TestAssignDepartmentsSupervisor:
    """Tests for assigning departments based on supervisor hierarchy."""
    
    def test_assign_supervisor_mode_basic(self, mock_timecamp_config):
        """Test basic supervisor mode assignment."""
        source_data = {
            'users': [
                {
                    'external_id': 'mgr-1',
                    'name': 'Manager',
                    'supervisor_id': '',
                    'department': '',
                    'job_title': ''
                },
                {
                    'external_id': 'emp-1',
                    'name': 'Employee',
                    'supervisor_id': 'mgr-1',
                    'department': '',
                    'job_title': ''
                }
            ]
        }
        
        users_by_id = {
            'mgr-1': source_data['users'][0],
            'emp-1': source_data['users'][1]
        }
        supervisor_ids = {'mgr-1'}
        supervisor_paths = {'mgr-1': 'Manager'}
        
        paths = assign_departments_supervisor(
            source_data, users_by_id, supervisor_ids, supervisor_paths, mock_timecamp_config
        )
        
        # Manager should be in own group
        assert source_data['users'][0]['department'] == 'Manager'
        # Employee should be in manager's group
        assert source_data['users'][1]['department'] == 'Manager'
        # Role assignments
        assert source_data['users'][0]['role_id'] == '2'  # Supervisor
        assert source_data['users'][1]['role_id'] == '3'  # User


class TestAssignDepartmentsStandard:
    """Tests for standard department assignment."""
    
    def test_assign_standard_basic(self, mock_timecamp_config):
        """Test basic standard department assignment."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'User 1',
                    'department': 'Engineering/Team A',
                    'job_title': '',
                    'supervisor_id': ''
                },
                {
                    'external_id': 'user-2',
                    'name': 'User 2',
                    'department': 'Sales',
                    'job_title': '',
                    'supervisor_id': ''
                }
            ]
        }
        
        paths = assign_departments_standard(source_data, mock_timecamp_config)
        
        assert 'Engineering/Team A' in paths
        assert 'Sales' in paths
        assert source_data['users'][0]['department'] == 'Engineering/Team A'
        assert source_data['users'][1]['department'] == 'Sales'
    
    def test_assign_standard_with_skip_departments(self, mock_timecamp_config):
        """Test department assignment with skip_departments config."""
        mock_timecamp_config.skip_departments = 'Company'
        
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'User 1',
                    'department': 'Company/Engineering',
                    'job_title': '',
                    'supervisor_id': ''
                }
            ]
        }
        
        paths = assign_departments_standard(source_data, mock_timecamp_config)
        
        # "Company" prefix should be removed
        assert source_data['users'][0]['department'] == 'Engineering'
        assert 'Engineering' in paths


class TestAssignDepartmentsHybrid:
    """Tests for hybrid department + supervisor assignment."""
    
    def test_assign_hybrid_basic(self, mock_timecamp_config):
        """Test basic hybrid mode assignment."""
        source_data = {
            'users': [
                {
                    'external_id': 'mgr-1',
                    'name': 'Manager',
                    'department': 'Engineering',
                    'job_title': 'Engineering Manager',
                    'supervisor_id': ''
                },
                {
                    'external_id': 'emp-1',
                    'name': 'Employee',
                    'department': 'Engineering',
                    'job_title': 'Developer',
                    'supervisor_id': 'mgr-1'
                }
            ]
        }
        
        users_by_id = {
            'mgr-1': source_data['users'][0],
            'emp-1': source_data['users'][1]
        }
        supervisor_ids = {'mgr-1'}
        supervisor_paths = {'mgr-1': 'Manager'}
        
        paths = assign_departments_hybrid(
            source_data, users_by_id, supervisor_ids, supervisor_paths, mock_timecamp_config
        )
        
        # Manager gets department + own name
        assert 'Engineering' in source_data['users'][0]['department']
        assert 'Manager' in source_data['users'][0]['department']
        
        # Employee gets department + supervisor name
        assert 'Engineering' in source_data['users'][1]['department']
        assert 'Manager' in source_data['users'][1]['department']


class TestProcessSourceData:
    """Integration tests for the main process_source_data function."""
    
    def test_process_department_only_mode(self, mock_timecamp_config, sample_users):
        """Test processing with department-only mode."""
        mock_timecamp_config.use_supervisor_groups = False
        mock_timecamp_config.use_department_groups = True
        
        users_by_email, dept_paths = process_source_data(sample_users, mock_timecamp_config)
        
        assert len(users_by_email) > 0
        assert len(dept_paths) > 0
        # All users should have email key in lowercase
        for email in users_by_email.keys():
            assert email == email.lower()
    
    def test_process_supervisor_only_mode(self, mock_timecamp_config):
        """Test processing with supervisor-only mode."""
        mock_timecamp_config.use_supervisor_groups = True
        mock_timecamp_config.use_department_groups = False
        
        source_data = {
            'users': [
                {
                    'external_id': 'mgr-1',
                    'name': 'Manager',
                    'email': 'mgr@test.com',
                    'department': 'Engineering',
                    'job_title': 'Manager',
                    'supervisor_id': '',
                    'status': 'active'
                },
                {
                    'external_id': 'emp-1',
                    'name': 'Employee',
                    'email': 'emp@test.com',
                    'department': 'Engineering',
                    'job_title': 'Developer',
                    'supervisor_id': 'mgr-1',
                    'status': 'active'
                }
            ]
        }
        
        users_by_email, dept_paths = process_source_data(source_data, mock_timecamp_config)
        
        assert len(users_by_email) == 2
        # In supervisor mode, departments are based on supervisor hierarchy
        for user in users_by_email.values():
            assert 'department' in user
    
    def test_process_hybrid_mode(self, mock_timecamp_config):
        """Test processing with hybrid mode."""
        mock_timecamp_config.use_supervisor_groups = True
        mock_timecamp_config.use_department_groups = True
        
        source_data = {
            'users': [
                {
                    'external_id': 'mgr-1',
                    'name': 'Manager',
                    'email': 'mgr@test.com',
                    'department': 'Sales',
                    'job_title': 'Sales Manager',
                    'supervisor_id': '',
                    'status': 'active'
                },
                {
                    'external_id': 'rep-1',
                    'name': 'Sales Rep',
                    'email': 'rep@test.com',
                    'department': 'Sales',
                    'job_title': 'Sales Representative',
                    'supervisor_id': 'mgr-1',
                    'status': 'active'
                }
            ]
        }
        
        users_by_email, dept_paths = process_source_data(source_data, mock_timecamp_config)
        
        assert len(users_by_email) == 2
        # Hybrid mode combines department + supervisor
        for user in users_by_email.values():
            if user['external_id'] in ['mgr-1', 'rep-1']:
                assert 'Sales' in user.get('department', '')
    
    def test_process_with_job_title_formatting(self, mock_timecamp_config):
        """Test processing with job title formatting enabled."""
        mock_timecamp_config.use_job_title_name_users = True
        mock_timecamp_config.use_job_title_name_groups = True
        
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'John Doe',
                    'email': 'john@test.com',
                    'department': 'IT',
                    'job_title': 'Senior Developer',
                    'supervisor_id': '',
                    'status': 'active'
                }
            ]
        }
        
        users_by_email, dept_paths = process_source_data(source_data, mock_timecamp_config)
        
        user = users_by_email['john@test.com']
        # User name should include job title
        assert 'Senior Developer' in user['name']
        assert '[John Doe]' in user['name']



