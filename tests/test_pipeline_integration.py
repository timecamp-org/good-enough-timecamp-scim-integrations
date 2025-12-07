"""
End-to-end pipeline integration tests.
Tests the complete flow: users.json → prepare_timecamp → timecamp_users.json
Verifies output for different configuration scenarios.
"""
import pytest
import json
import os
from unittest.mock import patch
from prepare_timecamp_json_from_fetch import prepare_timecamp_users
from common.utils import TimeCampConfig


class TestPipelineBasicConfigurations:
    """Test pipeline with basic configuration options."""
    
    def test_department_only_mode_output(self, sample_users):
        """Test output with department-only mode."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_SUPERVISOR_GROUPS': 'false',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(sample_users, config)
                
                # Verify structure
                assert len(result) > 0
                for user in result:
                    assert 'timecamp_email' in user
                    assert 'timecamp_user_name' in user
                    assert 'timecamp_groups_breadcrumb' in user
                    assert 'timecamp_status' in user
                    assert 'timecamp_role' in user
                    assert 'timecamp_external_id' in user
                
                # Verify departments are preserved
                user_with_dept = next((u for u in result if 'tc2minisync' in u.get('timecamp_groups_breadcrumb', '')), None)
                assert user_with_dept is not None
    
    def test_supervisor_only_mode_output(self):
        """Test output with supervisor-only mode."""
        source_data = {
            'users': [
                {
                    'external_id': 'mgr-1',
                    'name': 'Manager',
                    'email': 'mgr@test.com',
                    'department': 'Engineering',
                    'job_title': 'Engineering Manager',
                    'status': 'active',
                    'supervisor_id': ''
                },
                {
                    'external_id': 'emp-1',
                    'name': 'Employee',
                    'email': 'emp@test.com',
                    'department': 'Engineering',
                    'job_title': 'Developer',
                    'status': 'active',
                    'supervisor_id': 'mgr-1'
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_SUPERVISOR_GROUPS': 'true',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'false'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                # Both users should be in supervisor hierarchy
                mgr = next((u for u in result if u['timecamp_email'] == 'mgr@test.com'), None)
                emp = next((u for u in result if u['timecamp_email'] == 'emp@test.com'), None)
                
                assert mgr is not None
                assert emp is not None
                # Employee should be under manager's group
                assert 'Manager' in emp['timecamp_groups_breadcrumb']
    
    def test_hybrid_mode_output(self):
        """Test output with hybrid mode (department + supervisor)."""
        source_data = {
            'users': [
                {
                    'external_id': 'mgr-1',
                    'name': 'Jane Smith',
                    'email': 'jane@test.com',
                    'department': 'Sales',
                    'job_title': 'Sales Manager',
                    'status': 'active',
                    'supervisor_id': ''
                },
                {
                    'external_id': 'rep-1',
                    'name': 'Bob Wilson',
                    'email': 'bob@test.com',
                    'department': 'Sales',
                    'job_title': 'Sales Rep',
                    'status': 'active',
                    'supervisor_id': 'mgr-1'
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_SUPERVISOR_GROUPS': 'true',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                # Verify hybrid structure (department/supervisor)
                mgr = next((u for u in result if u['timecamp_email'] == 'jane@test.com'), None)
                rep = next((u for u in result if u['timecamp_email'] == 'bob@test.com'), None)
                
                assert mgr is not None
                assert rep is not None
                # Both should have department in path
                assert 'Sales' in mgr['timecamp_groups_breadcrumb']
                assert 'Sales' in rep['timecamp_groups_breadcrumb']
                # Rep should also have supervisor in path
                assert 'Jane Smith' in rep['timecamp_groups_breadcrumb']


class TestPipelineUserNameFormatting:
    """Test pipeline with user name formatting options."""
    
    def test_show_external_id_output(self, sample_users):
        """Test output with external ID shown in names."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_SHOW_EXTERNAL_ID': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(sample_users, config)
                
                # At least one user should have external_id in name
                user_with_ext_id = next(
                    (u for u in result if u['timecamp_external_id'] and 
                     u['timecamp_external_id'] in u['timecamp_user_name']), 
                    None
                )
                assert user_with_ext_id is not None
    
    def test_job_title_in_user_names_output(self, sample_users):
        """Test output with job titles in user names."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_JOB_TITLE_NAME_USERS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(sample_users, config)
                
                # Find user with job title
                user_with_job = next(
                    (u for u in sample_users['users'] if u.get('job_title')),
                    None
                )
                
                if user_with_job:
                    result_user = next(
                        (u for u in result if u['timecamp_email'] == user_with_job['email'].lower()),
                        None
                    )
                    # Name should contain job title
                    assert result_user is not None
                    assert '[' in result_user['timecamp_user_name']
    
    def test_job_title_in_group_names_output(self):
        """Test output with job titles in group names (supervisor mode)."""
        source_data = {
            'users': [
                {
                    'external_id': 'mgr-1',
                    'name': 'Alice Johnson',
                    'email': 'alice@test.com',
                    'department': 'Marketing',
                    'job_title': 'Marketing Director',
                    'status': 'active',
                    'supervisor_id': ''
                },
                {
                    'external_id': 'emp-1',
                    'name': 'Charlie Brown',
                    'email': 'charlie@test.com',
                    'department': 'Marketing',
                    'job_title': 'Marketing Specialist',
                    'status': 'active',
                    'supervisor_id': 'mgr-1'
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_SUPERVISOR_GROUPS': 'true',
            'TIMECAMP_USE_JOB_TITLE_NAME_GROUPS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                emp = next((u for u in result if u['timecamp_email'] == 'charlie@test.com'), None)
                assert emp is not None
                # Group name should contain job title
                assert 'Marketing Director' in emp['timecamp_groups_breadcrumb']


class TestPipelineEmailHandling:
    """Test pipeline with email configuration options."""
    
    def test_email_domain_replacement_output(self):
        """Test output with email domain replacement."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'Test User',
                    'email': 'test@olddomain.com',
                    'department': 'IT',
                    'job_title': 'Developer',
                    'status': 'active',
                    'supervisor_id': ''
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_REPLACE_EMAIL_DOMAIN': '@newdomain.com'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                assert len(result) == 1
                assert result[0]['timecamp_email'] == 'test@newdomain.com'
    
    def test_real_email_handling_output(self):
        """Test output with real_email field."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'Test User',
                    'email': 'test@federated.com',
                    'real_email': 'test@real.com',
                    'department': 'IT',
                    'job_title': 'Developer',
                    'status': 'active',
                    'supervisor_id': ''
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                assert len(result) == 1
                assert result[0]['timecamp_email'] == 'test@federated.com'
                assert 'timecamp_real_email' in result[0]
                assert result[0]['timecamp_real_email'] == 'test@real.com'


class TestPipelineDepartmentHandling:
    """Test pipeline with department configuration options."""
    
    def test_skip_departments_single_prefix_output(self):
        """Test output with single department prefix to skip."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'Test User',
                    'email': 'test@test.com',
                    'department': 'Company/Engineering/Team A',
                    'job_title': 'Developer',
                    'status': 'active',
                    'supervisor_id': ''
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_SKIP_DEPARTMENTS': 'Company'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                assert len(result) == 1
                assert result[0]['timecamp_groups_breadcrumb'] == 'Engineering/Team A'
    
    def test_skip_departments_multiple_levels_output(self):
        """Test output with multi-level department prefix to skip."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'Test User',
                    'email': 'test@test.com',
                    'department': 'Company/Organization/Engineering',
                    'job_title': 'Developer',
                    'status': 'active',
                    'supervisor_id': ''
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_SKIP_DEPARTMENTS': 'Company/Organization'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                assert len(result) == 1
                assert result[0]['timecamp_groups_breadcrumb'] == 'Engineering'
    
    def test_skip_departments_multiple_options_output(self):
        """Test output with multiple skip department options."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'User One',
                    'email': 'user1@test.com',
                    'department': 'CEO/Engineering',
                    'job_title': 'Developer',
                    'status': 'active',
                    'supervisor_id': ''
                },
                {
                    'external_id': 'user-2',
                    'name': 'User Two',
                    'email': 'user2@test.com',
                    'department': 'Chief Executive Officer/Sales',
                    'job_title': 'Sales Rep',
                    'status': 'active',
                    'supervisor_id': ''
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_SKIP_DEPARTMENTS': 'Chief Executive Officer,CEO,Executive'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                user1 = next((u for u in result if u['timecamp_email'] == 'user1@test.com'), None)
                user2 = next((u for u in result if u['timecamp_email'] == 'user2@test.com'), None)
                
                assert user1 is not None
                assert user2 is not None
                assert user1['timecamp_groups_breadcrumb'] == 'Engineering'
                assert user2['timecamp_groups_breadcrumb'] == 'Sales'


class TestPipelineRoleHandling:
    """Test pipeline with role configuration options."""
    
    def test_force_global_admin_role_output(self):
        """Test output with force_global_admin_role."""
        source_data = {
            'users': [
                {
                    'external_id': 'admin-1',
                    'name': 'Admin User',
                    'email': 'admin@test.com',
                    'department': 'IT/Management',
                    'job_title': 'CTO',
                    'status': 'active',
                    'supervisor_id': '',
                    'force_global_admin_role': True
                },
                {
                    'external_id': 'user-1',
                    'name': 'Regular User',
                    'email': 'user@test.com',
                    'department': 'IT',
                    'job_title': 'Developer',
                    'status': 'active',
                    'supervisor_id': ''
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                admin = next((u for u in result if u['timecamp_email'] == 'admin@test.com'), None)
                regular = next((u for u in result if u['timecamp_email'] == 'user@test.com'), None)
                
                assert admin is not None
                assert regular is not None
                assert admin['timecamp_role'] == 'administrator'
                assert admin['timecamp_groups_breadcrumb'] == ''  # Admin in root
                assert regular['timecamp_role'] == 'user'
    
    def test_force_supervisor_role_output(self):
        """Test output with force_supervisor_role."""
        source_data = {
            'users': [
                {
                    'external_id': 'sup-1',
                    'name': 'Supervisor',
                    'email': 'sup@test.com',
                    'department': 'Sales',
                    'job_title': 'Sales Manager',
                    'status': 'active',
                    'supervisor_id': '',
                    'force_supervisor_role': True
                },
                {
                    'external_id': 'user-1',
                    'name': 'Employee',
                    'email': 'emp@test.com',
                    'department': 'Sales',
                    'job_title': 'Sales Rep',
                    'status': 'active',
                    'supervisor_id': 'sup-1'
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                sup = next((u for u in result if u['timecamp_email'] == 'sup@test.com'), None)
                emp = next((u for u in result if u['timecamp_email'] == 'emp@test.com'), None)
                
                assert sup is not None
                assert emp is not None
                assert sup['timecamp_role'] == 'supervisor'
                # When force_supervisor exists, other users become regular users
                assert emp['timecamp_role'] == 'user'
    
    def test_is_supervisor_field_output(self):
        """Test output with is_supervisor boolean field."""
        source_data = {
            'users': [
                {
                    'external_id': 'mgr-1',
                    'name': 'Manager',
                    'email': 'mgr@test.com',
                    'department': 'Engineering',
                    'job_title': 'Engineering Manager',
                    'status': 'active',
                    'supervisor_id': '',
                    'is_supervisor': True
                },
                {
                    'external_id': 'dev-1',
                    'name': 'Developer',
                    'email': 'dev@test.com',
                    'department': 'Engineering',
                    'job_title': 'Developer',
                    'status': 'active',
                    'supervisor_id': 'mgr-1',
                    'is_supervisor': False
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_IS_SUPERVISOR_ROLE': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                mgr = next((u for u in result if u['timecamp_email'] == 'mgr@test.com'), None)
                dev = next((u for u in result if u['timecamp_email'] == 'dev@test.com'), None)
                
                assert mgr is not None
                assert dev is not None
                assert mgr['timecamp_role'] == 'supervisor'
                assert dev['timecamp_role'] == 'user'


class TestPipelineStatusHandling:
    """Test pipeline with user status handling."""
    
    def test_active_inactive_users_output(self):
        """Test output with active and inactive users."""
        source_data = {
            'users': [
                {
                    'external_id': 'active-1',
                    'name': 'Active User',
                    'email': 'active@test.com',
                    'department': 'IT',
                    'job_title': 'Developer',
                    'status': 'active',
                    'supervisor_id': ''
                },
                {
                    'external_id': 'inactive-1',
                    'name': 'Inactive User',
                    'email': 'inactive@test.com',
                    'department': 'IT',
                    'job_title': 'Developer',
                    'status': 'inactive',
                    'supervisor_id': ''
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                active = next((u for u in result if u['timecamp_email'] == 'active@test.com'), None)
                inactive = next((u for u in result if u['timecamp_email'] == 'inactive@test.com'), None)
                
                assert active is not None
                assert inactive is not None
                assert active['timecamp_status'] == 'active'
                assert inactive['timecamp_status'] == 'inactive'


class TestPipelineComplexScenarios:
    """Test pipeline with complex real-world scenarios."""
    
    def test_ldap_ou_structure_scenario(self):
        """Test LDAP OU structure scenario with skip departments."""
        source_data = {
            'users': [
                {
                    'external_id': 'user-1',
                    'name': 'John Doe',
                    'email': 'john.doe@ldap.com',
                    'real_email': 'john.doe@company.com',
                    'department': 'OU=Users,OU=Engineering,DC=company,DC=com',
                    'job_title': 'Senior Developer',
                    'status': 'active',
                    'supervisor_id': ''
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_SKIP_DEPARTMENTS': 'OU=Users',
            'TIMECAMP_REPLACE_EMAIL_DOMAIN': '@company.com',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                assert len(result) == 1
                # Email domain is replaced
                assert result[0]['timecamp_email'] == 'john.doe@company.com'
                # Real email is included (even though same after replacement, comparison is before replacement)
                assert 'timecamp_real_email' in result[0]
                assert result[0]['timecamp_real_email'] == 'john.doe@company.com'
                # Department prefix should be skipped
                assert 'OU=Engineering,DC=company,DC=com' in result[0]['timecamp_groups_breadcrumb']
    
    def test_full_featured_hybrid_scenario(self):
        """Test fully-featured hybrid scenario with all options."""
        source_data = {
            'users': [
                {
                    'external_id': 'ext-001',
                    'name': 'Alice Johnson',
                    'email': 'alice.johnson@old.com',
                    'real_email': 'alice@real.com',
                    'department': 'Company/Sales/EMEA',
                    'job_title': 'Regional Sales Director',
                    'status': 'active',
                    'supervisor_id': ''
                },
                {
                    'external_id': 'ext-002',
                    'name': 'Bob Smith',
                    'email': 'bob.smith@old.com',
                    'real_email': 'bob@real.com',
                    'department': 'Company/Sales/EMEA',
                    'job_title': 'Sales Manager',
                    'status': 'active',
                    'supervisor_id': 'ext-001'
                },
                {
                    'external_id': 'ext-003',
                    'name': 'Charlie Brown',
                    'email': 'charlie.brown@old.com',
                    'department': 'Company/Sales/EMEA',
                    'job_title': 'Sales Representative',
                    'status': 'active',
                    'supervisor_id': 'ext-002'
                }
            ]
        }
        
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_SUPERVISOR_GROUPS': 'true',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'true',
            'TIMECAMP_USE_JOB_TITLE_NAME_USERS': 'true',
            'TIMECAMP_USE_JOB_TITLE_NAME_GROUPS': 'true',
            'TIMECAMP_SKIP_DEPARTMENTS': 'Company',
            'TIMECAMP_REPLACE_EMAIL_DOMAIN': '@new.com',
            'TIMECAMP_SHOW_EXTERNAL_ID': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(source_data, config)
                
                assert len(result) == 3
                
                # Check Alice (top supervisor)
                alice = next((u for u in result if 'alice' in u['timecamp_email']), None)
                assert alice is not None
                assert alice['timecamp_email'] == 'alice.johnson@new.com'
                assert 'ext-001' in alice['timecamp_user_name']  # External ID shown
                assert 'Regional Sales Director' in alice['timecamp_user_name']  # Job title
                assert 'Sales/EMEA' in alice['timecamp_groups_breadcrumb']  # Dept without Company prefix
                
                # Check Bob (middle supervisor)
                bob = next((u for u in result if 'bob' in u['timecamp_email']), None)
                assert bob is not None
                assert bob['timecamp_email'] == 'bob.smith@new.com'
                assert 'Sales Manager' in bob['timecamp_user_name']
                assert bob['timecamp_role'] == 'supervisor'  # Has subordinates
                
                # Check Charlie (employee)
                charlie = next((u for u in result if 'charlie' in u['timecamp_email']), None)
                assert charlie is not None
                assert charlie['timecamp_email'] == 'charlie.brown@new.com'
                assert charlie['timecamp_role'] == 'user'
    
    def test_output_sorted_by_email(self, sample_users):
        """Test that output is always sorted by email."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(sample_users, config)
                
                # Extract emails
                emails = [u['timecamp_email'] for u in result]
                
                # Verify sorted
                assert emails == sorted(emails)
    
    def test_all_required_fields_present(self, sample_users):
        """Test that all required fields are always present in output."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                result = prepare_timecamp_users(sample_users, config)
                
                required_fields = [
                    'timecamp_external_id',
                    'timecamp_user_name',
                    'timecamp_email',
                    'timecamp_groups_breadcrumb',
                    'timecamp_status',
                    'timecamp_role'
                ]
                
                for user in result:
                    for field in required_fields:
                        assert field in user, f"Missing field {field} in user {user.get('timecamp_email')}"

