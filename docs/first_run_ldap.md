# Testing LDAP

## 1) 

Requirements: python3+ & git

## 2) 

`git clone https://github.com/timecamp-org/good-enough-timecamp-scim-integrations.git /var/www/scim`

## 3) 

```bash
cd /var/www/scim
touch .env
```

Insert in .env:

```bash
# 1. FETCH DATA FROM EXTERNAL SOURCES (fetch_*.py)
LDAP_HOST=ldap.example.com
LDAP_PORT=389
LDAP_DOMAIN=example.com
LDAP_DN=DC=example,DC=com
LDAP_USERNAME=ldap_username
LDAP_PASSWORD=ldap_password
LDAP_FILTER=(&(objectClass=person)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))
LDAP_PAGE_SIZE=1000  # Number of results per page (reduce if hitting server limits)
LDAP_USE_SAMACCOUNTNAME=false  # Set to true to generate email from sAMAccountName instead of mail attribute
LDAP_USE_OU_STRUCTURE=false  # Set to true to use the OU structure from DN instead of department attribute
LDAP_USE_REAL_EMAIL_AS_EMAIL=false  # Set to true to use real_email as primary email and clear real_email field
LDAP_USE_WINDOWS_LOGIN_EMAIL=false  # Set to true to generate email as {windows_login}@domain format
LDAP_EMAIL_DOMAIN=  # Custom domain for email generation (optional, defaults to LDAP_DOMAIN)
LDAP_USE_SSL=false  # Set to true to use LDAPS (SSL) connection (port 636)
LDAP_USE_START_TLS=false  # Set to true to use StartTLS to upgrade connection to encrypted
LDAP_SSL_VERIFY=true  # Set to false to disable SSL certificate verification (not recommended for production)

# 2. PREPARE TIMECAMP STRUCTURE (prepare_timecamp_json_from_fetch.py)
TIMECAMP_USE_SUPERVISOR_GROUPS=false
TIMECAMP_USE_DEPARTMENT_GROUPS=true

# 3. SYNCHRONIZE TO TIMECAMP (timecamp_sync_users.py)
TIMECAMP_API_KEY=your_api_key_here # (key from main account)
TIMECAMP_DOMAIN=app.timecamp.com # or on-prem domain
TIMECAMP_ROOT_GROUP_ID=18
TIMECAMP_IGNORED_USER_IDS=3
```

## 4)

```bash
sudo apt update
sudo apt install -y build-essential python3-dev libldap2-dev libsasl2-dev libssl-dev pkg-config python3-venv python3-pip 

cd /var/www/scim
python3 -m venv .venv
. .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
pip install --no-cache-dir -r requirements.txt

python3 fetch_ldap.py
python3 prepare_timecamp_json_from_fetch.py
python3 scripts/display_timecamp_tree.py > sample_structure.txt
```
