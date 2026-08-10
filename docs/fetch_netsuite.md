# NetSuite users and groups

`fetch_netsuite.py` reads employees and the department hierarchy from NetSuite
through SuiteTalk REST/SuiteQL. It writes the existing `var/users.json`
contract. The normal prepare and user-sync stages then create or update
TimeCamp groups and users.

This POC does not synchronize projects, tasks, time entries, or CAPEX/OPEX.

## Authentication

Use OAuth 2.0 client credentials (machine-to-machine). Token-based OAuth 1.0
authentication is intentionally not supported because Oracle is ending creation
of new TBA integrations for REST web services in NetSuite 2027.1.

In NetSuite:

1. Enable OAuth 2.0 and REST Web Services.
2. Create an integration record with Client Credentials (Machine to Machine)
   Grant and REST Web Services enabled.
3. Create a least-privilege role that can log in with OAuth 2.0 access tokens
   and read employees and departments through SuiteAnalytics Workbook.
4. Generate a supported certificate, upload its public part under OAuth 2.0
   Client Credentials (M2M) Setup, and map it to the integration, role, and user.
5. Keep the private key outside Git. Set it as `NETSUITE_PRIVATE_KEY`, or mount
   it and set `NETSUITE_PRIVATE_KEY_PATH`.

The certificate algorithm must match `NETSUITE_JWT_ALGORITHM`. `PS256` is the
default for an RSA-PSS certificate. Oracle also supports the configured EC
variants `ES256` and `ES512`.

## Required configuration

```dotenv
NETSUITE_ACCOUNT_ID=123456_SB1
NETSUITE_CLIENT_ID=your_oauth2_client_id
NETSUITE_CERTIFICATE_ID=your_certificate_id
NETSUITE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
NETSUITE_JWT_ALGORITHM=PS256
```

Sandbox account IDs are converted to the account-specific domain format; for
example, `123456_SB1` becomes
`https://123456-sb1.suitetalk.api.netsuite.com`. Use `NETSUITE_BASE_URL` only
when the account requires an explicit override.

## Default mapping

The default SuiteQL reads the standard `employee` and `department` records.
Departments are converted to slash-separated paths such as
`Operations/Delivery/Quality`; the existing preparation stage turns those
paths into TimeCamp groups.

Only paths assigned to active employees are created in TimeCamp. Empty
NetSuite departments are read to resolve hierarchy, but are not materialized as
empty TimeCamp groups by the existing synchronizer.

Employee aliases consumed by the adapter:

| Alias | Required | Meaning |
| --- | --- | --- |
| `external_id` | yes | Stable NetSuite employee ID |
| `email` | yes | TimeCamp login email |
| `first_name`, `last_name` | no | Preferred display name fields |
| `name` | no | Fallback display name |
| `job_title` | no | Employee title |
| `supervisor_id` | no | Manager's `external_id` |
| `group_id` | no | ID from the group query |
| `group_name` | no | Fallback when `group_id` is not returned by the group query |
| `status` | no | `inactive`, `disabled`, or `terminated` disables the user; other non-empty values are active |
| `is_inactive` | no | NetSuite boolean fallback when `status` is absent |
| `is_supervisor` | no | Explicit supervisor marker; managers are also inferred from `supervisor_id` references |

Group aliases consumed by the adapter:

| Alias | Required | Meaning |
| --- | --- | --- |
| `group_id` | yes | Stable group ID |
| `group_name` | yes | One hierarchy segment |
| `parent_id` | no | Parent `group_id`; empty means a root group |

WCG-specific saved fields or a different organizational record should be
introduced by overriding `NETSUITE_EMPLOYEE_QUERY` and `NETSUITE_GROUP_QUERY`
while preserving these aliases. Do not fork the transformer merely to rename a
custom NetSuite field.

## Run the POC

```bash
uv run fetch_netsuite.py --debug
uv run prepare_timecamp_json_from_fetch.py
uv run scripts/display_timecamp_tree.py
uv run timecamp_sync_users.py --dry-run --debug
```

Inspect `var/users.json`, the displayed hierarchy, and the dry-run before the
first write. The fetcher refuses to replace `var/users.json` when NetSuite
returns no active employees. `NETSUITE_ALLOW_EMPTY_RESULT=true` removes that
guard and should only be used for a deliberate empty-account test.

## Operational settings

- `NETSUITE_PAGE_SIZE`: SuiteQL page size, from 1 to 1000; default `1000`.
- `NETSUITE_TIMEOUT_SECONDS`: HTTP timeout; default `30`.
- `NETSUITE_SSL_VERIFY`: certificate verification; default `true`.
- `NETSUITE_BASE_URL`: optional API base URL override.
- `NETSUITE_EMPLOYEE_QUERY`: optional employee SuiteQL.
- `NETSUITE_GROUP_QUERY`: optional hierarchy SuiteQL.
- `NETSUITE_ALLOW_EMPTY_RESULT`: allow saving a dataset with no active users;
  default `false`.

## Oracle references

- [OAuth 2.0 client credentials flow](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_162730264820.html)
- [Client assertion and access-token request](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_162755359851.html)
- [Certificate requirements](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/subsect_162755332391.html)
- [Executing SuiteQL through REST web services](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_157909186990.html)
