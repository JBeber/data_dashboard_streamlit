# Missing Daily Execution Alert

## Alert Configuration

### Metric
- **Resource Type**: Cloud Run Job
- **Metric**: `run.googleapis.com/job/completed_execution_count`
- **Filter**: 
  ```
  resource.type="cloud_run_job"
  resource.labels.job_name="vv-data-collector"
  ```

### Trigger Condition
- **Alert Trigger**: Any time series violates
- **Threshold**: 0
- **Condition**: Below threshold
- **Retest window**: 30 minutes
- **Missing data**: Treat as breaching threshold
- **Duration**: 1 hour (job should run daily, alert if no execution in past hour after scheduled time)

### Documentation
```
Daily data collection job failed to execute as scheduled.

This alert triggers when the scheduled job doesn't run at the expected time (6 AM EST daily).

Common causes:
- Cloud Scheduler job is disabled or misconfigured
- Cloud Run Job service is experiencing issues
- IAM permissions issues preventing job execution
- Resource constraints or quota limits
- Cloud Scheduler service outage

Immediate actions:
1. Check Cloud Scheduler job status and logs
2. Verify Cloud Run Job configuration and permissions
3. Check for any Google Cloud service outages
4. Review IAM bindings for Cloud Scheduler service account
5. Check resource quotas and limits
6. Manually trigger the job if necessary

This is CRITICAL as missing daily executions mean no fresh data for dashboard users.
```

### Labels
```
environment: production
service: data-collection
component: cloud-scheduler
priority: critical
team: data-team
application: vv-dashboard
failure-type: scheduling
```
