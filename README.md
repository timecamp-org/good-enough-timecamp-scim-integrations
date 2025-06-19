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

## License

MIT