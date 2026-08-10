# Kubernetes configuration

Use Helm values to configure the integration. The chart converts these values
to environment variables in every CronJob.

## Where each setting belongs

| Setting | Put it here |
| --- | --- |
| Container image | `image` |
| Job enablement and schedules | `jobs` |
| TimeCamp behavior | `config.timecamp` |
| Okta, Azure AD, LDAP, BambooHR, HiBob, or Factorial settings | Matching section under `config` |
| API tokens, passwords, and access keys | Kubernetes Secret or External Secrets |
| S3-compatible storage | `s3` |
| Low-level process settings not modeled by the chart | Top-level `env` map |

All supported TimeCamp and provider settings belong under `config`. Do not
rewrite them as raw environment-variable names.

## Complete Okta example

Copy
[`helm/timecamp-scim/samples/values-example.yaml`](../../helm/timecamp-scim/samples/values-example.yaml)
when configuring another provider. The example below is the smallest useful
Okta deployment:

```yaml
image:
  repository: registry.example.com/integrations/timecamp-scim
  tag: "sha-1234567"
  pullPolicy: IfNotPresent

config:
  okta:
    orgUrl: "https://example.okta.com"
    userStatuses: "ACTIVE"
    filterGroups: ""
    filterGroupIds: "00gabc123,00gdef456"
    externalIdField: "employeeNumber"
    emailField: "email"
    nameField: "displayName"
    departmentField: "department"
    jobTitleField: "title"
    supervisorIdField: "managerEmail"
    supervisorMatchField: "email"
    maxHierarchyRoots: 20

  timecamp:
    domain: "app.timecamp.com"
    rootGroupId: "123456"
    ignoredUserIds: "1001,1002"
    disabledUsersGroupId: 123457
    useSupervisorGroups: true
    useDepartmentGroups: false
    useJobTitleNameUsers: false
    useJobTitleNameGroups: true
    showExternalId: false
    disableNewUsers: false
    disableManualUserUpdates: false
    disableUserDeactivation: false
    disableGroupUpdates: false
    disableRoleUpdates: false
    disableGroupsCreation: false
    removeEmptyGroups: true
    disableExternalIdSync: false
    updateEmailOnExternalId: true
    syncPersistentSettings: true

jobs:
  fetchOkta:
    enabled: true
    schedule: "0 */6 * * *"
  prepareTimecamp:
    enabled: true
    schedule: "20 */6 * * *"
  syncUsers:
    enabled: true
    schedule: "40 */6 * * *"
```

`filterGroupIds` is a comma-separated list of Okta group IDs. When it is set,
the fetcher reads members from those group endpoints instead of listing every
user in the Okta organization. If `filterGroups` is also set, the result is the
deduplicated union of both selections.

The three jobs must run in order: fetch, prepare, then sync. Give each stage
enough time to finish before the next starts.

## Flux HelmRelease

In a Flux `HelmRelease`, put the same chart values under `spec.values`:

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: timecamp-scim
spec:
  values:
    image:
      repository: registry.example.com/integrations/timecamp-scim
      tag: "sha-1234567"
    config:
      okta:
        orgUrl: "https://example.okta.com"
        filterGroupIds: "00gabc123"
        maxHierarchyRoots: 20
      timecamp:
        domain: "app.timecamp.com"
        rootGroupId: "123456"
    jobs:
      fetchOkta:
        enabled: true
      prepareTimecamp:
        enabled: true
      syncUsers:
        enabled: true
```

`spec.values.config` becomes the chart's `config`. Do not add another `env`
level inside it.

## Secrets

Never put tokens or passwords in Git-backed Helm values. Store these as
Kubernetes Secret keys, either directly or through External Secrets:

- `TIMECAMP_API_KEY`
- `OKTA_API_TOKEN`
- `BAMBOOHR_API_KEY`
- `HIBOB_SERVICE_USER_TOKEN`
- `AZURE_CLIENT_SECRET`
- `LDAP_PASSWORD`
- `FACTORIAL_API_KEY`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`

The chart injects the secret keys into the jobs with `secretKeyRef`.

## Raw environment variables

Top-level `env` is an escape hatch for process-level settings that the chart
does not model. It must be a YAML map:

```yaml
env:
  DEBUG: "true"
  DISABLE_FILE_LOGGING: "true"
```

Do not use it for a setting already available under `config`, and never define
the same variable in both places.

## Do and do not

Do:

```yaml
config:
  okta:
    filterGroupIds: "00gabc123"
  timecamp:
    rootGroupId: "123456"
```

Do not nest environment variables under `config`:

```yaml
config:
  env:
    OKTA_FILTER_GROUP_IDS: "00gabc123"
    TIMECAMP_ROOT_GROUP_ID: "123456"
```

Do not use `.env` file syntax in YAML:

```yaml
env:
  OKTA_FILTER_GROUP_IDS=00gabc123
  TIMECAMP_ROOT_GROUP_ID=123456
```

Do not store secrets as plain values:

```yaml
config:
  okta:
    apiToken: "secret-token"
```

## Validate before deployment

Render the manifests and inspect them before Flux or Helm applies anything:

```bash
helm lint ./helm/timecamp-scim -f my-values.yaml
helm template timecamp-scim ./helm/timecamp-scim \
  --namespace timecamp-scim \
  -f my-values.yaml > rendered.yaml
```

Confirm that the rendered fetch and sync CronJobs contain the expected
variables:

```text
OKTA_FILTER_GROUP_IDS
OKTA_MAX_HIERARCHY_ROOTS
TIMECAMP_ROOT_GROUP_ID
TIMECAMP_DISABLED_USERS_GROUP_ID
TIMECAMP_SYNC_PERSISTENT_SETTINGS
```

After deployment:

```bash
kubectl get cronjobs -n timecamp-scim
kubectl get cronjob timecamp-scim-fetch-okta -n timecamp-scim -o yaml
kubectl get cronjob timecamp-scim-sync-users -n timecamp-scim -o yaml
```

After changing a CronJob, create a new Job or wait for its next scheduled run.
Existing Jobs keep the configuration with which they were created.

For an Okta group-ID fetch, the new Job should log:

```text
Resolving Okta filter groups by ID: [...]
Fetching users directly from configured Okta filter groups...
```

If it only logs `Fetching users from Okta...`, inspect the rendered CronJob.
The setting did not reach the container.
