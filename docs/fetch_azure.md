# Azure AD / Microsoft Entra ID Setup

1. Register an application in Azure AD/Entra ID portal:
   - Go to Azure Portal > Azure Active Directory > App registrations > New registration
   - Name your application (e.g., "TimeCamp SCIM Integration")
   - Select "Accounts in this organizational directory only"
   - Click Register
   - Note down the Application (client) ID and Directory (tenant) ID

2. Create a client secret:
   - Go to your app > Certificates & secrets > New client secret
   - Give it a description (e.g., "SCIM Integration")
   - Select an expiration (e.g., 24 months)
   - Click Add
   - IMMEDIATELY copy the "Value" column (NOT the Secret ID)
   - ⚠️ The secret value will only be shown once and looks like `kv~8Q~...`
   - If you copied the wrong value or lost it, create a new secret

3. Configure API permissions:
   - Go to your app > API permissions
   - Click "Add a permission"
   - Select "Microsoft Graph" > "Application permissions"
   - Add these permissions:
     * Directory.Read.All
     * User.Read.All
     * Group.Read.All
   - Click "Grant admin consent" button

4. Configure OAuth credentials in `.env`:
```bash
AZURE_TENANT_ID=your-tenant-id  # Directory (tenant) ID
AZURE_CLIENT_ID=your-client-id  # Application (client) ID
AZURE_CLIENT_SECRET=your-client-secret  # The secret value you copied
```

5. (Optional) Configure email preference:
   - By default, the script uses the federated ID (userPrincipalName) as the primary email
   - To use real email addresses (mail attribute) when available, add this to your `.env`:
```bash
AZURE_PREFER_REAL_EMAIL=true
```

6. (Optional) Sync an Azure email field as TimeCamp additional email:
   - Primary email behavior remains controlled by `AZURE_PREFER_REAL_EMAIL`
   - To use Azure `mail` as primary email and `userPrincipalName` as `additional_email`:
```bash
AZURE_PREFER_REAL_EMAIL=true
AZURE_ADDITIONAL_EMAIL_SOURCE=userPrincipalName
TIMECAMP_DISABLE_ADDITIONAL_EMAIL_SYNC=false
```
   - To use Azure `userPrincipalName` as primary email and `mail` as `additional_email`:
```bash
AZURE_PREFER_REAL_EMAIL=false
AZURE_ADDITIONAL_EMAIL_SOURCE=mail
TIMECAMP_DISABLE_ADDITIONAL_EMAIL_SYNC=false
```

7. (Optional) Grant TimeCamp supervisor role from Azure groups:
   - Create one or more Azure AD / Entra ID groups for supervisors, for example `TimeCamp Supervisors`
   - Add the desired users to those groups
   - Configure them in `.env` as a comma-separated list:
```bash
AZURE_SUPERVISOR_GROUPS=TimeCamp Supervisors,Team Leads
```