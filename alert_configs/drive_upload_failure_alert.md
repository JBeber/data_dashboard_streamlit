# Google Drive Upload Failure Alert

## Alert Configuration

### Metric
- **Resource Type**: Cloud Run Job
- **Metric**: `logging.googleapis.com/log_entry_count`
- **Filter**: 
  ```
  resource.type="cloud_run_job"
  resource.labels.job_name="vv-data-collector"
  (jsonPayload.message:"Failed to process" AND jsonPayload.message:".csv") OR
  (jsonPayload.message:"Google Drive" AND jsonPayload.message:"error") OR
  (jsonPayload.message:"HttpError")
  ```

### Trigger Condition
- **Alert Trigger**: Any time series violates
- **Threshold**: 2  (Allow a few file failures, alert on pattern)
- **Condition**: Above threshold
- **Retest window**: 5 minutes
- **Missing data**: Treat as not breaching

### Documentation
```
Google Drive upload failures detected in daily data collection job.

This alert triggers when multiple files fail to upload to Google Drive during data collection.

Common causes:
- Google Drive API quota exceeded
- Insufficient permissions on target folder
- Drive storage quota reached
- Network connectivity issues to Google APIs
- File corruption or format issues
- OAuth token issues (check OAuth alert as well)

Immediate actions:
1. Check Cloud Run Job logs for specific Drive API errors
2. Verify Google Drive folder permissions
3. Check Google Drive storage quota
4. Review Google API quotas and usage
5. Test manual file upload to verify Drive access
6. Check if files are being created but with errors

Impact: Successfully downloaded files may not reach dashboard, causing stale data.
```

### Labels
```
environment: production
service: data-collection
component: drive-uploader
priority: high
team: data-team
application: vv-dashboard
failure-type: api-error
external-dependency: google-drive
```
