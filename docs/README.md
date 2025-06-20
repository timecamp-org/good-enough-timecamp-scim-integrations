# Documentation

This directory contains comprehensive documentation for deploying and configuring the TimeCamp SCIM integration system.

## Directory Structure

- **[deployment/](deployment/)** - Step-by-step deployment guides
  - [01-prerequisites.md](deployment/01-prerequisites.md) - System requirements and prerequisites
  - [02-helm-installation.md](deployment/02-helm-installation.md) - Helm chart installation guide
  - [03-testing-validation.md](deployment/03-testing-validation.md) - Testing and validation procedures

- **[ci-cd/](ci-cd/)** - Continuous Integration and Deployment
  - [README.md](ci-cd/README.md) - CI/CD overview and provider comparison
  - [google-cloud.md](ci-cd/google-cloud.md) - Google Cloud Platform with Artifact Registry
  - [aws.md](ci-cd/aws.md) - Amazon Web Services with ECR
  - [dockerhub.md](ci-cd/dockerhub.md) - Docker Hub setup

- **[secret-stores/](secret-stores/)** - Secret management for different providers
  - [google-secret-manager.md](secret-stores/google-secret-manager.md) - Google Secret Manager setup

- **[kubernetes/](kubernetes/)** - Kubernetes-specific documentation
  - [s3-storage.md](kubernetes/s3-storage.md) - S3-compatible storage configuration

## Quick Start

For a quick deployment, follow these steps:

1. **Prerequisites**: Read [deployment/01-prerequisites.md](deployment/01-prerequisites.md)
2. **CI/CD Setup**: Choose and configure container registry from [ci-cd/](ci-cd/)
3. **Secret Store**: Choose and configure a secret store from [secret-stores/](secret-stores/)
4. **S3 Storage**: Set up S3-compatible storage using [kubernetes/s3-storage.md](kubernetes/s3-storage.md)
5. **Deploy**: Follow the Helm installation guide in [deployment/02-helm-installation.md](deployment/02-helm-installation.md)
6. **Testing**: Validate your deployment using [deployment/03-testing-validation.md](deployment/03-testing-validation.md)

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   HR Systems    │───▶│ SCIM Integration │───▶│   TimeCamp      │
│ (BambooHR, etc) │    │   (Kubernetes)   │    │   (API)         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │  S3 Storage      │
                       │ (Shared Files)   │
                       └──────────────────┘
```

## Support

- For deployment issues, check [deployment/02-helm-installation.md](deployment/02-helm-installation.md)
- For testing and validation, see [deployment/03-testing-validation.md](deployment/03-testing-validation.md)
- For secret management issues, refer to the appropriate guide in [secret-stores/](secret-stores/)
- For Kubernetes issues, see [kubernetes/](kubernetes/) documentation