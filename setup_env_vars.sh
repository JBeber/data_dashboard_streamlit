#!/bin/bash
# Environment Variables Setup Script for Background Job
#
# This script helps set up all required environment variables 
# for the Enhanced OAuth Background Job in Cloud Run.

set -e

# Configuration
PROJECT_ID="vv-data-dashboard"  # Replace with your actual project ID
REGION="us-east5"              # Replace with your preferred region
JOB_NAME="data-collector-job"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔐 Environment Variables Setup for Background Job${NC}"
echo "=================================================="

# Function to set environment variable
set_env_var() {
    local var_name=$1
    local var_description=$2
    local is_secret=${3:-false}
    
    echo ""
    echo -e "${BLUE}Setting: ${var_name}${NC}"
    echo -e "${YELLOW}Description: ${var_description}${NC}"
    
    if [ "$is_secret" = true ]; then
        echo -e "${YELLOW}(Hidden input for security)${NC}"
        read -s -p "Enter value: " var_value
        echo ""
    else
        read -p "Enter value: " var_value
    fi
    
    if [ -n "$var_value" ]; then
        gcloud run jobs update ${JOB_NAME} \
            --region=${REGION} \
            --update-env-vars="${var_name}=${var_value}" \
            --quiet
        echo -e "${GREEN}✅ ${var_name} set successfully${NC}"
    else
        echo -e "${RED}❌ Skipped ${var_name} (empty value)${NC}"
    fi
}

echo -e "${YELLOW}📋 Project: ${PROJECT_ID}${NC}"
echo -e "${YELLOW}📍 Region: ${REGION}${NC}"
echo -e "${YELLOW}🏗️  Job Name: ${JOB_NAME}${NC}"

# Set project
gcloud config set project ${PROJECT_ID}

echo ""
echo -e "${YELLOW}🔧 Setting up environment variables...${NC}"

# Google OAuth Variables
echo -e "\n${BLUE}=== Google OAuth Credentials ===${NC}"
set_env_var "GOOGLE_CLIENT_ID" "Google OAuth Client ID from Google Cloud Console"
set_env_var "GOOGLE_CLIENT_SECRET" "Google OAuth Client Secret" true
set_env_var "GOOGLE_REFRESH_TOKEN" "Google OAuth Refresh Token" true
set_env_var "GOOGLE_DRIVE_FOLDER_ID" "Google Drive Folder ID where files will be uploaded"

# SFTP Variables  
echo -e "\n${BLUE}=== SFTP Connection Details ===${NC}"
set_env_var "TOAST_SFTP_HOSTNAME" "SFTP server hostname"
set_env_var "TOAST_SFTP_USERNAME" "SFTP username"
set_env_var "TOAST_SFTP_PASSWORD" "SFTP password" true
set_env_var "TOAST_SFTP_EXPORT_ID" "SFTP export directory ID"

echo -e "\n${BLUE}=== SFTP Private Key ===${NC}"
echo -e "${YELLOW}For the private key, you can either:${NC}"
echo "1. Paste the entire key content (including headers)"
echo "2. Reference a file path to read from"
echo ""
read -p "Choose option (1 or 2): " key_option

if [ "$key_option" = "1" ]; then
    echo -e "${YELLOW}Paste your private key (press Ctrl+D when done):${NC}"
    private_key=$(cat)
    
    gcloud run jobs update ${JOB_NAME} \
        --region=${REGION} \
        --update-env-vars="TOAST_SFTP_PRIVATE_KEY=${private_key}" \
        --quiet
    echo -e "${GREEN}✅ TOAST_SFTP_PRIVATE_KEY set successfully${NC}"
    
elif [ "$key_option" = "2" ]; then
    read -p "Enter path to private key file: " key_file
    if [ -f "$key_file" ]; then
        private_key=$(cat "$key_file")
        gcloud run jobs update ${JOB_NAME} \
            --region=${REGION} \
            --update-env-vars="TOAST_SFTP_PRIVATE_KEY=${private_key}" \
            --quiet
        echo -e "${GREEN}✅ TOAST_SFTP_PRIVATE_KEY set successfully${NC}"
    else
        echo -e "${RED}❌ File not found: ${key_file}${NC}"
    fi
fi

echo ""
echo -e "${GREEN}🎉 Environment Variables Setup Complete!${NC}"
echo "========================================"

echo ""
echo -e "${YELLOW}📋 Next Steps:${NC}"
echo "1. Test the job manually:"
echo "   gcloud run jobs execute ${JOB_NAME} --region=${REGION}"
echo ""
echo "2. View current environment variables:"
echo "   gcloud run jobs describe ${JOB_NAME} --region=${REGION} --format='value(spec.template.template.spec.template.spec.containers[0].env[].name)'"
echo ""
echo "3. Monitor job execution:"
echo "   gcloud logs read --limit=50 --filter='resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}'"
