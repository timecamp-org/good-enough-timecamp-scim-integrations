# Google Secret Manager Setup

This guide covers setting up Google Secret Manager as the secret store for the TimeCamp SCIM integration.

## Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI installed and authenticated
- Kubernetes cluster (preferably GKE)
- External Secrets Operator installed

## Setup Steps

### Step 1: Enable Required APIs

```bash
export PROJECT_ID="your-project-id"

gcloud services enable \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  --project=$PROJECT_ID
```

### Step 2: Create Service Account

```bash
export SA_NAME="scim-sa"

gcloud iam service-accounts create $SA_NAME \
  --display-name="SCIM Integration Service Account" \
  --project=$PROJECT_ID
```

### Step 3: Grant Permissions

```bash
export SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"
```

### Step 4: Set Up Workload Identity (GKE)

```bash
export NAMESPACE="scim"
export KSA_NAME="scim"  # Kubernetes service account name

# Create namespace if it doesn't exist
kubectl create namespace $NAMESPACE

# Enable Workload Identity binding
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:$PROJECT_ID.svc.id.goog[$NAMESPACE/$KSA_NAME]" \
  --project=$PROJECT_ID
```

### Step 5: Create Secrets in Google Secret Manager

1. **Prepare your secrets file**:
   ```bash
   cd helm/scim/samples/secrets
   cp scim-secrets.json my-secrets.json
   ```

2. **Edit `my-secrets.json`** with your actual values:
   ```json
   {
     "TIMECAMP_API_KEY": "your-actual-timecamp-api-key",
     "BAMBOOHR_API_KEY": "your-actual-bamboohr-api-key",
     "AZURE_CLIENT_SECRET": "your-actual-azure-secret",
     "AZURE_BEARER_TOKEN": "",
     "AZURE_REFRESH_TOKEN": "",
     "LDAP_PASSWORD": "your-actual-ldap-password",
     "FACTORIAL_API_KEY": "your-actual-factorial-key",
     "S3_ACCESS_KEY_ID": "your-s3-access-key",
     "S3_SECRET_ACCESS_KEY": "your-s3-secret-key"
   }
   ```

3. **Create the secret**:
   ```bash
   ./create-secrets.sh --project $PROJECT_ID
   ```

   Or manually:
   ```bash
   gcloud secrets create scim-secrets \
     --data-file=my-secrets.json \
     --project=$PROJECT_ID
   ```

### Step 6: Grant Secret Access

```bash
gcloud secrets add-iam-policy-binding scim-secrets \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID
```

## Helm Configuration

Configure your `values.yaml` for Google Secret Manager:

```yaml
serviceAccount:
  create: true
  annotations:
    iam.gke.io/gcp-service-account: "scim-sa@your-project-id.iam.gserviceaccount.com"
  name: "scim"

externalSecrets:
  enabled: true
  secretStore:
    projectID: "your-project-id"
    auth:
      workloadIdentity:
        clusterLocation: your-region
        clusterName: your-cluster-name
        serviceAccountRef:
          name: scim
```

## Alternative Authentication Methods

### Using Service Account Key (Not Recommended for Production)

1. **Create and download key**:
   ```bash
   gcloud iam service-accounts keys create sa-key.json \
     --iam-account=$SA_EMAIL \
     --project=$PROJECT_ID
   ```

2. **Create Kubernetes secret**:
   ```bash
   kubectl create secret generic gcp-credentials \
     --from-file=sa-key.json \
     --namespace=scim
   ```

3. **Configure External Secrets**:
   ```yaml
   externalSecrets:
     secretStore:
       projectID: "your-project-id"
       auth:
         secretRef:
           secretAccessKey:
             name: "gcp-credentials"
             key: "sa-key.json"
   ```

### Using Application Default Credentials

For development or testing:

```yaml
externalSecrets:
  secretStore:
    projectID: "your-project-id"
    # No auth section - uses node's default credentials
```

## Secret Management

### Updating Secrets

```bash
# Update existing secret
gcloud secrets versions add scim-secrets \
  --data-file=updated-secrets.json \
  --project=$PROJECT_ID
```

### Rotating Secrets

```bash
# Create new version
gcloud secrets versions add scim-secrets \
  --data-file=new-secrets.json \
  --project=$PROJECT_ID

# Disable old version (optional)
gcloud secrets versions disable 1 \
  --secret=scim-secrets \
  --project=$PROJECT_ID
```

### Viewing Secret Metadata

```bash
# List secrets
gcloud secrets list --project=$PROJECT_ID

# View secret versions
gcloud secrets versions list scim-secrets --project=$PROJECT_ID

# Access secret value (for debugging)
gcloud secrets versions access latest \
  --secret=scim-secrets \
  --project=$PROJECT_ID
```

## Monitoring and Auditing

### Cloud Logging

Enable audit logs to monitor secret access:

```bash
# Create log sink for secret access
gcloud logging sinks create secret-access-logs \
  bigquery.googleapis.com/projects/$PROJECT_ID/datasets/security_logs \
  --log-filter='protoPayload.serviceName="secretmanager.googleapis.com"'
```

### Monitoring Queries

Example Cloud Monitoring queries:

```yaml
# Secret access frequency
resource.type="gce_instance"
protoPayload.serviceName="secretmanager.googleapis.com"
protoPayload.methodName="google.cloud.secretmanager.v1.SecretManagerService.AccessSecretVersion"

# Failed secret access attempts
resource.type="gce_instance"
protoPayload.serviceName="secretmanager.googleapis.com"
severity>=ERROR
```

## Security Best Practices

### Access Control

1. **Principle of Least Privilege**:
   ```bash
   # Only grant secretAccessor, not secretManager
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:$SA_EMAIL" \
     --role="roles/secretmanager.secretAccessor"
   ```

2. **Conditional Access** (if available):
   ```yaml
   # Restrict access to specific secrets
   bindings:
   - members:
     - serviceAccount:scim-sa@project.iam.gserviceaccount.com
     role: roles/secretmanager.secretAccessor
     condition:
       title: "Restrict to SCIM secrets"
       description: "Only access SCIM-related secrets"
       expression: 'resource.name.startsWith("projects/PROJECT_ID/secrets/scim-")'
   ```

### Secret Rotation

Implement regular secret rotation:

```bash
#!/bin/bash
# rotate-secrets.sh

# Generate new API key (example for BambooHR)
NEW_API_KEY=$(generate_new_bamboohr_key)

# Update secret
echo '{"BAMBOOHR_API_KEY": "'$NEW_API_KEY'"}' | \
gcloud secrets versions add scim-secrets \
  --data-file=- \
  --project=$PROJECT_ID

# Restart pods to pick up new secret
kubectl rollout restart deployment/scim-integration -n scim
```

### Network Security

```bash
# Restrict Secret Manager access to VPC
gcloud services vpc-peerings create \
  --service=servicenetworking.googleapis.com \
  --vpc-network=your-vpc \
  --ranges=secret-manager-range
```

## Troubleshooting

### Common Issues

1. **Permission Denied**:
   ```bash
   # Check service account permissions
   gcloud projects get-iam-policy $PROJECT_ID \
     --flatten="bindings[].members" \
     --format='table(bindings.role)' \
     --filter="bindings.members:$SA_EMAIL"
   ```

2. **Workload Identity Issues**:
   ```bash
   # Verify Workload Identity binding
   gcloud iam service-accounts get-iam-policy $SA_EMAIL
   
   # Check pod annotation
   kubectl describe sa scim -n scim
   ```

3. **External Secrets not syncing**:
   ```bash
   # Check External Secret status
   kubectl describe externalsecret scim-integration-secrets -n scim
   
   # Check Secret Store
   kubectl describe secretstore scim-integration-gcpsm -n scim
   ```

### Debug Commands

```bash
# Test secret access from cluster
kubectl run test-secret --image=google/cloud-sdk:slim \
  --rm -it --restart=Never -n scim \
  --serviceaccount=scim \
  -- gcloud secrets versions access latest \
       --secret=scim-secrets \
       --project=$PROJECT_ID

# Check External Secrets Operator logs
kubectl logs -n external-secrets-system \
  deployment/external-secrets -f
```

### Validation Script

```bash
#!/bin/bash
# validate-gsm-setup.sh

echo "Validating Google Secret Manager setup..."

# Check if secret exists
if gcloud secrets describe scim-secrets --project=$PROJECT_ID &>/dev/null; then
    echo "✓ Secret 'scim-secrets' exists"
else
    echo "✗ Secret 'scim-secrets' not found"
    exit 1
fi

# Check service account
if gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT_ID &>/dev/null; then
    echo "✓ Service account exists"
else
    echo "✗ Service account not found"
    exit 1
fi

# Check Workload Identity binding
if gcloud iam service-accounts get-iam-policy $SA_EMAIL \
   --project=$PROJECT_ID | grep -q workloadIdentityUser; then
    echo "✓ Workload Identity configured"
else
    echo "✗ Workload Identity not configured"
fi

echo "Validation complete!"
```

## Cost Optimization

### Secret Manager Pricing

- $0.06 per 10,000 secret versions per month
- $0.03 per 10,000 access operations
- Free tier: 6 secret versions and 3,000 access operations per month

### Best Practices

1. **Minimize secret versions**: Clean up old versions
2. **Batch secret access**: Avoid frequent individual calls
3. **Use appropriate retention**: Set automatic deletion for old versions

```bash
# Set automatic deletion after 30 days
gcloud secrets update scim-secrets \
  --ttl=30d \
  --project=$PROJECT_ID
```

## Next Steps

After completing the Google Secret Manager setup:
1. Configure your [Helm values](../deployment/02-helm-installation.md)
2. Deploy the integration
3. Set up [monitoring](../deployment/04-monitoring.md)
4. Implement secret rotation procedures