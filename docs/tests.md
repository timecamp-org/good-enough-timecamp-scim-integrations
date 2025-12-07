# Testing Guide

This document provides comprehensive instructions for running, writing, and maintaining tests for the TimeCamp SCIM Integration project.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Writing Tests](#writing-tests)
- [Configuration Testing](#configuration-testing)
- [Continuous Integration](#continuous-integration)
- [Troubleshooting](#troubleshooting)

## Quick Start

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Installation

### Development Dependencies

Install all development dependencies including pytest:

```bash
pip install -r requirements-dev.txt
```

Or install just the testing requirements:

```bash
pip install pytest pytest-mock pytest-cov pytest-xdist
```

### Verify Installation

```bash
pytest --version
```

Expected output: `pytest 7.4.0` or higher

## Running Tests

### All Tests

```bash
# Run all tests with verbose output
pytest -v

# Run all tests quietly (summary only)
pytest -q

# Run all tests with detailed output
pytest -vv
```

### Specific Test Files

```bash
# Run a specific test file
pytest tests/test_api.py

# Run multiple specific files
pytest tests/test_api.py tests/test_utils.py
```

### Specific Test Classes or Methods

```bash
# Run a specific test class
pytest tests/test_utils.py::TestTimeCampConfig

# Run a specific test method
pytest tests/test_utils.py::TestTimeCampConfig::test_from_env_with_all_settings

# Run all tests matching a pattern
pytest -k "test_supervisor"
```

### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=. --cov-report=html

# Generate terminal coverage report
pytest --cov=. --cov-report=term

# Generate coverage with missing lines
pytest --cov=. --cov-report=term-missing

# Generate XML coverage (for CI/CD)
pytest --cov=. --cov-report=xml
```

### Parallel Execution

Run tests in parallel for faster execution:

```bash
# Auto-detect number of CPUs
pytest -n auto

# Use specific number of workers
pytest -n 4
```

### Debug Mode

```bash
# Show print statements and logging
pytest -s

# Stop on first failure
pytest -x

# Drop into debugger on failure
pytest --pdb

# Show local variables on failure
pytest -l
```

### Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

## Test Structure

### Directory Layout

```
tests/
├── __init__.py
├── conftest.py                      # Shared fixtures
├── fixtures/                        # Test data
│   ├── __init__.py
│   ├── users_sample.json
│   ├── timecamp_users_sample.json
│   ├── azure_api_responses.json
│   ├── timecamp_api_responses.json
│   └── vacation_sample.json
├── test_api.py                      # TimeCamp API tests
├── test_fetch_azuread.py            # Azure AD fetching tests
├── test_prepare_timecamp.py         # Data preparation tests
├── test_supervisor_groups.py        # Supervisor hierarchy tests
├── test_sync_users.py               # User synchronization tests
├── test_sync_time_off.py            # Time off sync tests
├── test_utils.py                    # Utility functions tests
├── test_config_integration.py       # Configuration tests
└── README.md                        # Detailed test documentation
```

### Test Coverage by Component

| Component | Test File | Coverage |
|-----------|-----------|----------|
| TimeCamp API | `test_api.py` | 88% |
| Azure AD Fetch | `test_fetch_azuread.py` | 64% |
| Data Preparation | `test_prepare_timecamp.py` | 46% |
| Supervisor Groups | `test_supervisor_groups.py` | 75% |
| User Sync | `test_sync_users.py` | 71% |
| Time Off Sync | `test_sync_time_off.py` | 86% |
| Utilities | `test_utils.py` | 100% |
| Configuration | `test_config_integration.py` | 100% |

## Writing Tests

### Test Naming Convention

Follow the pattern: `test_<component>_<scenario>_<expected>`

**Good Examples:**
- `test_transform_user_prefer_real_email`
- `test_sync_groups_dry_run_no_api_calls`
- `test_clean_department_skip_prefix`

**Bad Examples:**
- `test_user` (too vague)
- `test_1` (not descriptive)
- `testUserTransform` (wrong format)

### Test Structure (AAA Pattern)

```python
def test_create_new_user(self, mock_timecamp_api, mock_timecamp_config):
    """Test creating a new user in TimeCamp."""
    # ARRANGE - Set up test data and mocks
    tc_user_data = {
        'timecamp_email': 'newuser@test.com',
        'timecamp_user_name': 'New User',
        'timecamp_role': 'user'
    }
    
    # ACT - Execute the function being tested
    sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
    sync._create_new_user(tc_user_data, 101, 'Engineering', dry_run=False)
    
    # ASSERT - Verify the expected behavior
    mock_timecamp_api.add_user.assert_called_once_with(
        'newuser@test.com',
        'New User',
        101
    )
```

### Using Fixtures

```python
def test_with_sample_data(self, sample_users, mock_timecamp_config):
    """Test using predefined fixtures."""
    # sample_users is loaded from fixtures/users_sample.json
    assert len(sample_users['users']) > 0
    
    # mock_timecamp_config provides a default configuration
    assert mock_timecamp_config.root_group_id == 100
```

### Mocking External APIs

```python
from unittest.mock import patch, Mock

@patch('common.api.requests.request')
def test_api_call(self, mock_request, mock_timecamp_config):
    """Test API call with mocked requests."""
    # Create mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'data': 'test'}
    mock_request.return_value = mock_response
    
    # Make API call
    api = TimeCampAPI(mock_timecamp_config)
    result = api.some_method()
    
    # Verify
    assert mock_request.called
    assert result is not None
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input_value,expected", [
    ('true', True),
    ('false', False),
    ('1', True),
    ('0', False),
])
def test_boolean_parsing(self, input_value, expected):
    """Test parsing of boolean values."""
    result = parse_boolean(input_value)
    assert result == expected
```

### Testing Exceptions

```python
def test_missing_config_raises_error(self):
    """Test that missing configuration raises ValueError."""
    with pytest.raises(ValueError, match="Missing required"):
        TimeCampConfig.from_env()
```

## Configuration Testing

The project includes comprehensive configuration tests in `test_config_integration.py` that cover all environment variables from `samples/env.example`.

### Testing Configuration Options

```python
def test_custom_config(self):
    """Test custom configuration."""
    from unittest.mock import patch
    import os
    
    env = {
        'TIMECAMP_API_KEY': 'test_key',
        'TIMECAMP_ROOT_GROUP_ID': '100',
        'TIMECAMP_USE_SUPERVISOR_GROUPS': 'true'
    }
    
    with patch('common.utils.load_dotenv'):
        with patch.dict(os.environ, env, clear=True):
            config = TimeCampConfig.from_env()
            assert config.use_supervisor_groups is True
```

### Configuration Test Categories

1. **Group Structure Configurations**
   - Department-only mode
   - Supervisor-only mode
   - Hybrid mode

2. **User Name Formatting**
   - Show external ID
   - Job title in user names
   - Job title in group names

3. **Email Configurations**
   - Email domain replacement
   - Additional email sync

4. **Department Configurations**
   - Skip departments (single/multiple prefixes)
   - Department path processing

5. **Sync Disable Flags**
   - Disable new users
   - Disable external ID sync
   - Disable additional email sync
   - Disable manual user updates
   - Disable group updates
   - Disable role updates
   - Disable groups creation

6. **Role Configurations**
   - Use is_supervisor field
   - Force role fields

7. **User Management**
   - Ignored user IDs
   - Disabled users group

### Running Configuration Tests

```bash
# Run all configuration tests
pytest tests/test_config_integration.py -v

# Run specific configuration test class
pytest tests/test_config_integration.py::TestTimeCampGroupStructureConfigs -v

# Run tests for a specific configuration
pytest -k "supervisor" tests/test_config_integration.py
```

## Continuous Integration

### GitHub Actions

Tests run automatically on:
- Push to `main`, `develop`, or `automated_tests` branches
- Pull requests to `main` or `develop`

Workflow file: `.github/workflows/tests.yml`

### CI Commands

```bash
# Run tests as CI would
pytest --cov=. --cov-report=xml --cov-report=term-missing -v

# Generate JUnit XML for CI
pytest --junitxml=test-results.xml
```

### Coverage Requirements

- **Overall coverage target:** >45%
- **Critical components:** >80%
  - API wrapper
  - Utilities
  - Configuration loading
- **Integration components:** >60%
  - Data preparation
  - Synchronization logic

## Troubleshooting

### Common Issues

#### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'pytest'`

**Solution:**
```bash
pip install -r requirements-dev.txt
```

#### Tests Not Found

**Problem:** `collected 0 items`

**Solution:** Run from project root:
```bash
cd /path/to/good-enough-timecamp-scim-integrations
pytest
```

#### Mock Not Working

**Problem:** Mock doesn't affect the tested code

**Solution:** Patch at the location where it's used, not where it's defined:
```python
# If module A imports requests and uses it
# Patch 'module_a.requests', not 'requests'
@patch('fetch_azuread.requests.get')  # ✓ Correct
@patch('requests.get')                 # ✗ Wrong
```

#### Environment Variable Conflicts

**Problem:** Tests fail due to existing environment variables

**Solution:** Use `patch.dict` with `clear=True`:
```python
with patch.dict(os.environ, env, clear=True):
    # Test code
```

#### Coverage Not Showing Files

**Problem:** Some files not in coverage report

**Solution:** Check `.coveragerc` and ensure files aren't excluded:
```ini
[run]
omit = 
    tests/*
    venv/*
```

### Debug Failing Tests

```bash
# Show full error traceback
pytest --tb=long

# Show local variables on failure
pytest -l --tb=short

# Drop into debugger on failure
pytest --pdb

# Run only failed tests from last run
pytest --lf

# Run failed tests first, then others
pytest --ff
```

### Performance Issues

```bash
# Show slowest tests
pytest --durations=10

# Run tests in parallel
pytest -n auto

# Skip slow tests
pytest -m "not slow"
```

## Best Practices

### 1. Keep Tests Fast

- Mock all external API calls
- Use in-memory data structures
- Avoid file I/O when possible
- Run slow tests in separate suite

### 2. Make Tests Independent

- Don't depend on test execution order
- Clean up after tests (use fixtures)
- Avoid shared mutable state

### 3. Write Clear Tests

- One assertion concept per test
- Use descriptive names
- Add docstrings for complex tests
- Use comments for non-obvious logic

### 4. Test Edge Cases

- Empty inputs
- None values
- Missing fields
- Invalid data types
- Boundary values

### 5. Keep Tests Maintainable

- Use fixtures for common data
- Extract helper functions
- Keep tests DRY (Don't Repeat Yourself)
- Update tests when code changes

## Examples

### Testing a Pure Function

```python
def test_clean_name_removes_special_chars():
    """Test that special characters are removed from names."""
    # Test with various special characters
    assert clean_name("Name (with) {brackets}") == "Name with brackets"
    assert clean_name("Name_with_underscore") == "Name with underscore"
    assert clean_name("  Name  ") == "Name"
```

### Testing API Integration

```python
@patch('common.api.requests.request')
def test_get_users_with_enabled_status(self, mock_request):
    """Test fetching users with enabled status."""
    # Mock API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {'user_id': '1001', 'email': 'user@test.com'}
    ]
    mock_request.return_value = mock_response
    
    # Call API
    api = TimeCampAPI(mock_config)
    with patch.object(api, 'are_users_enabled', return_value={1001: True}):
        users = api.get_users()
    
    # Verify
    assert len(users) == 1
    assert users[0]['is_enabled'] is True
```

### Testing Configuration Loading

```python
def test_config_with_all_options():
    """Test loading configuration with all options set."""
    from unittest.mock import patch
    import os
    
    env = {
        'TIMECAMP_API_KEY': 'key',
        'TIMECAMP_ROOT_GROUP_ID': '100',
        'TIMECAMP_USE_SUPERVISOR_GROUPS': 'true',
        'TIMECAMP_SKIP_DEPARTMENTS': 'Company'
    }
    
    with patch('common.utils.load_dotenv'):
        with patch.dict(os.environ, env, clear=True):
            config = TimeCampConfig.from_env()
            
            assert config.api_key == 'key'
            assert config.root_group_id == 100
            assert config.use_supervisor_groups is True
            assert config.skip_departments == 'Company'
```

## Additional Resources

- **Test README:** `tests/README.md` - Detailed test suite documentation
- **Pytest Documentation:** https://docs.pytest.org/
- **Coverage.py:** https://coverage.readthedocs.io/
- **Mocking Guide:** https://docs.python.org/3/library/unittest.mock.html

## Contributing

When adding new features:

1. Write tests first (TDD recommended)
2. Ensure all tests pass: `pytest`
3. Check coverage: `pytest --cov=.`
4. Add tests to appropriate file
5. Update this documentation if needed
6. Run tests in CI before merging

---

**Last Updated:** December 2024  
**Test Suite Version:** 1.0  
**Total Tests:** 200+ tests covering all major components

