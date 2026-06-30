# Fetching Users From Okta

`fetch_okta.py` reads Okta users through the Okta Management API and writes the shared source format to `var/users.json`.

## Configuration

```env
OKTA_ORG_URL=https://company.okta.com
OKTA_API_TOKEN=your_okta_api_token
OKTA_USER_STATUSES=ACTIVE
OKTA_FILTER_GROUPS=TimeCamp Users
OKTA_SUPERVISOR_GROUPS=TimeCamp Supervisors
OKTA_EXCLUDED_DEPARTMENTS=
OKTA_EMAIL_FIELD=email
OKTA_NAME_FIELD=displayName
OKTA_DEPARTMENT_FIELD=department
OKTA_JOB_TITLE_FIELD=title
OKTA_SUPERVISOR_ID_FIELD=managerId
OKTA_SUPERVISOR_RULE=
```

`OKTA_FILTER_GROUPS` and `OKTA_SUPERVISOR_GROUPS` are exact Okta group names. Filtering limits the users synced into TimeCamp. Supervisor groups set `role_id=2` for matching users.

`OKTA_SUPERVISOR_ID_FIELD` should point to an Okta profile field containing the manager's Okta user ID or login. The fetcher uses it to pull missing supervisors so supervisor hierarchy transforms can still work.

`OKTA_SUPERVISOR_RULE` optionally sets `is_supervisor=true` based on a profile field value, for example:

```env
OKTA_SUPERVISOR_RULE=timecampSupervisor:yes
```

## Run

```sh
uv run fetch_okta.py
uv run fetch_okta.py --debug
```
