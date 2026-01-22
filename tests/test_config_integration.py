"""
Integration tests for configuration options from env.example.
Tests LDAP and TimeCamp configuration combinations.
"""
import pytest
import os
from unittest.mock import patch
from common.utils import TimeCampConfig


class TestTimeCampGroupStructureConfigs:
    """Test TimeCamp group structure configuration combinations."""
    
    def test_department_only_mode(self):
        """Test TIMECAMP_USE_DEPARTMENT_GROUPS=true only."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_SUPERVISOR_GROUPS': 'false',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.use_department_groups is True
                assert config.use_supervisor_groups is False
    
    def test_supervisor_only_mode(self):
        """Test TIMECAMP_USE_SUPERVISOR_GROUPS=true only."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_SUPERVISOR_GROUPS': 'true',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'false'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.use_supervisor_groups is True
                assert config.use_department_groups is False
    
    def test_hybrid_mode(self):
        """Test hybrid mode with both supervisor and department groups."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_SUPERVISOR_GROUPS': 'true',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.use_supervisor_groups is True
                assert config.use_department_groups is True


class TestTimeCampUserNameConfigs:
    """Test TimeCamp user name formatting configurations."""
    
    def test_show_external_id(self):
        """Test TIMECAMP_SHOW_EXTERNAL_ID configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_SHOW_EXTERNAL_ID': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.show_external_id is True
    
    def test_job_title_name_users(self):
        """Test TIMECAMP_USE_JOB_TITLE_NAME_USERS configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_JOB_TITLE_NAME_USERS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.use_job_title_name_users is True
    
    def test_job_title_name_groups(self):
        """Test TIMECAMP_USE_JOB_TITLE_NAME_GROUPS configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_JOB_TITLE_NAME_GROUPS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.use_job_title_name_groups is True
    
    def test_job_title_users_and_groups_separately(self):
        """Test that user and group job title settings are independent."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_JOB_TITLE_NAME_USERS': 'true',
            'TIMECAMP_USE_JOB_TITLE_NAME_GROUPS': 'false'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.use_job_title_name_users is True
                assert config.use_job_title_name_groups is False


class TestTimeCampEmailConfigs:
    """Test TimeCamp email configuration options."""
    
    def test_replace_email_domain(self):
        """Test TIMECAMP_REPLACE_EMAIL_DOMAIN configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_REPLACE_EMAIL_DOMAIN': '@test-timecamp.com'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.replace_email_domain == '@test-timecamp.com'
    
    def test_replace_email_domain_empty(self):
        """Test empty TIMECAMP_REPLACE_EMAIL_DOMAIN."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_REPLACE_EMAIL_DOMAIN': ''
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.replace_email_domain == ''


class TestTimeCampDepartmentConfigs:
    """Test TimeCamp department configuration options."""
    
    def test_skip_departments_single(self):
        """Test TIMECAMP_SKIP_DEPARTMENTS with single prefix."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_SKIP_DEPARTMENTS': 'Company'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.skip_departments == 'Company'
    
    def test_skip_departments_multiple(self):
        """Test TIMECAMP_SKIP_DEPARTMENTS with multiple prefixes."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_SKIP_DEPARTMENTS': 'Chief Executive Officer,CEO,Executive'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.skip_departments == 'Chief Executive Officer,CEO,Executive'
    
    def test_skip_departments_path(self):
        """Test TIMECAMP_SKIP_DEPARTMENTS with path prefix."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_SKIP_DEPARTMENTS': 'Company/Department'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.skip_departments == 'Company/Department'


class TestTimeCampSyncDisableConfigs:
    """Test TimeCamp synchronization disable flags."""
    
    def test_disable_new_users(self):
        """Test TIMECAMP_DISABLE_NEW_USERS configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLE_NEW_USERS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.disable_new_users is True
    
    def test_disable_external_id_sync(self):
        """Test TIMECAMP_DISABLE_EXTERNAL_ID_SYNC configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLE_EXTERNAL_ID_SYNC': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.disable_external_id_sync is True
    
    def test_disable_additional_email_sync(self):
        """Test TIMECAMP_DISABLE_ADDITIONAL_EMAIL_SYNC configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLE_ADDITIONAL_EMAIL_SYNC': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.disable_additional_email_sync is True
    
    def test_disable_manual_user_updates(self):
        """Test TIMECAMP_DISABLE_MANUAL_USER_UPDATES configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLE_MANUAL_USER_UPDATES': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.disable_manual_user_updates is True
    
    def test_disable_group_updates(self):
        """Test TIMECAMP_DISABLE_GROUP_UPDATES configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLE_GROUP_UPDATES': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.disable_group_updates is True
    
    def test_disable_role_updates(self):
        """Test TIMECAMP_DISABLE_ROLE_UPDATES configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLE_ROLE_UPDATES': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.disable_role_updates is True
    
    def test_disable_groups_creation(self):
        """Test TIMECAMP_DISABLE_GROUPS_CREATION configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLE_GROUPS_CREATION': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.disable_groups_creation is True
    
    def test_all_disable_flags_together(self):
        """Test all disable flags enabled together."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLE_NEW_USERS': 'true',
            'TIMECAMP_DISABLE_EXTERNAL_ID_SYNC': 'true',
            'TIMECAMP_DISABLE_ADDITIONAL_EMAIL_SYNC': 'true',
            'TIMECAMP_DISABLE_MANUAL_USER_UPDATES': 'true',
            'TIMECAMP_DISABLE_GROUP_UPDATES': 'true',
            'TIMECAMP_DISABLE_ROLE_UPDATES': 'true',
            'TIMECAMP_DISABLE_GROUPS_CREATION': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.disable_new_users is True
                assert config.disable_external_id_sync is True
                assert config.disable_additional_email_sync is True
                assert config.disable_manual_user_updates is True
                assert config.disable_group_updates is True
                assert config.disable_role_updates is True
                assert config.disable_groups_creation is True


class TestTimeCampRoleConfigs:
    """Test TimeCamp role determination configurations."""
    
    def test_use_is_supervisor_role(self):
        """Test TIMECAMP_USE_IS_SUPERVISOR_ROLE configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_IS_SUPERVISOR_ROLE': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.use_is_supervisor_role is True


class TestTimeCampIgnoredUsersConfigs:
    """Test TimeCamp ignored users configuration."""
    
    def test_ignored_user_ids_single(self):
        """Test TIMECAMP_IGNORED_USER_IDS with single ID."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_IGNORED_USER_IDS': '123'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert 123 in config.ignored_user_ids
                assert len(config.ignored_user_ids) == 1
    
    def test_ignored_user_ids_multiple(self):
        """Test TIMECAMP_IGNORED_USER_IDS with multiple IDs."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_IGNORED_USER_IDS': '123,456,789'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert 123 in config.ignored_user_ids
                assert 456 in config.ignored_user_ids
                assert 789 in config.ignored_user_ids
                assert len(config.ignored_user_ids) == 3
    
    def test_ignored_user_ids_with_spaces(self):
        """Test TIMECAMP_IGNORED_USER_IDS with spaces."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_IGNORED_USER_IDS': '123, 456 ,  789  '
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert 123 in config.ignored_user_ids
                assert 456 in config.ignored_user_ids
                assert 789 in config.ignored_user_ids


class TestTimeCampDisabledUsersGroupConfig:
    """Test TimeCamp disabled users group configuration."""
    
    def test_disabled_users_group_id_set(self):
        """Test TIMECAMP_DISABLED_USERS_GROUP_ID with value."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLED_USERS_GROUP_ID': '999'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.disabled_users_group_id == 999
    
    def test_disabled_users_group_id_zero(self):
        """Test TIMECAMP_DISABLED_USERS_GROUP_ID=0 (disabled)."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLED_USERS_GROUP_ID': '0'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.disabled_users_group_id == 0


class TestTimeCampDomainConfig:
    """Test TimeCamp domain configuration."""
    
    def test_custom_domain(self):
        """Test custom TIMECAMP_DOMAIN."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DOMAIN': 'custom.timecamp.com'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.domain == 'custom.timecamp.com'
    
    def test_default_domain(self):
        """Test default TIMECAMP_DOMAIN when not set."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.domain == 'app.timecamp.com'


class TestTimeCampSslConfig:
    """Test TimeCamp SSL configuration."""
    
    def test_ssl_verify_default(self):
        """Test default TIMECAMP_SSL_VERIFY (should be true)."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.ssl_verify is True
    
    def test_ssl_verify_false(self):
        """Test TIMECAMP_SSL_VERIFY=false."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_SSL_VERIFY': 'false'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.ssl_verify is False
    
    def test_ssl_verify_true(self):
        """Test TIMECAMP_SSL_VERIFY=true."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_SSL_VERIFY': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                assert config.ssl_verify is True


class TestConfigurationCombinations:
    """Test realistic configuration combinations."""
    
    def test_ldap_basic_sync_config(self):
        """Test basic LDAP sync configuration."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'true',
            'TIMECAMP_USE_SUPERVISOR_GROUPS': 'false',
            'TIMECAMP_DISABLE_ADDITIONAL_EMAIL_SYNC': 'true'  # Common with LDAP
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.use_department_groups is True
                assert config.use_supervisor_groups is False
                assert config.disable_additional_email_sync is True
    
    def test_ldap_ou_structure_config(self):
        """Test LDAP with OU structure as departments."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'true',
            'TIMECAMP_SKIP_DEPARTMENTS': 'OU=Users,DC=company'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.use_department_groups is True
                assert config.skip_departments == 'OU=Users,DC=company'
    
    def test_supervisor_hierarchy_with_job_titles(self):
        """Test supervisor hierarchy with job titles in names."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_SUPERVISOR_GROUPS': 'true',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'false',
            'TIMECAMP_USE_JOB_TITLE_NAME_USERS': 'true',
            'TIMECAMP_USE_JOB_TITLE_NAME_GROUPS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.use_supervisor_groups is True
                assert config.use_department_groups is False
                assert config.use_job_title_name_users is True
                assert config.use_job_title_name_groups is True
    
    def test_read_only_sync_config(self):
        """Test configuration for read-only sync (updates only)."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLE_NEW_USERS': 'true',
            'TIMECAMP_DISABLE_GROUPS_CREATION': 'true',
            'TIMECAMP_DISABLE_GROUP_UPDATES': 'true',
            'TIMECAMP_DISABLE_ROLE_UPDATES': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.disable_new_users is True
                assert config.disable_groups_creation is True
                assert config.disable_group_updates is True
                assert config.disable_role_updates is True
    
    def test_hybrid_mode_with_skip_departments(self):
        """Test hybrid mode with department prefix skipping."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_USE_SUPERVISOR_GROUPS': 'true',
            'TIMECAMP_USE_DEPARTMENT_GROUPS': 'true',
            'TIMECAMP_SKIP_DEPARTMENTS': 'Company/Organization',
            'TIMECAMP_USE_JOB_TITLE_NAME_GROUPS': 'true'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.use_supervisor_groups is True
                assert config.use_department_groups is True
                assert config.skip_departments == 'Company/Organization'
                assert config.use_job_title_name_groups is True
    
    def test_email_domain_replacement_config(self):
        """Test configuration with email domain replacement."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_REPLACE_EMAIL_DOMAIN': '@test-timecamp.com',
            'TIMECAMP_DISABLE_ADDITIONAL_EMAIL_SYNC': 'false'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.replace_email_domain == '@test-timecamp.com'
                assert config.disable_additional_email_sync is False
    
    def test_preserve_manual_changes_config(self):
        """Test configuration to preserve manual TimeCamp changes."""
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100',
            'TIMECAMP_DISABLE_MANUAL_USER_UPDATES': 'true',
            'TIMECAMP_IGNORED_USER_IDS': '1,2,3'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.disable_manual_user_updates is True
                assert 1 in config.ignored_user_ids
                assert 2 in config.ignored_user_ids
                assert 3 in config.ignored_user_ids

