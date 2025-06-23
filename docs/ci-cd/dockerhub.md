# Docker Hub CI/CD Setup

This guide covers setting up GitHub Actions to build and push Docker images to Docker Hub using access tokens for secure authentication.

## Prerequisites

- Docker Hub account
- GitHub repository with admin access

## Setup Steps

### Step 1: Create Docker Hub Repository

1. **Log in to Docker Hub**: Go to [hub.docker.com](https://hub.docker.com)

2. **Create Repository**:
   - Click "Create Repository"
   - Repository name: `scim-integration`
   - Visibility: Public or Private
   - Description: "TimeCamp SCIM Integration"

### Step 2: Create Docker Hub Access Token

1. **Go to Account Settings**: Click your username → Account Settings

2. **Security Tab**: Click "Security" in the left sidebar

3. **Create New Access Token**:
   - Description: "GitHub Actions CI/CD"
   - Permissions: "Read, Write, Delete" (or "Read, Write" for minimal permissions)
   - Click "Generate"
   - **Copy the token immediately** (you won't see it again)

### Step 3: Configure GitHub Repository Secrets

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions → Secrets):

```bash
DOCKERHUB_USERNAME=your-dockerhub-username
DOCKERHUB_TOKEN=your-access-token-from-step-2
```

## GitHub Actions Workflow

Create `.github/workflows/docker-build-push-dockerhub.yml`:

```yaml
name: Build and Push to Docker Hub

on:
  push:
    branches:
      - main
      - develop
    tags:
      - 'v*'
  pull_request:
    branches:
      - main
      - develop

env:
  DOCKERHUB_USERNAME: ${{ secrets.DOCKERHUB_USERNAME }}
  IMAGE_NAME: scim-integration

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Docker Hub
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      
      - name: Generate Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.DOCKERHUB_USERNAME }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            type=sha,prefix={{branch}}-
            type=raw,value=latest,enable={{is_default_branch}}
      
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            BUILD_DATE=${{ fromJSON(steps.meta.outputs.json).labels['org.opencontainers.image.created'] }}
            VCS_REF=${{ github.sha }}
            VERSION=${{ fromJSON(steps.meta.outputs.json).labels['org.opencontainers.image.version'] }}
      
      - name: Generate image digest output
        if: github.event_name != 'pull_request'
        run: |
          echo "### Docker Image Published 🚀" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Repository:** \`${{ env.DOCKERHUB_USERNAME }}/${{ env.IMAGE_NAME }}\`" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Tags:**" >> $GITHUB_STEP_SUMMARY
          echo "${{ steps.meta.outputs.tags }}" | sed 's/^/- /' >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Pull command:**" >> $GITHUB_STEP_SUMMARY
          echo "\`\`\`bash" >> $GITHUB_STEP_SUMMARY
          echo "docker pull ${{ env.DOCKERHUB_USERNAME }}/${{ env.IMAGE_NAME }}:latest" >> $GITHUB_STEP_SUMMARY
          echo "\`\`\`" >> $GITHUB_STEP_SUMMARY
```

## Alternative: Using Variables for Username

You can also use repository variables for the username:

### Variables (Settings → Secrets and variables → Actions → Variables)
```bash
DOCKERHUB_USERNAME=your-dockerhub-username
```

### Secrets (Settings → Secrets and variables → Actions → Secrets)
```bash
DOCKERHUB_TOKEN=your-access-token
```

Then update the workflow:

```yaml
env:
  DOCKERHUB_USERNAME: ${{ vars.DOCKERHUB_USERNAME }}
```

## Verification

### Test the Setup

1. **Push a test commit**:
   ```bash
   git checkout -b test-dockerhub-ci
   git commit --allow-empty -m "Test Docker Hub CI/CD"
   git push origin test-dockerhub-ci
   ```

2. **Check the workflow logs** in GitHub Actions

3. **Verify the image on Docker Hub**:
   - Go to your Docker Hub repository
   - Check the "Tags" tab for new images

### Pull and Test Image

```bash
# Pull the image
docker pull your-username/scim-integration:latest

# Test the image
docker run --rm your-username/scim-integration:latest --help

# Check image details
docker image inspect your-username/scim-integration:latest
```

## Advanced Configuration

### Multi-Stage Build Optimization

```dockerfile
# Example optimized Dockerfile
FROM python:3.11-slim as builder

# Install dependencies in builder stage
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim
WORKDIR /app

# Copy only necessary files
COPY --from=builder /root/.local /root/.local
COPY . .

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

CMD ["python", "--help"]
```

### Repository-Specific Workflow

For organizations with multiple repositories:

```yaml
name: Build and Push to Docker Hub

on:
  push:
    branches: [main, develop]
    tags: ['v*']
  pull_request:
    branches: [main, develop]

env:
  REGISTRY: docker.io
  NAMESPACE: ${{ vars.DOCKERHUB_USERNAME || github.repository_owner }}
  IMAGE_NAME: ${{ github.event.repository.name }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Docker Hub
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ vars.DOCKERHUB_USERNAME || github.repository_owner }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.NAMESPACE }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            type=sha,prefix={{branch}}-
            type=raw,value=latest,enable={{is_default_branch}}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

## Security Best Practices

### Access Token Management

1. **Use Fine-Grained Tokens**: Create tokens with minimal required permissions
2. **Regular Rotation**: Rotate access tokens every 90 days
3. **Monitor Usage**: Check Docker Hub access logs regularly
4. **Separate Tokens**: Use different tokens for different projects

### Token Rotation Script

```bash
#!/bin/bash
# rotate-dockerhub-token.sh

# This script helps rotate Docker Hub access tokens
echo "Docker Hub Token Rotation Guide"
echo "1. Go to https://hub.docker.com/settings/security"
echo "2. Create new access token with same permissions"
echo "3. Update GitHub repository secrets"
echo "4. Test the new token with a test push"
echo "5. Delete the old token from Docker Hub"
echo ""
echo "GitHub Secrets to update:"
echo "- DOCKERHUB_TOKEN"
```

### Repository Permissions

For private repositories, configure access:

```bash
# Docker Hub repository settings
# 1. Go to your repository on Docker Hub
# 2. Click "Settings" tab
# 3. Configure "Collaborators" for team access
# 4. Set "Visibility" (Public/Private)
```

## Docker Hub Features

### Automated Builds (Legacy)

While Docker Hub automated builds are deprecated, you can still use webhooks:

```yaml
# Add webhook notification to workflow
- name: Notify Docker Hub
  if: github.event_name != 'pull_request'
  run: |
    curl -X POST "${{ secrets.DOCKERHUB_WEBHOOK_URL }}" \
      -H "Content-Type: application/json" \
      -d '{"push_data":{"tag":"${{ github.ref_name }}"}}'
```

### Repository Webhooks

Set up webhooks for downstream automation:

1. Go to your Docker Hub repository
2. Click "Webhooks" tab
3. Add webhook URL for your deployment system
4. Configure trigger events (push, etc.)

## Rate Limits and Quotas

### Docker Hub Limits

- **Anonymous pulls**: 100 pulls per 6 hours per IP
- **Authenticated pulls**: 200 pulls per 6 hours (free account)
- **Private repositories**: Limited by plan
- **Parallel builds**: Limited by plan

### Avoiding Rate Limits

```yaml
# Use Docker Layer Caching
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    cache-from: type=registry,ref=${{ env.DOCKERHUB_USERNAME }}/${{ env.IMAGE_NAME }}:cache
    cache-to: type=registry,ref=${{ env.DOCKERHUB_USERNAME }}/${{ env.IMAGE_NAME }}:cache,mode=max
```

## Monitoring and Analytics

### Docker Hub Insights

1. **Repository Analytics**: View pull statistics
2. **Vulnerability Scanning**: Available for paid plans
3. **Usage Metrics**: Track downloads and usage patterns

### Custom Monitoring

```yaml
# Add monitoring step to workflow
- name: Report metrics
  if: github.event_name != 'pull_request'
  run: |
    # Send metrics to your monitoring system
    curl -X POST "${{ secrets.METRICS_WEBHOOK }}" \
      -H "Content-Type: application/json" \
      -d '{
        "event": "docker_push",
        "repository": "${{ env.DOCKERHUB_USERNAME }}/${{ env.IMAGE_NAME }}",
        "tag": "${{ github.ref_name }}",
        "commit": "${{ github.sha }}"
      }'
```

## Troubleshooting

### Common Issues

1. **Authentication Failed**:
   ```bash
   # Check token validity
   docker login --username your-username --password your-token
   
   # Test token with API
   curl -u "your-username:your-token" https://hub.docker.com/v2/user/
   ```

2. **Rate Limit Exceeded**:
   ```bash
   # Check rate limit status
   TOKEN=$(curl -s -H "Content-Type: application/json" \
     -X POST -d '{"username": "your-username", "password": "your-token"}' \
     https://hub.docker.com/v2/users/login/ | jq -r .token)
   
   curl -H "Authorization: JWT ${TOKEN}" \
     https://hub.docker.com/v2/users/your-username/
   ```

3. **Image Push Failed**:
   ```bash
   # Check repository exists
   curl -s https://hub.docker.com/v2/repositories/your-username/scim-integration/
   
   # Verify image size (Docker Hub has limits)
   docker images your-username/scim-integration:latest
   ```

### Debug Commands

```bash
# Test Docker Hub connectivity
docker run --rm appropriate/curl -s https://hub.docker.com/

# Check image layers
docker history your-username/scim-integration:latest

# Inspect image manifest
docker manifest inspect your-username/scim-integration:latest

# Test multi-arch support
docker buildx imagetools inspect your-username/scim-integration:latest
```

### Validation Script

```bash
#!/bin/bash
# validate-dockerhub-setup.sh

set -e

REPO="$DOCKERHUB_USERNAME/scim-integration"

echo "Validating Docker Hub CI/CD setup..."

# Test authentication
if docker login --username "$DOCKERHUB_USERNAME" --password "$DOCKERHUB_TOKEN" &>/dev/null; then
  echo "✓ Docker Hub authentication successful"
else
  echo "✗ Docker Hub authentication failed"
  exit 1
fi

# Check repository exists
if curl -s "https://hub.docker.com/v2/repositories/$REPO/" | grep -q '"name"'; then
  echo "✓ Repository exists on Docker Hub"
else
  echo "✗ Repository not found on Docker Hub"
  exit 1
fi

# Check for recent images
if docker pull "$REPO:latest" &>/dev/null; then
  echo "✓ Latest image available"
else
  echo "✗ Latest image not found"
fi

echo "✓ All checks passed!"
```

## Cost Considerations

### Docker Hub Pricing

- **Free Plan**: 1 private repository, unlimited public repositories
- **Pro Plan**: $5/month for unlimited private repositories
- **Team Plan**: $25/month for organizations

### Cost Optimization

1. **Use public repositories** when possible
2. **Optimize image size** to reduce transfer costs
3. **Implement lifecycle policies** manually or via scripts
4. **Monitor usage** to avoid unexpected charges

## Integration with Helm

Update your Helm values to use Docker Hub:

```yaml
image:
  registry: docker.io  # or omit for default
  repository: your-username/scim-integration
  tag: "latest"

# No special authentication needed for public images
# For private images in Kubernetes:
imagePullSecrets:
  - name: dockerhub-secret
```

Create image pull secret for private repositories:

```bash
kubectl create secret docker-registry dockerhub-secret \
  --docker-server=docker.io \
  --docker-username=your-username \
  --docker-password=your-token \
  --docker-email=your-email@example.com
```

## Next Steps

After completing the Docker Hub setup:
1. Test the workflow with a sample commit
2. Update your Helm chart to use Docker Hub registry
3. Set up monitoring for pull statistics
4. Implement automated cleanup of old tags
5. Consider upgrading to paid plan for private repositories if needed