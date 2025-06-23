# Testing and Validation

This guide covers how to test and validate your SCIM integration deployment before going to production.

## Overview

The TimeCamp SCIM integration supports comprehensive testing through multiple methods:

- **Dry-run mode**: Simulate operations without making changes
- **Debug logging**: Detailed operation visibility
- **Staged testing**: Test individual components
- **End-to-end validation**: Complete workflow testing

## Pre-Production Testing

### 1. Environment Validation

Before deploying to production, validate your environment setup:

```bash
# Test connection to HR system (example for BambooHR)
python fetch_bamboohr.py --dry-run --debug

# Test TimeCamp API connection
python timecamp_sync_users.py --dry-run --debug

# Validate configuration
python -c "from common.utils import TimeCampConfig; config = TimeCampConfig(); print('Config loaded successfully')"
```

### 2. Data Flow Testing

Test each stage of the data pipeline:

```bash
# Stage 1: Fetch data from HR system
python fetch_bamboohr.py --debug
# Verify: Check var/users.json is created and contains expected data

# Stage 2: Transform data
python prepare_timecamp_json_from_fetch.py --debug
# Verify: Check var/timecamp_users.json contains transformed data

# Stage 3: Preview organizational structure
python scripts/display_timecamp_tree.py
# Verify: Review the organizational structure before sync

# Stage 4: Sync to TimeCamp (DRY RUN FIRST!)
python timecamp_sync_users.py --dry-run --debug
# Verify: Review planned changes without executing them

# Stage 5: Actual sync (only after dry-run validation)
python timecamp_sync_users.py --debug
```

### 3. Kubernetes Testing

For Kubernetes deployments, test each component:

```bash
# Test fetch job
kubectl create job test-fetch --from=cronjob/scim-fetch-bamboohr -n scim
kubectl logs job/test-fetch -n scim -f

# Test prepare job
kubectl create job test-prepare --from=cronjob/scim-prepare -n scim
kubectl logs job/test-prepare -n scim -f

# Test sync job (dry-run)
kubectl create job test-sync --from=cronjob/scim-sync-users -n scim
kubectl logs job/test-sync -n scim -f

# Clean up test jobs
kubectl delete job test-fetch test-prepare test-sync -n scim
```

## Test Scenarios

### User Management Testing

The integration has been tested with these scenarios:

#### ✅ User Changes
- **Name updates**: First name, last name modifications
- **Email changes**: Primary email address updates
- **Department transfers**: Moving users between departments
- **Role changes**: Job title and role updates
- **Status changes**: Active/inactive status modifications

#### ✅ New User Creation
- **Standard users**: Regular employee onboarding
- **Managers**: Users with supervisor responsibilities
- **Department heads**: Users with department management roles
- **External contractors**: Non-employee user types

#### ✅ User Deactivation/Removal
- **Soft deactivation**: Marking users as inactive
- **Department removal**: Removing users from specific groups
- **Complete removal**: Full user account cleanup

#### ✅ Organizational Changes
- **Department restructuring**: Creating/modifying department hierarchies
- **Supervisor changes**: Updating reporting relationships
- **Group reorganization**: Moving groups within organizational structure

#### ✅ Data Synchronization
- **External ID management**: Linking users across systems
- **Email matching**: Primary and secondary email matching
- **Duplicate handling**: Managing duplicate user scenarios

### Example Test Cases

#### Test Case 1: New Employee Onboarding

```bash
# Scenario: New employee added to HR system
# Expected: User created in TimeCamp with correct department and manager

# 1. Add user to HR system (BambooHR, Azure AD, etc.)
# 2. Run sync process
python fetch_bamboohr.py --debug
python prepare_timecamp_json_from_fetch.py --debug
python timecamp_sync_users.py --dry-run --debug  # Review changes first
python timecamp_sync_users.py --debug

# 3. Verify in TimeCamp:
# - User exists with correct name and email
# - User is in correct department group
# - User reports to correct manager
# - External ID is set correctly
```

#### Test Case 2: Department Reorganization

```bash
# Scenario: Department structure changes in HR system
# Expected: TimeCamp groups updated to match new structure

# 1. Modify department structure in HR system
# 2. Run sync with dry-run first
python fetch_bamboohr.py --debug
python prepare_timecamp_json_from_fetch.py --debug
python scripts/display_timecamp_tree.py  # Preview new structure
python timecamp_sync_users.py --dry-run --debug

# 3. Review planned changes, then execute
python timecamp_sync_users.py --debug

# 4. Clean up empty groups if needed
python scripts/remove_empty_groups.py --dry-run --debug
python scripts/remove_empty_groups.py --debug
```

#### Test Case 3: User Status Changes

```bash
# Scenario: Employee leaves company (marked inactive in HR)
# Expected: User deactivated in TimeCamp but data preserved

# 1. Mark user as inactive in HR system
# 2. Run sync process
python fetch_bamboohr.py --debug
python prepare_timecamp_json_from_fetch.py --debug
python timecamp_sync_users.py --dry-run --debug  # Verify deactivation plan
python timecamp_sync_users.py --debug

# 3. Verify in TimeCamp:
# - User status is inactive
# - User data is preserved
# - User removed from active groups
```

## Validation Scripts

### Configuration Validation

Create a validation script to check your setup:

```bash
#!/bin/bash
# validate-setup.sh

set -e

echo "🔍 Validating SCIM Integration Setup..."

# Check environment file
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    exit 1
fi
echo "✅ Environment file exists"

# Check required directories
for dir in var var/logs; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo "✅ Created directory: $dir"
    fi
done

# Test Python dependencies
python -c "import requests, ldap3, msal, bamboo_hr" 2>/dev/null && echo "✅ Python dependencies available" || echo "❌ Missing Python dependencies"

# Test TimeCamp API connection
python -c "
from common.api import TimeCampAPI
from common.utils import TimeCampConfig
config = TimeCampConfig()
api = TimeCampAPI(config)
try:
    api.get_users(limit=1)
    print('✅ TimeCamp API connection successful')
except Exception as e:
    print(f'❌ TimeCamp API connection failed: {e}')
"

echo "🎉 Setup validation complete!"
```

### Data Validation

Validate data integrity during sync:

```python
# validate_data.py
import json
import sys
from pathlib import Path

def validate_users_json():
    """Validate users.json structure"""
    users_file = Path("var/users.json")
    if not users_file.exists():
        print("❌ var/users.json not found")
        return False
    
    with open(users_file) as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        print("❌ users.json should contain a list")
        return False
    
    required_fields = ['email', 'first_name', 'last_name']
    for i, user in enumerate(data):
        for field in required_fields:
            if field not in user:
                print(f"❌ User {i} missing required field: {field}")
                return False
    
    print(f"✅ users.json valid ({len(data)} users)")
    return True

def validate_timecamp_json():
    """Validate timecamp_users.json structure"""
    timecamp_file = Path("var/timecamp_users.json")
    if not timecamp_file.exists():
        print("❌ var/timecamp_users.json not found")
        return False
    
    with open(timecamp_file) as f:
        data = json.load(f)
    
    if 'users' not in data or 'groups' not in data:
        print("❌ timecamp_users.json missing users or groups")
        return False
    
    print(f"✅ timecamp_users.json valid ({len(data['users'])} users, {len(data['groups'])} groups)")
    return True

if __name__ == "__main__":
    success = True
    success &= validate_users_json()
    success &= validate_timecamp_json()
    
    if success:
        print("🎉 All data validation checks passed!")
        sys.exit(0)
    else:
        print("❌ Data validation failed!")
        sys.exit(1)
```

## Monitoring and Debugging

### Log Analysis

Monitor sync operations through logs:

```bash
# Local logs
tail -f var/logs/sync.log

# Kubernetes logs
kubectl logs -l app=scim-sync -n scim -f

# Search for errors
grep -i error var/logs/sync.log
kubectl logs -l app=scim-sync -n scim | grep -i error
```

### Common Issues and Solutions

#### Issue: Authentication Failures

```bash
# Symptoms: "401 Unauthorized" or "403 Forbidden" errors
# Solutions:
# 1. Verify API keys in .env
# 2. Check API permissions in HR system
# 3. Validate TimeCamp API key permissions

# Debug commands:
python -c "
from common.utils import TimeCampConfig
config = TimeCampConfig()
print(f'TimeCamp Domain: {config.timecamp_domain}')
print(f'API Key set: {bool(config.timecamp_api_key)}')
"
```

#### Issue: User Matching Problems

```bash
# Symptoms: Users not found or duplicated
# Solutions:
# 1. Check email address formats
# 2. Verify external ID mapping
# 3. Review matching logic configuration

# Debug commands:
python -c "
import json
with open('var/users.json') as f:
    users = json.load(f)
emails = [u.get('email') for u in users]
print(f'Found {len(emails)} emails')
print(f'Unique emails: {len(set(emails))}')
if len(emails) != len(set(emails)):
    print('⚠️  Duplicate emails detected')
"
```

#### Issue: Group Creation Failures

```bash
# Symptoms: Department groups not created
# Solutions:
# 1. Verify department data in HR system
# 2. Check group creation permissions
# 3. Review supervisor relationships

# Debug commands:
python scripts/display_timecamp_tree.py --debug
```

## Performance Testing

### Load Testing

Test with larger datasets:

```bash
# Test with production-sized data
# 1. Export larger dataset from HR system
# 2. Monitor memory usage during processing
# 3. Check API rate limiting

# Monitor resource usage
python -c "
import psutil
import time
import subprocess

# Start sync process
proc = subprocess.Popen(['python', 'timecamp_sync_users.py', '--debug'])

# Monitor while running
while proc.poll() is None:
    memory = psutil.Process(proc.pid).memory_info().rss / 1024 / 1024
    print(f'Memory usage: {memory:.1f} MB')
    time.sleep(5)
"
```

### Rate Limiting

Test API rate limiting behavior:

```bash
# Configure rate limiting in common/api.py
# Test with different request rates
# Monitor for 429 (Too Many Requests) responses

# Example rate limit test
python -c "
from common.api import TimeCampAPI
from common.utils import TimeCampConfig
import time

config = TimeCampConfig()
api = TimeCampAPI(config)

# Test rapid requests
for i in range(10):
    start = time.time()
    users = api.get_users(limit=1)
    elapsed = time.time() - start
    print(f'Request {i+1}: {elapsed:.2f}s')
"
```

## Security Testing

### Credential Security

Verify credentials are properly protected:

```bash
# Check for exposed credentials
grep -r "api_key\|password\|secret" . --exclude-dir=.git --exclude="*.md" || echo "No exposed credentials found"

# Verify environment variable loading
python -c "
import os
from common.utils import TimeCampConfig

# Check if sensitive values are loaded from environment
config = TimeCampConfig()
sensitive_fields = ['timecamp_api_key', 'bamboohr_api_key', 'azure_client_secret']

for field in sensitive_fields:
    value = getattr(config, field, None)
    if value and len(value) > 10:
        print(f'✅ {field}: Loaded ({"*" * min(len(value), 8)})')
    else:
        print(f'⚠️  {field}: Not set or too short')
"
```

### Data Privacy

Verify data handling:

```bash
# Check for PII in logs
grep -i "email\|phone\|ssn" var/logs/sync.log | head -5

# Verify data encryption in transit (HTTPS)
python -c "
import requests
from common.utils import TimeCampConfig

config = TimeCampConfig()
response = requests.get(f'https://{config.timecamp_domain}/api/v3/users', 
                       headers={'Authorization': f'Bearer {config.timecamp_api_key}'})
print(f'SSL Certificate verified: {response.url.startswith(\"https://\")}')
"
```

## Production Deployment Checklist

Before going live:

### Pre-Deployment

- [ ] All test scenarios pass
- [ ] Dry-run validation successful
- [ ] Backup of current TimeCamp data
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured

### During Deployment

- [ ] Deploy in maintenance window
- [ ] Monitor logs in real-time
- [ ] Verify first sync cycle
- [ ] Check user access immediately after

### Post-Deployment

- [ ] Validate user synchronization
- [ ] Check organizational structure
- [ ] Verify scheduled jobs running
- [ ] Monitor for 24 hours
- [ ] Document any issues and resolutions

## Rollback Procedures

If issues occur during production deployment:

```bash
# 1. Stop automated sync jobs
kubectl patch cronjob scim-fetch-bamboohr -p '{"spec":{"suspend":true}}' -n scim
kubectl patch cronjob scim-prepare -p '{"spec":{"suspend":true}}' -n scim
kubectl patch cronjob scim-sync-users -p '{"spec":{"suspend":true}}' -n scim

# 2. Review logs for issues
kubectl logs -l app=scim-sync -n scim --tail=100

# 3. If needed, restore from backup
# (Follow your organization's backup restoration procedures)

# 4. Re-enable jobs after fixes
kubectl patch cronjob scim-fetch-bamboohr -p '{"spec":{"suspend":false}}' -n scim
kubectl patch cronjob scim-prepare -p '{"spec":{"suspend":false}}' -n scim
kubectl patch cronjob scim-sync-users -p '{"spec":{"suspend":false}}' -n scim
```

## Next Steps

After successful testing:

1. **Schedule regular testing** - Monthly validation runs
2. **Set up monitoring** - Alerts for sync failures
3. **Document customizations** - Any environment-specific changes
4. **Train team members** - On troubleshooting and maintenance
5. **Plan for updates** - Process for updating the integration

For ongoing maintenance, refer to the monitoring and troubleshooting sections in the main documentation.