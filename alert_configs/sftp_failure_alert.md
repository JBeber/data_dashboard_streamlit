# SFTP Connection Failure Alert

## Alert Configuration

### Metric
- **Resource Type**: Cloud Run Job
- **Metric**: `logging.googleapis.com/log_entry_count`
- **Filter**: 
  ```
  resource.type="cloud_run_job"
  resource.labels.job_name="vv-data-collector"
  (jsonPayload.message:"SFTP" AND jsonPayload.message:"error") OR
  (jsonPayload.message:"Failed to connect" AND jsonPayload.message:"sftp")
  ```

### Trigger Condition
- **Alert Trigger**: Any time series violates
- **Threshold**: 0
- **Condition**: Above threshold
- **Retest window**: 1 minute
- **Missing data**: Treat as not breaching

### Documentation
```
SFTP connection failure detected in daily data collection job.

This alert triggers when the job cannot connect to Toast SFTP server to download daily reports.

Common causes:
- SFTP server maintenance or downtime
- Network connectivity issues
- Invalid SFTP credentials (username, password, private key)
- SSH key authentication failures
- Firewall or security group blocking connections

Immediate actions:
1. Check Cloud Run Job logs for specific SFTP error messages
2. Verify SFTP credentials in Secret Manager
3. Test SFTP connectivity manually if possible
4. Check with Toast support for server status
5. Verify hostname hasn't changed (AWS Transfer Family uses dynamic hostnames)

Impact: No new data will be collected until SFTP access is restored.
```

### Labels
```
environment: production
service: data-collection
component: sftp-client
priority: high
team: data-team
application: vv-dashboard
failure-type: connectivity
external-dependency: toast-sftp
```
