# Install the Helm chart

This guide installs the chart directly with Helm. If Flux owns the release,
commit the same values under `spec.values` in the `HelmRelease` instead of
running `helm upgrade`.

## 1. Prepare values

Copy the example:

```bash
cp helm/timecamp-scim/samples/values-example.yaml my-values.yaml
```

Edit these sections:

- `image`: the complete image repository and immutable tag.
- `config.timecamp`: TimeCamp behavior.
- One provider under `config`, such as `config.okta`.
- `jobs`: one fetch job, followed by prepare and sync jobs.
- `s3`: shared storage used by all three jobs.
- `externalSecrets`: the secret backend, if enabled.

The complete rules and examples are in
[Kubernetes configuration](../configuration.md).

For example, a HiBob fetch uses non-secret values under `config.hibob` and
enables its matching job:

```yaml
config:
  hibob:
    serviceUserId: "service-user-id"
    excludedDepartments: "Contractors"

jobs:
  fetchHibob:
    enabled: true
    schedule: "0 */6 * * *"
```

Store `HIBOB_SERVICE_USER_TOKEN` in the release Secret, not in this values
file.

For NetSuite, use `config.netsuite` and enable `jobs.fetchNetsuite`. Store the
PEM private key as `NETSUITE_PRIVATE_KEY` in the release Secret:

```yaml
config:
  netsuite:
    accountId: "123456_SB1"
    clientId: "your-oauth2-client-id"
    certificateId: "your-certificate-id"
    jwtAlgorithm: "PS256"

jobs:
  fetchNetsuite:
    enabled: true
    schedule: "0 */6 * * *"
```

## 2. Configure secrets

Do not commit API tokens or passwords to `my-values.yaml`. The chart expects
secret keys such as `TIMECAMP_API_KEY` and the selected provider's token in the
release Secret.

The default chart configuration uses External Secrets. Configure its backend
before installing the chart. For Google Secret Manager, see
[Google Secret Manager](../secret-stores/google-secret-manager.md).

If another system manages the Kubernetes Secret, disable the chart-managed
ExternalSecret:

```yaml
externalSecrets:
  enabled: false
```

The managed Secret must use the chart fullname plus `-secrets`. With the
commands in this guide, its name is `timecamp-scim-secrets`. Confirm the exact
name in the rendered manifest and include the required keys.

## 3. Validate before applying

```bash
helm lint ./helm/timecamp-scim -f my-values.yaml
helm template timecamp-scim ./helm/timecamp-scim \
  --namespace timecamp-scim \
  -f my-values.yaml > rendered.yaml
```

Inspect `rendered.yaml`. Confirm:

- The expected image tag is used.
- Exactly one provider fetch CronJob is enabled.
- Fetch, prepare, and sync schedules run in that order.
- Provider filters appear in the fetch CronJob.
- `TIMECAMP_ROOT_GROUP_ID` appears in the sync CronJob.
- Secret values are references, not plaintext.

Do not deploy until the rendered manifest is correct. A value present in the
Helm file but absent from the rendered CronJob cannot reach the Python script.

## 4. Install or upgrade

```bash
helm upgrade --install timecamp-scim ./helm/timecamp-scim \
  --namespace timecamp-scim \
  --create-namespace \
  -f my-values.yaml
```

Use immutable image tags, preferably a Git SHA. Avoid `latest`; Kubernetes may
keep an older cached image and makes rollback state unclear.

## 5. Verify Kubernetes resources

```bash
helm status timecamp-scim -n timecamp-scim
kubectl get cronjobs -n timecamp-scim
kubectl get externalsecrets -n timecamp-scim
kubectl get secretstores -n timecamp-scim
```

Inspect the actual configuration rendered into a CronJob:

```bash
kubectl get cronjob timecamp-scim-fetch-okta \
  -n timecamp-scim \
  -o yaml

kubectl get cronjob timecamp-scim-sync-users \
  -n timecamp-scim \
  -o yaml
```

## 6. Run one pipeline manually

Create new Jobs from the CronJobs:

```bash
kubectl create job manual-fetch \
  --from=cronjob/timecamp-scim-fetch-okta \
  -n timecamp-scim

kubectl create job manual-prepare \
  --from=cronjob/timecamp-scim-prepare-timecamp \
  -n timecamp-scim

kubectl create job manual-sync \
  --from=cronjob/timecamp-scim-sync-users \
  -n timecamp-scim
```

Run them in order. Wait for each stage to complete before starting the next:

```bash
kubectl logs -f job/manual-fetch -n timecamp-scim
kubectl logs -f job/manual-prepare -n timecamp-scim
kubectl logs -f job/manual-sync -n timecamp-scim
```

The sync stage changes TimeCamp data. Validate the fetched and prepared output
before running it against a production account.

Remove the manual Jobs when finished:

```bash
kubectl delete job manual-fetch manual-prepare manual-sync \
  -n timecamp-scim
```

## Flux

Flux passes `spec.values` directly to the chart. The correct nesting is:

```yaml
spec:
  values:
    config:
      okta:
        filterGroupIds: "00gabc123"
      timecamp:
        rootGroupId: "123456"
```

After committing a change:

```bash
flux reconcile helmrelease timecamp-scim \
  --namespace timecamp-scim \
  --with-source
kubectl get cronjob timecamp-scim-fetch-okta \
  -n timecamp-scim \
  -o yaml
```

Existing Jobs are not updated when a CronJob changes. Create a new Job or wait
for the next schedule before checking the new configuration.

## Troubleshooting

### A required variable is reported missing

Inspect the rendered CronJob, not only the Helm values file:

```bash
kubectl get cronjob timecamp-scim-sync-users \
  -n timecamp-scim \
  -o yaml
```

If the variable is absent, correct the values nesting and reconcile the
release. Use `config.timecamp` and the selected provider's `config` section.
Do not use `config.env` or `.env`-style `KEY=value` lines.

### A job is using an old image

Check the CronJob and Job separately:

```bash
kubectl get cronjob timecamp-scim-fetch-okta \
  -n timecamp-scim \
  -o jsonpath='{.spec.jobTemplate.spec.template.spec.containers[0].image}'

kubectl get job manual-fetch \
  -n timecamp-scim \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

Delete and recreate only the manual Job after confirming the CronJob contains
the correct immutable tag.

### External Secrets are not ready

```bash
kubectl describe externalsecret \
  timecamp-scim-secrets \
  -n timecamp-scim
kubectl describe secretstore \
  timecamp-scim-gcpsm \
  -n timecamp-scim
```

Fix the provider authentication or missing remote secret properties before
running jobs.
