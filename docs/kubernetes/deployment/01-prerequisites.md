# Prerequisites

This document outlines the system requirements and prerequisites for deploying the TimeCamp SCIM integration.

## Infrastructure Requirements

### Kubernetes Cluster

- **Kubernetes Version**: 1.24+
- **Node Requirements**:
  - Minimum 2 nodes
  - 2 vCPU and 4 GB RAM per node
  - Container runtime (containerd/Docker)
- **Cluster Features**:
  - LoadBalancer support (for ingress)
  - Persistent Volume support (if not using S3)
  - Network policies support (recommended)

### Cloud Provider Requirements

#### Google Cloud Platform (GKE)
- **Required APIs**:
  - Kubernetes Engine API
  - Secret Manager API
  - Artifact Registry API (for Docker images)
  - IAM API
- **Permissions**:
  - Workload Identity enabled on cluster
  - Service account with appropriate roles

#### Amazon Web Services (EKS)
- **Required Services**:
  - EKS cluster
  - IAM roles for service accounts (IRSA)
  - AWS Secrets Manager or Systems Manager Parameter Store
  - ECR or external container registry
- **Permissions**:
  - EKS cluster admin access
  - Secrets Manager read access

#### Microsoft Azure (AKS)
- **Required Services**:
  - AKS cluster
  - Azure Key Vault
  - Azure Container Registry (ACR)
  - Workload Identity or Pod Identity
- **Permissions**:
  - AKS cluster admin access
  - Key Vault access policies

### External Secrets Operator

The deployment requires External Secrets Operator to be pre-installed in your cluster.

#### Installation
```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace \
  --set installCRDs=true
```

#### Verification
```bash
kubectl get pods -n external-secrets-system
kubectl get crd | grep external-secrets
```

## S3-Compatible Storage

The integration requires S3-compatible storage for sharing files between jobs.

### Supported Providers
- **MinIO** (recommended for on-premises)
- **AWS S3**
- **Google Cloud Storage** (with S3 compatibility)
- **Azure Blob Storage** (with S3 compatibility)
- **DigitalOcean Spaces**
- **Any S3-compatible storage**

### MinIO Setup (Self-Hosted)
```bash
helm repo add minio https://charts.min.io/
helm repo update

helm install minio minio/minio \
  --namespace minio \
  --create-namespace \
  --set auth.rootUser=admin \
  --set auth.rootPassword=password123 \
  --set defaultBuckets="scim-data"
```

### AWS S3 Setup
1. Create S3 bucket: `scim-data`
2. Create IAM user with S3 access
3. Store credentials in secret management system

## Tools and Dependencies

### Required Tools
- **kubectl**: Kubernetes command-line tool
- **helm**: Helm 3.x for chart deployment
- **Cloud CLI**: gcloud, aws, or az depending on provider

### Installation Scripts
```bash
# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# gcloud (for GCP)
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
```

## HR System Access

Ensure you have access credentials for your HR system:

### BambooHR
- API key from BambooHR admin panel
- Subdomain name

### Azure AD / Entra ID
- Tenant ID
- Client ID and Secret
- Appropriate Graph API permissions

### LDAP
- LDAP server hostname/IP
- Bind DN and credentials
- Search base DN

### FactorialHR
- API key from Factorial admin panel
- API endpoint URL

## TimeCamp API Access

- **TimeCamp API Key**: Obtain from TimeCamp account settings
- **Root Group ID**: Optional, specific group to sync under
- **API Rate Limits**: Ensure account has sufficient API quota

## Network Requirements

### Outbound Connectivity
The Kubernetes cluster needs outbound access to:
- HR system APIs (BambooHR, Azure AD, etc.)
- TimeCamp API (`api.timecamp.com`)
- Container registries
- Secret management services
- S3 storage endpoints

### Firewall Rules
```bash
# TimeCamp API
443/tcp -> api.timecamp.com

# HR Systems (examples)
443/tcp -> api.bamboohr.com
443/tcp -> graph.microsoft.com
389/tcp or 636/tcp -> your-ldap-server
443/tcp -> api.factorialhr.com

# Cloud Provider APIs
443/tcp -> secretmanager.googleapis.com (GCP)
443/tcp -> secretsmanager.amazonaws.com (AWS)
443/tcp -> vault.azure.net (Azure)
```

## Security Considerations

### Secret Management
- Never store secrets in plain text
- Use external secret management (Google Secret Manager, AWS Secrets Manager, etc.)
- Rotate secrets regularly
- Use least-privilege access principles

### Network Security
- Enable network policies in Kubernetes
- Use private endpoints where available
- Implement proper RBAC
- Regular security audits

### Data Protection
- Enable encryption at rest for S3 storage
- Use TLS for all API communications
- Implement proper backup strategies
- Consider data residency requirements

## Validation Checklist

Before proceeding to installation, verify:

- [ ] Kubernetes cluster is running and accessible
- [ ] External Secrets Operator is installed
- [ ] S3-compatible storage is configured
- [ ] HR system credentials are available
- [ ] TimeCamp API access is confirmed
- [ ] Required cloud provider APIs are enabled
- [ ] Network connectivity is verified
- [ ] Secret management system is ready

## Next Steps

After meeting all prerequisites:
1. Review [cluster requirements](../kubernetes/cluster-requirements.md)
2. Set up [secret store](../secret-stores/) of your choice
3. Proceed to [Helm installation](02-helm-installation.md)