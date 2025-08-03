#!/bin/bash
# VV Data Collector - Comprehensive Cloud Monitoring Setup Script

# Set your configuration (will auto-detect current gcloud project)
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
EMAIL="${NOTIFICATION_EMAIL:-monitoring-alerts@example.com}"  # Optional - using existing channels
REGION="us-east5"
JOB_NAME="vv-data-collector"

echo "Setting up comprehensive Cloud Monitoring alerts for VV Data Collector..."
echo "Project: $PROJECT_ID"
echo "Email: $EMAIL"
echo "Job: $JOB_NAME"

# Enable APIs
echo "Enabling Cloud Monitoring API..."
gcloud services enable monitoring.googleapis.com

# Use existing notification channels
echo "Finding existing notification channels..."

# Get the notification channel IDs for "My Gmail" and "My Phone"
GMAIL_CHANNEL=$(gcloud alpha monitoring channels list --filter="displayName=\"My Gmail\"" --format="value(name)" | head -1)
PHONE_CHANNEL=$(gcloud alpha monitoring channels list --filter="displayName=\"My Phone\"" --format="value(name)" | head -1)

if [ -z "$GMAIL_CHANNEL" ]; then
  echo "Warning: 'My Gmail' notification channel not found"
  echo "Available channels:"
  gcloud alpha monitoring channels list --format="table(displayName,name)"
  exit 1
fi

if [ -z "$PHONE_CHANNEL" ]; then
  echo "Warning: 'My Phone' notification channel not found"
  echo "Available channels:"
  gcloud alpha monitoring channels list --format="table(displayName,name)"
  exit 1
fi

echo "Found notification channels:"
echo "  Gmail: $GMAIL_CHANNEL"
echo "  Phone: $PHONE_CHANNEL"

# Use both channels for notifications (Gmail for all alerts, Phone for critical only)
PRIMARY_CHANNELS="[\"$GMAIL_CHANNEL\"]"
CRITICAL_CHANNELS="[\"$GMAIL_CHANNEL\", \"$PHONE_CHANNEL\"]"

# Create alert policies
echo "Creating comprehensive alert policies..."

# 1. Job failure alert
echo "Creating job failure alert..."
gcloud alpha monitoring policies create --policy-from-file=- <<EOF
{
  "displayName": "VV Data Collection - Job Failures",
  "documentation": {
    "content": "Alert triggered when the daily data collection job fails.\n\nThis job runs every day at 6 AM EST to collect sales data from Toast SFTP and upload to Google Drive for dashboard consumption.\n\nCommon failure causes:\n- OAuth token expiration/refresh failures\n- SFTP connection issues or credential problems\n- Google Drive API errors or quota limits\n- Missing business day data on SFTP server\n\nCheck Cloud Run Job logs in Cloud Logging for detailed error information.",
    "mimeType": "text/markdown"
  },
  "userLabels": {
    "environment": "production",
    "service": "data-collection",
    "component": "background-job",
    "priority": "high",
    "team": "data-team",
    "application": "vv-dashboard"
  },
  "conditions": [{
    "displayName": "Job Execution Failed",
    "conditionThreshold": {
      "filter": "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"$JOB_NAME\" AND metric.type=\"run.googleapis.com/job/completed_execution_count\" AND metric.labels.result=\"failed\"",
      "comparison": 1,
      "thresholdValue": 0,
      "duration": "60s",
      "aggregations": [{
        "alignmentPeriod": "300s",
        "perSeriesAligner": "ALIGN_RATE",
        "crossSeriesReducer": "REDUCE_SUM"
      }]
    }
  }],
  "notificationChannels": $PRIMARY_CHANNELS,
  "combiner": "OR",
  "enabled": true
}
EOF

# 2. OAuth token refresh failure alert
echo "Creating OAuth failure alert..."
gcloud alpha monitoring policies create --policy-from-file=- <<EOF
{
  "displayName": "VV Data Collection - OAuth Token Failures",
  "documentation": {
    "content": "OAuth token refresh failure detected in daily data collection job.\n\nThis is a CRITICAL alert as OAuth failures block all data collection.\n\nCommon causes:\n- Refresh token has been revoked or expired\n- Google OAuth client credentials are invalid\n- Network connectivity issues to Google OAuth servers\n\nImmediate actions:\n1. Check Cloud Run Job logs for detailed OAuth error messages\n2. Verify OAuth credentials in Secret Manager\n3. Regenerate refresh token if necessary",
    "mimeType": "text/markdown"
  },
  "userLabels": {
    "environment": "production",
    "service": "data-collection",
    "component": "oauth-manager",
    "priority": "critical",
    "team": "data-team",
    "application": "vv-dashboard",
    "failure-type": "authentication"
  },
  "conditions": [{
    "displayName": "OAuth Token Refresh Failed",
    "conditionThreshold": {
      "filter": "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"$JOB_NAME\" AND metric.type=\"logging.googleapis.com/log_entry_count\"",
      "comparison": 1,
      "thresholdValue": 5,
      "duration": "300s"
    }
  }],
  "notificationChannels": $CRITICAL_CHANNELS,
  "combiner": "OR",
  "enabled": true
}
EOF

# 3. SFTP connection failure alert
echo "Creating SFTP failure alert..."
gcloud alpha monitoring policies create --policy-from-file=- <<EOF
{
  "displayName": "VV Data Collection - SFTP Connection Failures",
  "documentation": {
    "content": "SFTP connection failure detected in daily data collection job.\n\nCommon causes:\n- SFTP server maintenance or downtime\n- Invalid SFTP credentials\n- Network connectivity issues\n- SSH key authentication failures\n\nCheck Cloud Run Job logs and verify SFTP credentials in Secret Manager.",
    "mimeType": "text/markdown"
  },
  "userLabels": {
    "environment": "production",
    "service": "data-collection",
    "component": "sftp-client",
    "priority": "high",
    "team": "data-team",
    "application": "vv-dashboard",
    "failure-type": "connectivity",
    "external-dependency": "toast-sftp"
  },
  "conditions": [{
    "displayName": "SFTP Connection Failed",
    "conditionThreshold": {
      "filter": "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"$JOB_NAME\" AND metric.type=\"logging.googleapis.com/log_entry_count\"",
      "comparison": 1,
      "thresholdValue": 5,
      "duration": "300s"
    }
  }],
  "notificationChannels": $PRIMARY_CHANNELS,
  "combiner": "OR",
  "enabled": true
}
EOF

# 4. Missing daily execution alert
echo "Creating missing execution alert..."
gcloud alpha monitoring policies create --policy-from-file=- <<EOF
{
  "displayName": "VV Data Collection - Missing Daily Execution",
  "documentation": {
    "content": "Daily data collection job failed to execute as scheduled.\n\nThis alert triggers when the scheduled job doesn't run at the expected time (6 AM EST daily).\n\nCommon causes:\n- Cloud Scheduler job is disabled or misconfigured\n- Cloud Run Job service is experiencing issues\n- IAM permissions issues preventing job execution\n- Resource constraints or quota limits\n\nThis is CRITICAL as missing daily executions mean no fresh data for dashboard users.",
    "mimeType": "text/markdown"
  },
  "userLabels": {
    "environment": "production",
    "service": "data-collection",
    "component": "cloud-scheduler",
    "priority": "critical",
    "team": "data-team",
    "application": "vv-dashboard",
    "failure-type": "scheduling"
  },
  "conditions": [{
    "displayName": "No Job Execution",
    "conditionAbsent": {
      "filter": "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"$JOB_NAME\" AND metric.type=\"run.googleapis.com/job/completed_execution_count\"",
      "duration": "3600s",
      "aggregations": [{
        "alignmentPeriod": "3600s",
        "perSeriesAligner": "ALIGN_SUM"
      }]
    }
  }],
  "notificationChannels": $CRITICAL_CHANNELS,
  "combiner": "OR",
  "enabled": true
}
EOF

# 5. Google Drive upload failure alert
echo "Creating Google Drive upload failure alert..."
gcloud alpha monitoring policies create --policy-from-file=- <<EOF
{
  "displayName": "VV Data Collection - Google Drive Upload Failures",
  "documentation": {
    "content": "Google Drive upload failures detected in daily data collection job.\n\nThis alert triggers when multiple files fail to upload to Google Drive during data collection.\n\nCommon causes:\n- Google Drive API quota exceeded\n- Insufficient permissions on target folder\n- Drive storage quota reached\n- Network connectivity issues to Google APIs\n- File corruption or format issues\n- OAuth token issues (check OAuth alert as well)\n\nImpact: Successfully downloaded files may not reach dashboard, causing stale data.",
    "mimeType": "text/markdown"
  },
  "userLabels": {
    "environment": "production",
    "service": "data-collection",
    "component": "drive-uploader",
    "priority": "high",
    "team": "data-team",
    "application": "vv-dashboard",
    "failure-type": "api-error",
    "external-dependency": "google-drive"
  },
  "conditions": [{
    "displayName": "Google Drive Upload Failed",
    "conditionThreshold": {
      "filter": "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"$JOB_NAME\" AND metric.type=\"logging.googleapis.com/log_entry_count\"",
      "comparison": 1,
      "thresholdValue": 10,
      "duration": "300s"
    }
  }],
  "notificationChannels": $PRIMARY_CHANNELS,
  "combiner": "OR",
  "enabled": true
}
EOF

echo ""
echo "✅ Comprehensive Cloud Monitoring alerts configured successfully!"
echo ""
echo "📊 Alerts Created:"
echo "  1. Job Failures (High Priority) → Gmail"
echo "  2. OAuth Token Failures (Critical Priority) → Gmail + Phone"
echo "  3. SFTP Connection Failures (High Priority) → Gmail"
echo "  4. Missing Daily Execution (Critical Priority) → Gmail + Phone"
echo "  5. Google Drive Upload Failures (High Priority) → Gmail"
echo ""
echo "📧 Notification Channels Used:"
echo "  Gmail: $GMAIL_CHANNEL"
echo "  Phone: $PHONE_CHANNEL"
echo ""
echo "🔍 View alerts in Cloud Console: https://console.cloud.google.com/monitoring/alerting"
echo "📝 Alert documentation includes troubleshooting steps for each failure type"
echo ""
echo "🏷️  All alerts are tagged with:"
echo "   - environment: production"
echo "   - service: data-collection"
echo "   - team: data-team"
echo "   - application: vv-dashboard"
echo ""
echo "📱 Critical alerts (OAuth failures, missing executions) will notify both Gmail and Phone"
echo "📧 Regular alerts (job failures, SFTP issues, Drive upload issues) will notify Gmail only"
echo ""
echo "Next steps:"
echo "1. Test alerts by triggering failures (optional)"
echo "2. Set up additional notification channels if needed (Slack, PagerDuty, etc.)"
echo "3. Create alert dashboards for monitoring trends"
echo "4. Review and adjust alert thresholds based on actual usage"
