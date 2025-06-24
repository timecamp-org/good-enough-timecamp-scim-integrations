{{/*
Expand the name of the chart.
*/}}
{{- define "timecamp-scim.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "timecamp-scim.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "timecamp-scim.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "timecamp-scim.labels" -}}
helm.sh/chart: {{ include "timecamp-scim.chart" . }}
{{ include "timecamp-scim.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "timecamp-scim.selectorLabels" -}}
app.kubernetes.io/name: {{ include "timecamp-scim.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "timecamp-scim.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "timecamp-scim.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the image name
*/}}
{{- define "timecamp-scim.image" -}}
{{- $registry := .Values.image.registry -}}
{{- $repository := .Values.image.repository -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end }}

{{/*
Common environment variables
*/}}
{{- define "timecamp-scim.commonEnv" -}}
{{- range $key, $value := .Values.env }}
- name: {{ $key }}
  value: {{ $value | quote }}
{{- end }}
{{- /* TimeCamp Configuration */ -}}
{{- with .Values.config.timecamp }}
- name: TIMECAMP_DOMAIN
  value: {{ .domain | quote }}
{{- if .rootGroupId }}
- name: TIMECAMP_ROOT_GROUP_ID
  value: {{ .rootGroupId | quote }}
{{- end }}
{{- if .ignoredUserIds }}
- name: TIMECAMP_IGNORED_USER_IDS
  value: {{ .ignoredUserIds | quote }}
{{- end }}
- name: TIMECAMP_SHOW_EXTERNAL_ID
  value: {{ .showExternalId | quote }}
- name: TIMECAMP_SKIP_DEPARTMENTS
  value: {{ .skipDepartments | quote }}
- name: TIMECAMP_USE_SUPERVISOR_GROUPS
  value: {{ .useSupervisorGroups | quote }}
- name: TIMECAMP_USE_DEPARTMENT_GROUPS
  value: {{ .useDepartmentGroups | quote }}
- name: TIMECAMP_DISABLE_NEW_USERS
  value: {{ .disableNewUsers | quote }}
- name: TIMECAMP_DISABLE_EXTERNAL_ID_SYNC
  value: {{ .disableExternalIdSync | quote }}
- name: TIMECAMP_DISABLE_MANUAL_USER_UPDATES
  value: {{ .disableManualUserUpdates | quote }}
- name: TIMECAMP_USE_JOB_TITLE_NAME
  value: {{ .useJobTitleName | quote }}
{{- end }}
{{- /* BambooHR Configuration */ -}}
{{- with .Values.config.bamboohr }}
{{- if .subdomain }}
- name: BAMBOOHR_SUBDOMAIN
  value: {{ .subdomain | quote }}
{{- end }}
- name: BAMBOOHR_EXCLUDE_FILTER
  value: {{ .excludeFilter | quote }}
- name: BAMBOOHR_EXCLUDED_DEPARTMENTS
  value: {{ .excludedDepartments | quote }}
{{- end }}
{{- /* Azure AD Configuration */ -}}
{{- with .Values.config.azure }}
{{- if .tenantId }}
- name: AZURE_TENANT_ID
  value: {{ .tenantId | quote }}
{{- end }}
{{- if .clientId }}
- name: AZURE_CLIENT_ID
  value: {{ .clientId | quote }}
{{- end }}
- name: AZURE_SCIM_ENDPOINT
  value: {{ .scimEndpoint | quote }}
- name: AZURE_FILTER_GROUPS
  value: {{ .filterGroups | quote }}
- name: AZURE_PREFER_REAL_EMAIL
  value: {{ .preferRealEmail | quote }}
- name: AZURE_TOKEN_EXPIRES_AT
  value: {{ .tokenExpiresAt | quote }}
- name: AZURE_REFRESH_TOKEN_EXPIRES_AT
  value: {{ .refreshTokenExpiresAt | quote }}
{{- end }}
{{- /* LDAP Configuration */ -}}
{{- with .Values.config.ldap }}
{{- if .host }}
- name: LDAP_HOST
  value: {{ .host | quote }}
{{- end }}
- name: LDAP_PORT
  value: {{ .port | quote }}
{{- if .domain }}
- name: LDAP_DOMAIN
  value: {{ .domain | quote }}
{{- end }}
{{- if .dn }}
- name: LDAP_DN
  value: {{ .dn | quote }}
{{- end }}
{{- if .username }}
- name: LDAP_USERNAME
  value: {{ .username | quote }}
{{- end }}
- name: LDAP_FILTER
  value: {{ .filter | quote }}
- name: LDAP_EMAIL_DOMAIN
  value: {{ .emailDomain | quote }}
- name: LDAP_PAGE_SIZE
  value: {{ .pageSize | quote }}
- name: LDAP_USE_SAMACCOUNTNAME
  value: {{ .useSamaccountname | quote }}
- name: LDAP_USE_OU_STRUCTURE
  value: {{ .useOuStructure | quote }}
- name: LDAP_USE_REAL_EMAIL_AS_EMAIL
  value: {{ .useRealEmailAsEmail | quote }}
- name: LDAP_USE_WINDOWS_LOGIN_EMAIL
  value: {{ .useWindowsLoginEmail | quote }}
- name: LDAP_USE_SSL
  value: {{ .useSsl | quote }}
- name: LDAP_USE_START_TLS
  value: {{ .useStartTls | quote }}
- name: LDAP_SSL_VERIFY
  value: {{ .sslVerify | quote }}
{{- end }}
{{- /* FactorialHR Configuration */ -}}
{{- with .Values.config.factorial }}
- name: FACTORIAL_API_URL
  value: {{ .apiUrl | quote }}
- name: LeaveTypeMap
  value: {{ .leaveTypeMap | quote }}
{{- end }}
{{- /* S3 Configuration */ -}}
{{- with .Values.s3 }}
- name: USE_S3_STORAGE
  value: {{ .enabled | quote }}
- name: S3_ENDPOINT_URL
  value: {{ .endpointUrl | quote }}
- name: S3_REGION
  value: {{ .region | quote }}
- name: S3_BUCKET_NAME
  value: {{ .bucketName | quote }}
- name: S3_PATH_PREFIX
  value: {{ .pathPrefix | quote }}
- name: S3_FORCE_PATH_STYLE
  value: {{ .forcePathStyle | quote }}
{{- end }}
{{- end }}

{{/*
Secret environment variables from External Secrets
*/}}
{{- define "timecamp-scim.secretEnv" -}}
- name: TIMECAMP_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "timecamp-scim.fullname" . }}-secrets
      key: TIMECAMP_API_KEY
{{- if or .Values.jobs.fetchBamboohr.enabled }}
- name: BAMBOOHR_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "timecamp-scim.fullname" . }}-secrets
      key: BAMBOOHR_API_KEY
      optional: true
{{- end }}
{{- if or .Values.jobs.fetchAzuread.enabled }}
- name: AZURE_CLIENT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ include "timecamp-scim.fullname" . }}-secrets
      key: AZURE_CLIENT_SECRET
      optional: true
- name: AZURE_BEARER_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ include "timecamp-scim.fullname" . }}-secrets
      key: AZURE_BEARER_TOKEN
      optional: true
- name: AZURE_REFRESH_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ include "timecamp-scim.fullname" . }}-secrets
      key: AZURE_REFRESH_TOKEN
      optional: true
{{- end }}
{{- if or .Values.jobs.fetchLdap.enabled }}
- name: LDAP_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "timecamp-scim.fullname" . }}-secrets
      key: LDAP_PASSWORD
      optional: true
{{- end }}
{{- if or .Values.jobs.fetchFactorial.enabled .Values.jobs.syncTimeOff.enabled }}
- name: FACTORIAL_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "timecamp-scim.fullname" . }}-secrets
      key: FACTORIAL_API_KEY
      optional: true
{{- end }}
# S3 credentials
- name: S3_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "timecamp-scim.fullname" . }}-secrets
      key: S3_ACCESS_KEY_ID
- name: S3_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "timecamp-scim.fullname" . }}-secrets
      key: S3_SECRET_ACCESS_KEY
{{- end }}