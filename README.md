# TimeCamp SCIM Integration

A comprehensive solution for synchronizing users from various HR systems to TimeCamp. This integration supports multiple deployment methods and provides automated, scheduled synchronization workflows.

## Table of Contents

- [🚀 Quick Start - Kubernetes (Production)](#-quick-start---kubernetes-production)
- [Deployment Options](#deployment-options)
  - [Kubernetes (Production)](#-kubernetes-recommended-for-production)
  - [Docker Compose (Development)](#-docker-compose-development--testing)
  - [Local Development](#-local-development)
  - [Deployment Comparison](#deployment-comparison)
- [Supported HR Systems](#supported-hr-systems)
- [Architecture](#architecture)
- [Complete Documentation](#-complete-documentation)
- [HR System Setup](#hr-system-setup)
- [Features](#features)
- [Configuration](#configuration-options)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## 🚀 Quick Start - Kubernetes (Production)

Ready to deploy to production? Follow our comprehensive Kubernetes deployment guide:

**👉 [Complete Kubernetes Documentation](docs/README.md)**

```bash
# Prerequisites
helm repo add external-secrets https://charts.external-secrets.io

# Quick deployment
helm install scim-integration ./helm/scim \
  --namespace scim \
  --create-namespace \
  --values my-values.yaml
```

Key features of the Kubernetes deployment:
- ✅ **Automated CronJobs** for scheduled synchronization
- ✅ **External secret management** (Google Secret Manager, AWS Secrets Manager)
- ✅ **S3-compatible storage** for shared data files
- ✅ **Multi-cloud CI/CD** support (GCP, AWS, Docker Hub)
- ✅ **Production-ready** monitoring and logging

## Supported HR Systems

- **BambooHR** - Complete user and department synchronization
- **Azure AD / Microsoft Entra ID** - User and group management
- **LDAP** - Directory service integration
- **FactorialHR** - User and time-off synchronization

## Deployment Options

### 🚀 Kubernetes (Recommended for Production)

Deploy using Helm charts with automated CronJobs, external secret management, and S3-compatible storage.

```bash
# Quick start
helm install scim-integration ./helm/scim \
  --namespace scim \
  --values my-values.yaml
```

📖 **[Complete Kubernetes Documentation](docs/README.md)**

### 🐳 Docker Compose (Development & Testing)

Run locally or on a single server using Docker Compose.

```bash
# Build and run
docker-compose build
docker compose run --rm fetch-bamboohr
docker compose run --rm prepare-timecamp
docker compose run --rm sync-users
```

### 💻 Local Development

Run directly with Python for development and debugging.

```bash
python fetch_bamboohr.py
python prepare_timecamp_json_from_fetch.py
python timecamp_sync_users.py
```

### Deployment Comparison

| Feature | Kubernetes | Docker Compose | Local Development |
|---------|------------|----------------|-------------------|
| **Production Ready** | ✅ Yes | ⚠️ Limited | ❌ No |
| **Automated Scheduling** | ✅ CronJobs | ⚠️ Manual | ❌ Manual |
| **Secret Management** | ✅ External Secrets | ⚠️ Env files | ❌ Env files |
| **Scalability** | ✅ High | ⚠️ Limited | ❌ None |
| **Monitoring** | ✅ Built-in | ⚠️ Basic | ❌ Manual |
| **Setup Complexity** | 🔶 Medium | 🟢 Low | 🟢 Low |
| **Best For** | Production | Testing/Staging | Development |

**Recommendation:** Use Kubernetes for production deployments and Docker Compose for testing and staging environments.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   HR Systems    │───▶│ SCIM Integration │───▶│   TimeCamp      │
│ (BambooHR, etc) │    │                  │    │   (API)         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │  Data Storage    │
                       │ (S3/Local Files) │
                       └──────────────────┘
```

## 📖 Complete Documentation

**For production deployment and advanced configuration, refer to our comprehensive documentation:**

📚 **[Complete Documentation](docs/README.md)**

### Quick Access to Key Guides

| Topic | Description | Link |
|-------|-------------|------|
| 🔧 Prerequisites | System requirements and setup | [Prerequisites Guide](docs/deployment/01-prerequisites.md) |
| ☸️ Kubernetes Deployment | Production Helm installation | [Helm Installation](docs/deployment/02-helm-installation.md) |
| 🧪 Testing & Validation | Test procedures and validation | [Testing Guide](docs/deployment/03-testing-validation.md) |
| 🔄 CI/CD Setup | GitHub Actions workflows | [CI/CD Guide](docs/ci-cd/README.md) |
| 🔐 Secret Management | External secrets configuration | [Secret Stores](docs/secret-stores/google-secret-manager.md) |
| 💾 S3 Storage | Shared file storage setup | [S3 Configuration](docs/kubernetes/s3-storage.md) |

## Quick Start (Local Development)

### 1. Configure Environment

Copy the environment template:
```bash
cp samples/env.example .env
```

Edit `.env` with your TimeCamp API key and HR system credentials.

### 2. Run the Sync Process

```bash
# Fetch data from HR system
python fetch_bamboohr.py  # or fetch_azuread.py, fetch_ldap.py, etc.

# Transform data for TimeCamp
python prepare_timecamp_json_from_fetch.py

# Preview structure (optional)
python scripts/display_timecamp_tree.py

# Sync to TimeCamp
python timecamp_sync_users.py

# Clean up empty groups (optional)
python scripts/remove_empty_groups.py
```

## HR System Setup

### BambooHR

Add to your `.env`:
```bash
BAMBOOHR_SUBDOMAIN=yourcompany
BAMBOOHR_API_KEY=your-api-key
```

### Azure AD / Microsoft Entra ID

1. Register an application in Azure AD portal
2. Create a client secret
3. Configure API permissions: `Directory.Read.All`, `User.Read.All`, `Group.Read.All`
4. Add to `.env`:

```bash
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_PREFER_REAL_EMAIL=true  # Optional
```

### LDAP

Add to your `.env`:
```bash
LDAP_HOST=ldap.company.com
LDAP_PORT=389
LDAP_DOMAIN=company.com
LDAP_DN=CN=Users,DC=company,DC=com
LDAP_USERNAME=ldap-reader
LDAP_PASSWORD=password
LDAP_USE_SAMACCOUNTNAME=false  # Optional
LDAP_USE_OU_STRUCTURE=false   # Optional
```

### FactorialHR

Add to your `.env`:
```bash
FACTORIAL_API_URL=https://api.factorialhr.com/api/v1
FACTORIAL_API_KEY=your-api-key
LeaveTypeMap={"vacation": "Vacation", "sick": "Sick Leave"}
```

## Command Line Options

All scripts support these flags:
- `--debug` - Enable debug logging
- `--dry-run` - Simulate without making changes

```bash
python timecamp_sync_users.py --dry-run --debug
```

## Automation

### Crontab (Local/Server)

```bash
# Edit crontab
crontab -e

# Add these lines for BambooHR (adjust for your HR system)
0 * * * * cd /path/to/project && python fetch_bamboohr.py
10 * * * * cd /path/to/project && python prepare_timecamp_json_from_fetch.py
20 * * * * cd /path/to/project && python timecamp_sync_users.py
```

### Kubernetes CronJobs

The Helm chart automatically creates CronJobs for scheduled synchronization:

```yaml
jobs:
  fetchBamboohr:
    enabled: true
    schedule: "0 */6 * * *"  # Every 6 hours
  
  syncUsers:
    enabled: true
    schedule: "0 1,7,13,19 * * *"  # 4 times daily
```

## Features

### ✅ User Management
- Create, update, and disable users
- Department and group synchronization
- Supervisor relationship mapping
- External ID management for user matching

### ✅ Data Flow
- **Fetch**: Pull user data from HR systems
- **Prepare**: Transform data to TimeCamp format
- **Sync**: Upload to TimeCamp via REST API
- **Cleanup**: Remove empty organizational groups

### ✅ Security & Reliability
- Dry-run mode for testing
- Comprehensive logging
- Error handling and retry logic
- External secret management (Kubernetes)
- Billing protection controls

### ✅ Deployment Flexibility
- Local development support
- Docker containerization
- Kubernetes production deployment
- Multi-cloud CI/CD support

## Configuration Options

### TimeCamp Settings

```bash
TIMECAMP_API_KEY=your-api-key
TIMECAMP_DOMAIN=app.timecamp.com
TIMECAMP_ROOT_GROUP_ID=12345  # Optional
TIMECAMP_USE_SUPERVISOR_GROUPS=false
TIMECAMP_USE_DEPARTMENT_GROUPS=true
TIMECAMP_DISABLE_NEW_USERS=false
TIMECAMP_SHOW_EXTERNAL_ID=true
```

### Billing Protection

```bash
# Prevent unexpected billing charges
TIMECAMP_DISABLE_NEW_USERS=true  # Only update existing users
TIMECAMP_DISABLE_MANUAL_USER_UPDATES=false  # Allow updates
```

⚠️ **BILLING WARNING**: If your TimeCamp account doesn't have enough paid seats for all users being synced, additional seats will be automatically added and charged to your account.

## Development

### Prerequisites

- Python 3.11+
- pip or poetry for dependency management

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp samples/env.example .env

# Edit configuration
vim .env
```

### Testing

All features have been tested with various scenarios:

- ✅ User changes (name, group, status)
- ✅ New user creation
- ✅ User deactivation/removal
- ✅ Department reorganization
- ✅ Supervisor relationship updates
- ✅ External ID synchronization
- ✅ Email matching (primary/secondary)

📋 **[Complete Testing Guide](docs/deployment/03-testing-validation.md)** - Comprehensive testing procedures, validation scripts, and production deployment checklists.

## Troubleshooting

### Common Issues

1. **API Rate Limits**: Use appropriate delays and retry logic
2. **Authentication Errors**: Verify API keys and permissions
3. **User Matching**: Check email addresses and external IDs
4. **Group Creation**: Ensure proper department/supervisor data

### Debug Mode

```bash
# Enable detailed logging
python timecamp_sync_users.py --debug

# Test without changes
python timecamp_sync_users.py --dry-run
```

### Logs

- Local: `var/logs/sync.log`
- Docker: Container logs via `docker logs`
- Kubernetes: Pod logs via `kubectl logs`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Test Cases

- User changed name ✅
- User changed group ✅
- User added ✅
- User disabled ✅
- User removed ✅
- User added as inactive ✅
- User added with empty department ✅
- Group name with whitespaces near / ✅
- Setting enabled to add external_id to user name ✅
- Don't send automatic email when user is created ✅
- Setting and updating real user email as second email setting in TimeCamp ✅
- Update user roles based on supervisor ✅
- Update user external id ✅
- Matching users based on TC email or TC additional email ✅
- If setting TIMECAMP_DISABLE_NEW_USERS=true create only groups that could be potentialy created ✅
- Creating TimeCamp groups based on supervisor ✅
    - User A (no supervisor) → Group A
    - User B (supervisor: A) → Group "A/B"
    - User C (supervisor: B) → Group "A/B"
    - User D (supervisor: A) → Group "A"
    - User E (no supervisor, not a supervisor) → root group id
- Remove empty groups
- S3-compatible storage for JSON files ✅

## License

MIT License - see LICENSE file for details.

## Support

- 📖 [Documentation](docs/README.md)
- 🐛 [Issues](https://github.com/timecamp-org/good-enough-timecamp-scim-integrations/issues)
- 💬 [Discussions](https://github.com/timecamp-org/good-enough-timecamp-scim-integrations/discussions)