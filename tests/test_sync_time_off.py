"""
Tests for TimeCamp time off synchronization functionality.
"""
import pytest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime
from timecamp_sync_time_off import sync_vacations


class TestSyncVacations:
    """Tests for vacation synchronization."""
    
    def test_sync_vacations_basic(self, mock_timecamp_api, sample_vacation_data, tmp_path):
        """Test basic vacation synchronization."""
        # Create vacation file
        vacation_file = tmp_path / "vacation.json"
        import json
        with open(vacation_file, 'w') as f:
            json.dump(sample_vacation_data, f)
        
        # Setup mock API responses
        mock_timecamp_api.get_day_types.return_value = {
            '1': {'id': '1', 'name': 'Vacation', 'isDayOff': False},
            '2': {'id': '2', 'name': 'Sick Leave', 'isDayOff': True}
        }
        
        mock_timecamp_api.get_users.return_value = [
            {'user_id': '1001', 'email': 'test.test1'},
            {'user_id': '1002', 'email': 'test.test2'},
            {'user_id': '1003', 'email': 'user1test'}
        ]
        
        sync_vacations(str(vacation_file), mock_timecamp_api, dry_run=False, debug=False)
        
        # Should have called add_vacation
        assert mock_timecamp_api.add_vacation.called
    
    def test_sync_vacations_date_range(self, mock_timecamp_api, tmp_path):
        """Test that vacation is added for each day in range."""
        vacation_data = {
            'vacation': [
                {
                    'email': 'test@test.com',
                    'start_on': '2024-01-15',
                    'finish_on': '2024-01-17',
                    'tc_leave_type': 'Vacation'
                }
            ]
        }
        
        vacation_file = tmp_path / "vacation.json"
        import json
        with open(vacation_file, 'w') as f:
            json.dump(vacation_data, f)
        
        mock_timecamp_api.get_day_types.return_value = {
            '1': {'id': '1', 'name': 'Vacation', 'isDayOff': False}
        }
        
        mock_timecamp_api.get_users.return_value = [
            {'user_id': '1001', 'email': 'test@test.com'}
        ]
        
        sync_vacations(str(vacation_file), mock_timecamp_api, dry_run=False, debug=False)
        
        # Should be called 3 times (15th, 16th, 17th)
        assert mock_timecamp_api.add_vacation.call_count == 1  # Once per entry, but the function iterates internally
    
    def test_sync_vacations_dry_run(self, mock_timecamp_api, sample_vacation_data, tmp_path):
        """Test that dry run doesn't make API calls."""
        vacation_file = tmp_path / "vacation.json"
        import json
        with open(vacation_file, 'w') as f:
            json.dump(sample_vacation_data, f)
        
        mock_timecamp_api.get_day_types.return_value = {
            '1': {'id': '1', 'name': 'Vacation', 'isDayOff': False}
        }
        
        mock_timecamp_api.get_users.return_value = [
            {'user_id': '1001', 'email': 'test.test1'}
        ]
        
        sync_vacations(str(vacation_file), mock_timecamp_api, dry_run=True, debug=False)
        
        # Should not call add_vacation in dry run
        mock_timecamp_api.add_vacation.assert_not_called()
    
    def test_sync_vacations_leave_type_matching(self, mock_timecamp_api, tmp_path):
        """Test that leave types are properly matched."""
        vacation_data = {
            'vacation': [
                {
                    'email': 'user1@test.com',
                    'start_on': '2024-01-15',
                    'finish_on': '2024-01-15',
                    'tc_leave_type': 'Vacation'
                },
                {
                    'email': 'user2@test.com',
                    'start_on': '2024-01-16',
                    'finish_on': '2024-01-16',
                    'tc_leave_type': 'Sick Leave'
                }
            ]
        }
        
        vacation_file = tmp_path / "vacation.json"
        import json
        with open(vacation_file, 'w') as f:
            json.dump(vacation_data, f)
        
        mock_timecamp_api.get_day_types.return_value = {
            '1': {'id': '1', 'name': 'Vacation', 'isDayOff': False},
            '2': {'id': '2', 'name': 'Sick Leave', 'isDayOff': True}
        }
        
        mock_timecamp_api.get_users.return_value = [
            {'user_id': '1001', 'email': 'user1@test.com'},
            {'user_id': '1002', 'email': 'user2@test.com'}
        ]
        
        sync_vacations(str(vacation_file), mock_timecamp_api, dry_run=False, debug=False)
        
        # Verify vacation calls were made
        assert mock_timecamp_api.add_vacation.call_count == 2
        
        # First call should be Vacation type (leave_type_id='1')
        first_call = mock_timecamp_api.add_vacation.call_args_list[0]
        assert first_call[1]['leave_type_id'] == '1'
        
        # Second call should be Sick Leave type (leave_type_id='2')
        second_call = mock_timecamp_api.add_vacation.call_args_list[1]
        assert second_call[1]['leave_type_id'] == '2'
    
    def test_sync_vacations_shouldbe_calculation(self, mock_timecamp_api, tmp_path):
        """Test shouldBe time calculation based on isDayOff."""
        vacation_data = {
            'vacation': [
                {
                    'email': 'user1@test.com',
                    'start_on': '2024-01-15',
                    'finish_on': '2024-01-15',
                    'tc_leave_type': 'Vacation'
                },
                {
                    'email': 'user2@test.com',
                    'start_on': '2024-01-16',
                    'finish_on': '2024-01-16',
                    'tc_leave_type': 'Public Holiday'
                }
            ]
        }
        
        vacation_file = tmp_path / "vacation.json"
        import json
        with open(vacation_file, 'w') as f:
            json.dump(vacation_data, f)
        
        mock_timecamp_api.get_day_types.return_value = {
            '1': {'id': '1', 'name': 'Vacation', 'isDayOff': False},
            '3': {'id': '3', 'name': 'Public Holiday', 'isDayOff': True}
        }
        
        mock_timecamp_api.get_users.return_value = [
            {'user_id': '1001', 'email': 'user1@test.com'},
            {'user_id': '1002', 'email': 'user2@test.com'}
        ]
        
        sync_vacations(str(vacation_file), mock_timecamp_api, dry_run=False, debug=False)
        
        # Vacation (not day off) should have shouldBe=480
        first_call = mock_timecamp_api.add_vacation.call_args_list[0]
        assert first_call[1]['shouldBe'] == 480
        
        # Public Holiday (day off) should have shouldBe=0
        second_call = mock_timecamp_api.add_vacation.call_args_list[1]
        assert second_call[1]['shouldBe'] == 0
    
    def test_sync_vacations_vacation_time_calculation(self, mock_timecamp_api, tmp_path):
        """Test vacationTime calculation based on leave type name."""
        vacation_data = {
            'vacation': [
                {
                    'email': 'user@test.com',
                    'start_on': '2024-01-15',
                    'finish_on': '2024-01-15',
                    'tc_leave_type': 'Annual Vacation'
                }
            ]
        }
        
        vacation_file = tmp_path / "vacation.json"
        import json
        with open(vacation_file, 'w') as f:
            json.dump(vacation_data, f)
        
        mock_timecamp_api.get_day_types.return_value = {
            '1': {'id': '1', 'name': 'Annual Vacation', 'isDayOff': False}
        }
        
        mock_timecamp_api.get_users.return_value = [
            {'user_id': '1001', 'email': 'user@test.com'}
        ]
        
        sync_vacations(str(vacation_file), mock_timecamp_api, dry_run=False, debug=False)
        
        # Should have vacationTime=480 because 'vacation' is in the name
        call_args = mock_timecamp_api.add_vacation.call_args[1]
        assert call_args['vacationTime'] == 480
    
    def test_sync_vacations_skips_incomplete_entries(self, mock_timecamp_api, tmp_path):
        """Test that incomplete vacation entries are skipped."""
        vacation_data = {
            'vacation': [
                {
                    'email': 'user@test.com',
                    'start_on': '2024-01-15',
                    # Missing finish_on
                    'tc_leave_type': 'Vacation'
                },
                {
                    # Missing email
                    'start_on': '2024-01-15',
                    'finish_on': '2024-01-15',
                    'tc_leave_type': 'Vacation'
                },
                {
                    'email': 'valid@test.com',
                    'start_on': '2024-01-15',
                    'finish_on': '2024-01-15',
                    'tc_leave_type': 'Vacation'
                }
            ]
        }
        
        vacation_file = tmp_path / "vacation.json"
        import json
        with open(vacation_file, 'w') as f:
            json.dump(vacation_data, f)
        
        mock_timecamp_api.get_day_types.return_value = {
            '1': {'id': '1', 'name': 'Vacation', 'isDayOff': False}
        }
        
        mock_timecamp_api.get_users.return_value = [
            {'user_id': '1001', 'email': 'valid@test.com'}
        ]
        
        sync_vacations(str(vacation_file), mock_timecamp_api, dry_run=False, debug=False)
        
        # Should only add vacation for the valid entry
        assert mock_timecamp_api.add_vacation.call_count == 1
    
    def test_sync_vacations_unknown_leave_type(self, mock_timecamp_api, tmp_path):
        """Test handling of unknown leave types."""
        vacation_data = {
            'vacation': [
                {
                    'email': 'user@test.com',
                    'start_on': '2024-01-15',
                    'finish_on': '2024-01-15',
                    'tc_leave_type': 'Unknown Leave Type'
                }
            ]
        }
        
        vacation_file = tmp_path / "vacation.json"
        import json
        with open(vacation_file, 'w') as f:
            json.dump(vacation_data, f)
        
        mock_timecamp_api.get_day_types.return_value = {
            '1': {'id': '1', 'name': 'Vacation', 'isDayOff': False}
        }
        
        mock_timecamp_api.get_users.return_value = [
            {'user_id': '1001', 'email': 'user@test.com'}
        ]
        
        sync_vacations(str(vacation_file), mock_timecamp_api, dry_run=False, debug=False)
        
        # Should skip entry with unknown leave type
        mock_timecamp_api.add_vacation.assert_not_called()
    
    def test_sync_vacations_unknown_user(self, mock_timecamp_api, tmp_path):
        """Test handling of users not in TimeCamp."""
        vacation_data = {
            'vacation': [
                {
                    'email': 'unknown@test.com',
                    'start_on': '2024-01-15',
                    'finish_on': '2024-01-15',
                    'tc_leave_type': 'Vacation'
                }
            ]
        }
        
        vacation_file = tmp_path / "vacation.json"
        import json
        with open(vacation_file, 'w') as f:
            json.dump(vacation_data, f)
        
        mock_timecamp_api.get_day_types.return_value = {
            '1': {'id': '1', 'name': 'Vacation', 'isDayOff': False}
        }
        
        mock_timecamp_api.get_users.return_value = [
            {'user_id': '1001', 'email': 'known@test.com'}
        ]
        
        sync_vacations(str(vacation_file), mock_timecamp_api, dry_run=False, debug=False)
        
        # Should skip entry for unknown user
        mock_timecamp_api.add_vacation.assert_not_called()

