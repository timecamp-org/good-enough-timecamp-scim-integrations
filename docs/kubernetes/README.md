# Kubernetes deployment

The Helm chart runs the integration as three scheduled stages:

1. Fetch users from one HR or identity provider.
2. Prepare the TimeCamp user structure.
3. Synchronize the prepared users to TimeCamp.

Start with these guides:

1. [Configuration](configuration.md) — where values belong, a complete example,
   Flux usage, mistakes to avoid, and validation.
2. [Prerequisites](deployment/01-prerequisites.md) — required cluster tooling.
3. [Helm installation](deployment/02-helm-installation.md) — render, install,
   upgrade, and inspect the chart.
4. [Testing and validation](deployment/03-testing-validation.md) — test the
   pipeline before enabling production sync.

## Configuration rule

Use chart-native values for supported settings:

```yaml
config:
  okta:
    filterGroupIds: "00gabc123"
  timecamp:
    rootGroupId: "123456"
```

Keep API tokens and passwords in a Kubernetes Secret or External Secrets.
Reserve top-level `env` for low-level process settings that have no chart
field. Do not put `KEY=value` lines under `config.env`.

## Minimal workflow

```bash
cp helm/timecamp-scim/samples/values-example.yaml my-values.yaml
helm lint ./helm/timecamp-scim -f my-values.yaml
helm template timecamp-scim ./helm/timecamp-scim \
  -f my-values.yaml > rendered.yaml
helm upgrade --install timecamp-scim ./helm/timecamp-scim \
  --namespace timecamp-scim \
  --create-namespace \
  -f my-values.yaml
kubectl get cronjobs -n timecamp-scim
```

For Flux, place the same values under `spec.values` in the `HelmRelease`. See
the [Flux example](configuration.md#flux-helmrelease).

## Additional guides

- [S3-compatible storage](s3-storage.md)
- [Google Secret Manager](secret-stores/google-secret-manager.md)
- [CI/CD and registries](ci-cd/README.md)
