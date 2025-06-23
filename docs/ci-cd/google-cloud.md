# Google Cloud Platform CI/CD Setup

This guide covers setting up GitHub Actions to build and push Docker images to Google Artifact Registry using Workload Identity Federation (keyless authentication).

## Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI installed and authenticated
- Owner or appropriate IAM permissions on the GCP project
- GitHub repository with admin access

## Setup Steps

### Step 1: Enable Required APIs

```bash
export PROJECT_ID="your-project-id"

gcloud services enable \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  artifactregistry.googleapis.com \
  --project=$PROJECT_ID
```

### Step 2: Create Artifact Registry Repository

```bash
export LOCATION="us-central1"
export REPOSITORY="docker-images"

# Create the repository
gcloud artifacts repositories create $REPOSITORY \
  --repository-format=docker \
  --location=$LOCATION \
  --description="Docker images for SCIM integration" \
  --project=$PROJECT_ID
```

### Step 3: Create Service Account

```bash
export SERVICE_ACCOUNT_NAME="github-actions-docker"

gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
  --display-name="GitHub Actions Docker Push" \
  --project=$PROJECT_ID
```

### Step 4: Grant Permissions to Service Account

```bash
export SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

# Grant Artifact Registry Writer role
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/artifactregistry.writer"
```

### Step 5: Create Workload Identity Pool

```bash
export POOL_NAME="github-actions-pool"

gcloud iam workload-identity-pools create $POOL_NAME \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  --project=$PROJECT_ID
```

### Step 6: Create Workload Identity Provider

```bash
export PROVIDER_NAME="github-provider"
export GITHUB_ORG="timecamp-org"  # Replace with your GitHub organization
export GITHUB_REPO="good-enough-timecamp-scim-integrations"  # Replace with your repository name

gcloud iam workload-identity-pools providers create-oidc $PROVIDER_NAME \
  --location="global" \
  --workload-identity-pool=$POOL_NAME \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner == '$GITHUB_ORG'" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --project=$PROJECT_ID
```

### Step 7: Configure Service Account Impersonation

```bash
# Get the full provider name
export WORKLOAD_IDENTITY_PROVIDER="projects/$PROJECT_ID/locations/global/workloadIdentityPools/$POOL_NAME/providers/$PROVIDER_NAME"

# Allow the GitHub repository to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding $SERVICE_ACCOUNT_EMAIL \
  --member="principalSet://iam.googleapis.com/$WORKLOAD_IDENTITY_PROVIDER/attribute.repository/$GITHUB_ORG/$GITHUB_REPO" \
  --role="roles/iam.workloadIdentityUser" \
  --project=$PROJECT_ID
```

### Step 8: Configure GitHub Repository

#### Secrets (Settings → Secrets and variables → Actions → Secrets)
```bash
# Add these secrets to your GitHub repository
GCP_WORKLOAD_IDENTITY_PROVIDER="projects/$PROJECT_ID/locations/global/workloadIdentityPools/$POOL_NAME/providers/$PROVIDER_NAME"
GCP_SERVICE_ACCOUNT="$SERVICE_ACCOUNT_EMAIL"
```

#### Variables (Settings → Secrets and variables → Actions → Variables)
```bash
# Add these variables to your GitHub repository
GCP_PROJECT_ID="$PROJECT_ID"
GAR_LOCATION="$LOCATION"
GAR_REPOSITORY="$REPOSITORY"
```

## GitHub Actions Workflow

The workflow is already configured in `.github/workflows/docker-build-push.yml`. It will:

1. Authenticate to Google Cloud using Workload Identity Federation
2. Configure Docker for Artifact Registry
3. Build multi-architecture images (linux/amd64, linux/arm64)
4. Push images with appropriate tags

### Workflow Triggers

- **Push to main/develop**: Builds and pushes with branch name tag + `latest`
- **Tags (v*)**: Builds and pushes with semantic version tags
- **Pull requests**: Builds only (no push)

### Image Tags

The workflow automatically creates these tags:
- `main` or `develop` for branch pushes
- `v1.0.0`, `v1.0`, `v1` for version tags
- `main-abc123` for commit SHA
- `latest` for main branch
- `pr-123` for pull requests

## Verification

### Test the Setup

1. **Create a test PR or push to a branch**:
   ```bash
   git checkout -b test-ci
   git commit --allow-empty -m "Test CI/CD"
   git push origin test-ci
   ```

2. **Check the GitHub Actions workflow logs**

3. **Verify the image appears in Artifact Registry**:
   ```bash
   gcloud artifacts docker images list \
     $LOCATION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY
   ```

### Example Commands

```bash
# List all images
gcloud artifacts docker images list \
  $LOCATION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY

# Pull and test the image
docker pull $LOCATION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/scim-integration:latest

# Test the image
docker run --rm $LOCATION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/scim-integration:latest --help
```

## Advanced Configuration

### Custom Build Arguments

Add build arguments to the workflow:

```yaml
# In .github/workflows/docker-build-push.yml
- name: Build and push Docker image
  uses: docker/build-push-action@v5
  with:
    build-args: |
      VERSION=${{ github.sha }}
      BUILD_DATE=${{ steps.meta.outputs.labels['org.opencontainers.image.created'] }}
      CUSTOM_ARG=value
```

### Multiple Repositories

Create separate workflows for different components:

```bash
# Create additional repositories
gcloud artifacts repositories create scim-worker \
  --repository-format=docker \
  --location=$LOCATION \
  --project=$PROJECT_ID

gcloud artifacts repositories create scim-api \
  --repository-format=docker \
  --location=$LOCATION \
  --project=$PROJECT_ID
```

### Regional Replication

```bash
# Enable multi-regional replication
gcloud artifacts repositories update $REPOSITORY \
  --location=$LOCATION \
  --description="Multi-region repository" \
  --project=$PROJECT_ID
```

## Troubleshooting

### Common Issues

1. **Authentication Failed**:
   ```bash
   # Check the attribute condition in the provider
   gcloud iam workload-identity-pools providers describe $PROVIDER_NAME \
     --location=global \
     --workload-identity-pool=$POOL_NAME \
     --project=$PROJECT_ID
   ```

2. **Permission Denied**:
   ```bash
   # Check service account permissions
   gcloud projects get-iam-policy $PROJECT_ID \
     --flatten="bindings[].members" \
     --format='table(bindings.role)' \
     --filter="bindings.members:$SERVICE_ACCOUNT_EMAIL"
   ```

3. **Invalid Provider**:
   ```bash
   # Verify the provider name format
   echo $WORKLOAD_IDENTITY_PROVIDER
   # Should be: projects/PROJECT_ID/locations/global/workloadIdentityPools/POOL_NAME/providers/PROVIDER_NAME
   ```

### Debug Commands

```bash
# List workload identity pools
gcloud iam workload-identity-pools list --location=global --project=$PROJECT_ID

# List providers
gcloud iam workload-identity-pools providers list \
  --workload-identity-pool=$POOL_NAME \
  --location=global \
  --project=$PROJECT_ID

# Check service account IAM policy
gcloud iam service-accounts get-iam-policy $SERVICE_ACCOUNT_EMAIL --project=$PROJECT_ID

# Test authentication from local machine
gcloud auth print-identity-token \
  --audiences="https://iam.googleapis.com/$WORKLOAD_IDENTITY_PROVIDER"
```

### Validation Script

```bash
#!/bin/bash
# validate-gcp-setup.sh

set -e

echo "Validating Google Cloud CI/CD setup..."

# Check if APIs are enabled
echo "Checking APIs..."
for api in iam.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com; do
  if gcloud services list --enabled --filter="name:$api" --format="value(name)" --project=$PROJECT_ID | grep -q $api; then
    echo "✓ $api enabled"
  else
    echo "✗ $api not enabled"
    exit 1
  fi
done

# Check repository exists
if gcloud artifacts repositories describe $REPOSITORY --location=$LOCATION --project=$PROJECT_ID &>/dev/null; then
  echo "✓ Artifact Registry repository exists"
else
  echo "✗ Artifact Registry repository not found"
  exit 1
fi

# Check service account
if gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL --project=$PROJECT_ID &>/dev/null; then
  echo "✓ Service account exists"
else
  echo "✗ Service account not found"
  exit 1
fi

# Check Workload Identity pool
if gcloud iam workload-identity-pools describe $POOL_NAME --location=global --project=$PROJECT_ID &>/dev/null; then
  echo "✓ Workload Identity pool exists"
else
  echo "✗ Workload Identity pool not found"
  exit 1
fi

# Check provider
if gcloud iam workload-identity-pools providers describe $PROVIDER_NAME \
   --workload-identity-pool=$POOL_NAME --location=global --project=$PROJECT_ID &>/dev/null; then
  echo "✓ Workload Identity provider exists"
else
  echo "✗ Workload Identity provider not found"
  exit 1
fi

echo "✓ All checks passed!"
```

## Security Best Practices

### Principle of Least Privilege

```bash
# Create custom role with minimal permissions
gcloud iam roles create artifactRegistryMinimal \
  --project=$PROJECT_ID \
  --title="Artifact Registry Minimal" \
  --description="Minimal permissions for pushing to Artifact Registry" \
  --permissions="artifactregistry.repositories.uploadArtifacts,artifactregistry.tags.create,artifactregistry.tags.update"

# Use the custom role instead of artifactregistry.writer
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="projects/$PROJECT_ID/roles/artifactRegistryMinimal"
```

### Audit and Monitoring

```bash
# Enable audit logs
gcloud logging sinks create artifact-registry-audit \
  bigquery.googleapis.com/projects/$PROJECT_ID/datasets/audit_logs \
  --log-filter='protoPayload.serviceName="artifactregistry.googleapis.com"' \
  --project=$PROJECT_ID

# Create alerting policy for unauthorized access
gcloud alpha monitoring policies create --policy-from-file=alert-policy.yaml --project=$PROJECT_ID
```

### Regular Cleanup

```bash
# Clean up old images (keep last 10 versions)
gcloud artifacts packages list \
  --repository=$REPOSITORY \
  --location=$LOCATION \
  --project=$PROJECT_ID \
  --format="value(name)" | while read package; do
  gcloud artifacts versions list \
    --package=$package \
    --repository=$REPOSITORY \
    --location=$LOCATION \
    --project=$PROJECT_ID \
    --sort-by="~createTime" \
    --format="value(name)" \
    --limit=999 | tail -n +11 | while read version; do
    gcloud artifacts versions delete $version \
      --package=$package \
      --repository=$REPOSITORY \
      --location=$LOCATION \
      --project=$PROJECT_ID \
      --quiet
  done
done
```

## Cost Optimization

### Artifact Registry Pricing

- Storage: $0.10 per GB per month
- Network egress: Standard GCP rates
- No charges for image pulls within same region

### Cost Reduction Tips

1. **Use lifecycle policies**:
   ```bash
   # Delete images older than 30 days
   gcloud artifacts packages list --repository=$REPOSITORY --location=$LOCATION --project=$PROJECT_ID \
     --filter="createTime<-P30D" --format="value(name)" | \
     xargs -I {} gcloud artifacts packages delete {} --repository=$REPOSITORY --location=$LOCATION --project=$PROJECT_ID --quiet
   ```

2. **Choose optimal region**: Use same region as your Kubernetes cluster

3. **Minimize image size**: Use multi-stage builds and minimal base images

4. **Regular cleanup**: Implement automated cleanup of old images

## Next Steps

After completing the Google Cloud setup:
1. Test the workflow with a sample commit
2. Update your Helm chart to use the new registry
3. Set up monitoring and alerting
4. Implement automated cleanup policies
5. Document the process for your team