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
if gcloud run jobs describe ${JOB_NAME} --region=${REGION} &> /dev/null; then
    echo -e "${YELLOW}📝 Job already exists, deleting and recreating...${NC}"
    gcloud run jobs delete ${JOB_NAME} --region=${REGION} --quiet
fi

gcloud run jobs create ${JOB_NAME} \
    --image=${IMAGE_NAME} \
    --region=${REGION} \
    --task-timeout=3600 \
    --memory=1Gi \
    --cpu=1 \
    --max-retries=3 \
    --parallelism=1 \
    --set-env-vars="PYTHONUNBUFFERED=1"

echo -e "${GREEN}✅ Cloud Run Job deployed successfully${NC}"

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
echo "1. Set up environment variables in Cloud Run Job:"
echo "   - GOOGLE_CLIENT_ID"
echo "   - GOOGLE_CLIENT_SECRET" 
echo "   - GOOGLE_REFRESH_TOKEN"
echo "   - GOOGLE_DRIVE_FOLDER_ID"
echo "   - TOAST_SFTP_PRIVATE_KEY"
echo "   - TOAST_SFTP_HOSTNAME"
echo "   - TOAST_SFTP_USERNAME"
echo "   - TOAST_SFTP_PASSWORD"
echo "   - TOAST_SFTP_EXPORT_ID"
echo ""
echo "2. Test the job manually:"
echo "   gcloud run jobs execute ${JOB_NAME} --region=${REGION}"
echo ""
echo "3. Monitor logs:"
echo "   gcloud logs read --limit=50 --format='table(timestamp,severity,textPayload)' --filter='resource.type=cloud_run_job'"
echo ""
echo "4. Check scheduler status:"
echo "   gcloud scheduler jobs describe ${SCHEDULER_JOB_NAME} --location=${SCHEDULER_REGION}"
