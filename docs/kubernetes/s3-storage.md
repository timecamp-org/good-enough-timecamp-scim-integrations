# S3-Compatible Storage Configuration

This guide covers setting up S3-compatible storage for the TimeCamp SCIM integration to share data files between different job types.

## Overview

The SCIM integration uses S3-compatible storage to share intermediate JSON files between jobs:
- **Fetch jobs** write `users.json` to S3
- **Prepare jobs** read `users.json` and write `timecamp_users.json`
- **Sync jobs** read `timecamp_users.json` to sync with TimeCamp

## Supported Storage Providers

### MinIO (Self-Hosted)
- **Best for**: On-premises deployments, full control
- **Pros**: Full S3 compatibility, self-hosted, no egress costs
- **Cons**: Requires maintenance, storage management

### AWS S3
- **Best for**: AWS-based deployments
- **Pros**: Fully managed, high durability, global availability
- **Cons**: Data egress costs, vendor lock-in

### Google Cloud Storage
- **Best for**: GCP-based deployments
- **Pros**: Fully managed, integrated with GCP
- **Cons**: Requires S3 compatibility mode

### Azure Blob Storage
- **Best for**: Azure-based deployments
- **Pros**: Fully managed, integrated with Azure
- **Cons**: Limited S3 compatibility

## MinIO Setup (Recommended)

### Install MinIO with Helm

```bash
# Add MinIO Helm repository
helm repo add minio https://charts.min.io/
helm repo update

# Create namespace
kubectl create namespace minio

# Install MinIO
helm install minio minio/minio \
  --namespace minio \
  --set auth.rootUser=admin \
  --set auth.rootPassword="SecurePassword123!" \
  --set defaultBuckets="scim-data" \
  --set persistence.size=10Gi \
  --set service.type=ClusterIP
```

### Create Storage User

```bash
# Port forward to MinIO console
kubectl port-forward svc/minio-console 9001:9001 -n minio

# Access MinIO console at http://localhost:9001
# Login with admin/SecurePassword123!

# Create bucket 'scim-data' via console
# Create access key for SCIM integration
```

### Alternative: MinIO with Custom Values

```yaml
# minio-values.yaml
auth:
  rootUser: admin
  rootPassword: "SecurePassword123!"

defaultBuckets: "scim-data"

persistence:
  enabled: true
  size: 20Gi
  storageClass: "fast-ssd"

service:
  type: ClusterIP
  port: 9000

consoleService:
  type: LoadBalancer

resources:
  requests:
    memory: 256Mi
    cpu: 100m
  limits:
    memory: 1Gi
    cpu: 500m

# Security context
securityContext:
  enabled: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
```

```bash
helm install minio minio/minio \
  --namespace minio \
  --values minio-values.yaml
```

## AWS S3 Setup

### Create S3 Bucket

```bash
export BUCKET_NAME="scim-data-$(date +%s)"
export AWS_REGION="us-east-1"

# Create bucket
aws s3 mb s3://$BUCKET_NAME --region $AWS_REGION

# Configure bucket policy for least privilege
cat <<EOF > bucket-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT-ID:user/scim-user"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
    },
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT-ID:user/scim-user"
      },
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::$BUCKET_NAME"
    }
  ]
}
EOF

aws s3api put-bucket-policy \
  --bucket $BUCKET_NAME \
  --policy file://bucket-policy.json
```

### Create IAM User

```bash
# Create IAM user
aws iam create-user --user-name scim-s3-user

# Create policy
cat <<EOF > s3-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::$BUCKET_NAME",
        "arn:aws:s3:::$BUCKET_NAME/*"
      ]
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name SCIMIntegrationS3Policy \
  --policy-document file://s3-policy.json

# Attach policy to user
aws iam attach-user-policy \
  --user-name scim-s3-user \
  --policy-arn arn:aws:iam::ACCOUNT-ID:policy/SCIMIntegrationS3Policy

# Create access key
aws iam create-access-key --user-name scim-s3-user
```

## Google Cloud Storage Setup

### Create Bucket

```bash
export BUCKET_NAME="scim-data-$(date +%s)"
export PROJECT_ID="your-project-id"

# Create bucket
gsutil mb -p $PROJECT_ID gs://$BUCKET_NAME

# Enable S3 compatibility
gsutil web set -m index.html -e 404.html gs://$BUCKET_NAME
```

### Create Service Account

```bash
# Create service account
gcloud iam service-accounts create scim-storage-sa \
  --display-name="SCIM Storage Service Account"

# Grant storage permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:scim-storage-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

# Create HMAC key for S3 compatibility
gcloud auth activate-service-account \
  scim-storage-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --key-file=path/to/service-account-key.json

gsutil hmac create scim-storage-sa@$PROJECT_ID.iam.gserviceaccount.com
```

## Configuration in Helm Chart

### MinIO Configuration

```yaml
# values.yaml
s3:
  enabled: true
  endpointUrl: "http://minio.minio.svc.cluster.local:9000"
  region: "us-east-1"  # Any region for MinIO
  bucketName: "scim-data"
  pathPrefix: ""
  forcePathStyle: true  # Required for MinIO

# In your secrets
{
  "S3_ACCESS_KEY_ID": "your-minio-access-key",
  "S3_SECRET_ACCESS_KEY": "your-minio-secret-key"
}
```

### AWS S3 Configuration

```yaml
# values.yaml
s3:
  enabled: true
  endpointUrl: "https://s3.amazonaws.com"
  region: "us-east-1"
  bucketName: "your-bucket-name"
  pathPrefix: "production/"
  forcePathStyle: false

# In your secrets
{
  "S3_ACCESS_KEY_ID": "AKIA...",
  "S3_SECRET_ACCESS_KEY": "your-aws-secret-key"
}
```

### Google Cloud Storage Configuration

```yaml
# values.yaml
s3:
  enabled: true
  endpointUrl: "https://storage.googleapis.com"
  region: "us-central1"
  bucketName: "your-gcs-bucket"
  pathPrefix: ""
  forcePathStyle: false

# In your secrets
{
  "S3_ACCESS_KEY_ID": "GOOG...",
  "S3_SECRET_ACCESS_KEY": "your-hmac-secret"
}
```

## File Structure in S3

The integration uses this file structure:

```
bucket/
├── [pathPrefix/]
│   ├── users.json              # Raw user data from HR systems
│   ├── timecamp_users.json     # Processed data for TimeCamp
│   └── logs/                   # Optional log files
│       ├── fetch.log
│       ├── prepare.log
│       └── sync.log
```

## Security Best Practices

### Bucket Policies

**MinIO Bucket Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": ["arn:aws:iam:::user/scim-user"]
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": ["arn:aws:s3:::scim-data/*"]
    }
  ]
}
```

### Encryption

**AWS S3 Encryption**:
```bash
# Enable default encryption
aws s3api put-bucket-encryption \
  --bucket $BUCKET_NAME \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }
    ]
  }'
```

**MinIO Encryption**:
```bash
# Enable encryption at rest
mc admin config set myminio server_side_encryption_master_key="my-encryption-key"
mc admin service restart myminio
```

### Access Control

**Network Policies** (for MinIO):
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: minio-access
  namespace: minio
spec:
  podSelector:
    matchLabels:
      app: minio
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: scim  # Only allow access from SCIM namespace
    ports:
    - protocol: TCP
      port: 9000
```

## Monitoring and Logging

### MinIO Monitoring

```bash
# Enable MinIO Prometheus metrics
mc admin prometheus generate myminio

# View metrics
kubectl port-forward svc/minio 9000:9000 -n minio
curl http://localhost:9000/minio/v2/metrics/cluster
```

### AWS S3 Monitoring

```bash
# Enable CloudTrail for S3 API calls
aws cloudtrail create-trail \
  --name scim-s3-trail \
  --s3-bucket-name cloudtrail-logs-bucket \
  --include-global-service-events

# Enable CloudWatch metrics
aws s3api put-bucket-metrics-configuration \
  --bucket $BUCKET_NAME \
  --id EntireBucket \
  --metrics-configuration Id=EntireBucket,Status=Enabled
```

## Backup and Disaster Recovery

### MinIO Backup

```bash
# Create backup using mc mirror
mc mirror myminio/scim-data backup-location/scim-data

# Automated backup with CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: minio-backup
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: minio/mc
            command:
            - /bin/sh
            - -c
            - |
              mc alias set source http://minio.minio.svc.cluster.local:9000 $ACCESS_KEY $SECRET_KEY
              mc mirror source/scim-data /backup/$(date +%Y%m%d)
          restartPolicy: OnFailure
```

### AWS S3 Cross-Region Replication

```bash
# Enable versioning (required for replication)
aws s3api put-bucket-versioning \
  --bucket $BUCKET_NAME \
  --versioning-configuration Status=Enabled

# Create replication configuration
cat <<EOF > replication-config.json
{
  "Role": "arn:aws:iam::ACCOUNT-ID:role/replication-role",
  "Rules": [
    {
      "Status": "Enabled",
      "Priority": 1,
      "Filter": {},
      "Destination": {
        "Bucket": "arn:aws:s3:::backup-bucket"
      }
    }
  ]
}
EOF

aws s3api put-bucket-replication \
  --bucket $BUCKET_NAME \
  --replication-configuration file://replication-config.json
```

## Troubleshooting

### Common Issues

1. **Connection Timeouts**:
   ```bash
   # Test connectivity from pod
   kubectl run s3-test --image=amazon/aws-cli --rm -it -- \
     aws s3 ls s3://your-bucket --endpoint-url=http://your-endpoint
   ```

2. **Permission Denied**:
   ```bash
   # Check bucket policy
   aws s3api get-bucket-policy --bucket $BUCKET_NAME
   
   # Test with MinIO client
   mc ls myminio/scim-data
   ```

3. **SSL/TLS Issues**:
   ```yaml
   # Disable SSL for development
   s3:
     endpointUrl: "http://minio.minio.svc.cluster.local:9000"
     forcePathStyle: true
   ```

### Debug Commands

```bash
# Test S3 from SCIM pod
kubectl run debug --image=your-scim-image --rm -it -- \
  python -c "
import boto3
s3 = boto3.client('s3',
    endpoint_url='http://minio.minio.svc.cluster.local:9000',
    aws_access_key_id='admin',
    aws_secret_access_key='password')
print(s3.list_buckets())
"

# Check MinIO logs
kubectl logs deployment/minio -n minio -f

# Test file operations
kubectl exec -it deployment/scim-integration -- \
  python -c "
import os
print('S3_ENDPOINT_URL:', os.getenv('S3_ENDPOINT_URL'))
print('S3_BUCKET_NAME:', os.getenv('S3_BUCKET_NAME'))
"
```

## Performance Tuning

### MinIO Performance

```yaml
# High-performance MinIO configuration
resources:
  requests:
    cpu: 2
    memory: 4Gi
  limits:
    cpu: 4
    memory: 8Gi

# Use SSD storage class
persistence:
  storageClass: "fast-ssd"
  size: 100Gi

# Multiple replicas for HA
replicas: 4
```

### S3 Transfer Optimization

```yaml
# Environment variables for better performance
env:
  AWS_S3_MAX_CONCURRENT_REQUESTS: "20"
  AWS_S3_MAX_QUEUE_SIZE: "2000"
  AWS_S3_MULTIPART_THRESHOLD: "64MB"
  AWS_S3_MULTIPART_CHUNKSIZE: "16MB"
```

## Cost Optimization

### AWS S3 Cost Optimization

```bash
# Set lifecycle policy
cat <<EOF > lifecycle-policy.json
{
  "Rules": [
    {
      "ID": "DeleteOldFiles",
      "Status": "Enabled",
      "Filter": {},
      "Expiration": {
        "Days": 30
      }
    }
  ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
  --bucket $BUCKET_NAME \
  --lifecycle-configuration file://lifecycle-policy.json
```

### MinIO Storage Optimization

```bash
# Set object lifecycle
mc ilm add myminio/scim-data --expiry-days 30

# Enable compression
mc admin config set myminio compression enable=on
```

## Next Steps

After setting up S3 storage:
1. Update your Helm values with S3 configuration
2. Add S3 credentials to your secret store
3. Deploy the SCIM integration
4. Test file operations with a manual job