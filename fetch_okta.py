import argparse
import json
import os
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from common.logger import setup_logger

logger = None

NOT_FOUND_USERS_CACHE = set()


def get_logger():
    """Return a module logger, initializing it for direct helper use."""
    global logger
    if logger is None:
        logger = setup_logger()
    return logger


def parse_csv(value):
    """Parse a comma-separated environment value into non-empty strings."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def normalize_org_url(org_url):
    """Normalize an Okta org URL for API calls."""
    if not org_url:
        return ""

    normalized = org_url.strip().rstrip("/")
    if normalized and not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"
    return normalized


def build_headers(api_token):
    """Build Okta API token headers."""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"SSWS {api_token}",
    }


def get_nested_value(data, path, default=""):
    """Read a dotted path from nested dictionaries."""
    if not path:
        return default

    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return default

        if current is None:
            return default

    return current


def get_profile_value(user, field_name, default=""):
    """Read a field from Okta profile, with dotted paths supported."""
    profile = user.get("profile", {}) or {}

    if not field_name:
        return default

    if "." in field_name:
        return get_nested_value(user, field_name, default)

    return profile.get(field_name, default)


def get_external_id(user, field_name):
    """Read the configured identifier, defaulting to Okta's top-level user ID."""
    if not field_name or field_name == "id":
        value = user.get("id", "")
    else:
        value = get_profile_value(user, field_name)

    return str(value) if value is not None else ""


def normalize_match_value(value, field_name):
    """Normalize identifiers used to match manager references to Okta users."""
    normalized = str(value).strip() if value is not None else ""
    field_leaf = (field_name or "").rsplit(".", 1)[-1].lower()
    if field_leaf in {"email", "login"}:
        return normalized.casefold()
    return normalized


def get_supervisor_reference(user, field_name):
    """Read the raw manager reference from an Okta user."""
    value = get_profile_value(user, field_name)
    if isinstance(value, dict):
        value = value.get("id", "")
    return str(value) if value else ""


def build_display_name(profile, name_field):
    """Build a stable display name from Okta profile fields."""
    display_name = profile.get(name_field) if name_field else ""
    if display_name:
        return str(display_name).strip()

    first_name = profile.get("firstName", "") or ""
    last_name = profile.get("lastName", "") or ""
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name

    return profile.get("email") or profile.get("login") or ""


def parse_supervisor_rule(rule):
    """Parse a field:value rule used to set is_supervisor."""
    if not rule or ":" not in rule:
        return None, None

    field, value = rule.split(":", 1)
    field = field.strip()
    value = value.strip()

    if not field:
        return None, None

    return field, value


def transform_okta_user_to_schema(user, field_config=None, supervisor_field=None, supervisor_value=None):
    """Transform an Okta user object to the internal source-user schema."""
    field_config = field_config or {}
    profile = user.get("profile", {}) or {}

    email_field = field_config.get("email", "email")
    name_field = field_config.get("name", "displayName")
    department_field = field_config.get("department", "department")
    job_title_field = field_config.get("job_title", "title")
    supervisor_id_field = field_config.get("supervisor_id", "managerId")
    external_id_field = field_config.get("external_id", "id")

    email = get_profile_value(user, email_field) or profile.get("login", "")
    supervisor_id = get_supervisor_reference(user, supervisor_id_field)

    is_supervisor = False
    if supervisor_field and supervisor_value is not None:
        field_value = get_profile_value(user, supervisor_field)
        is_supervisor = str(field_value).strip() == supervisor_value

    return {
        "external_id": get_external_id(user, external_id_field),
        "name": build_display_name(profile, name_field),
        "email": str(email).lower() if email else "",
        "department": get_profile_value(user, department_field, ""),
        "job_title": get_profile_value(user, job_title_field, ""),
        "status": "active" if user.get("status") == "ACTIVE" else "inactive",
        "supervisor_id": str(supervisor_id) if supervisor_id else "",
        "is_supervisor": is_supervisor,
        "raw_data": user,
    }


def resolve_supervisor_ids(users, field_config, supervisor_match_field):
    """Translate raw manager references to the managers' configured external IDs."""
    supervisor_id_field = field_config.get("supervisor_id", "managerId")
    users_by_match_value = {}

    for user in users:
        external_id = user.get("external_id")
        raw_data = user.get("raw_data", {})
        match_value = normalize_match_value(
            get_external_id(raw_data, supervisor_match_field),
            supervisor_match_field,
        )
        if not external_id or not match_value:
            continue

        existing_external_id = users_by_match_value.get(match_value)
        if existing_external_id and existing_external_id != external_id:
            raise ValueError(
                f"Okta supervisor match field '{supervisor_match_field}' is not unique: "
                f"'{match_value}'"
            )
        users_by_match_value[match_value] = external_id

    unresolved_references = set()
    for user in users:
        raw_data = user.get("raw_data")
        if raw_data is None:
            reference = str(user.get("supervisor_id") or "")
        else:
            reference = get_supervisor_reference(raw_data, supervisor_id_field)
        if not reference:
            user["supervisor_id"] = ""
            continue

        match_value = normalize_match_value(reference, supervisor_match_field)
        resolved_external_id = users_by_match_value.get(match_value)
        if resolved_external_id:
            user["supervisor_id"] = resolved_external_id
        else:
            user["supervisor_id"] = reference
            unresolved_references.add(reference)

    return unresolved_references


class OktaClient:
    def __init__(self, org_url, api_token):
        self.org_url = normalize_org_url(org_url)
        self.headers = build_headers(api_token)

    def _url(self, path_or_url):
        if path_or_url.startswith(("http://", "https://")):
            return path_or_url
        return f"{self.org_url}{path_or_url}"

    def get(self, path_or_url, params=None):
        response = requests.get(self._url(path_or_url), headers=self.headers, params=params)
        response.raise_for_status()
        return response

    def paginated_get(self, path_or_url, params=None):
        url = self._url(path_or_url)
        next_params = params

        while url:
            response = self.get(url, params=next_params)
            data = response.json()

            if isinstance(data, list):
                yield from data
            else:
                yield data

            links = response.links if isinstance(getattr(response, "links", None), dict) else {}
            url = links.get("next", {}).get("url")
            next_params = None

    def list_users(self, statuses):
        seen_user_ids = set()
        statuses = statuses or ["ACTIVE"]

        for status in statuses:
            params = {
                "limit": 200,
                "filter": f'status eq "{status}"',
            }
            for user in self.paginated_get("/api/v1/users", params=params):
                user_id = user.get("id")
                if user_id in seen_user_ids:
                    continue
                seen_user_ids.add(user_id)
                yield user

    def get_user(self, user_id):
        encoded_user_id = quote(str(user_id), safe="")
        response = self.get(f"/api/v1/users/{encoded_user_id}")
        return response.json()

    def find_user_by_field(self, field_name, value):
        """Find one user by an Okta top-level or profile field."""
        if field_name in {"id", "login", "profile.login"}:
            candidate = self.get_user(value)
            candidate_value = normalize_match_value(
                get_external_id(candidate, field_name),
                field_name,
            )
            return candidate if candidate_value == normalize_match_value(value, field_name) else None

        search_field = field_name if "." in field_name else f"profile.{field_name}"
        escaped_value = str(value).replace("\\", "\\\\").replace('"', '\\"')
        params = {
            "limit": 2,
            "search": f'{search_field} eq "{escaped_value}"',
        }
        candidates = list(self.paginated_get("/api/v1/users", params=params))
        normalized_value = normalize_match_value(value, field_name)
        matches = [
            candidate
            for candidate in candidates
            if normalize_match_value(get_external_id(candidate, field_name), field_name) == normalized_value
        ]

        if len(matches) > 1:
            raise ValueError(
                f"Okta supervisor match field '{field_name}' is not unique: '{value}'"
            )
        return matches[0] if matches else None

    def find_group_by_name(self, group_name):
        params = {"q": group_name, "limit": 200}

        for group in self.paginated_get("/api/v1/groups", params=params):
            profile = group.get("profile", {}) or {}
            if profile.get("name") == group_name:
                return group

        get_logger().warning(f"No Okta group found with name: {group_name}")
        return None

    def list_group_users(self, group_id):
        encoded_group_id = quote(str(group_id), safe="")
        return self.paginated_get(f"/api/v1/groups/{encoded_group_id}/users", params={"limit": 200})


def collect_group_member_ids(group_names, group_purpose, client):
    """Collect unique Okta user IDs from groups identified by exact profile.name."""
    if not group_names:
        return set()

    member_ids = set()
    get_logger().info(f"Resolving Okta {group_purpose} groups: {group_names}")

    for group_name in group_names:
        group = client.find_group_by_name(group_name)
        if not group:
            continue

        group_id = group.get("id")
        group_members = client.list_group_users(group_id)
        for user in group_members:
            user_id = user.get("id")
            if user_id:
                member_ids.add(user_id)

    if not member_ids:
        get_logger().warning(f"No users found in the specified Okta {group_purpose} groups.")

    return member_ids


def fetch_missing_supervisors(
    client,
    users,
    field_config,
    supervisor_field=None,
    supervisor_value=None,
    supervisor_match_field=None,
):
    """Fetch supervisors referenced by users but missing from the current output."""
    supervisor_match_field = supervisor_match_field or field_config.get("external_id", "id")
    unresolved_references = resolve_supervisor_ids(users, field_config, supervisor_match_field)
    missing_supervisor_ids = unresolved_references - NOT_FOUND_USERS_CACHE

    if not missing_supervisor_ids:
        return []

    get_logger().info(f"Found {len(missing_supervisor_ids)} missing Okta supervisors, fetching...")

    inactive_supervisors = []

    for supervisor_id in sorted(missing_supervisor_ids):
        try:
            okta_user = client.find_user_by_field(supervisor_match_field, supervisor_id)
        except requests.exceptions.HTTPError as exc:
            response = getattr(exc, "response", None)
            if response is not None and response.status_code == 404:
                NOT_FOUND_USERS_CACHE.add(supervisor_id)
                get_logger().warning(f"Could not find Okta supervisor: {supervisor_id}")
                continue
            raise

        if not okta_user:
            NOT_FOUND_USERS_CACHE.add(supervisor_id)
            get_logger().warning(
                f"Could not find Okta supervisor where {supervisor_match_field} = '{supervisor_id}'"
            )
            continue

        user = transform_okta_user_to_schema(okta_user, field_config, supervisor_field, supervisor_value)
        if not user.get("external_id"):
            NOT_FOUND_USERS_CACHE.add(supervisor_id)
            get_logger().warning(
                f"Could not link Okta supervisor '{supervisor_id}': configured external ID is empty"
            )
            continue
        user["status"] = "inactive"
        inactive_supervisors.append(user)

    all_users = users + inactive_supervisors
    new_missing_ids = resolve_supervisor_ids(
        all_users,
        field_config,
        supervisor_match_field,
    ) - NOT_FOUND_USERS_CACHE

    if new_missing_ids:
        temp_users = users + inactive_supervisors
        inactive_supervisors.extend(
            fetch_missing_supervisors(
                client,
                temp_users,
                field_config,
                supervisor_field,
                supervisor_value,
                supervisor_match_field,
            )
        )

    resolve_supervisor_ids(
        users + inactive_supervisors,
        field_config,
        supervisor_match_field,
    )

    return inactive_supervisors


def fetch_okta_users(debug=False):
    """Fetch users from Okta and save them to var/users.json."""
    global logger

    if logger is None:
        logger = setup_logger(debug=debug)

    try:
        load_dotenv()

        if os.getenv("DEBUG", "false").lower() == "true":
            logger = setup_logger(debug=True)

        org_url = os.getenv("OKTA_ORG_URL")
        api_token = os.getenv("OKTA_API_TOKEN")
        if not all([org_url, api_token]):
            raise ValueError("Missing required environment variables: OKTA_ORG_URL and OKTA_API_TOKEN")

        statuses = [status.upper() for status in parse_csv(os.getenv("OKTA_USER_STATUSES", "ACTIVE"))]
        filter_groups = parse_csv(os.getenv("OKTA_FILTER_GROUPS", ""))
        supervisor_groups = parse_csv(os.getenv("OKTA_SUPERVISOR_GROUPS", ""))
        excluded_departments = set(parse_csv(os.getenv("OKTA_EXCLUDED_DEPARTMENTS", "")))

        field_config = {
            "external_id": os.getenv("OKTA_EXTERNAL_ID_FIELD", "id"),
            "email": os.getenv("OKTA_EMAIL_FIELD", "email"),
            "name": os.getenv("OKTA_NAME_FIELD", "displayName"),
            "department": os.getenv("OKTA_DEPARTMENT_FIELD", "department"),
            "job_title": os.getenv("OKTA_JOB_TITLE_FIELD", "title"),
            "supervisor_id": os.getenv("OKTA_SUPERVISOR_ID_FIELD", "managerId"),
        }
        supervisor_match_field = (
            os.getenv("OKTA_SUPERVISOR_MATCH_FIELD", "").strip() or field_config["external_id"]
        )

        supervisor_field, supervisor_value = parse_supervisor_rule(os.getenv("OKTA_SUPERVISOR_RULE", ""))
        if supervisor_field and supervisor_value is not None:
            logger.info(f"Using Okta supervisor rule: {supervisor_field} = '{supervisor_value}'")

        client = OktaClient(org_url, api_token)

        filtered_user_ids = collect_group_member_ids(filter_groups, "filter", client)
        supervisor_user_ids = collect_group_member_ids(supervisor_groups, "supervisor", client)

        users = []
        logger.info("Fetching users from Okta...")

        for okta_user in client.list_users(statuses):
            user_id = okta_user.get("id")
            if filter_groups and user_id not in filtered_user_ids:
                continue

            user = transform_okta_user_to_schema(okta_user, field_config, supervisor_field, supervisor_value)

            if not user.get("email"):
                continue

            if user.get("department") in excluded_departments:
                continue

            if user_id in supervisor_user_ids:
                user["role_id"] = "2"

            logger.debug(f"Processed Okta user: {json.dumps(user, indent=2)}")
            users.append(user)

        logger.info("Checking for missing Okta supervisors in the hierarchy...")
        inactive_supervisors = fetch_missing_supervisors(
            client,
            users,
            field_config,
            supervisor_field,
            supervisor_value,
            supervisor_match_field,
        )

        if inactive_supervisors:
            logger.info(f"Found {len(inactive_supervisors)} inactive supervisors to complete the hierarchy")
            users.extend(inactive_supervisors)

        from common.storage import save_json_file

        save_json_file({"users": users}, "var/users.json")

        logger.info(
            f"Successfully saved {len(users)} users to var/users.json "
            f"({len(users) - len(inactive_supervisors)} active, {len(inactive_supervisors)} inactive supervisors)"
        )

    except requests.exceptions.RequestException as exc:
        logger.error(f"Error fetching Okta users: {str(exc)}")
        raise
    except Exception as exc:
        logger.error(f"Error processing Okta users: {str(exc)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch users from Okta")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    fetch_okta_users(debug=args.debug)
