# TimeCamp SCIM Integrations

Scripts to synchronize users from various HR systems with TimeCamp. Currently supports:
- BambooHR
- Azure AD / Microsoft Entra ID
- LDAP
- Factorial

First run:

1. Create and fill `.env` file (see samples/env.sample)
2. Get row data from SCIM system to json file, like
   `python fetch_bamboohr.py`
3. Transform SCIM json file data into TimeCamp json file structure 
   `python prepare_timecamp_json_from_fetch.py`
   `python scripts/display_timecamp_tree.py > var/structure.txt` (optional to visualise)
4. Synchronize with TimeCamp API
   `python timecamp_sync_users.py`
5. Cleanup empty groups (optional)
   `python scripts/remove_empty_groups.py`

Options:
- `--debug` - Enable debug logging
- `--dry-run` - Simulate without making changes

**⚠️ IMPORTANT: BY DEFAULT IF ACCOUNT DOESN'T HAVE ENOUGH PAID SEATS IN SAAS, THEY WILL BE INCREASED AUTOMATICALLY**

## Crontab Setup

To automate the synchronization with the two-stage process:

```bash
# Edit crontab
crontab -e

# For BambooHR:
# Fetch users from BambooHR every hour
0 * * * * cd /path/to/project && python fetch_bamboohr.py

# Prepare TimeCamp data 10 minutes after fetch
10 * * * * cd /path/to/project && python prepare_timecamp_json_from_fetch.py

# Sync with TimeCamp 10 minutes after fetch
20 * * * * cd /path/to/project && python timecamp_sync_users.py
```

Notes:
- Replace `/path/to/project` with the actual path to your project
- All operations are logged to `var/logs/sync.log`

## LDAP

- Set the environment variables: `LDAP_HOST`, `LDAP_PORT`, `LDAP_DOMAIN`, `LDAP_DN`, `LDAP_USERNAME`, and `LDAP_PASSWORD`
- Optionally set `LDAP_FILTER` to customize the user filter query (default filter includes only active users)
- Optionally set `LDAP_PAGE_SIZE` to control the number of results retrieved per page (default is 1000)
- Optionally set `LDAP_USE_SAMACCOUNTNAME=true` to generate email addresses from sAMAccountName rather than using the mail attribute
- Optionally set `LDAP_USE_OU_STRUCTURE=true` to use the organizational unit (OU) structure from user's DN as the department value instead of the department attribute
- Run `python ldap_fetch.py` to fetch users from LDAP
- Note: When using sAMAccountName for email, the original mail attribute is always included as `real_email` field if available

## Azure AD / Microsoft Entra ID Setup

1. Register an application in Azure AD/Entra ID portal:
   - Go to Azure Portal > Azure Active Directory > App registrations > New registration
   - Name your application (e.g., "TimeCamp SCIM Integration")
   - Select "Accounts in this organizational directory only"
   - Click Register
   - Note down the Application (client) ID and Directory (tenant) ID

2. Create a client secret:
   - Go to your app > Certificates & secrets > New client secret
   - Give it a description (e.g., "SCIM Integration")
   - Select an expiration (e.g., 24 months)
   - Click Add
   - IMMEDIATELY copy the "Value" column (NOT the Secret ID)
   - ⚠️ The secret value will only be shown once and looks like `kv~8Q~...`
   - If you copied the wrong value or lost it, create a new secret

3. Configure API permissions:
   - Go to your app > API permissions
   - Click "Add a permission"
   - Select "Microsoft Graph" > "Application permissions"
   - Add these permissions:
     * Directory.Read.All
     * User.Read.All
     * Group.Read.All
   - Click "Grant admin consent" button

4. Configure OAuth credentials in `.env`:
```bash
AZURE_TENANT_ID=your-tenant-id  # Directory (tenant) ID
AZURE_CLIENT_ID=your-client-id  # Application (client) ID
AZURE_CLIENT_SECRET=your-client-secret  # The secret value you copied
```

5. (Optional) Configure email preference:
   - By default, the script uses the federated ID (userPrincipalName) as the primary email
   - To use real email addresses (mail attribute) when available, add this to your `.env`:
```bash
AZURE_PREFER_REAL_EMAIL=true
```

## Not Yet Implemented

- Setting to sync only selected things (like only new users)
- Setting to move disabled users to specific group_id
- Change of email (use external_id to identify user)
- Refactor deparments and use array instead of string

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
- If setting TIMECAMP_DISABLE_NEW_USERS=true create only groups that are needed for existing users, don't create all groups that could be potentialy created ✅
- Creating TimeCamp groups based on supervisor ✅
   - User A (no supervisor) → Group A
   - User B (supervisor: A) → Group "A/B"
   - User C (supervisor: B) → Group "A/B"
   - User D (supervisor: A) → Group "A"
   - User E (no supervisor, not a supervisor) → root group id
- Remove empty groups

## Docker Support

For easy deployment and consistent environments, you can run the application using Docker.

### Prerequisites

- Docker and Docker Compose installed on your system
- Environment variables configured (see `samples/env.example` for reference)

### Quick Start with Docker

1. **Set up environment variables:**
   
   **Option A: Using .env file (recommended for docker-compose)**
   ```bash
   # Copy the sample env file and configure it
   cp samples/env.example .env
   # Edit .env with your actual configuration values
   # Docker Compose will automatically load variables from .env
   ```
   
   **Option B: Export environment variables directly**
   ```bash
   export TIMECAMP_API_KEY=your_api_key
   export TIMECAMP_ROOT_GROUP_ID=your_root_group_id
   export BAMBOOHR_SUBDOMAIN=your_subdomain
   export BAMBOOHR_API_KEY=your_api_key
   # ... add other variables as needed
   ```

   > **Note**: All environment variables from `samples/env.example` are supported. The Docker Compose configuration includes sensible defaults for optional settings.

2. **Build the Docker image:**
   ```bash
   docker-compose build
   ```

3. **Run specific commands using predefined services:**
   ```bash
   # Fetch users from BambooHR
   docker-compose run --rm fetch-bamboohr
   
   # Fetch users from Azure AD
   docker-compose run --rm fetch-azuread
   
   # Fetch users from LDAP
   docker-compose run --rm fetch-ldap
   
   # Fetch vacation data from FactorialHR
   docker-compose run --rm fetch-factorial
   
   # Prepare TimeCamp data
   docker-compose run --rm prepare-timecamp
   
   # Sync users with TimeCamp
   docker-compose run --rm sync-users
   
   # Display TimeCamp tree structure
   docker-compose run --rm display-tree
   
   # Remove empty groups
   docker-compose run --rm remove-empty-groups
   ```

4. **Run the complete workflow:**
   ```bash
   # Example: Complete BambooHR sync workflow
   docker-compose run --rm fetch-bamboohr
   docker-compose run --rm prepare-timecamp
   docker-compose run --rm sync-users
   docker-compose run --rm remove-empty-groups
   ```

5. **Run custom commands:**
   ```bash
   # Run any script with custom arguments
   docker-compose run --rm timecamp-scim python timecamp_sync_users.py --dry-run --debug
   
   # Or use the convenience commands with flags
   docker-compose run --rm timecamp-scim sync-users --dry-run --debug
   ```

### Alternative: Direct Docker Commands

You can also run the container directly without docker-compose by passing environment variables:

```bash
# Build the image
docker build -t timecamp-scim .

# Run commands with environment variables
docker run --rm \
  -e TIMECAMP_API_KEY=your_api_key \
  -e TIMECAMP_ROOT_GROUP_ID=your_root_group_id \
  -e BAMBOOHR_SUBDOMAIN=your_subdomain \
  -e BAMBOOHR_API_KEY=your_api_key \
  -v ./var:/app/var \
  timecamp-scim fetch-bamboohr

# For production, use an env file
docker run --rm \
  --env-file .env \
  -v ./var:/app/var \
  timecamp-scim sync-users --dry-run

# See all available commands
docker run --rm timecamp-scim help
```

### Docker Compose Services

The following services are available:

- `fetch-bamboohr` - Fetch users from BambooHR
- `fetch-azuread` - Fetch users from Azure AD/Entra ID
- `fetch-ldap` - Fetch users from LDAP
- `fetch-factorial` - Fetch vacation data from FactorialHR
- `prepare-timecamp` - Transform fetched data for TimeCamp
- `sync-users` - Synchronize users with TimeCamp
- `sync-time-off` - Synchronize time-off data with TimeCamp
- `display-tree` - Display TimeCamp group structure
- `remove-empty-groups` - Clean up empty groups

### Environment Variables & Volumes

- **Configuration**: Environment variables are passed directly to the container (more secure and Docker-native)
- **Data persistence**: The `var/` directory is mounted to persist logs and output files

### Docker Environment

The Docker container includes all necessary dependencies including:
- Python 3.11
- LDAP development libraries
- All Python packages from `requirements.txt`

### Production Deployment

For production deployments, you can:

- **Use with Kubernetes**: Pass environment variables via ConfigMaps and Secrets
- **Use with Docker Swarm**: Set environment variables in your stack file
- **Use with CI/CD**: Set environment variables in your pipeline configuration
- **Use with container orchestrators**: All major platforms support environment variable injection

The environment-based configuration makes the container truly portable across any Docker-compatible platform.

## License

MIT