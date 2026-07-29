# Fetching Users From Okta

`fetch_okta.py` reads Okta users through the Okta Management API and writes the shared source format to `var/users.json`.

## Configuration

```env
OKTA_ORG_URL=https://company.okta.com
OKTA_API_TOKEN=your_okta_api_token
OKTA_USER_STATUSES=ACTIVE
OKTA_FILTER_GROUPS=TimeCamp Users
OKTA_FILTER_GROUP_IDS=00gabc123,00gdef456
OKTA_SUPERVISOR_GROUPS=TimeCamp Supervisors
OKTA_EXCLUDED_DEPARTMENTS=
OKTA_EXTERNAL_ID_FIELD=id
OKTA_EMAIL_FIELD=email
OKTA_NAME_FIELD=displayName
OKTA_DEPARTMENT_FIELD=department
OKTA_JOB_TITLE_FIELD=title
OKTA_SUPERVISOR_ID_FIELD=managerId
OKTA_SUPERVISOR_MATCH_FIELD=
OKTA_SUPERVISOR_RULE=
```

`OKTA_FILTER_GROUPS` contains exact Okta group names. `OKTA_FILTER_GROUP_IDS` contains Okta group IDs. Both are optional and comma-separated. When either setting is configured, the fetcher reads users directly from the matching Okta group-members endpoints instead of listing every user in the organization. When both are configured, it includes the deduplicated union of their members. `OKTA_USER_STATUSES` is then applied to those group members. `OKTA_SUPERVISOR_GROUPS` contains exact group names and sets `role_id=2` for matching users.

`OKTA_EXTERNAL_ID_FIELD` selects the Okta profile field stored as the TimeCamp external ID. It defaults to Okta's top-level `id`.

`OKTA_SUPERVISOR_ID_FIELD` selects the field containing a manager reference. `OKTA_SUPERVISOR_MATCH_FIELD` selects the field on the manager that reference is compared against. After finding the manager, the fetcher writes the manager's configured external ID to `supervisor_id`.

For example, when TimeCamp should use `employeeNumber` as its external ID but Okta's `managerId` contains the manager's email:

```env
OKTA_EXTERNAL_ID_FIELD=employeeNumber
OKTA_SUPERVISOR_ID_FIELD=managerId
OKTA_SUPERVISOR_MATCH_FIELD=email
```

When `OKTA_SUPERVISOR_MATCH_FIELD` is empty, it defaults to `OKTA_EXTERNAL_ID_FIELD`, preserving the direct-ID behavior. The fetcher uses Okta user search to pull missing supervisors by standard or custom profile fields. These settings support dotted paths such as `profile.email`.

`OKTA_SUPERVISOR_RULE` optionally sets `is_supervisor=true` based on a profile field value, for example:

```env
OKTA_SUPERVISOR_RULE=timecampSupervisor:yes
```

## Run

```sh
uv run fetch_okta.py
uv run fetch_okta.py --debug
```
