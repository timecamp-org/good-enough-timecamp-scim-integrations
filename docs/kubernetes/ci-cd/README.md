# CI/CD Documentation

This directory contains documentation for setting up Continuous Integration and Continuous Deployment pipelines for the SCIM integration.

## Overview

The project includes GitHub Actions workflows for building and pushing Docker images to various container registries. This documentation covers how to configure these workflows for different cloud providers and container registries.

## Available Guides

- **[google-cloud.md](google-cloud.md)** - Google Cloud Platform setup with Artifact Registry and Workload Identity Federation
- **[aws.md](aws.md)** - Amazon Web Services setup with ECR and OIDC
- **[azure.md](azure.md)** - Microsoft Azure setup with ACR and Workload Identity
- **[dockerhub.md](dockerhub.md)** - Docker Hub setup with username/password or access tokens
- **[github-packages.md](github-packages.md)** - GitHub Container Registry setup

## Quick Start

1. Choose your container registry provider
2. Follow the specific setup guide for your provider
3. Configure the required GitHub secrets and variables
4. The workflow will automatically build and push images on:
   - Push to `main` or `develop` branches
   - Creation of version tags (`v*`)
   - Pull requests (build only, no push)

## Workflow Features

The GitHub Actions workflow provides:

- **Multi-architecture builds**: linux/amd64 and linux/arm64
- **Automatic tagging**: Based on git branches, tags, and commits
- **Build caching**: Using GitHub Actions cache for faster builds
- **Security**: Keyless authentication using OIDC where supported
- **Conditional deployment**: Only pushes on main branch and tags

## Supported Container Registries

| Provider | Authentication | Multi-arch | Cost |
|----------|---------------|------------|------|
| Google Artifact Registry | Workload Identity (OIDC) | ✅ | Pay per GB |
| AWS ECR | OIDC + IAM Roles | ✅ | Pay per GB |
| Azure ACR | Workload Identity | ✅ | Pay per GB |
| Docker Hub | Username/Token | ✅ | Free tier available |
| GitHub Packages | GITHUB_TOKEN | ✅ | Free for public repos |

## Environment Variables

The workflow uses these configurable variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Google Cloud Project ID | - |
| `GAR_LOCATION` | Artifact Registry location | `us-central1` |
| `GAR_REPOSITORY` | Artifact Registry repository | `docker-images` |
| `AWS_REGION` | AWS region for ECR | `us-east-1` |
| `ECR_REPOSITORY` | ECR repository name | `scim-integration` |
| `AZURE_REGISTRY` | Azure Container Registry name | - |
| `DOCKERHUB_USERNAME` | Docker Hub username | - |

## Security Best Practices

1. **Use OIDC when available**: Eliminates need for long-lived credentials
2. **Minimal permissions**: Grant only necessary permissions for pushing images
3. **Short-lived tokens**: Use temporary credentials where possible
4. **Secret rotation**: Regularly rotate access keys and tokens
5. **Audit access**: Monitor who accesses container registries

## Troubleshooting

### Common Issues

1. **Authentication failures**: Check OIDC configuration and permissions
2. **Build failures**: Verify Dockerfile and build context
3. **Push failures**: Check registry permissions and quotas
4. **Multi-arch failures**: Ensure base images support target architectures

### Debug Steps

1. **Check workflow logs**: Review GitHub Actions logs for detailed errors
2. **Verify credentials**: Test authentication outside of workflow
3. **Test locally**: Use Docker buildx to test multi-arch builds
4. **Check quotas**: Ensure registry storage and rate limits aren't exceeded

## Migration Between Providers

If you need to migrate between container registries:

1. Update the workflow configuration
2. Configure new registry authentication
3. Update Helm values to point to new registry
4. Test the new setup with a test build
5. Update documentation and team knowledge

## Next Steps

1. Choose your container registry provider
2. Follow the provider-specific setup guide
3. Test the workflow with a sample commit
4. Update your Helm chart values to use the new registry
5. Deploy and verify the integration works