# Crontab Setup

To automate the synchronization with the two-stage process:

```bash
# Edit crontab
crontab -e

# For BambooHR:
# Fetch users from BambooHR every hour
0 * * * * cd /path/to/project && python fetch_bamboohr.py

# For Okta, use fetch_okta.py instead:
# 0 * * * * cd /path/to/project && python fetch_okta.py

# For HiBob, use this fetch command instead:
# 0 * * * * cd /path/to/project && python fetch_hibob.py

# Prepare TimeCamp data 10 minutes after fetch
10 * * * * cd /path/to/project && python prepare_timecamp_json_from_fetch.py

# Sync with TimeCamp 10 minutes after fetch
20 * * * * cd /path/to/project && python timecamp_sync_users.py
```

Notes:
- Replace `/path/to/project` with the actual path to your project
- All operations are logged to `var/logs/sync.log`
