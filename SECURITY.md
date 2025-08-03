# Security Documentation

## Known Security Decisions and Technical Debt

### SFTP Host Key Verification Disabled

**File**: `background_data_collector.py`  
**Line**: ~337  
**Date**: August 3, 2025  
**Status**: 🔶 Accepted Risk / Technical Debt  

#### Issue
SFTP connection to AWS Transfer Family disables host key verification:
```python
cnopts.hostkeys = None  # Disable host key checking
```

#### Root Cause
AWS Transfer Family uses dynamic hostnames that change between sessions:
- Example: `s-9b0f88558b264dfda.server.transfer.us-east-1.amazonaws.com`
- Traditional known_hosts file cannot accommodate dynamic hostnames
- Static host key files become outdated immediately

#### Risk Assessment
- **Risk Level**: Medium
- **Attack Vector**: Man-in-the-middle attacks, DNS hijacking
- **Likelihood**: Low (managed AWS environment)
- **Impact**: Credential compromise, data interception

#### Mitigating Factors
✅ AWS Transfer Family is a managed service with inherent security controls  
✅ Multiple authentication layers (SSH private key + password)  
✅ Credentials stored securely in Cloud Run environment variables  
✅ Automated script with limited attack surface (no interactive sessions)  
✅ Network traffic within AWS infrastructure  

#### Alternative Solutions for Future Implementation

**Option 1: Dynamic Host Key Retrieval**
```python
import subprocess

def get_current_host_key(hostname):
    result = subprocess.run(['ssh-keyscan', '-t', 'rsa', hostname], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        with open('/tmp/known_hosts', 'w') as f:
            f.write(result.stdout)
        return '/tmp/known_hosts'
    return None

# Use in connection setup
known_hosts_path = get_current_host_key(hostname)
if known_hosts_path:
    cnopts.hostkeys.load(known_hosts_path)
else:
    cnopts.hostkeys = None  # Fallback
```

**Option 2: Certificate-Based Authentication**
- Implement SSH certificate authority
- More scalable for dynamic environments
- Requires infrastructure changes

**Option 3: Host Key Fingerprint Verification**
- Store expected fingerprints in environment variables
- Implement custom verification logic
- More secure than complete bypass

#### Monitoring and Review
- **Review Frequency**: Quarterly security reviews
- **Monitoring**: Log SFTP connection events for anomaly detection
- **Trigger for Change**: Security policy updates, AWS infrastructure changes

#### Decision Makers
- **Technical Lead**: [Your Name]
- **Security Review**: [If applicable]
- **Business Justification**: Operational necessity for automated data collection

---

## Security Best Practices

### Environment Variables
All sensitive credentials stored in Cloud Run environment variables:
- `TOAST_SFTP_PRIVATE_KEY`: SSH private key (password protected)
- `TOAST_SFTP_PASSWORD`: Private key passphrase
- `GOOGLE_REFRESH_TOKEN`: OAuth refresh token
- `GOOGLE_CLIENT_SECRET`: OAuth client secret

### Access Controls
- Cloud Run Job runs with minimal IAM permissions
- SFTP access restricted to specific export directory
- Google Drive access scoped to single folder

### Audit Trail
- All operations logged to Cloud Logging
- Failed authentication attempts monitored
- File transfer events tracked

---

*Last Updated: August 3, 2025*  
*Next Review Due: November 3, 2025*
