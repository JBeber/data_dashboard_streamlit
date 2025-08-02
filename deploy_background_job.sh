#!/bin/bash
# Enhanced OAuth Background Job Deployment Script
# 
# This script deploys the background data collector as a Cloud Run Job
# and sets up Cloud Scheduler for daily execution.

set -e

# Configuration
PROJECT_ID="vv-data-dashboard"
REGION="us-east5"              # Cloud Run location
# Note: Cloud Scheduler location can be different from Cloud Run
SCHEDULER_REGION="us-east1"    # Cloud Scheduler location
JOB_NAME="data-collector-job"
SCHEDULER_JOB_NAME="daily-data-collection"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${JOB_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Enhanced OAuth Background Job Deployment${NC}"
echo "=============================================="

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ Error: gcloud CLI is not installed${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Error: Docker is not running${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Project: ${PROJECT_ID}${NC}"
echo -e "${YELLOW}📍 Cloud Run Region: ${REGION}${NC}"
echo -e "${YELLOW}📍 Scheduler Region: ${SCHEDULER_REGION}${NC}"
echo -e "${YELLOW}🏗️  Job Name: ${JOB_NAME}${NC}"

# Set the project
echo -e "${YELLOW}🔧 Setting project...${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "${YELLOW}🔌 Enabling required APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    logging.googleapis.com \
    appengine.googleapis.com

# Build and push Docker image
echo -e "${YELLOW}🐳 Building Docker image...${NC}"
docker build -f Dockerfile.job -t ${IMAGE_NAME} .

echo -e "${YELLOW}📤 Pushing Docker image to Container Registry...${NC}"
docker push ${IMAGE_NAME}

# Deploy Cloud Run Job
echo -e "${YELLOW}☁️  Deploying Cloud Run Job...${NC}"

# Environment variables for the job
ENV_VARS="PYTHONUNBUFFERED=1"

# Configure secrets from Google Secret Manager
echo -e "${YELLOW}🔐 Configuring secrets from Secret Manager...${NC}"

# Map of environment variable names to secret names in Secret Manager
declare -A SECRET_MAP=(
    ["GOOGLE_CLIENT_ID"]="oauth-client-id"
    ["GOOGLE_CLIENT_SECRET"]="oauth-client-secret"
    ["GOOGLE_REFRESH_TOKEN"]="oauth-refresh-token"
    ["GOOGLE_DRIVE_FOLDER_ID"]="google-drive-folder-id"
    ["TOAST_SFTP_PRIVATE_KEY"]="toast-sftp-private-key"
    ["TOAST_SFTP_HOSTNAME"]="toast-sftp-hostname"
    ["TOAST_SFTP_USERNAME"]="toast-sftp-username"
    ["TOAST_SFTP_PASSWORD"]="toast-sftp-password"
    ["TOAST_SFTP_EXPORT_ID"]="toast-sftp-export-id"
)

MISSING_SECRETS=()
SECRET_ENV_VARS=""

# Check which secrets exist and build environment variable list
for env_var in "${!SECRET_MAP[@]}"; do
    secret_name="${SECRET_MAP[$env_var]}"
    
    if gcloud secrets describe "$secret_name" &> /dev/null; then
        if [[ -z "$SECRET_ENV_VARS" ]]; then
            SECRET_ENV_VARS="$env_var"
        else
            SECRET_ENV_VARS="$SECRET_ENV_VARS,$env_var"
        fi
    else
        MISSING_SECRETS+=("$secret_name")
    fi
done

# If we have missing secrets, inform the user
if [[ ${#MISSING_SECRETS[@]} -gt 0 ]]; then
    echo -e "${YELLOW}⚠️  Missing secrets in Secret Manager: ${MISSING_SECRETS[*]}${NC}"
    echo -e "${YELLOW}💡 You can create them using:${NC}"
    for secret in "${MISSING_SECRETS[@]}"; do
        echo "   echo 'your-secret-value' | gcloud secrets create $secret --data-file=-"
    done
    echo ""
fi

# Use hybrid approach: update if exists, create if not
if gcloud run jobs describe ${JOB_NAME} --region=${REGION} &> /dev/null; then
    echo -e "${YELLOW}📝 Job already exists, updating...${NC}"
    
    # Build secrets flags for gcloud command
    SECRET_FLAGS=""
    if [[ -n "$SECRET_ENV_VARS" ]]; then
        IFS=',' read -ra VARS <<< "$SECRET_ENV_VARS"
        for var in "${VARS[@]}"; do
            secret_name="${SECRET_MAP[$var]}"
            SECRET_FLAGS="$SECRET_FLAGS --set-secrets=${var}=${secret_name}:latest"
        done
    fi
    
    gcloud run jobs update ${JOB_NAME} \
        --image=${IMAGE_NAME} \
        --region=${REGION} \
        --task-timeout=3600 \
        --memory=1Gi \
        --cpu=1 \
        --max-retries=3 \
        --parallelism=1 \
        --set-env-vars="PYTHONUNBUFFERED=1" \
        $SECRET_FLAGS
    
    echo -e "${GREEN}✅ Cloud Run Job updated successfully${NC}"
else
    echo -e "${YELLOW}➕ Job doesn't exist, creating new job...${NC}"
    
    # Build secrets flags for gcloud command
    SECRET_FLAGS=""
    if [[ -n "$SECRET_ENV_VARS" ]]; then
        IFS=',' read -ra VARS <<< "$SECRET_ENV_VARS"
        for var in "${VARS[@]}"; do
            secret_name="${SECRET_MAP[$var]}"
            SECRET_FLAGS="$SECRET_FLAGS --set-secrets=${var}=${secret_name}:latest"
        done
    fi
    
    gcloud run jobs create ${JOB_NAME} \
        --image=${IMAGE_NAME} \
        --region=${REGION} \
        --task-timeout=3600 \
        --memory=1Gi \
        --cpu=1 \
        --max-retries=3 \
        --parallelism=1 \
        --set-env-vars="PYTHONUNBUFFERED=1" \
        $SECRET_FLAGS
    
    echo -e "${GREEN}✅ Cloud Run Job created successfully${NC}"
fi

# Create or update Cloud Scheduler job
echo -e "${YELLOW}⏰ Setting up Cloud Scheduler...${NC}"

# First, check if App Engine application exists (required for Cloud Scheduler)
if ! gcloud app describe &> /dev/null; then
    echo -e "${YELLOW}📱 Creating App Engine application (required for Cloud Scheduler)...${NC}"
    gcloud app create --region=${SCHEDULER_REGION} --quiet
fi

# Check if scheduler job exists
if gcloud scheduler jobs describe ${SCHEDULER_JOB_NAME} --location=${SCHEDULER_REGION} &> /dev/null; then
    echo -e "${YELLOW}📝 Updating existing scheduler job...${NC}"
    gcloud scheduler jobs update http ${SCHEDULER_JOB_NAME} \
        --location=${SCHEDULER_REGION} \
        --schedule="0 6 * * *" \
        --time-zone="America/New_York" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
        --http-method=POST \
        --oidc-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com"
else
    echo -e "${YELLOW}➕ Creating new scheduler job...${NC}"
    gcloud scheduler jobs create http ${SCHEDULER_JOB_NAME} \
        --location=${SCHEDULER_REGION} \
        --schedule="0 6 * * *" \
        --time-zone="America/New_York" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
        --http-method=POST \
        --oidc-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com"
fi

echo -e "${GREEN}✅ Cloud Scheduler configured successfully${NC}"

# Display next steps
echo ""
echo -e "${GREEN}🎉 Deployment Complete!${NC}"
echo "========================="
echo ""
echo -e "${YELLOW}📋 Next Steps:${NC}"
if [[ ${#MISSING_SECRETS[@]} -gt 0 ]]; then
    echo "1. Create missing secrets in Secret Manager:"
    for secret in "${MISSING_SECRETS[@]}"; do
        echo "   echo 'your-secret-value' | gcloud secrets create $secret --data-file=-"
    done
    echo ""
    echo "   Then redeploy to pick up the new secrets:"
    echo "   ./deploy_background_job.sh"
    echo ""
else
    echo "1. ✅ All secrets are configured!"
    echo ""
fi
echo "2. Test the job manually:"
echo "   gcloud run jobs execute ${JOB_NAME} --region=${REGION}"
echo ""
echo "3. Monitor logs:"
echo "   gcloud logs read --limit=50 --format='table(timestamp,severity,textPayload)' --filter='resource.type=cloud_run_job'"
echo ""
echo "4. Check scheduler status:"
echo "   gcloud scheduler jobs describe ${SCHEDULER_JOB_NAME} --location=${SCHEDULER_REGION}"
