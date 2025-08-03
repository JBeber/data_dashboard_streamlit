# OAuth Token Refresh Failure Alert

## Alert Configuration

### Metric
- **Resource Type**: Cloud Run Job
- **Metric**: `logging.googleapis.com/log_entry_count`
- **Filter**: 
  ```
  resource.type="cloud_run_job"
  resource.labels.job_name="vv-data-collector"
  jsonPayload.message:"Failed to refresh OAuth token"
  ```

### Trigger Condition
- **Alert Trigger**: Any time series violates
- **Threshold**: 0
- **Condition**: Above threshold
- **Retest window**: 1 minute
- **Missing data**: Treat as not breaching

### Documentation
```
OAuth token refresh failure detected in daily data collection job.

This alert triggers when the Google OAuth token cannot be refreshed, preventing access to Google Drive API.

Common causes:
- Refresh token has been revoked or expired
- Google OAuth client credentials are invalid
- Network connectivity issues to Google OAuth servers
- Rate limiting from Google OAuth service

Immediate actions:
1. Check Cloud Run Job logs for detailed OAuth error messages
2. Verify OAuth credentials in Secret Manager are valid
3. Regenerate refresh token if necessary using get_google_refresh_token.py
4. Check Google Cloud Console for any OAuth client issues

This is a HIGH PRIORITY alert as it blocks all data collection.
```

### Labels
```
environment: production
service: data-collection
component: oauth-manager
priority: critical
team: data-team
application: vv-dashboard
failure-type: authentication
```
