# HiBob Setup

`fetch_hibob.py` reads active employees from HiBob and writes the normalized source file to `var/users.json`.

## Required Credentials

Create a HiBob service user with read access to people data, then configure:

```bash
HIBOB_SERVICE_USER_ID=your-service-user-id
HIBOB_SERVICE_USER_TOKEN=your-service-user-token
```

The script uses HiBob Basic authentication with the service user ID and token.

## Optional Configuration

```bash
# Comma-separated department names to skip after HiBob returns employees.
HIBOB_EXCLUDED_DEPARTMENTS=Operations,Back Office

# Optional HiBob people/search filter JSON.
# Current code supports only the HiBob "equals" operator.
# This narrows the source population; use HIBOB_EXCLUDED_DEPARTMENTS for department exclusions.
HIBOB_EXCLUDE_FILTER='{"fieldPath":"work.site","operator":"equals","values":["Headquarters"]}'

# Override the default supervisor flag.
# Supports nested field paths and compares the field value as text.
HIBOB_SUPERVISOR_RULE=work.isManager:true

# Additional HiBob field paths to request.
# Use this when HIBOB_SUPERVISOR_RULE depends on a custom field or you need raw data downstream.
HIBOB_CUSTOM_FIELDS=work.customField1,work.customField2
```

## Fetched Fields

By default the fetcher requests identity, email, department, title, manager, start date, site, employee ID, and status fields. It requests HiBob `humanReadable=APPEND`, so raw IDs remain available while department and title names can be read from `humanReadable`.

## Supervisor Handling

The fetcher sets:

- `supervisor_id` from `work.reportsTo.id`
- `is_supervisor` from `work.isManager`, unless `HIBOB_SUPERVISOR_RULE` is set

If an active employee reports to a manager who was not returned in the active result set, the script recursively fetches that manager by ID and writes them as an inactive supervisor. That keeps the TimeCamp hierarchy complete without treating missing managers as active employees.

## Run

```bash
uv run --python 3.14 --with-requirements requirements.txt fetch_hibob.py --debug
uv run --python 3.14 --with-requirements requirements.txt prepare_timecamp_json_from_fetch.py
uv run --python 3.14 --with-requirements requirements.txt timecamp_sync_users.py --dry-run
```

Review `var/users.json` and run the sync without `--dry-run` only after the output matches the intended TimeCamp structure.
