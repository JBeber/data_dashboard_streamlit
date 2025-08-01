# Enhanced OAuth Background Job

This directory contains the Enhanced OAuth Background Job implementation that replaces the on-demand data collection in the Streamlit app with a reliable, scheduled background process.

## 🏗️ Architecture

```
Cloud Scheduler → Cloud Run Job → SFTP Server → Google Drive
                      ↓
              Enhanced OAuth Management
                      ↓
              Comprehensive Logging & Monitoring
```

## 📁 Files Overview

### Core Components
- **`background_data_collector.py`** - Main background job script with enhanced OAuth
- **`Dockerfile.job`** - Docker container configuration for Cloud Run Job
- **`deploy_background_job.sh`** - Automated deployment script
- **`setup_env_vars.sh`** - Environment variables configuration helper
- **`monitor_job.py`** - Job monitoring and management utilities

### Configuration
- **`config.yaml`** - Business logic configuration (holidays, schedules, etc.)
- **`Toast_SFTP_known_hosts`** - SFTP server host key verification
- **`requirements.txt`** - Python dependencies

### Updated App
- **`app.py`** - Updated Streamlit app without data collection dependency

## 🚀 Features

### Enhanced OAuth Management
- **Proactive Token Refresh**: Automatically refreshes tokens before expiration
- **Comprehensive Error Handling**: Detailed logging for authentication failures
- **Robust Retry Logic**: Multiple retry attempts with exponential backoff
- **Token Monitoring**: Tracks token expiry and refresh cycles

### Cloud-Native Architecture
- **Cloud Run Jobs**: Serverless execution with automatic scaling
- **Cloud Scheduler**: Reliable daily scheduling with timezone support
- **Cloud Logging**: Centralized logging with structured output
- **Error Monitoring**: Integration with Google Cloud Operations

### Data Collection Improvements
- **Duplicate Prevention**: Checks for existing files before upload
- **Atomic Operations**: Complete file processing or rollback
- **Progress Tracking**: Detailed statistics and timing information
- **Graceful Error Handling**: Continues processing despite individual failures

## 🛠️ Deployment Guide

### Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Google Cloud SDK** installed and configured
3. **Docker** installed and running
4. **OAuth Credentials** from Google Cloud Console

### Step 1: Clone and Setup

```bash
# Navigate to project directory
cd data_dashboard_streamlit

# Make scripts executable
chmod +x deploy_background_job.sh
chmod +x setup_env_vars.sh
```

### Step 2: Update Configuration

Edit `deploy_background_job.sh` and update:
- `PROJECT_ID` - Your Google Cloud project ID
- `REGION` - Your preferred region (e.g., us-east5)

### Step 3: Deploy the Job

```bash
# Deploy Cloud Run Job and Cloud Scheduler
./deploy_background_job.sh
```

This script will:
- Enable required Google Cloud APIs
- Build and push Docker image
- Deploy Cloud Run Job
- Create Cloud Scheduler job (daily at 6 AM EST)

### Step 4: Configure Environment Variables

```bash
# Run the interactive setup script
./setup_env_vars.sh
```

You'll need to provide:

#### Google OAuth Credentials
- `GOOGLE_CLIENT_ID` - From Google Cloud Console
- `GOOGLE_CLIENT_SECRET` - From Google Cloud Console  
- `GOOGLE_REFRESH_TOKEN` - Generated OAuth refresh token
- `GOOGLE_DRIVE_FOLDER_ID` - Target Google Drive folder

#### SFTP Connection Details
- `TOAST_SFTP_HOSTNAME` - SFTP server hostname
- `TOAST_SFTP_USERNAME` - SFTP username
- `TOAST_SFTP_PASSWORD` - SFTP password
- `TOAST_SFTP_PRIVATE_KEY` - SSH private key content
- `TOAST_SFTP_EXPORT_ID` - Export directory ID

### Step 5: Test the Deployment

```bash
# Test manual execution
gcloud run jobs execute data-collector-job --region=us-east5

# Monitor execution
python monitor_job.py logs
```

## 🔧 Management & Monitoring

### Monitoring Commands

```bash
# Check job and scheduler status
python monitor_job.py status

# View recent logs (last 24 hours)
python monitor_job.py logs

# View recent executions
python monitor_job.py executions

# Manually trigger execution
python monitor_job.py trigger

# Continuous monitoring
python monitor_job.py monitor
```

### Cloud Console Monitoring

1. **Cloud Run Jobs**: Monitor executions and performance
2. **Cloud Scheduler**: View schedule and execution history
3. **Cloud Logging**: Search and filter detailed logs
4. **Cloud Monitoring**: Set up alerts and dashboards

### Log Analysis

The job produces structured logs with the following levels:
- **INFO**: Normal operation progress
- **WARNING**: Non-critical issues (missing files, etc.)
- **ERROR**: Critical failures requiring attention

## 🔒 Security Features

### OAuth Token Security
- Tokens stored as environment variables in Cloud Run
- Automatic refresh prevents token expiration
- No tokens stored in code or containers

### SFTP Security
- SSH key-based authentication
- Host key verification
- Secure temporary file handling

### Container Security
- Non-root user execution
- Minimal base image
- No sensitive data in image layers

## 📊 Performance & Reliability

### Execution Characteristics
- **Runtime**: Typically 2-10 minutes depending on data volume
- **Memory**: 1GB allocated, typically uses ~200-500MB
- **CPU**: 1 vCPU allocated, scales based on workload
- **Timeout**: 60 minutes maximum execution time

### Error Handling
- **Retry Logic**: Up to 3 automatic retries for failed executions
- **Partial Failures**: Continues processing despite individual file failures
- **Monitoring**: Failed executions trigger Cloud Monitoring alerts

### Cost Optimization
- **Serverless**: Only pay for actual execution time
- **Efficient Processing**: Optimized for minimal resource usage
- **Scheduled Execution**: Runs only when needed

## 🔄 Migration from App-Based Collection

### What Changed
1. **Data Collection**: Moved from Streamlit app startup to background job
2. **User Experience**: App loads instantly without waiting for data collection
3. **Reliability**: Scheduled execution with proper error handling
4. **Monitoring**: Comprehensive logging and status tracking

### App Updates
- Removed `collect_data()` call from app startup
- Added background job status indicator
- Updated dependencies to remove collection-specific imports

### Data Freshness
- **Schedule**: Daily execution at 6 AM EST
- **Indicators**: App shows last update timestamp
- **Manual Refresh**: Can trigger manual execution if needed

## 🐛 Troubleshooting

### Common Issues

#### Authentication Errors
```
google.auth.exceptions.RefreshError: invalid_grant
```
**Solution**: Regenerate OAuth refresh token

#### SFTP Connection Failures
```
paramiko.ssh_exception.AuthenticationException
```
**Solution**: Verify SFTP credentials and private key format

#### File Upload Errors
```
googleapiclient.errors.HttpError: 403 Forbidden
```
**Solution**: Check Google Drive folder permissions and API quotas

### Debug Commands

```bash
# View detailed logs
gcloud logs read --limit=100 --filter='resource.type=cloud_run_job' --format='table(timestamp,severity,textPayload)'

# Check environment variables
gcloud run jobs describe data-collector-job --region=us-east5 --format='value(spec.template.template.spec.template.spec.containers[0].env[].name)'

# Test SFTP connectivity (manual)
python -c "from background_data_collector import DataCollector; dc = DataCollector(); print('Config loaded successfully')"
```

## 📈 Future Enhancements

### Phase 2: Service Account Migration
- Migrate to Google Shared Drive
- Replace OAuth with Service Account authentication
- Enhanced security and reliability

### Phase 3: Database Backend
- Replace Google Drive with Cloud SQL/Firestore
- Real-time data access for the app
- Advanced analytics and reporting

### Monitoring Improvements
- Custom dashboards in Cloud Monitoring
- Slack/email notifications for failures
- Performance metrics and optimization

## 🆘 Support

### Getting Help
1. Check logs using `monitor_job.py logs`
2. Verify environment variables are set correctly
3. Test manual execution to isolate issues
4. Review Cloud Run Job configuration in console

### Contact Information
- Technical Issues: Check Cloud Console error logs
- Configuration Help: Review this README and deployment scripts
- Feature Requests: Create issues in project repository
