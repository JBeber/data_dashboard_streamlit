# Technical Debt and Future Improvements

## 🔶 Security Technical Debt

### [MEDIUM] SFTP Host Key Verification Disabled
- **File**: `background_data_collector.py:337`
- **Impact**: Potential MITM attacks
- **Effort**: 2-3 days
- **Priority**: Medium
- **Dependencies**: None
- **Solution**: Implement dynamic host key retrieval
- **Tracking Issue**: [Create GitHub issue if using GitHub]

## 🔧 Performance Improvements

### [LOW] Implement Connection Pooling
- **File**: `background_data_collector.py`
- **Impact**: Reduced connection overhead
- **Effort**: 1 day
- **Priority**: Low

## 🚀 Feature Enhancements

### [MEDIUM] Real-time Data Status Dashboard
- **File**: `app.py`
- **Impact**: Better user experience
- **Effort**: 3-5 days
- **Priority**: Medium
- **Dependencies**: Cloud Run API integration

## 📊 Monitoring Improvements

### [HIGH] Alerting on Job Failures
- **Impact**: Faster incident response
- **Effort**: 1-2 days
- **Priority**: High
- **Solution**: Cloud Monitoring alerts + email notifications

---

## Review Schedule

- **Weekly**: Check for new technical debt
- **Monthly**: Prioritize and plan improvements
- **Quarterly**: Security-focused review of all technical debt

## Template for New Entries

```markdown
### [PRIORITY] Brief Description
- **File**: path/to/file.py:line
- **Impact**: What this affects
- **Effort**: Time estimate
- **Priority**: High/Medium/Low
- **Dependencies**: What needs to be done first
- **Solution**: Brief description of fix
- **Tracking Issue**: Link to issue tracker
```
