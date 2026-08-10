"""Fetch NetSuite employees and department hierarchy for the TimeCamp user sync."""

from __future__ import annotations

import argparse
import os
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import jwt
import requests
from dotenv import load_dotenv

from common.logger import setup_logger
from common.storage import save_json_file

DEFAULT_EMPLOYEE_QUERY = """
SELECT
    e.id AS external_id,
    e.email AS email,
    e.firstname AS first_name,
    e.lastname AS last_name,
    e.entityid AS name,
    e.title AS job_title,
    e.supervisor AS supervisor_id,
    e.department AS group_id,
    BUILTIN.DF(e.department) AS group_name,
    CASE WHEN e.isinactive = 'F' THEN 'active' ELSE 'inactive' END AS status
FROM employee e
WHERE e.email IS NOT NULL
""".strip()

DEFAULT_GROUP_QUERY = """
SELECT
    d.id AS group_id,
    d.name AS group_name,
    d.parent AS parent_id
FROM department d
""".strip()

logger = setup_logger("fetch_netsuite")


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing {name} environment variable")
    return value


def _parse_positive_integer(name: str, default: int, maximum: int | None = None) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must not exceed {maximum}")
    return value


def _load_private_key() -> str:
    inline_key = os.getenv("NETSUITE_PRIVATE_KEY", "").strip()
    key_path = os.getenv("NETSUITE_PRIVATE_KEY_PATH", "").strip()

    if inline_key:
        return inline_key.replace("\\n", "\n")
    if key_path:
        try:
            with open(key_path, encoding="utf-8") as private_key_file:
                return private_key_file.read()
        except OSError as exc:
            raise ValueError(
                f"Cannot read NETSUITE_PRIVATE_KEY_PATH: {key_path}"
            ) from exc
    raise ValueError(
        "Missing NetSuite private key: set NETSUITE_PRIVATE_KEY or "
        "NETSUITE_PRIVATE_KEY_PATH"
    )


@dataclass(frozen=True)
class NetSuiteConfig:
    account_id: str
    client_id: str
    certificate_id: str
    private_key: str
    employee_query: str = DEFAULT_EMPLOYEE_QUERY
    group_query: str = DEFAULT_GROUP_QUERY
    page_size: int = 1000
    timeout_seconds: int = 30
    ssl_verify: bool = True
    allow_empty_result: bool = False
    jwt_algorithm: str = "PS256"
    base_url: str | None = None

    @classmethod
    def from_env(cls) -> NetSuiteConfig:
        load_dotenv()
        account_id = _required_environment("NETSUITE_ACCOUNT_ID")
        algorithm = os.getenv("NETSUITE_JWT_ALGORITHM", "PS256").strip().upper()
        if algorithm not in {"PS256", "ES256", "ES512"}:
            raise ValueError(
                "NETSUITE_JWT_ALGORITHM must be one of: PS256, ES256, ES512"
            )

        base_url = os.getenv("NETSUITE_BASE_URL", "").strip().rstrip("/") or None
        return cls(
            account_id=account_id,
            client_id=_required_environment("NETSUITE_CLIENT_ID"),
            certificate_id=_required_environment("NETSUITE_CERTIFICATE_ID"),
            private_key=_load_private_key(),
            employee_query=(
                os.getenv("NETSUITE_EMPLOYEE_QUERY", "").strip()
                or DEFAULT_EMPLOYEE_QUERY
            ),
            group_query=(
                os.getenv("NETSUITE_GROUP_QUERY", "").strip() or DEFAULT_GROUP_QUERY
            ),
            page_size=_parse_positive_integer("NETSUITE_PAGE_SIZE", 1000, 1000),
            timeout_seconds=_parse_positive_integer("NETSUITE_TIMEOUT_SECONDS", 30),
            ssl_verify=os.getenv("NETSUITE_SSL_VERIFY", "true").lower() == "true",
            allow_empty_result=os.getenv("NETSUITE_ALLOW_EMPTY_RESULT", "false").lower()
            == "true",
            jwt_algorithm=algorithm,
            base_url=base_url,
        )

    @property
    def service_url(self) -> str:
        if self.base_url:
            return self.base_url
        domain_account_id = self.account_id.lower().replace("_", "-")
        return f"https://{domain_account_id}.suitetalk.api.netsuite.com"


class NetSuiteClient:
    """Small SuiteTalk REST client supporting OAuth 2.0 client credentials."""

    def __init__(
        self,
        config: NetSuiteConfig,
        session: requests.Session | None = None,
        now: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.now = now
        self.sleep = sleep
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0

    @property
    def token_url(self) -> str:
        return f"{self.config.service_url}/services/rest/auth/oauth2/v1/token"

    @property
    def suiteql_url(self) -> str:
        return f"{self.config.service_url}/services/rest/query/v1/suiteql"

    def _create_client_assertion(self) -> str:
        issued_at = int(self.now())
        payload = {
            "iss": self.config.client_id,
            "scope": ["rest_webservices"],
            "aud": self.token_url,
            "iat": issued_at,
            "exp": issued_at + 300,
            "jti": uuid.uuid4().hex,
        }
        headers = {
            "typ": "JWT",
            "alg": self.config.jwt_algorithm,
            "kid": self.config.certificate_id,
        }
        return jwt.encode(
            payload,
            self.config.private_key,
            algorithm=self.config.jwt_algorithm,
            headers=headers,
        )

    def _get_access_token(self, force_refresh: bool = False) -> str:
        if (
            not force_refresh
            and self._access_token
            and self.now() < self._access_token_expires_at
        ):
            return self._access_token

        response = self.session.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_assertion_type": (
                    "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
                ),
                "client_assertion": self._create_client_assertion(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.config.timeout_seconds,
            verify=self.config.ssl_verify,
        )
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("NetSuite token response did not contain access_token")

        expires_in = int(token_data.get("expires_in", 3600))
        self._access_token = str(access_token)
        self._access_token_expires_at = self.now() + max(expires_in - 60, 0)
        return self._access_token

    def _post_suiteql_page(self, query: str, offset: int) -> dict[str, Any]:
        force_refresh = False
        for attempt in range(4):
            response = self.session.post(
                self.suiteql_url,
                params={"limit": self.config.page_size, "offset": offset},
                json={"q": query},
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Prefer": "transient",
                    "Authorization": (
                        f"Bearer {self._get_access_token(force_refresh=force_refresh)}"
                    ),
                },
                timeout=self.config.timeout_seconds,
                verify=self.config.ssl_verify,
            )

            if response.status_code == 401 and not force_refresh:
                force_refresh = True
                continue
            if response.status_code in {429, 502, 503, 504} and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                self.sleep(min(delay, 60))
                continue

            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise TypeError("NetSuite SuiteQL response must be a JSON object")
            return result

        raise requests.RequestException("NetSuite SuiteQL request failed after retries")

    def run_suiteql(self, query: str) -> list[dict[str, Any]]:
        if not query.strip():
            raise ValueError("SuiteQL query cannot be empty")

        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._post_suiteql_page(query, offset)
            page_items = page.get("items", [])
            if not isinstance(page_items, list):
                raise TypeError("NetSuite SuiteQL response items must be a list")

            rows.extend(page_items)
            count = int(page.get("count", len(page_items)))
            has_more = bool(page.get("hasMore", False))
            if not has_more:
                break
            if count <= 0:
                raise ValueError("NetSuite returned hasMore=true without any rows")
            offset += count

        return rows


def _row_with_lowercase_keys(row: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key).lower(): value for key, value in row.items()}


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _string(value).lower() in {"1", "t", "true", "yes", "y"}


def _status(row: Mapping[str, Any]) -> str:
    status = _string(row.get("status")).lower()
    if status in {"inactive", "disabled", "terminated", "t", "true", "1"}:
        return "inactive"
    if status:
        return "active"
    return "inactive" if _boolean(row.get("is_inactive")) else "active"


def build_group_paths(group_rows: list[Mapping[str, Any]]) -> dict[str, str]:
    """Build slash-separated paths from rows aliased as group_id/name/parent_id."""
    groups: dict[str, dict[str, str]] = {}
    for original_row in group_rows:
        row = _row_with_lowercase_keys(original_row)
        group_id = _string(row.get("group_id"))
        group_name = _string(row.get("group_name"))
        if not group_id or not group_name:
            logger.warning("Skipping NetSuite group without group_id or group_name")
            continue
        if group_id in groups:
            raise ValueError(f"Duplicate NetSuite group_id: {group_id}")
        groups[group_id] = {
            "name": group_name,
            "parent_id": _string(row.get("parent_id")),
        }

    resolved: dict[str, str] = {}

    def resolve(group_id: str, resolving: list[str]) -> str:
        if group_id in resolved:
            return resolved[group_id]
        if group_id in resolving:
            cycle = " -> ".join([*resolving, group_id])
            raise ValueError(f"Cycle in NetSuite group hierarchy: {cycle}")

        group = groups[group_id]
        parent_id = group["parent_id"]
        if not parent_id:
            path = group["name"]
        elif parent_id not in groups:
            logger.warning(
                "NetSuite group %s references missing parent %s; using a root group",
                group_id,
                parent_id,
            )
            path = group["name"]
        else:
            parent_path = resolve(parent_id, [*resolving, group_id])
            path = f"{parent_path}/{group['name']}"

        resolved[group_id] = path
        return path

    for group_id in groups:
        resolve(group_id, [])
    return resolved


def transform_employees(
    employee_rows: list[Mapping[str, Any]], group_paths: Mapping[str, str]
) -> list[dict[str, Any]]:
    normalized_rows = [_row_with_lowercase_keys(row) for row in employee_rows]
    supervisor_ids = {
        _string(row.get("supervisor_id"))
        for row in normalized_rows
        if _string(row.get("supervisor_id"))
    }
    users: list[dict[str, Any]] = []

    for row in normalized_rows:
        external_id = _string(row.get("external_id"))
        email = _string(row.get("email"))
        if not external_id or not email:
            logger.warning("Skipping NetSuite employee without external_id or email")
            continue

        first_name = _string(row.get("first_name"))
        last_name = _string(row.get("last_name"))
        name = " ".join(part for part in (first_name, last_name) if part)
        name = name or _string(row.get("name")) or email.split("@", 1)[0]
        group_id = _string(row.get("group_id"))
        group_name = _string(row.get("group_name"))

        users.append(
            {
                "external_id": external_id,
                "job_title": _string(row.get("job_title")),
                "name": name,
                "email": email,
                "department": group_paths.get(group_id, group_name),
                "status": _status(row),
                "supervisor_id": _string(row.get("supervisor_id")),
                "is_supervisor": (
                    _boolean(row.get("is_supervisor")) or external_id in supervisor_ids
                ),
                "raw_data": dict(row),
            }
        )

    return users


def fetch_netsuite_users(
    debug: bool = False,
    config: NetSuiteConfig | None = None,
    client: NetSuiteClient | None = None,
) -> dict[str, Any]:
    global logger
    logger = setup_logger("fetch_netsuite", debug=debug)
    config = config or NetSuiteConfig.from_env()
    client = client or NetSuiteClient(config)

    logger.info("Fetching NetSuite department hierarchy")
    group_rows = client.run_suiteql(config.group_query)
    group_paths = build_group_paths(group_rows)

    logger.info("Fetching NetSuite employees")
    employee_rows = client.run_suiteql(config.employee_query)
    users = transform_employees(employee_rows, group_paths)
    active_users = [user for user in users if user["status"] == "active"]
    if not active_users and not config.allow_empty_result:
        raise ValueError(
            "NetSuite returned no active employees; refusing to overwrite var/users.json. "
            "Set NETSUITE_ALLOW_EMPTY_RESULT=true only if this is intentional."
        )

    output_data = {"users": users}
    save_json_file(output_data, "var/users.json")
    logger.info(
        "Saved %s NetSuite users (%s active) and %s group paths to var/users.json",
        len(users),
        len(active_users),
        len(group_paths),
    )
    return output_data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch NetSuite users and groups for TimeCamp synchronization"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    fetch_netsuite_users(debug=args.debug)


if __name__ == "__main__":
    main()
