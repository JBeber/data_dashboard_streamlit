#!/usr/bin/env python3
"""
Background Job Monitoring Script

This script provides utilities to monitor the Enhanced OAuth Background Job,
check its status, view logs, and trigger manual executions.
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional

def run_command(command: List[str]) -> tuple[str, str, int]:
    """Run a shell command and return stdout, stderr, and return code."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1

def check_job_status(project_id: str, region: str, job_name: str) -> Dict:
    """Check the status of the Cloud Run Job."""
    print(f"🔍 Checking status of job: {job_name}")
    
    # Get job description
    stdout, stderr, code = run_command([
        "gcloud", "run", "jobs", "describe", job_name,
        "--region", region,
        "--project", project_id,
        "--format", "json"
    ])
    
    if code != 0:
        return {"error": f"Failed to get job status: {stderr}"}
    
    try:
        job_info = json.loads(stdout)
        
        # Extract key information
        status = {
            "name": job_info.get("metadata", {}).get("name"),
            "creation_time": job_info.get("metadata", {}).get("creationTimestamp"),
            "update_time": job_info.get("metadata", {}).get("updateTimestamp"),
            "generation": job_info.get("metadata", {}).get("generation"),
            "ready": job_info.get("status", {}).get("conditions", [{}])[0].get("status") == "True"
        }
        
        return status
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse job status: {e}"}

def get_recent_executions(project_id: str, region: str, job_name: str, limit: int = 10) -> List[Dict]:
    """Get recent job executions."""
    print(f"📋 Getting recent executions for: {job_name}")
    
    stdout, stderr, code = run_command([
        "gcloud", "run", "jobs", "executions", "list",
        "--job", job_name,
        "--region", region,
        "--project", project_id,
        "--limit", str(limit),
        "--format", "json"
    ])
    
    if code != 0:
        print(f"❌ Failed to get executions: {stderr}")
        return []
    
    try:
        executions = json.loads(stdout)
        return executions
        
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse executions: {e}")
        return []

def view_logs(project_id: str, job_name: str, hours: int = 24, limit: int = 50):
    """View recent logs for the job."""
    print(f"📄 Viewing logs for {job_name} (last {hours} hours)")
    
    # Calculate time filter
    since_time = datetime.utcnow() - timedelta(hours=hours)
    time_filter = since_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    command = [
        "gcloud", "logs", "read",
        f"resource.type=cloud_run_job AND resource.labels.job_name={job_name}",
        "--project", project_id,
        "--limit", str(limit),
        "--format", "table(timestamp,severity,textPayload)",
        "--filter", f"timestamp>='{time_filter}'"
    ]
    
    stdout, stderr, code = run_command(command)
    
    if code != 0:
        print(f"❌ Failed to get logs: {stderr}")
        return
    
    print(stdout)

def trigger_execution(project_id: str, region: str, job_name: str):
    """Manually trigger a job execution."""
    print(f"🚀 Triggering execution of: {job_name}")
    
    stdout, stderr, code = run_command([
        "gcloud", "run", "jobs", "execute", job_name,
        "--region", region,
        "--project", project_id
    ])
    
    if code == 0:
        print("✅ Job execution triggered successfully")
        print(stdout)
    else:
        print(f"❌ Failed to trigger execution: {stderr}")

def check_scheduler_status(project_id: str, region: str, scheduler_name: str):
    """Check the status of the Cloud Scheduler job."""
    print(f"⏰ Checking scheduler status: {scheduler_name}")
    
    stdout, stderr, code = run_command([
        "gcloud", "scheduler", "jobs", "describe", scheduler_name,
        "--location", region,
        "--project", project_id,
        "--format", "json"
    ])
    
    if code != 0:
        print(f"❌ Failed to get scheduler status: {stderr}")
        return
    
    try:
        scheduler_info = json.loads(stdout)
        
        print(f"📅 Schedule: {scheduler_info.get('schedule')}")
        print(f"🌍 Timezone: {scheduler_info.get('timeZone')}")
        print(f"📊 State: {scheduler_info.get('state')}")
        
        # Last run information
        if 'lastAttemptTime' in scheduler_info:
            last_run = scheduler_info['lastAttemptTime']
            print(f"🕐 Last run: {last_run}")
        
        # Next run information  
        if 'scheduleTime' in scheduler_info:
            next_run = scheduler_info['scheduleTime']
            print(f"⏭️  Next run: {next_run}")
            
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse scheduler info: {e}")

def main():
    """Main monitoring interface."""
    
    # Configuration - update these values
    PROJECT_ID = "vv-data-dashboard"  # Replace with your project ID
    REGION = "us-east5"              # Replace with your region
    JOB_NAME = "data-collector-job"
    SCHEDULER_NAME = "daily-data-collection"
    
    print("🖥️  Enhanced OAuth Background Job Monitor")
    print("=" * 50)
    
    if len(sys.argv) < 2:
        print("Usage: python monitor_job.py <command>")
        print("\nAvailable commands:")
        print("  status     - Check job and scheduler status")
        print("  logs       - View recent logs")
        print("  executions - Show recent executions") 
        print("  trigger    - Manually trigger job execution")
        print("  monitor    - Continuous monitoring mode")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "status":
        print("\n📊 Job Status:")
        print("-" * 20)
        job_status = check_job_status(PROJECT_ID, REGION, JOB_NAME)
        if "error" in job_status:
            print(f"❌ {job_status['error']}")
        else:
            for key, value in job_status.items():
                print(f"{key}: {value}")
        
        print("\n⏰ Scheduler Status:")
        print("-" * 20)
        check_scheduler_status(PROJECT_ID, REGION, SCHEDULER_NAME)
    
    elif command == "logs":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        view_logs(PROJECT_ID, JOB_NAME, hours)
    
    elif command == "executions":
        executions = get_recent_executions(PROJECT_ID, REGION, JOB_NAME)
        if executions:
            print(f"\n📋 Recent Executions ({len(executions)}):")
            print("-" * 30)
            for exec_info in executions:
                name = exec_info.get("metadata", {}).get("name", "unknown")
                creation_time = exec_info.get("metadata", {}).get("creationTimestamp", "unknown")
                completion_time = exec_info.get("status", {}).get("completionTime", "running")
                
                # Extract status
                conditions = exec_info.get("status", {}).get("conditions", [])
                status = "unknown"
                if conditions:
                    status = conditions[0].get("type", "unknown")
                
                print(f"📄 {name}")
                print(f"   Created: {creation_time}")
                print(f"   Completed: {completion_time}")
                print(f"   Status: {status}")
                print()
        else:
            print("❌ No recent executions found")
    
    elif command == "trigger":
        trigger_execution(PROJECT_ID, REGION, JOB_NAME)
    
    elif command == "monitor":
        print("🔄 Continuous monitoring mode (Ctrl+C to exit)")
        import time
        try:
            while True:
                print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                job_status = check_job_status(PROJECT_ID, REGION, JOB_NAME)
                if "error" not in job_status:
                    print(f"✅ Job ready: {job_status.get('ready', False)}")
                
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")
    
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
