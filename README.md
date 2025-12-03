# TimeCamp SCIM Integrations

Scripts to synchronize users from various HR systems with TimeCamp. Currently supports:
- BambooHR
- Azure AD / Microsoft Entra ID
- LDAP
- Factorial

Follow these steps to sync your SCIM system data with TimeCamp:


```
sudo apt update
sudo apt install python3-requests python3-dotenv python3-ldap python3-boto3 python3-flask
```

1. Create your .env file using the provided template if run without Docker (see samples/env.sample)
2. Pull employee data from your SCIM system to json file:
   `python fetch_bamboohr.py` (Note: Replace with your specific SCIM fetch script if different)
3. Convert the SCIM data format to match TimeCamp's requirements:
   `python prepare_timecamp_json_from_fetch.py`
   `python scripts/display_timecamp_tree.py > var/structure.txt` (Optional: Preview the organizational structure)
4. Upload the transformed data to TimeCamp using TimeCamp REST API:
   `python timecamp_sync_users.py`
5. Remove any empty organizational groups (optional):
   `python scripts/remove_empty_groups.py`

Options:
- `--debug` - Enable debug logging
- `--dry-run` - Simulate without making changes

**⚠️ BILLING WARNING**

AUTOMATIC SEAT UPGRADES: If your TimeCamp account doesn't have enough paid seats for all users being synced, additional seats will be automatically added and charged to your account. Review your user count before proceeding to avoid unexpected billing charges.

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
- Optionally set `LDAP_SUPERVISOR_GROUP_NAME` to specify an LDAP group name (e.g. `timecamp_mgr`) - when set, users belonging to this group will have `force_supervisor_role=true` set in the output
- Optionally set `LDAP_GLOBAL_ADMIN_GROUP_NAME` to specify an LDAP group name (e.g. `timecamp_admin`) - when set, users belonging to this group will have `force_global_admin_role=true` set in the output
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
- Change of email (use external_id to identify user)
- Refactor deparments and use array instead of string
- Unit tests and integration tests!

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
- Move disabled users to specific group (TIMECAMP_DISABLED_USERS_GROUP_ID) ✅
- Re-enable disabled users ✅
- Set added_manually=0 for user after any update to ensure proper tracking ✅

## Docker Support

For easy deployment and consistent environments, you can run the application using Docker.

```bash
docker compose build

# Run specific commands using predefined services:

docker compose run --rm fetch-bamboohr
docker compose run --rm fetch-azuread
docker compose run --rm fetch-ldap
docker compose run --rm fetch-factorial

docker compose run --rm prepare-timecamp

docker compose run --rm sync-users

docker compose run --rm display-tree # (optional)
docker compose run --rm remove-empty-groups # (optional)

# Run any script with custom arguments (optional)
docker compose run --rm timecamp-scim python timecamp_sync_users.py --dry-run --debug
docker compose run --rm sync-users --dry-run
docker compose run --rm sync-users --debug

# HTTP Service (run scripts via REST API on port 8181)
docker compose up -d http-service

# Sample sync command
docker compose run --rm fetch-ldap && docker compose run --rm prepare-timecamp && docker compose run --rm sync-users --debug
```

## License

MIT
