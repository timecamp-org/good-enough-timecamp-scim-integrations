# Test Suite Documentation

This directory contains comprehensive automated tests for the TimeCamp SCIM Integration project.

## Overview

The test suite is built using pytest and provides extensive coverage of all major components:
- Azure AD user fetching
- Data preparation and transformation
- Supervisor group processing
- TimeCamp user synchronization
- Time off synchronization
- API wrapper functionality
- Common utilities

## Running Tests

### Install Dependencies

First, install the test dependencies:

```bash
pip install -r requirements-dev.txt
```

Or just the basic requirements:

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Files

```bash
# Test Azure AD fetching
pytest tests/test_fetch_azuread.py

# Test data preparation
pytest tests/test_prepare_timecamp.py

# Test user synchronization
pytest tests/test_sync_users.py

# Test time off synchronization
pytest tests/test_sync_time_off.py

# Test API wrapper
pytest tests/test_api.py

# Test utilities
pytest tests/test_utils.py

# Test supervisor groups
pytest tests/test_supervisor_groups.py
```

### Run Specific Test Classes or Methods

```bash
# Run a specific test class
pytest tests/test_utils.py::TestTimeCampConfig

# Run a specific test method
pytest tests/test_utils.py::TestTimeCampConfig::test_from_env_with_all_settings
```

### Run Tests with Coverage Report

```bash
pytest --cov=. --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`.

### Run Tests in Parallel

```bash
pytest -n auto
```

This uses all available CPU cores to run tests in parallel.

### Run Tests with Verbose Output

```bash
pytest -v
```

### Run Tests with Debug Output

```bash
pytest -s
```

This shows print statements and logging output.

## Test Organization

### Test Files

- `test_fetch_azuread.py` - Azure AD integration tests
  - Token management
  - User data transformation
  - Group filtering
  - Pagination handling

- `test_prepare_timecamp.py` - Data preparation tests
  - Role determination logic
  - Email domain replacement
  - Group path processing
  - Job title formatting

- `test_supervisor_groups.py` - Supervisor hierarchy tests
  - Supervisor path building
  - Hybrid mode (department + supervisor)
  - Department-only mode
  - Supervisor-only mode

- `test_sync_users.py` - User synchronization tests
  - Group structure synchronization
  - User creation and updates
  - User deactivation
  - Additional email handling
  - External ID synchronization

- `test_sync_time_off.py` - Time off synchronization tests
  - Vacation entry parsing
  - Leave type matching
  - Date range iteration
  - Should-be time calculation

- `test_api.py` - API wrapper tests
  - Request construction
  - Retry logic
  - Batch operations
  - Error handling

- `test_utils.py` - Utility function tests
  - Configuration loading
  - Name cleaning
  - Department path processing

### Fixtures

Test fixtures are defined in `conftest.py` and include:

- **Mock API Clients**
  - `mock_timecamp_api` - Mock TimeCamp API
  - `mock_azure_token_manager` - Mock Azure token manager

- **Sample Data**
  - `sample_users` - Sample user data
  - `sample_timecamp_users` - Prepared TimeCamp user data
  - `sample_vacation_data` - Sample vacation data
  - `azure_api_responses` - Mock Azure API responses
  - `timecamp_api_responses` - Mock TimeCamp API responses

- **Configuration**
  - `mock_timecamp_config` - Mock configuration object
  - `mock_env_vars` - Mock environment variables

- **Utilities**
  - `temp_output_dir` - Temporary directory for test output
  - `mock_storage_functions` - Mock storage functions

### Fixture Files

Sample data files are stored in `tests/fixtures/`:

- `users_sample.json` - Sample user data from external source
- `timecamp_users_sample.json` - Prepared TimeCamp user data
- `azure_api_responses.json` - Mock Azure AD API responses
- `timecamp_api_responses.json` - Mock TimeCamp API responses
- `vacation_sample.json` - Sample vacation/time off data

## Test Patterns

### Mocking

All tests use mocks for external API calls to ensure:
- Fast test execution
- No dependency on external services
- Consistent, reproducible results
- No risk of modifying production data

Example:
```python
@patch('common.api.requests.request')
def test_get_users(self, mock_request, mock_timecamp_config):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [...]
    mock_request.return_value = mock_response
    
    api = TimeCampAPI(mock_timecamp_config)
    users = api.get_users()
    
    assert len(users) > 0
```

### Parametrized Tests

Tests use pytest's parametrize feature for testing multiple scenarios:

```python
@pytest.mark.parametrize("value,expected", [
    ('true', 'supervisor'),
    ('false', 'user'),
    ('1', 'supervisor'),
    ('0', 'user'),
])
def test_is_supervisor_role_string(self, value, expected):
    # Test implementation
```

### Test Organization

Tests are organized into classes based on the component being tested:

```python
class TestTimeCampConfig:
    """Tests for TimeCampConfig class."""
    
    def test_from_env_with_all_settings(self):
        """Test loading configuration from environment variables."""
        # Test implementation
```

## Writing New Tests

### Test Naming Convention

Follow the pattern: `test_<what>_<when>_<expected>`

Examples:
- `test_transform_user_prefer_real_email` - Tests user transformation when preferring real email
- `test_sync_groups_dry_run_no_api_calls` - Tests that dry run doesn't make API calls
- `test_clean_department_skip_prefix` - Tests department cleaning with skip prefix

### Test Structure

1. **Arrange** - Set up test data and mocks
2. **Act** - Execute the function being tested
3. **Assert** - Verify the expected behavior

Example:
```python
def test_create_new_user(self, mock_timecamp_api, mock_timecamp_config):
    # Arrange
    tc_user_data = {
        'timecamp_email': 'newuser@test.com',
        'timecamp_user_name': 'New User',
        'timecamp_role': 'user'
    }
    
    # Act
    sync = TimeCampSynchronizer(mock_timecamp_api, mock_timecamp_config)
    sync._create_new_user(tc_user_data, 101, 'Engineering', dry_run=False)
    
    # Assert
    mock_timecamp_api.add_user.assert_called_once_with(
        'newuser@test.com',
        'New User',
        101
    )
```

### Adding Test Fixtures

Add shared fixtures to `conftest.py`:

```python
@pytest.fixture
def my_custom_fixture():
    """Description of what this fixture provides."""
    # Setup
    data = create_test_data()
    
    yield data
    
    # Teardown (if needed)
    cleanup(data)
```

## Continuous Integration

Tests are designed to run in CI/CD environments:

```bash
# Run tests with coverage and generate reports
pytest --cov=. --cov-report=term --cov-report=xml

# Run with JUnit XML output for CI
pytest --junitxml=test-results.xml
```

## Troubleshooting

### Tests Failing Locally

1. Ensure all dependencies are installed:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. Clear pytest cache:
   ```bash
   pytest --cache-clear
   ```

3. Run a single test to isolate the issue:
   ```bash
   pytest tests/test_file.py::TestClass::test_method -v
   ```

### Import Errors

Make sure you're running tests from the project root:
```bash
cd /path/to/good-enough-timecamp-scim-integrations
pytest
```

### Mock Not Working

Ensure mocks are patched at the correct location:
- Patch where the function is used, not where it's defined
- Use the full module path

Example:
```python
# If fetch_azuread.py imports requests
# Patch 'fetch_azuread.requests', not 'requests'
@patch('fetch_azuread.requests.get')
def test_something(self, mock_get):
    ...
```

## Code Coverage Goals

The test suite aims for:
- Overall coverage: >80%
- Critical paths: 100%
- API wrapper: >90%
- Data transformation: >90%

Check current coverage:
```bash
pytest --cov=. --cov-report=term-missing
```

## Contributing

When adding new functionality:

1. Write tests first (TDD approach recommended)
2. Ensure all tests pass
3. Maintain or improve code coverage
4. Follow existing test patterns
5. Add docstrings to test classes and methods
6. Update this README if adding new test categories

