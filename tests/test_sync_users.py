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
            {}, {}, {}, {}, False, dry_run=False
        )
        
        # Should update user with new name
        mock_timecamp_api.update_user.assert_called()
        call_args = mock_timecamp_api.update_user.call_args[0]
        assert call_args[0] == 1001
        assert 'fullName' in call_args[1]
        assert call_args[1]['fullName'] == 'New Name'

    def test_sync_users_updates_email_when_matched_by_external_id(self, mock_timecamp_api, mock_timecamp_config):
        """Test updating email when matched by external ID and enabled."""
        mock_timecamp_config.update_email_on_external_id = True
        
        mock_timecamp_api.get_users.return_value = [
            {
                'user_id': '1001',
                'email': 'old@test.com',
                'display_name': 'User Name',
                'group_id': '100',
                'is_enabled': True
            }
        ]
        mock_timecamp_api.get_user_settings_bulk.return_value = {
            'additional_email': {},
            'external_id': {1001: 'ext-123'},
            'added_manually': {},
            'disabled_user': {}
        }
        mock_timecamp_api.get_user_roles.return_value = {}
        
        timecamp_users = [
            {
                'timecamp_email': 'new@test.com',
                'timecamp_user_name': 'User Name',
                'timecamp_role': 'user',
                'timecamp_status': 'active',
                'timecamp_external_id': 'ext-123'
            }
        ]
        
        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._sync_users(timecamp_users, group_structure={}, dry_run=False)
        
        call_args = mock_timecamp_api.update_user.call_args[0]
        assert call_args[0] == 1001
        assert call_args[1]['email'] == 'new@test.com'
    
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
            {}, {}, {}, {}, False, dry_run=False
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
            {}, {}, {}, {}, False, dry_run=False
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
            {}, {}, {}, {}, False, dry_run=False
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
            {}, {}, manually_added, {}, False, dry_run=False
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
            {}, {}, {}, {}, False, dry_run=False
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
        
        # Should deactivate missing user and reset added_manually
        mock_timecamp_api.update_user_setting.assert_any_call(1002, 'disabled_user', '1')
        mock_timecamp_api.update_user_setting.assert_any_call(1002, 'added_manually', '0')
    
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
        
        # Should deactivate user marked as inactive and reset added_manually
        mock_timecamp_api.update_user_setting.assert_any_call(1001, 'disabled_user', '1')
        mock_timecamp_api.update_user_setting.assert_any_call(1001, 'added_manually', '0')
    
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

        # Should move to disabled group and reset added_manually
        mock_timecamp_api.update_user.assert_called_with(
            1001, {'groupId': 999}, '100'
        )
        mock_timecamp_api.update_user_setting.assert_any_call(1001, 'added_manually', '0')

    def test_handle_deactivations_moves_already_disabled_user(self, mock_timecamp_api, mock_timecamp_config):
        """Test moving already disabled users to disabled group regardless of added_manually."""
        mock_timecamp_config.disabled_users_group_id = 999
        mock_timecamp_config.disable_manual_user_updates = True

        timecamp_users = []
        tc_users_by_email = {
            'disabled@test.com': {
                'user_id': '1001',
                'email': 'disabled@test.com',
                'is_enabled': False,
                'group_id': '100'
            }
        }

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._handle_deactivations(
            timecamp_users, tc_users_by_email, {},
            set(), {1001: True}, dry_run=False
        )

        mock_timecamp_api.update_user.assert_called_with(
            1001, {'groupId': 999}, '100'
        )
        mock_timecamp_api.update_user_setting.assert_any_call(1001, 'added_manually', '0')

    def test_handle_deactivations_skips_move_when_already_in_disabled_group(self, mock_timecamp_api, mock_timecamp_config):
        """Test skipping move when user is already in disabled group."""
        mock_timecamp_config.disabled_users_group_id = 999

        timecamp_users = []
        tc_users_by_email = {
            'disabled@test.com': {
                'user_id': '1001',
                'email': 'disabled@test.com',
                'is_enabled': False,
                'group_id': '999'
            }
        }

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._handle_deactivations(
            timecamp_users, tc_users_by_email, {},
            set(), {}, dry_run=False
        )

        mock_timecamp_api.update_user.assert_not_called()

    def test_handle_deactivations_disable_user_deactivation_moves_only(self, mock_timecamp_api, mock_timecamp_config):
        """Test skipping deactivation but moving when disable_user_deactivation is enabled."""
        mock_timecamp_config.disable_user_deactivation = True
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

        mock_timecamp_api.update_user.assert_called_with(
            1001, {'groupId': 999}, '100'
        )
        # Should NOT set disabled_user, but SHOULD set added_manually=0
        disabled_calls = [c for c in mock_timecamp_api.update_user_setting.call_args_list
                         if c == call(1001, 'disabled_user', '1')]
        assert len(disabled_calls) == 0
        mock_timecamp_api.update_user_setting.assert_any_call(1001, 'added_manually', '0')
    
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
    
    def test_finalize_new_users_sets_added_manually_with_no_optional_settings(self, mock_timecamp_api, mock_timecamp_config):
        """Test that added_manually=0 is set even when no optional settings (role/email/external_id) apply."""
        mock_timecamp_api.get_users.return_value = [
            {
                'user_id': '1004',
                'email': 'plain@test.com',
                'display_name': 'Plain User',
                'group_id': '101',
                'is_enabled': True
            }
        ]

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync.newly_created_users = [
            {
                'email': 'plain@test.com',
                'name': 'Plain User',
                'group_id': 101,
                'role': 'user',
                'real_email': None,
                'external_id': None
            }
        ]

        sync._finalize_new_users()

        # Should set added_manually=0 even with no optional settings
        mock_timecamp_api.update_user_setting.assert_any_call(1004, 'added_manually', '0')
        # Should NOT have set role, additional email, or external ID
        mock_timecamp_api.update_user.assert_not_called()
        mock_timecamp_api.set_additional_email.assert_not_called()

    def test_finalize_new_users_sets_added_manually_after_all_settings(self, mock_timecamp_api, mock_timecamp_config):
        """Test that added_manually=0 is set after role, additional email, and external ID."""
        mock_timecamp_api.get_users.return_value = [
            {
                'user_id': '1004',
                'email': 'full@test.com',
                'display_name': 'Full User',
                'group_id': '101',
                'is_enabled': True
            }
        ]

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync.newly_created_users = [
            {
                'email': 'full@test.com',
                'name': 'Full User',
                'group_id': 101,
                'role': 'administrator',
                'real_email': 'real@test.com',
                'external_id': 'ext-456'
            }
        ]

        sync._finalize_new_users()

        # Verify added_manually=0 is the last update_user_setting call
        setting_calls = mock_timecamp_api.update_user_setting.call_args_list
        last_call = setting_calls[-1]
        assert last_call == call(1004, 'added_manually', '0')

        # Verify added_manually=0 was set once (consolidated final call)
        added_manually_calls = [c for c in setting_calls if c == call(1004, 'added_manually', '0')]
        assert len(added_manually_calls) == 1

    @patch('timecamp_sync_users.time.sleep')
    def test_finalize_new_users_retries_on_not_found(self, mock_sleep, mock_timecamp_api, mock_timecamp_config):
        """Test that finalization retries when a newly created user is not found."""
        # First call: user not found. Second call: user found.
        mock_timecamp_api.get_users.side_effect = [
            [],  # attempt 1: empty
            [    # attempt 2: user appears
                {
                    'user_id': '1004',
                    'email': 'delayed@test.com',
                    'display_name': 'Delayed User',
                    'group_id': '101',
                    'is_enabled': True
                }
            ]
        ]

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync.newly_created_users = [
            {
                'email': 'delayed@test.com',
                'name': 'Delayed User',
                'group_id': 101,
                'role': 'user',
                'real_email': None,
                'external_id': None
            }
        ]

        sync._finalize_new_users()

        # Should have fetched users twice
        assert mock_timecamp_api.get_users.call_count == 2
        # Should have slept between retries
        mock_sleep.assert_called_once_with(60)
        # Should have applied settings after finding the user
        mock_timecamp_api.update_user_setting.assert_any_call(1004, 'added_manually', '0')

    @patch('timecamp_sync_users.time.sleep')
    def test_finalize_new_users_gives_up_after_max_retries(self, mock_sleep, mock_timecamp_api, mock_timecamp_config):
        """Test that finalization gives up after max retries for unfound users."""
        # User never appears in any attempt
        mock_timecamp_api.get_users.return_value = []

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync.newly_created_users = [
            {
                'email': 'ghost@test.com',
                'name': 'Ghost User',
                'group_id': 101,
                'role': 'user',
                'real_email': None,
                'external_id': None
            }
        ]

        sync._finalize_new_users()

        # Should have fetched users 3 times (max_retries)
        assert mock_timecamp_api.get_users.call_count == 3
        # Should have slept twice (between attempt 1->2 and 2->3)
        assert mock_sleep.call_count == 2
        # Should NOT have applied any settings
        mock_timecamp_api.update_user_setting.assert_not_called()

    @patch('timecamp_sync_users.time.sleep')
    def test_finalize_new_users_partial_retry(self, mock_sleep, mock_timecamp_api, mock_timecamp_config):
        """Test that only missing users are retried, found users are processed immediately."""
        mock_timecamp_api.get_users.side_effect = [
            [   # attempt 1: only user_a found
                {
                    'user_id': '1001',
                    'email': 'user_a@test.com',
                    'display_name': 'User A',
                    'group_id': '101',
                    'is_enabled': True
                }
            ],
            [   # attempt 2: user_b now found too
                {
                    'user_id': '1001',
                    'email': 'user_a@test.com',
                    'display_name': 'User A',
                    'group_id': '101',
                    'is_enabled': True
                },
                {
                    'user_id': '1002',
                    'email': 'user_b@test.com',
                    'display_name': 'User B',
                    'group_id': '101',
                    'is_enabled': True
                }
            ]
        ]

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync.newly_created_users = [
            {
                'email': 'user_a@test.com',
                'name': 'User A',
                'group_id': 101,
                'role': 'user',
                'real_email': None,
                'external_id': None
            },
            {
                'email': 'user_b@test.com',
                'name': 'User B',
                'group_id': 101,
                'role': 'user',
                'real_email': None,
                'external_id': None
            }
        ]

        sync._finalize_new_users()

        # Both users should have added_manually=0 set
        mock_timecamp_api.update_user_setting.assert_any_call(1001, 'added_manually', '0')
        mock_timecamp_api.update_user_setting.assert_any_call(1002, 'added_manually', '0')
        # Should have retried once
        assert mock_timecamp_api.get_users.call_count == 2
        mock_sleep.assert_called_once_with(60)

    @patch('timecamp_sync_users.time.sleep')
    def test_finalize_new_users_persists_unfound_when_persistent_settings(self, mock_sleep, mock_timecamp_api, mock_timecamp_config):
        """Test that unfound users are saved for next run when persistent_settings is enabled."""
        mock_timecamp_config.persistent_settings = True
        mock_timecamp_api.get_users.return_value = []

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync.newly_created_users = [
            {
                'email': 'ghost@test.com',
                'name': 'Ghost User',
                'group_id': 101,
                'role': 'user',
                'real_email': None,
                'external_id': None
            }
        ]

        with patch('timecamp_sync_users.file_exists', return_value=False), \
             patch('timecamp_sync_users.save_json_file') as mock_save:
            sync._finalize_new_users()

            # Should persist the unfound user
            mock_save.assert_called_once()
            saved_data = mock_save.call_args[0][0]
            assert len(saved_data) == 1
            assert saved_data[0]['email'] == 'ghost@test.com'

    @patch('timecamp_sync_users.time.sleep')
    def test_finalize_new_users_does_not_persist_when_persistent_settings_off(self, mock_sleep, mock_timecamp_api, mock_timecamp_config):
        """Test that unfound users are NOT saved when persistent_settings is disabled."""
        mock_timecamp_config.persistent_settings = False
        mock_timecamp_api.get_users.return_value = []

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync.newly_created_users = [
            {
                'email': 'ghost@test.com',
                'name': 'Ghost User',
                'group_id': 101,
                'role': 'user',
                'real_email': None,
                'external_id': None
            }
        ]

        with patch('timecamp_sync_users.save_json_file') as mock_save:
            sync._finalize_new_users()
            mock_save.assert_not_called()

    def test_process_pending_new_users_applies_settings(self, mock_timecamp_api, mock_timecamp_config):
        """Test that pending new users from previous runs get their settings applied."""
        mock_timecamp_config.persistent_settings = True
        pending_users = [
            {
                'email': 'pending@test.com',
                'name': 'Pending User',
                'group_id': 101,
                'role': 'supervisor',
                'real_email': 'real@test.com',
                'external_id': 'ext-789'
            }
        ]

        mock_timecamp_api.get_users.return_value = [
            {
                'user_id': '2001',
                'email': 'pending@test.com',
                'display_name': 'Pending User',
                'group_id': '101',
                'is_enabled': True
            }
        ]

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)

        with patch('timecamp_sync_users.file_exists', return_value=True), \
             patch('timecamp_sync_users.load_json_file', return_value=pending_users), \
             patch('timecamp_sync_users.save_json_file') as mock_save:
            sync._process_pending_new_users()

            # Should apply settings
            mock_timecamp_api.set_additional_email.assert_called_with(2001, 'real@test.com')
            mock_timecamp_api.update_user_setting.assert_any_call(2001, 'external_id', 'ext-789')
            # Should save empty list (user was processed)
            mock_save.assert_called()
            saved_data = mock_save.call_args[0][0]
            assert len(saved_data) == 0

    def test_process_pending_new_users_keeps_still_missing(self, mock_timecamp_api, mock_timecamp_config):
        """Test that pending users still not found are kept for the next run."""
        mock_timecamp_config.persistent_settings = True
        pending_users = [
            {
                'email': 'still_missing@test.com',
                'name': 'Still Missing',
                'group_id': 101,
                'role': 'user',
                'real_email': None,
                'external_id': None
            }
        ]

        mock_timecamp_api.get_users.return_value = []

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)

        with patch('timecamp_sync_users.file_exists', return_value=True), \
             patch('timecamp_sync_users.load_json_file', return_value=pending_users), \
             patch('timecamp_sync_users.save_json_file') as mock_save:
            sync._process_pending_new_users()

            # Should NOT apply any settings
            mock_timecamp_api.update_user_setting.assert_not_called()
            # Should save user back to pending
            saved_data = mock_save.call_args[0][0]
            assert len(saved_data) == 1
            assert saved_data[0]['email'] == 'still_missing@test.com'

    def test_handle_deactivations_dry_run_does_not_set_added_manually(self, mock_timecamp_api, mock_timecamp_config):
        """Test that dry run doesn't set added_manually=0 during deactivation."""
        timecamp_users = []
        tc_users_by_email = {
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
            set(), {}, dry_run=True
        )

        mock_timecamp_api.update_user_setting.assert_not_called()

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

    def test_remove_empty_groups_deletes_leaf_without_users(self, mock_timecamp_api, mock_timecamp_config):
        """Test that empty leaf groups are removed."""
        mock_timecamp_config.remove_empty_groups = True
        mock_timecamp_config.root_group_id = 100

        mock_timecamp_api.get_groups.return_value = [
            {'group_id': '100', 'name': 'Root', 'parent_id': '0'},
            {'group_id': '101', 'name': 'Empty Group', 'parent_id': '100'},
        ]
        mock_timecamp_api.get_users.return_value = []

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._remove_empty_groups(dry_run=False)

        mock_timecamp_api.delete_group.assert_called_once_with(101)

    def test_remove_empty_groups_keeps_groups_with_users(self, mock_timecamp_api, mock_timecamp_config):
        """Test that groups with users are not removed."""
        mock_timecamp_config.remove_empty_groups = True
        mock_timecamp_config.root_group_id = 100

        mock_timecamp_api.get_groups.return_value = [
            {'group_id': '100', 'name': 'Root', 'parent_id': '0'},
            {'group_id': '101', 'name': 'Has Users', 'parent_id': '100'},
        ]
        mock_timecamp_api.get_users.return_value = [
            {'user_id': '1', 'email': 'user@test.com', 'group_id': '101'}
        ]

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._remove_empty_groups(dry_run=False)

        mock_timecamp_api.delete_group.assert_not_called()

    def test_remove_empty_groups_removes_nested_empty_groups(self, mock_timecamp_api, mock_timecamp_config):
        """Test that nested empty groups are removed bottom-up."""
        mock_timecamp_config.remove_empty_groups = True
        mock_timecamp_config.root_group_id = 100

        mock_timecamp_api.get_groups.return_value = [
            {'group_id': '100', 'name': 'Root', 'parent_id': '0'},
            {'group_id': '101', 'name': 'Parent', 'parent_id': '100'},
            {'group_id': '102', 'name': 'Child', 'parent_id': '101'},
        ]
        mock_timecamp_api.get_users.return_value = []

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._remove_empty_groups(dry_run=False)

        # Both should be removed; child first (deeper), then parent
        assert mock_timecamp_api.delete_group.call_count == 2
        calls = mock_timecamp_api.delete_group.call_args_list
        assert calls[0] == call(102)  # child removed first
        assert calls[1] == call(101)  # then parent

    def test_remove_empty_groups_keeps_parent_with_non_empty_child(self, mock_timecamp_api, mock_timecamp_config):
        """Test that parent is kept if it has a non-empty child."""
        mock_timecamp_config.remove_empty_groups = True
        mock_timecamp_config.root_group_id = 100

        mock_timecamp_api.get_groups.return_value = [
            {'group_id': '100', 'name': 'Root', 'parent_id': '0'},
            {'group_id': '101', 'name': 'Parent', 'parent_id': '100'},
            {'group_id': '102', 'name': 'Child With Users', 'parent_id': '101'},
            {'group_id': '103', 'name': 'Empty Child', 'parent_id': '101'},
        ]
        mock_timecamp_api.get_users.return_value = [
            {'user_id': '1', 'email': 'user@test.com', 'group_id': '102'}
        ]

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._remove_empty_groups(dry_run=False)

        # Only Empty Child should be removed; Parent has a remaining child with users
        mock_timecamp_api.delete_group.assert_called_once_with(103)

    def test_remove_empty_groups_dry_run(self, mock_timecamp_api, mock_timecamp_config):
        """Test that dry run doesn't delete groups."""
        mock_timecamp_config.remove_empty_groups = True
        mock_timecamp_config.root_group_id = 100

        mock_timecamp_api.get_groups.return_value = [
            {'group_id': '100', 'name': 'Root', 'parent_id': '0'},
            {'group_id': '101', 'name': 'Empty Group', 'parent_id': '100'},
        ]
        mock_timecamp_api.get_users.return_value = []

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync._remove_empty_groups(dry_run=True)

        mock_timecamp_api.delete_group.assert_not_called()

    def test_remove_empty_groups_not_called_when_disabled(self, mock_timecamp_api, mock_timecamp_config, sample_timecamp_users):
        """Test that remove_empty_groups is not called when config is False."""
        mock_timecamp_config.remove_empty_groups = False
        mock_timecamp_config.root_group_id = 100
        mock_timecamp_api.get_groups.return_value = [
            {'group_id': '100', 'name': 'Root', 'parent_id': '0'}
        ]
        mock_timecamp_api.get_users.return_value = []
        mock_timecamp_api.add_group.return_value = '101'

        sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
        sync.sync(sample_timecamp_users, dry_run=False)

        mock_timecamp_api.delete_group.assert_not_called()

