# Helm Installation Guide

This guide walks you through installing the TimeCamp SCIM integration using Helm.

## Prerequisites

Before starting, ensure you have completed:
1. [Prerequisites](01-prerequisites.md) - System requirements
2. [Cluster Requirements](../kubernetes/cluster-requirements.md) - Kubernetes cluster setup
3. [Secret Store Setup](../secret-stores/) - Choose and configure a secret provider

## Installation Steps

### Step 1: Prepare Configuration

1. **Copy the values template**:
   ```bash
   cp helm/scim/samples/values-example.yaml my-values.yaml
   ```

2. **Edit configuration** (`my-values.yaml`):
   ```yaml
   image:
     registry: your-region-docker.pkg.dev
     repository: your-project-id/scim-integration-repo/scim-integration
     tag: "latest"

   serviceAccount:
     annotations:
       iam.gke.io/gcp-service-account: "scim-sa@your-project-id.iam.gserviceaccount.com"

   externalSecrets:
     secretStore:
       projectID: "your-project-id"
       auth:
         workloadIdentity:
           clusterLocation: your-region
           clusterName: your-cluster-name

   s3:
     enabled: true
     endpointUrl: "http://s3.example.local:9000"
     region: "your-region"
     bucketName: "scim-data"
     forcePathStyle: true

   config:
     timecamp:
       domain: "app.timecamp.com"
       rootGroupId: "00000"
       
     # Enable based on your HR system
     bamboohr:
       subdomain: "your-company"
       
   jobs:
     fetchBamboohr:
       enabled: true
       schedule: "0 */6 * * *"
     
     prepareTimecamp:
       enabled: true
       schedule: "30 */6 * * *"
     
     syncUsers:
       enabled: true
       schedule: "0 1,7,13,19 * * *"
   ```

### Step 2: Create Namespace

```bash
kubectl create namespace scim
```

### Step 3: Install External Secrets (if not done)

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace
```

### Step 4: Deploy the Helm Chart

```bash
helm install scim-integration ./helm/scim \
  --namespace scim \
  --values my-values.yaml
```

### Step 5: Verify Installation

1. **Check pod status**:
   ```bash
   kubectl get pods -n scim
   ```

2. **Check External Secrets**:
   ```bash
   kubectl get externalsecrets -n scim
   kubectl get secretstore -n scim
   ```

3. **Check CronJobs**:
   ```bash
   kubectl get cronjobs -n scim
   ```

4. **Verify secrets are synced**:
   ```bash
   kubectl get secrets -n scim
   kubectl describe secret scim-integration-secrets -n scim
   ```

## Configuration Options

### Image Configuration

```yaml
image:
  registry: your-registry.com
  repository: timecamp-org/scim-integration
  tag: "v1.0.0"
  pullPolicy: IfNotPresent
```

### Job Scheduling

```yaml
jobs:
  # Fetch from HR system every 6 hours
  fetchBamboohr:
    enabled: true
    schedule: "0 */6 * * *"
    successfulJobsHistoryLimit: 3
    failedJobsHistoryLimit: 3
  
  # Prepare data 30 minutes after fetch
  prepareTimecamp:
    enabled: true
    schedule: "30 */6 * * *"
  
  # Sync to TimeCamp 4 times daily
  syncUsers:
    enabled: true
    schedule: "0 1,7,13,19 * * *"
```

### Resource Limits

```yaml
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 128Mi
```

### S3 Storage Options

```yaml
s3:
  enabled: true
  endpointUrl: "https://s3.amazonaws.com"  # or MinIO endpoint
  region: "us-east-1"
  bucketName: "my-scim-data"
  pathPrefix: "production/"  # optional
  forcePathStyle: false  # true for MinIO
```

## HR System Configuration

### BambooHR

```yaml
config:
  bamboohr:
    subdomain: "your-company"
    excludeFilter: ""
    excludedDepartments: "IT,HR"

jobs:
  fetchBamboohr:
    enabled: true
    schedule: "0 */6 * * *"
```

### Azure AD

```yaml
config:
  azure:
    tenantId: "your-tenant-id"
    clientId: "your-client-id"
    scimEndpoint: "https://graph.microsoft.com/v1.0"
    filterGroups: "Engineering,Sales"
    preferRealEmail: false

jobs:
  fetchAzuread:
    enabled: true
    schedule: "0 */6 * * *"
```

### LDAP

```yaml
config:
  ldap:
    host: "ldap.company.local"
    port: 389
    domain: "company.local"
    dn: "CN=Users,DC=company,DC=local"
    username: "ldap-service"
    filter: "(objectClass=user)"
    emailDomain: "company.local"
    useSsl: false
    useStartTls: true

jobs:
  fetchLdap:
    enabled: true
    schedule: "0 */6 * * *"
```

### FactorialHR

```yaml
config:
  factorial:
    apiUrl: "https://api.factorialhr.com/api/v1"
    leaveTypeMap: '{"vacation": "Vacation", "sick": "Sick Leave"}'

jobs:
  fetchFactorial:
    enabled: true
    schedule: "0 */6 * * *"
  
  syncTimeOff:
    enabled: true
    schedule: "0 8 * * *"  # Daily at 8 AM
```

## Manual Operations

### Run Manual Sync

```bash
# Manual fetch from HR system
kubectl create job --from=cronjob/scim-integration-fetch-bamboohr manual-fetch -n scim

# Manual prepare
kubectl create job --from=cronjob/scim-integration-prepare-timecamp manual-prepare -n scim

# Manual sync to TimeCamp
kubectl create job --from=cronjob/scim-integration-sync-users manual-sync -n scim
```

### Check Job Logs

```bash
# View job status
kubectl get jobs -n scim

# View job logs
kubectl logs job/manual-fetch -n scim

# Follow live logs
kubectl logs -f job/manual-sync -n scim
```

### Debug Mode

Run jobs with debug logging:

```bash
kubectl create job manual-debug --image=your-registry/scim-integration:latest -n scim -- \
  python fetch_bamboohr.py --debug
```

## Upgrades

### Upgrade Chart

```bash
# Update values if needed
helm upgrade scim-integration ./helm/scim \
  --namespace scim \
  --values my-values.yaml
```

### Update Image Version

```bash
helm upgrade scim-integration ./helm/scim \
  --namespace scim \
  --values my-values.yaml \
  --set image.tag=v2.0.0
```

## Troubleshooting

### Common Issues

1. **External Secrets not syncing**:
   ```bash
   kubectl describe externalsecret scim-integration-secrets -n scim
   kubectl logs -n external-secrets-system deployment/external-secrets
   ```

2. **Jobs failing**:
   ```bash
   kubectl describe job <job-name> -n scim
   kubectl logs job/<job-name> -n scim
   ```

3. **S3 connection issues**:
   ```bash
   # Test S3 connectivity
   kubectl run s3-test --image=amazon/aws-cli --rm -it -- \
     aws s3 ls s3://your-bucket --endpoint-url=http://your-s3-endpoint
   ```

4. **Secret access issues**:
   ```bash
   kubectl get secrets -n scim
   kubectl describe secret scim-integration-secrets -n scim
   ```

### Debug Pod

Create a debug pod to test configuration:

```bash
kubectl run debug-pod --image=your-registry/scim-integration:latest \
  --rm -it --restart=Never -n scim -- /bin/bash
```

## Security Considerations

### RBAC

The chart creates minimal RBAC permissions:
- ServiceAccount for the integration
- ClusterRole for External Secrets access
- RoleBinding for secret access

### Network Policies

Consider implementing network policies:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: scim-integration-netpol
  namespace: scim
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: scim
  policyTypes:
  - Egress
  egress:
  - to: []  # Allow all egress (customize as needed)
    ports:
    - protocol: TCP
      port: 443
    - protocol: TCP
      port: 80
```

## Next Steps

After successful installation:
1. [Configure monitoring](04-monitoring.md)
2. Set up log aggregation
3. Implement backup strategies
4. Plan for disaster recovery