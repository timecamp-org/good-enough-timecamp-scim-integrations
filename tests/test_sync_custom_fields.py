"""
Tests for TimeCamp user custom field synchronization.
"""
import logging
from unittest.mock import call, patch

import pytest
import requests

from timecamp_sync_users import TimeCampSynchronizer

TEMPLATES = [
    {'id': 15, 'name': 'Job Position', 'resourceType': 'user', 'required': False, 'fieldType': 'string'},
    {'id': 16, 'name': 'Cost Center', 'resourceType': 'user', 'required': False, 'fieldType': 'number'},
    {'id': 17, 'name': 'Notes', 'resourceType': 'user', 'required': False, 'fieldType': 'string'},
    {'id': 18, 'name': 'Contract Type', 'resourceType': 'user', 'required': True, 'fieldType': 'string',
     'defaultValue': 'Employee'},
]


@pytest.fixture
def sync_logs(caplog):
    caplog.set_level(logging.INFO, logger='timecamp_sync_v2')
    return caplog


@pytest.fixture
def api(mock_timecamp_api):
    mock_timecamp_api.get_users.return_value = [
        {'user_id': '1001', 'email': 'user@example.com', 'display_name': 'Sample User', 'group_id': '100'},
    ]
    mock_timecamp_api.get_user_settings_bulk.return_value = {
        'additional_email': {}, 'external_id': {}, 'added_manually': {}, 'disabled_user': {},
    }
    mock_timecamp_api.get_user_roles.return_value = {'1001': [{'group_id': '100', 'role_id': '3'}]}
    mock_timecamp_api.get_custom_field_templates.return_value = TEMPLATES
    mock_timecamp_api.get_custom_field_values.return_value = {}
    return mock_timecamp_api


def make_prepared_user(email='user@example.com', name='Sample User', custom_fields=None):
    user = {
        'timecamp_email': email,
        'timecamp_user_name': name,
        'timecamp_role': 'user',
        'timecamp_status': 'active',
        'timecamp_groups_breadcrumb': '',
        'timecamp_external_id': '',
    }
    if custom_fields is not None:
        user['timecamp_custom_fields'] = custom_fields
    return user


def added_manually_calls(api, user_id=1001):
    return [
        c for c in api.update_user_setting.call_args_list
        if c == call(user_id, 'added_manually', '0')
    ]


def test_sync_users_updates_only_changed_custom_fields(api, mock_timecamp_config):
    api.get_custom_field_values.return_value = {
        1001: {15: 'Junior Developer', 16: '100', 17: 'Old note', 18: 'Contractor'},
    }
    user = make_prepared_user(custom_fields={
        'Job Position': 'Developer',
        'Cost Center': '100.0',
        'Notes': None,
    })

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=False)

    api.get_custom_field_templates.assert_called_once_with('user')
    api.get_custom_field_values.assert_called_once_with('user', [1001], [15, 16, 17])
    api.assign_custom_field_value.assert_called_once_with(15, 1001, 'Developer')
    api.unassign_custom_field_value.assert_called_once_with(17, 1001)
    api.update_user.assert_not_called()
    assert len(added_manually_calls(api)) == 1


def test_sync_users_matches_template_names_without_letter_case(api, mock_timecamp_config):
    user = make_prepared_user(custom_fields={'job position': 'Developer'})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=False)

    api.assign_custom_field_value.assert_called_once_with(15, 1001, 'Developer')


def test_sync_users_with_unchanged_custom_fields_makes_no_writes(api, mock_timecamp_config):
    api.get_custom_field_values.return_value = {1001: {15: 'Developer', 17: None}}
    user = make_prepared_user(custom_fields={'Job Position': 'Developer', 'Notes': None})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=False)

    api.assign_custom_field_value.assert_not_called()
    api.unassign_custom_field_value.assert_not_called()
    api.update_user_setting.assert_not_called()


def test_sync_users_without_custom_fields_does_not_call_custom_field_api(api, mock_timecamp_config):
    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([make_prepared_user()], group_structure={}, dry_run=False)

    api.get_custom_field_templates.assert_not_called()
    api.get_custom_field_values.assert_not_called()


def test_disable_custom_fields_sync_skips_custom_field_api(api, mock_timecamp_config):
    mock_timecamp_config.disable_custom_fields_sync = True
    user = make_prepared_user(custom_fields={'Job Position': 'Developer'})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=False)

    api.get_custom_field_templates.assert_not_called()
    api.get_custom_field_values.assert_not_called()
    api.assign_custom_field_value.assert_not_called()


def test_dry_run_reports_custom_field_changes_without_writes(api, mock_timecamp_config, sync_logs):
    api.get_custom_field_values.return_value = {1001: {15: 'Junior Developer', 17: 'Old note'}}
    user = make_prepared_user(custom_fields={'Job Position': 'Developer', 'Notes': None})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=True)

    api.assign_custom_field_value.assert_not_called()
    api.unassign_custom_field_value.assert_not_called()
    api.update_user_setting.assert_not_called()
    assert (
        "[DRY RUN] Would update custom field 'Job Position' for user user@example.com "
        "from 'Junior Developer' to 'Developer'"
    ) in sync_logs.text
    assert (
        "[DRY RUN] Would update custom field 'Notes' for user user@example.com from 'Old note' to '(empty)'"
    ) in sync_logs.text


def test_missing_template_is_reported_once_and_other_fields_still_sync(api, mock_timecamp_config, sync_logs):
    api.get_users.return_value.append(
        {'user_id': '1002', 'email': 'other@example.com', 'display_name': 'Other User', 'group_id': '100'}
    )
    api.get_user_roles.return_value['1002'] = [{'group_id': '100', 'role_id': '3'}]
    users = [
        make_prepared_user(custom_fields={'Unknown Field': 'x', 'Job Position': 'Developer'}),
        make_prepared_user('other@example.com', 'Other User', {'Unknown Field': 'y'}),
    ]

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users(users, group_structure={}, dry_run=False)

    api.assign_custom_field_value.assert_called_once_with(15, 1001, 'Developer')
    warnings = [r for r in sync_logs.records if "'Unknown Field' was not found" in r.getMessage()]
    assert len(warnings) == 1
    assert "Available user custom fields: 'Contract Type', 'Cost Center', 'Job Position', 'Notes'" in (
        warnings[0].getMessage()
    )


def test_required_custom_field_is_not_cleared(api, mock_timecamp_config, sync_logs):
    api.get_custom_field_values.return_value = {1001: {18: 'Employee'}}
    user = make_prepared_user(custom_fields={'Contract Type': None})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=False)

    api.unassign_custom_field_value.assert_not_called()
    assert "TimeCamp custom field 'Contract Type' is required" in sync_logs.text


def test_invalid_number_is_skipped(api, mock_timecamp_config, sync_logs):
    user = make_prepared_user(custom_fields={'Cost Center': 'CC-100', 'Job Position': 'Developer'})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=False)

    api.assign_custom_field_value.assert_called_once_with(15, 1001, 'Developer')
    assert "Skipping custom field 'Cost Center' for user user@example.com: 'CC-100' is not a number" in (
        sync_logs.text
    )


def test_template_list_error_does_not_stop_user_sync(api, mock_timecamp_config, sync_logs):
    api.get_custom_field_templates.side_effect = requests.exceptions.HTTPError('403 Forbidden')
    user = make_prepared_user(name='New Name', custom_fields={'Job Position': 'Developer'})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=False)

    api.update_user.assert_called_once_with(1001, {'fullName': 'New Name'}, '100')
    api.get_custom_field_values.assert_not_called()
    api.assign_custom_field_value.assert_not_called()
    assert "Cannot read TimeCamp user custom fields, custom fields will not be synced" in sync_logs.text


def test_value_read_error_does_not_write_custom_fields(api, mock_timecamp_config, sync_logs):
    api.get_custom_field_values.side_effect = requests.exceptions.HTTPError('500 Server Error')
    user = make_prepared_user(custom_fields={'Job Position': 'Developer'})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=False)

    api.assign_custom_field_value.assert_not_called()
    assert "Cannot read TimeCamp user custom field values" in sync_logs.text


def test_failed_assignment_continues_with_next_field(api, mock_timecamp_config, sync_logs):
    api.assign_custom_field_value.side_effect = [requests.exceptions.HTTPError('400 Bad Request'), None]
    user = make_prepared_user(custom_fields={'Job Position': 'Developer', 'Cost Center': '100'})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=False)

    assert api.assign_custom_field_value.call_args_list == [
        call(15, 1001, 'Developer'),
        call(16, 1001, '100'),
    ]
    assert "Failed to update custom field 'Job Position' for user user@example.com" in sync_logs.text
    assert len(added_manually_calls(api)) == 1


def test_ignored_users_are_not_read_or_updated(api, mock_timecamp_config):
    api.get_users.return_value.append(
        {'user_id': '9999', 'email': 'owner@example.com', 'display_name': 'Owner', 'group_id': '100'}
    )
    users = [
        make_prepared_user(custom_fields={'Job Position': 'Developer'}),
        make_prepared_user('owner@example.com', 'Owner', {'Job Position': 'Owner'}),
    ]

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users(users, group_structure={}, dry_run=False)

    api.get_custom_field_values.assert_called_once_with('user', [1001], [15])
    api.assign_custom_field_value.assert_called_once_with(15, 1001, 'Developer')


def test_manually_added_user_is_not_updated_when_manual_updates_are_disabled(api, mock_timecamp_config):
    mock_timecamp_config.disable_manual_user_updates = True
    api.get_user_settings_bulk.return_value['added_manually'] = {1001: '1'}
    user = make_prepared_user(custom_fields={'Job Position': 'Developer'})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=False)

    api.assign_custom_field_value.assert_not_called()


def test_persistent_settings_queue_added_manually_after_custom_field_update(api, mock_timecamp_config):
    mock_timecamp_config.persistent_settings = True
    user = make_prepared_user(custom_fields={'Job Position': 'Developer'})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    with patch('timecamp_sync_users.save_json_file'):
        sync._sync_users([user], group_structure={}, dry_run=False)

    api.assign_custom_field_value.assert_called_once_with(15, 1001, 'Developer')
    assert added_manually_calls(api) == []
    assert sync.pending_settings['1001']['settings'] == {'added_manually': '0'}


def test_new_user_receives_custom_fields_before_added_manually(api, mock_timecamp_config):
    api.get_users.return_value = [
        {'user_id': '1004', 'email': 'new@example.com', 'display_name': 'New User', 'group_id': '101'},
    ]
    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._create_new_user(
        make_prepared_user('new@example.com', 'New User', {'Job Position': 'Developer', 'Notes': None}),
        101, 'Engineering', dry_run=False,
    )
    assert sync.newly_created_users[0]['custom_fields'] == {'Job Position': 'Developer', 'Notes': None}

    sync._finalize_new_users()

    api.assign_custom_field_value.assert_called_once_with(15, 1004, 'Developer')
    api.unassign_custom_field_value.assert_not_called()
    write_calls = [
        c for c in api.mock_calls
        if c[0] in ('assign_custom_field_value', 'update_user_setting')
    ]
    assert write_calls == [
        call.assign_custom_field_value(15, 1004, 'Developer'),
        call.update_user_setting(1004, 'added_manually', '0'),
    ]


def test_no_matching_templates_skips_value_request(api, mock_timecamp_config):
    user = make_prepared_user(custom_fields={'Unknown Field': 'x'})

    sync = TimeCampSynchronizer(api, mock_timecamp_config)
    sync._sync_users([user], group_structure={}, dry_run=False)

    api.get_custom_field_values.assert_not_called()
    api.assign_custom_field_value.assert_not_called()
    assert sync.custom_field_values == {}
