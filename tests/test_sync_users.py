"""
Tests for TimeCamp user synchronization functionality.
"""
import pytest
from unittest.mock import MagicMock, Mock, patch, call
from timecamp_sync_users import TimeCampSynchronizer


class TestTimeCampSynchronizer:
    """Tests for the TimeCampSynchronizer class."""
    
    def test_build_group_paths_flat_structure(self, mock_timecamp_api, mock_timecamp_config):
        """Test building group paths from flat group list."""
        groups = [
            {'group_id': '100', 'name': 'Root', 'parent_id': '0'},
            {'group_id': '101', 'name': 'Engineering', 'parent_id': '100'},
            {'group_id': '102', 'name': 'Team A', 'parent_id': '101'}
        ]
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        path_map = sync._build_group_paths(groups)
        
        assert 'Root' in path_map
        assert 'Root/Engineering' in path_map
        assert 'Root/Engineering/Team A' in path_map
        assert path_map['Root/Engineering/Team A']['group_id'] == '102'
    
    def test_build_group_paths_with_whitespace(self, mock_timecamp_api, mock_timecamp_config):
        """Test that group names are properly trimmed."""
        groups = [
            {'group_id': '100', 'name': '  Root  ', 'parent_id': '0'},
            {'group_id': '101', 'name': ' Engineering ', 'parent_id': '100'}
        ]
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        path_map = sync._build_group_paths(groups)
        
        assert 'Root' in path_map
        assert 'Root/Engineering' in path_map
    
    def test_get_required_groups_active_users_only(self, mock_timecamp_api, mock_timecamp_config):
        """Test that only active users' groups are considered required."""
        timecamp_users = [
            {
                'timecamp_email': 'active@test.com',
                'timecamp_status': 'active',
                'timecamp_groups_breadcrumb': 'Engineering/Team A'
            },
            {
                'timecamp_email': 'inactive@test.com',
                'timecamp_status': 'inactive',
                'timecamp_groups_breadcrumb': 'Sales/Team B'
            }
        ]
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        required_groups = sync._get_required_groups(timecamp_users)
        
        assert 'Engineering/Team A' in required_groups
        assert 'Engineering' in required_groups  # Parent path
        assert 'Sales/Team B' not in required_groups  # Inactive user's group
    
    def test_get_required_groups_includes_parent_paths(self, mock_timecamp_api, mock_timecamp_config):
        """Test that parent paths are included in required groups."""
        timecamp_users = [
            {
                'timecamp_email': 'user@test.com',
                'timecamp_status': 'active',
                'timecamp_groups_breadcrumb': 'A/B/C/D'
            }
        ]
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        required_groups = sync._get_required_groups(timecamp_users)
        
        assert 'A' in required_groups
        assert 'A/B' in required_groups
        assert 'A/B/C' in required_groups
        assert 'A/B/C/D' in required_groups
    
    def test_sync_groups_creates_missing_groups(self, mock_timecamp_api, mock_timecamp_config):
        """Test that missing groups are created."""
        mock_timecamp_config.root_group_id = 100
        mock_timecamp_api.get_groups.return_value = []
        mock_timecamp_api.add_group.return_value = '101'
        
        required_groups = {'Engineering'}
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        group_structure = sync._sync_groups(required_groups, dry_run=False)
        
        mock_timecamp_api.add_group.assert_called_once_with('Engineering', 100)
        assert 'Engineering' in group_structure
    
    def test_sync_groups_dry_run_no_api_calls(self, mock_timecamp_api, mock_timecamp_config):
        """Test that dry run doesn't make API calls."""
        mock_timecamp_config.root_group_id = 100
        mock_timecamp_api.get_groups.return_value = []
        
        required_groups = {'NewGroup'}
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._sync_groups(required_groups, dry_run=True)
        
        mock_timecamp_api.add_group.assert_not_called()
    
    def test_sync_groups_respects_disable_groups_creation(self, mock_timecamp_api, mock_timecamp_config):
        """Test that groups are not created when disable_groups_creation is True."""
        mock_timecamp_config.disable_groups_creation = True
        mock_timecamp_config.root_group_id = 100
        mock_timecamp_api.get_groups.return_value = []
        
        required_groups = {'NewGroup'}
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._sync_groups(required_groups, dry_run=False)
        
        mock_timecamp_api.add_group.assert_not_called()
    
    def test_create_new_user(self, mock_timecamp_api, mock_timecamp_config):
        """Test creating a new user."""
        tc_user_data = {
            'timecamp_email': 'newuser@test.com',
            'timecamp_user_name': 'New User',
            'timecamp_role': 'user',
            'timecamp_real_email': 'real@test.com',
            'timecamp_external_id': 'ext-123'
        }
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._create_new_user(tc_user_data, 101, 'Engineering', dry_run=False)
        
        mock_timecamp_api.add_user.assert_called_once_with(
            'newuser@test.com',
            'New User',
            101
        )
        assert len(sync.newly_created_users) == 1
        assert sync.newly_created_users[0]['email'] == 'newuser@test.com'
    
    def test_create_new_user_dry_run(self, mock_timecamp_api, mock_timecamp_config):
        """Test that dry run doesn't create users."""
        tc_user_data = {
            'timecamp_email': 'newuser@test.com',
            'timecamp_user_name': 'New User',
            'timecamp_role': 'user'
        }
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._create_new_user(tc_user_data, 101, 'Engineering', dry_run=True)
        
        mock_timecamp_api.add_user.assert_not_called()
    
    def test_update_existing_user_name_change(self, mock_timecamp_api, mock_timecamp_config):
        """Test updating user name."""
        existing_user = {
            'user_id': '1001',
            'email': 'user@test.com',
            'display_name': 'Old Name',
            'group_id': '100',
            'is_enabled': True
        }
        
        tc_user_data = {
            'timecamp_email': 'user@test.com',
            'timecamp_user_name': 'New Name',
            'timecamp_role': 'user',
            'timecamp_status': 'active'
        }
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._update_existing_user(
            existing_user, tc_user_data, 100, 'root',
            {}, {}, {}, {}, dry_run=False
        )
        
        # Should update user with new name
        mock_timecamp_api.update_user.assert_called()
        call_args = mock_timecamp_api.update_user.call_args[0]
        assert call_args[0] == 1001
        assert 'fullName' in call_args[1]
        assert call_args[1]['fullName'] == 'New Name'
    
    def test_update_existing_user_group_change(self, mock_timecamp_api, mock_timecamp_config):
        """Test updating user group."""
        existing_user = {
            'user_id': '1001',
            'email': 'user@test.com',
            'display_name': 'User Name',
            'group_id': '100',
            'is_enabled': True
        }
        
        tc_user_data = {
            'timecamp_email': 'user@test.com',
            'timecamp_user_name': 'User Name',
            'timecamp_role': 'user',
            'timecamp_status': 'active'
        }
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._update_existing_user(
            existing_user, tc_user_data, 101, 'Engineering',
            {}, {}, {}, {}, dry_run=False
        )
        
        # Should update group
        call_args = mock_timecamp_api.update_user.call_args[0]
        assert 'groupId' in call_args[1]
        assert call_args[1]['groupId'] == 101
    
    def test_update_existing_user_respects_disable_group_updates(self, mock_timecamp_api, mock_timecamp_config):
        """Test that group updates are skipped when disabled."""
        mock_timecamp_config.disable_group_updates = True
        
        existing_user = {
            'user_id': '1001',
            'email': 'user@test.com',
            'display_name': 'User Name',
            'group_id': '100',
            'is_enabled': True
        }
        
        tc_user_data = {
            'timecamp_email': 'user@test.com',
            'timecamp_user_name': 'User Name',
            'timecamp_role': 'user',
            'timecamp_status': 'active'
        }
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._update_existing_user(
            existing_user, tc_user_data, 101, 'Engineering',
            {}, {}, {}, {}, dry_run=False
        )
        
        # Should not update if only difference is group
        if mock_timecamp_api.update_user.called:
            call_args = mock_timecamp_api.update_user.call_args[0]
            assert 'groupId' not in call_args[1]
    
    def test_update_existing_user_skips_ignored_users(self, mock_timecamp_api, mock_timecamp_config):
        """Test that ignored users are skipped."""
        mock_timecamp_config.ignored_user_ids = {1001}
        
        existing_user = {
            'user_id': '1001',
            'email': 'ignored@test.com',
            'display_name': 'Old Name',
            'group_id': '100',
            'is_enabled': True
        }
        
        tc_user_data = {
            'timecamp_email': 'ignored@test.com',
            'timecamp_user_name': 'New Name',
            'timecamp_role': 'user',
            'timecamp_status': 'active'
        }
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._update_existing_user(
            existing_user, tc_user_data, 100, 'root',
            {}, {}, {}, {}, dry_run=False
        )
        
        mock_timecamp_api.update_user.assert_not_called()
    
    def test_update_existing_user_skips_manually_added(self, mock_timecamp_api, mock_timecamp_config):
        """Test that manually added users are skipped when configured."""
        mock_timecamp_config.disable_manual_user_updates = True
        
        existing_user = {
            'user_id': '1001',
            'email': 'manual@test.com',
            'display_name': 'Old Name',
            'group_id': '100',
            'is_enabled': True
        }
        
        tc_user_data = {
            'timecamp_email': 'manual@test.com',
            'timecamp_user_name': 'New Name',
            'timecamp_role': 'user',
            'timecamp_status': 'active'
        }
        
        manually_added = {1001: True}
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._update_existing_user(
            existing_user, tc_user_data, 100, 'root',
            {}, {}, manually_added, {}, dry_run=False
        )
        
        mock_timecamp_api.update_user.assert_not_called()
    
    def test_update_existing_user_re_enable_disabled(self, mock_timecamp_api, mock_timecamp_config):
        """Test re-enabling a disabled user."""
        existing_user = {
            'user_id': '1001',
            'email': 'disabled@test.com',
            'display_name': 'User Name',
            'group_id': '100',
            'is_enabled': False
        }
        
        tc_user_data = {
            'timecamp_email': 'disabled@test.com',
            'timecamp_user_name': 'User Name',
            'timecamp_role': 'user',
            'timecamp_status': 'active'
        }
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._update_existing_user(
            existing_user, tc_user_data, 100, 'root',
            {}, {}, {}, {}, dry_run=False
        )
        
        # Should re-enable user
        mock_timecamp_api.update_user_setting.assert_any_call(1001, 'disabled_user', '0')
        mock_timecamp_api.update_user_setting.assert_any_call(1001, 'added_manually', '0')
    
    def test_handle_deactivations_user_not_in_source(self, mock_timecamp_api, mock_timecamp_config):
        """Test deactivating users not in source data."""
        timecamp_users = [
            {
                'timecamp_email': 'active@test.com',
                'timecamp_status': 'active'
            }
        ]
        
        tc_users_by_email = {
            'active@test.com': {
                'user_id': '1001',
                'email': 'active@test.com',
                'is_enabled': True
            },
            'missing@test.com': {
                'user_id': '1002',
                'email': 'missing@test.com',
                'is_enabled': True,
                'group_id': '100'
            }
        }
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._handle_deactivations(
            timecamp_users, tc_users_by_email, {},
            {1001}, {}, dry_run=False
        )
        
        # Should deactivate missing user
        mock_timecamp_api.update_user_setting.assert_called_with(1002, 'disabled_user', '1')
    
    def test_handle_deactivations_user_marked_inactive(self, mock_timecamp_api, mock_timecamp_config):
        """Test deactivating users marked as inactive."""
        timecamp_users = [
            {
                'timecamp_email': 'inactive@test.com',
                'timecamp_status': 'inactive'
            }
        ]
        
        tc_users_by_email = {
            'inactive@test.com': {
                'user_id': '1001',
                'email': 'inactive@test.com',
                'is_enabled': True,
                'group_id': '100'
            }
        }
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._handle_deactivations(
            timecamp_users, tc_users_by_email, {},
            set(), {}, dry_run=False
        )
        
        # Should deactivate user marked as inactive
        mock_timecamp_api.update_user_setting.assert_called_with(1001, 'disabled_user', '1')
    
    def test_handle_deactivations_move_to_disabled_group(self, mock_timecamp_api, mock_timecamp_config):
        """Test moving deactivated users to disabled group."""
        mock_timecamp_config.disabled_users_group_id = 999
        
        timecamp_users = []
        tc_users_by_email = {
            'deactivated@test.com': {
                'user_id': '1001',
                'email': 'deactivated@test.com',
                'is_enabled': True,
                'group_id': '100'
            }
        }
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._handle_deactivations(
            timecamp_users, tc_users_by_email, {},
            set(), {}, dry_run=False
        )
        
        # Should move to disabled group
        mock_timecamp_api.update_user.assert_called_with(
            1001, {'groupId': 999}, '100'
        )
    
    def test_finalize_new_users_sets_role(self, mock_timecamp_api, mock_timecamp_config):
        """Test finalizing newly created users with role."""
        mock_timecamp_api.get_users.return_value = [
            {
                'user_id': '1004',
                'email': 'newuser@test.com',
                'display_name': 'New User',
                'group_id': '101',
                'is_enabled': True
            }
        ]
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync.newly_created_users = [
            {
                'email': 'newuser@test.com',
                'name': 'New User',
                'group_id': 101,
                'role': 'supervisor',
                'real_email': None,
                'external_id': None
            }
        ]
        
        sync._finalize_new_users()
        
        # Should set added_manually to 0
        mock_timecamp_api.update_user_setting.assert_any_call(1004, 'added_manually', '0')
        
        # Should set supervisor role (role_id=2)
        mock_timecamp_api.update_user.assert_called()
        call_args = mock_timecamp_api.update_user.call_args[0]
        assert call_args[1]['role_id'] == '2'
    
    def test_finalize_new_users_sets_additional_email(self, mock_timecamp_api, mock_timecamp_config):
        """Test setting additional email for new users."""
        mock_timecamp_api.get_users.return_value = [
            {
                'user_id': '1004',
                'email': 'federated@test.com',
                'display_name': 'New User',
                'group_id': '101',
                'is_enabled': True
            }
        ]
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync.newly_created_users = [
            {
                'email': 'federated@test.com',
                'name': 'New User',
                'group_id': 101,
                'role': 'user',
                'real_email': 'real@test.com',
                'external_id': 'ext-123'
            }
        ]
        
        sync._finalize_new_users()
        
        # Should set additional email
        mock_timecamp_api.set_additional_email.assert_called_with(1004, 'real@test.com')
        
        # Should set external ID
        mock_timecamp_api.update_user_setting.assert_any_call(1004, 'external_id', 'ext-123')
    
    def test_sync_integration(self, mock_timecamp_api, mock_timecamp_config, sample_timecamp_users):
        """Test the main sync method integration."""
        mock_timecamp_config.root_group_id = 100
        mock_timecamp_api.get_groups.return_value = [
            {'group_id': '100', 'name': 'Root', 'parent_id': '0'}
        ]
        mock_timecamp_api.get_users.return_value = []
        mock_timecamp_api.add_group.return_value = '101'
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync.sync(sample_timecamp_users, dry_run=False)
        
        # Should have called the API
        assert mock_timecamp_api.get_groups.called
        assert mock_timecamp_api.get_users.called

