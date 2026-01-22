"""
Tests for common utility functions.
"""
import pytest
import os
from common.utils import (
    TimeCampConfig,
    clean_name,
    clean_department_path,
    get_users_file,
)


class TestTimeCampConfig:
    """Tests for TimeCampConfig class."""
    
    def test_from_env_with_all_settings(self, mock_env_vars):
        """Test loading configuration from environment variables."""
        config = TimeCampConfig.from_env()
        
        assert config.api_key == "test_api_key"
        assert config.domain == "app.timecamp.com"
        assert config.root_group_id == 100
        assert 9999 in config.ignored_user_ids
        assert config.show_external_id is False
        assert config.use_supervisor_groups is False
        assert config.use_department_groups is True
        assert config.prepare_transform_config == ""
    
    def test_from_env_missing_api_key(self):
        """Test that missing API key raises error."""
        import os
        from unittest.mock import patch
        
        # Mock environment with only ROOT_GROUP_ID
        env = {'TIMECAMP_ROOT_GROUP_ID': '100'}
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(ValueError, match="Missing TIMECAMP_API_KEY"):
                    TimeCampConfig.from_env()
    
    def test_from_env_missing_root_group_id(self):
        """Test that missing root group ID raises error."""
        import os
        from unittest.mock import patch
        
        # Mock environment with only API_KEY
        env = {'TIMECAMP_API_KEY': 'test_key'}
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(ValueError, match="Missing TIMECAMP_ROOT_GROUP_ID"):
                    TimeCampConfig.from_env()
    
    def test_from_env_default_values(self):
        """Test default values for optional settings."""
        import os
        from unittest.mock import patch
        
        # Mock minimal environment
        env = {
            'TIMECAMP_API_KEY': 'test_key',
            'TIMECAMP_ROOT_GROUP_ID': '100'
        }
        
        with patch('common.utils.load_dotenv'):
            with patch.dict(os.environ, env, clear=True):
                config = TimeCampConfig.from_env()
                
                assert config.domain == 'app.timecamp.com'
                assert config.ignored_user_ids == set()
                assert config.show_external_id is False
                assert config.skip_departments == ''
                assert config.use_supervisor_groups is False
                assert config.use_department_groups is True
                assert config.disable_new_users is False
                assert config.disable_user_deactivation is False
                assert config.prepare_transform_config == ''
    
    def test_from_env_boolean_parsing(self, monkeypatch):
        """Test parsing of boolean environment variables."""
        monkeypatch.setenv('TIMECAMP_API_KEY', 'test_key')
        monkeypatch.setenv('TIMECAMP_ROOT_GROUP_ID', '100')
        monkeypatch.setenv('TIMECAMP_SHOW_EXTERNAL_ID', 'true')
        monkeypatch.setenv('TIMECAMP_USE_SUPERVISOR_GROUPS', 'TRUE')
        monkeypatch.setenv('TIMECAMP_DISABLE_NEW_USERS', 'True')
        monkeypatch.setenv('TIMECAMP_USE_DEPARTMENT_GROUPS', 'false')
        
        config = TimeCampConfig.from_env()
        
        assert config.show_external_id is True
        assert config.use_supervisor_groups is True
        assert config.disable_new_users is True
        assert config.use_department_groups is False
    
    def test_from_env_ignored_user_ids_parsing(self, monkeypatch):
        """Test parsing of ignored user IDs."""
        monkeypatch.setenv('TIMECAMP_API_KEY', 'test_key')
        monkeypatch.setenv('TIMECAMP_ROOT_GROUP_ID', '100')
        monkeypatch.setenv('TIMECAMP_IGNORED_USER_IDS', '1001, 1002,1003,  ')
        
        config = TimeCampConfig.from_env()
        
        assert 1001 in config.ignored_user_ids
        assert 1002 in config.ignored_user_ids
        assert 1003 in config.ignored_user_ids
        assert len(config.ignored_user_ids) == 3
    
    def test_from_env_empty_ignored_user_ids(self, monkeypatch):
        """Test empty ignored user IDs."""
        monkeypatch.setenv('TIMECAMP_API_KEY', 'test_key')
        monkeypatch.setenv('TIMECAMP_ROOT_GROUP_ID', '100')
        monkeypatch.setenv('TIMECAMP_IGNORED_USER_IDS', '')
        
        config = TimeCampConfig.from_env()
        
        assert config.ignored_user_ids == set()


class TestCleanName:
    """Tests for clean_name function."""
    
    def test_clean_name_basic(self):
        """Test cleaning basic name."""
        result = clean_name("John Doe")
        assert result == "John Doe"
    
    def test_clean_name_with_special_characters(self):
        """Test removing special characters."""
        result = clean_name("Name (with) {brackets} and `backticks`")
        assert "(" not in result
        assert ")" not in result
        assert "{" not in result
        assert "}" not in result
        assert "`" not in result
    
    def test_clean_name_with_underscore(self):
        """Test that underscores are removed."""
        result = clean_name("Name_With_Underscore")
        assert "_" not in result
    
    def test_clean_name_with_quotes(self):
        """Test removing various quote characters."""
        result = clean_name('Name "with" "quotes"')
        # Note: Regular quotes (") are not removed by clean_name
        # Only special quote characters ("" ) are removed
        assert result == 'Name "with" "quotes"'
    
    def test_clean_name_empty_string(self):
        """Test cleaning empty string."""
        result = clean_name("")
        assert result == ""
    
    def test_clean_name_none(self):
        """Test cleaning None."""
        result = clean_name(None)
        assert result == ""
    
    def test_clean_name_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        result = clean_name("  Name with spaces  ")
        assert result == "Name with spaces"
    
    def test_clean_name_preserves_polish_characters(self):
        """Test that Polish characters are preserved."""
        result = clean_name("Łukasz Żółć")
        assert result == "Łukasz Żółć"


class TestCleanDepartmentPath:
    """Tests for clean_department_path function."""
    
    def test_clean_department_basic(self):
        """Test basic department path cleaning."""
        result = clean_department_path("Engineering/Team A")
        assert result == "Engineering/Team A"
    
    def test_clean_department_with_whitespace(self):
        """Test trimming whitespace from path components."""
        result = clean_department_path("  Engineering  /  Team A  ")
        assert result == "Engineering/Team A"
    
    def test_clean_department_empty_string(self):
        """Test empty department path."""
        result = clean_department_path("")
        assert result == ""
    
    def test_clean_department_none(self):
        """Test None department path."""
        result = clean_department_path(None)
        assert result == ""
    
    def test_clean_department_skip_exact_match(self, mock_timecamp_config):
        """Test skipping exact department match."""
        mock_timecamp_config.skip_departments = "Company"
        
        result = clean_department_path("Company", mock_timecamp_config)
        assert result == ""
    
    def test_clean_department_skip_prefix(self, mock_timecamp_config):
        """Test skipping department prefix."""
        mock_timecamp_config.skip_departments = "Company"
        
        result = clean_department_path("Company/Engineering/Team A", mock_timecamp_config)
        assert result == "Engineering/Team A"
    
    def test_clean_department_skip_multiple_levels(self, mock_timecamp_config):
        """Test skipping multiple level prefix."""
        mock_timecamp_config.skip_departments = "Company/Division"
        
        result = clean_department_path("Company/Division/Engineering", mock_timecamp_config)
        assert result == "Engineering"
    
    def test_clean_department_skip_first_match_only(self, mock_timecamp_config):
        """Test that only first matching prefix is skipped."""
        mock_timecamp_config.skip_departments = "Org1,Org2"
        
        result = clean_department_path("Org1/Engineering", mock_timecamp_config)
        assert result == "Engineering"
        
        result = clean_department_path("Org2/Sales", mock_timecamp_config)
        assert result == "Sales"
    
    def test_clean_department_no_config(self):
        """Test cleaning without config."""
        result = clean_department_path("Company/Engineering")
        assert result == "Company/Engineering"
    
    def test_clean_department_skip_not_matching(self, mock_timecamp_config):
        """Test path where skip prefix doesn't match."""
        mock_timecamp_config.skip_departments = "OtherCompany"
        
        result = clean_department_path("Company/Engineering", mock_timecamp_config)
        assert result == "Company/Engineering"
    
    def test_clean_department_partial_component_no_match(self, mock_timecamp_config):
        """Test that partial component matches don't count."""
        mock_timecamp_config.skip_departments = "Eng"
        
        result = clean_department_path("Engineering/Team A", mock_timecamp_config)
        # "Eng" doesn't match "Engineering" as a full component
        assert result == "Engineering/Team A"
    
    def test_clean_department_empty_components_removed(self):
        """Test that empty path components are removed."""
        result = clean_department_path("Engineering//Team A/")
        assert result == "Engineering/Team A"


class TestGetUsersFile:
    """Tests for get_users_file function."""
    
    def test_get_users_file_exists(self, tmp_path, monkeypatch):
        """Test getting users file when it exists."""
        from unittest.mock import patch
        
        # Create a mock users.json file
        var_dir = tmp_path / "var"
        var_dir.mkdir()
        users_file = var_dir / "users.json"
        users_file.write_text('{"users": []}')
        
        # Change working directory to tmp_path
        monkeypatch.chdir(tmp_path)
        
        # Mock storage.file_exists to return True
        with patch('common.storage.file_exists', return_value=True):
            result = get_users_file()
            assert result == "var/users.json"
    
    def test_get_users_file_not_exists(self):
        """Test that missing users file raises error."""
        from unittest.mock import patch
        
        with patch('common.storage.file_exists', return_value=False):
            with pytest.raises(FileNotFoundError, match="var/users.json file not found"):
                get_users_file()


class TestIntegration:
    """Integration tests for utility functions."""
    
    def test_config_and_clean_department_integration(self, mock_env_vars):
        """Test integration of config loading and department cleaning."""
        config = TimeCampConfig.from_env()
        
        # Test with skip_departments set
        config.skip_departments = "Company"
        result = clean_department_path("Company/Engineering/Team A", config)
        
        assert result == "Engineering/Team A"
    
    def test_clean_name_in_department_context(self):
        """Test clean_name used with department names."""
        dept = "Engineering (Main)"
        cleaned = clean_name(dept)
        
        # Parentheses should be removed
        assert "(" not in cleaned
        assert ")" not in cleaned
        assert "Engineering Main" in cleaned

