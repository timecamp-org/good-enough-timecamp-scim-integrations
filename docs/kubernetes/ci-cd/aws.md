# Amazon Web Services CI/CD Setup

This guide covers setting up GitHub Actions to build and push Docker images to Amazon Elastic Container Registry (ECR) using OIDC authentication.

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured
- GitHub repository with admin access

## Setup Steps

### Step 1: Create ECR Repository

```bash
export AWS_REGION="us-east-1"
export ECR_REPOSITORY="scim-integration"

# Create ECR repository
aws ecr create-repository \
  --repository-name $ECR_REPOSITORY \
  --region $AWS_REGION \
  --image-tag-mutability MUTABLE \
  --image-scanning-configuration scanOnPush=true
```

### Step 2: Create OIDC Identity Provider

```bash
# Create OIDC identity provider for GitHub Actions
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  --client-id-list sts.amazonaws.com
```

### Step 3: Create IAM Role for GitHub Actions

```bash
export ROLE_NAME="GitHubActionsECRRole"
export GITHUB_ORG="timecamp-org"
export GITHUB_REPO="good-enough-timecamp-scim-integrations"
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create trust policy
cat <<EOF > trust-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:$GITHUB_ORG/$GITHUB_REPO:*"
        }
      }
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document file://trust-policy.json
```

### Step 4: Create and Attach ECR Policy

```bash
# Create ECR permission policy
cat <<EOF > ecr-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource": "arn:aws:ecr:$AWS_REGION:$ACCOUNT_ID:repository/$ECR_REPOSITORY"
    }
  ]
}
EOF

# Create policy
aws iam create-policy \
  --policy-name ECRPushPolicy \
  --policy-document file://ecr-policy.json

# Attach policy to role
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::$ACCOUNT_ID:policy/ECRPushPolicy
```

### Step 5: Configure GitHub Repository

#### Secrets (Settings → Secrets and variables → Actions → Secrets)
```bash
# Add these secrets to your GitHub repository
AWS_ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME"
```

#### Variables (Settings → Secrets and variables → Actions → Variables)
```bash
# Add these variables to your GitHub repository
AWS_REGION="$AWS_REGION"
ECR_REPOSITORY="$ECR_REPOSITORY"
```

## GitHub Actions Workflow

Create or update `.github/workflows/docker-build-push-aws.yml`:

```yaml
name: Build and Push to AWS ECR

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
  AWS_REGION: ${{ vars.AWS_REGION || 'us-east-1' }}
  ECR_REPOSITORY: ${{ vars.ECR_REPOSITORY || 'scim-integration' }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    
    permissions:
      id-token: write
      contents: read
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}
          role-session-name: GitHubActions
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Generate Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}
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
      
      - name: Generate image digest output
        if: github.event_name != 'pull_request'
        run: |
          echo "### Docker Image Published 🚀" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Registry:** \`${{ steps.login-ecr.outputs.registry }}\`" >> $GITHUB_STEP_SUMMARY
          echo "**Repository:** \`${{ env.ECR_REPOSITORY }}\`" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Tags:**" >> $GITHUB_STEP_SUMMARY
          echo "${{ steps.meta.outputs.tags }}" | sed 's/^/- /' >> $GITHUB_STEP_SUMMARY
```

## Verification

### Test the Setup

1. **Check ECR repository**:
   ```bash
   aws ecr describe-repositories \
     --repository-names $ECR_REPOSITORY \
     --region $AWS_REGION
   ```

2. **Push a test commit**:
   ```bash
   git checkout -b test-aws-ci
   git commit --allow-empty -m "Test AWS CI/CD"
   git push origin test-aws-ci
   ```

3. **Verify images in ECR**:
   ```bash
   aws ecr list-images \
     --repository-name $ECR_REPOSITORY \
     --region $AWS_REGION
   ```

### Pull and Test Image

```bash
# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Pull image
docker pull $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest

# Test image
docker run --rm $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest --help
```

## Advanced Configuration

### Cross-Region Replication

```bash
# Create replication configuration
cat <<EOF > replication-config.json
{
  "rules": [
    {
      "destinations": [
        {
          "region": "us-west-2",
          "registryId": "$ACCOUNT_ID"
        },
        {
          "region": "eu-west-1",
          "registryId": "$ACCOUNT_ID"
        }
      ]
    }
  ]
}
EOF

# Apply replication configuration
aws ecr put-replication-configuration \
  --replication-configuration file://replication-config.json
```

### Lifecycle Policy

```bash
# Create lifecycle policy to manage image retention
cat <<EOF > lifecycle-policy.json
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Keep last 10 production images",
      "selection": {
        "tagStatus": "tagged",
        "tagPrefixList": ["v"],
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": {
        "type": "expire"
      }
    },
    {
      "rulePriority": 2,
      "description": "Delete untagged images older than 1 day",
      "selection": {
        "tagStatus": "untagged",
        "countType": "sinceImagePushed",
        "countUnit": "days",
        "countNumber": 1
      },
      "action": {
        "type": "expire"
      }
    }
  ]
}
EOF

# Apply lifecycle policy
aws ecr put-lifecycle-policy \
  --repository-name $ECR_REPOSITORY \
  --lifecycle-policy-text file://lifecycle-policy.json
```

### Repository Policy

```bash
# Create repository policy for cross-account access
cat <<EOF > repository-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowPull",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::$ACCOUNT_ID:root"
      },
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability"
      ]
    }
  ]
}
EOF

# Apply repository policy
aws ecr set-repository-policy \
  --repository-name $ECR_REPOSITORY \
  --policy-text file://repository-policy.json
```

## Security Best Practices

### Minimal IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource": "arn:aws:ecr:region:account:repository/scim-integration"
    }
  ]
}
```

### Image Scanning

```bash
# Enable image scanning on push
aws ecr put-image-scanning-configuration \
  --repository-name $ECR_REPOSITORY \
  --image-scanning-configuration scanOnPush=true

# Get scan results
aws ecr describe-image-scan-findings \
  --repository-name $ECR_REPOSITORY \
  --image-id imageTag=latest
```

### Encryption

```bash
# Enable encryption at rest (KMS)
aws ecr create-repository \
  --repository-name $ECR_REPOSITORY \
  --encryption-configuration encryptionType=KMS,kmsKey=alias/ecr-key
```

## Monitoring and Logging

### CloudWatch Metrics

```bash
# Create CloudWatch dashboard for ECR
aws cloudwatch put-dashboard \
  --dashboard-name "ECR-SCIM-Integration" \
  --dashboard-body file://dashboard-config.json
```

### CloudTrail Events

```bash
# Enable CloudTrail for ECR events
aws logs create-log-group --log-group-name /aws/ecr/api-calls

# Create event rule for ECR push events
aws events put-rule \
  --name ecr-push-rule \
  --event-pattern '{"source":["aws.ecr"],"detail-type":["ECR Image Action"],"detail":{"action-type":["PUSH"]}}'
```

### Cost Monitoring

```bash
# Set up billing alert for ECR costs
aws budgets create-budget \
  --account-id $ACCOUNT_ID \
  --budget file://ecr-budget.json
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**:
   ```bash
   # Check OIDC provider
   aws iam list-open-id-connect-providers
   
   # Verify role trust policy
   aws iam get-role --role-name $ROLE_NAME
   ```

2. **Permission Denied**:
   ```bash
   # Check attached policies
   aws iam list-attached-role-policies --role-name $ROLE_NAME
   
   # Test ECR access
   aws ecr describe-repositories --repository-names $ECR_REPOSITORY
   ```

3. **Image Push Failures**:
   ```bash
   # Check repository exists
   aws ecr describe-repositories --repository-names $ECR_REPOSITORY
   
   # Test docker login
   aws ecr get-login-password --region $AWS_REGION
   ```

### Debug Commands

```bash
# Test OIDC token (from GitHub Actions)
curl -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
  "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=sts.amazonaws.com"

# Assume role manually
aws sts assume-role-with-web-identity \
  --role-arn arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME \
  --role-session-name test-session \
  --web-identity-token $TOKEN

# Check ECR authorization
aws ecr get-authorization-token --region $AWS_REGION
```

### Validation Script

```bash
#!/bin/bash
# validate-aws-setup.sh

set -e

echo "Validating AWS ECR CI/CD setup..."

# Check ECR repository
if aws ecr describe-repositories --repository-names $ECR_REPOSITORY --region $AWS_REGION &>/dev/null; then
  echo "✓ ECR repository exists"
else
  echo "✗ ECR repository not found"
  exit 1
fi

# Check IAM role
if aws iam get-role --role-name $ROLE_NAME &>/dev/null; then
  echo "✓ IAM role exists"
else
  echo "✗ IAM role not found"
  exit 1
fi

# Check OIDC provider
if aws iam list-open-id-connect-providers | grep -q "token.actions.githubusercontent.com"; then
  echo "✓ OIDC provider configured"
else
  echo "✗ OIDC provider not found"
  exit 1
fi

# Check policies
if aws iam list-attached-role-policies --role-name $ROLE_NAME | grep -q "ECRPushPolicy"; then
  echo "✓ ECR policy attached"
else
  echo "✗ ECR policy not attached"
  exit 1
fi

echo "✓ All checks passed!"
```

## Cost Optimization

### ECR Pricing

- Storage: $0.10 per GB per month
- Data transfer: Standard AWS rates
- No charges for data transfer within same region

### Cost Reduction Tips

1. **Lifecycle policies**: Automatically delete old images
2. **Image compression**: Use multi-stage builds
3. **Regional optimization**: Use same region as EKS cluster
4. **Monitoring**: Set up cost alerts and budgets

```bash
# Create cost budget for ECR
cat <<EOF > ecr-budget.json
{
  "BudgetName": "ECR-Monthly-Budget",
  "BudgetLimit": {
    "Amount": "10.0",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST",
  "CostFilters": {
    "Service": ["Amazon Elastic Container Registry (ECR)"]
  }
}
EOF

aws budgets create-budget \
  --account-id $ACCOUNT_ID \
  --budget file://ecr-budget.json
```

## Integration with Helm

Update your Helm values to use ECR:

```yaml
image:
  registry: 123456789012.dkr.ecr.us-east-1.amazonaws.com
  repository: scim-integration
  tag: "latest"

# For EKS with IRSA
serviceAccount:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/scim-ecr-role
```

## Next Steps

After completing the AWS setup:
1. Test the workflow with a sample commit
2. Update your Helm chart to use ECR registry
3. Set up lifecycle policies for cost optimization
4. Configure monitoring and alerting
5. Implement security scanning workflows