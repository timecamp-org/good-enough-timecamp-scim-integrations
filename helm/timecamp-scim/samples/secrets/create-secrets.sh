#!/bin/bash

# Script to create/update Google Secret Manager secret for TimeCamp SCIM integration
# Usage: ./create-secrets.sh [OPTIONS]
#
# Options:
#   -p, --project PROJECT_ID     Google Cloud Project ID (required)
#   -s, --secret SECRET_NAME     Secret name (default: timecamp-scim-secrets)
#   -f, --file SECRET_FILE       JSON file with secrets (default: timecamp-scim-secrets.json)
#   -a, --sa-name SA_NAME        Service account name (default: timecamp-scim-sa)
#   -h, --help                   Show this help message
#
# Examples:
#   ./create-secrets.sh --project my-project-id
#   ./create-secrets.sh -p my-project-id -s my-secrets -f my-secrets.json

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
SECRET_NAME="scim-secrets"
SECRET_FILE="scim-secrets.json"
SA_NAME="scim-sa"
PROJECT_ID=""

# Function to show help
show_help() {
    echo -e "${BLUE}TimeCamp SCIM Secret Manager Setup${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -p, --project PROJECT_ID     Google Cloud Project ID (required)"
    echo "  -s, --secret SECRET_NAME     Secret name (default: timecamp-scim-secrets)"
    echo "  -f, --file SECRET_FILE       JSON file with secrets (default: timecamp-scim-secrets.json)"
    echo "  -a, --sa-name SA_NAME        Service account name (default: timecamp-scim-sa)"
    echo "  -h, --help                   Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --project my-project-id"
    echo "  $0 -p my-project-id -s my-secrets -f my-secrets.json"
    echo "  $0 --project my-project-id --sa-name my-service-account"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--project)
            PROJECT_ID="$2"
            shift 2
            ;;
        -s|--secret)
            SECRET_NAME="$2"
            shift 2
            ;;
        -f|--file)
            SECRET_FILE="$2"
            shift 2
            ;;
        -a|--sa-name)
            SA_NAME="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with gcloud. Run 'gcloud auth login'${NC}"
    exit 1
fi

# Validate required parameters
if [ -z "$PROJECT_ID" ]; then
    # Try to get from gcloud config if not provided
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        echo -e "${RED}Error: Project ID is required!${NC}"
        echo "Provide it with --project flag or set it with 'gcloud config set project PROJECT_ID'"
        echo "Use --help for usage information."
        exit 1
    else
        echo -e "${YELLOW}Using project from gcloud config: $PROJECT_ID${NC}"
    fi
fi

# Check if secret file exists
if [ ! -f "$SECRET_FILE" ]; then
    echo -e "${RED}Error: $SECRET_FILE not found!${NC}"
    echo "Please ensure the file exists in the current directory."
    echo "You can specify a different file with --file parameter."
    exit 1
fi

# Display configuration
echo -e "${BLUE}Configuration:${NC}"
echo "  Project ID: ${GREEN}$PROJECT_ID${NC}"
echo "  Secret Name: ${GREEN}$SECRET_NAME${NC}"
echo "  Secret File: ${GREEN}$SECRET_FILE${NC}"
echo "  Service Account: ${GREEN}$SA_NAME${NC}"
echo ""

echo -e "${YELLOW}Processing secret: $SECRET_NAME${NC}"

# Check if secret exists
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
    echo "Secret exists, creating new version..."
    gcloud secrets versions add "$SECRET_NAME" \
        --data-file="$SECRET_FILE" \
        --project="$PROJECT_ID"
else
    echo "Creating new secret..."
    gcloud secrets create "$SECRET_NAME" \
        --data-file="$SECRET_FILE" \
        --replication-policy="automatic" \
        --project="$PROJECT_ID"
fi

echo -e "${GREEN}✓ Secret $SECRET_NAME processed successfully${NC}\n"

echo -e "${BLUE}Next Steps:${NC}"
echo "To grant access to this secret for your Kubernetes service account:"
echo ""
echo -e "${GREEN}export SA_EMAIL=\"${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com\"${NC}"
echo ""
echo -e "${GREEN}gcloud secrets add-iam-policy-binding $SECRET_NAME \\${NC}"
echo -e "${GREEN}  --member=\"serviceAccount:\$SA_EMAIL\" \\${NC}"
echo -e "${GREEN}  --role=\"roles/secretmanager.secretAccessor\" \\${NC}"
echo -e "${GREEN}  --project=\"$PROJECT_ID\"${NC}"
echo ""
echo -e "${BLUE}Or run this command directly:${NC}"
echo ""
echo -e "${YELLOW}gcloud secrets add-iam-policy-binding $SECRET_NAME \\${NC}"
echo -e "${YELLOW}  --member=\"serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com\" \\${NC}"
echo -e "${YELLOW}  --role=\"roles/secretmanager.secretAccessor\" \\${NC}"
echo -e "${YELLOW}  --project=\"$PROJECT_ID\"${NC}"