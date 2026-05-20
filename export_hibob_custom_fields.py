import argparse
import os
import requests
from dotenv import load_dotenv

from common.logger import setup_logger
from common.storage import save_json_file
from fetch_hibob import build_headers

logger = None


def is_custom_hibob_field(field):
    """Return True when HiBob field metadata represents a custom field."""
    field_id = field.get("id", "") or ""
    json_path = field.get("jsonPath", "") or ""

    return (
        ".custom." in field_id
        or field_id.startswith("custom.")
        or ".custom." in json_path
        or json_path.startswith("custom.")
    )


def fetch_hibob_custom_fields(output_path="var/hibob_custom_fields.json", debug=False):
    """Export HiBob custom field metadata to a JSON file."""
    global logger

    if logger is None:
        logger = setup_logger("export_hibob_custom_fields", debug=debug)

    load_dotenv()

    service_user_id = os.getenv("HIBOB_SERVICE_USER_ID")
    service_user_token = os.getenv("HIBOB_SERVICE_USER_TOKEN")

    if not all([service_user_id, service_user_token]):
        raise ValueError("Missing required environment variables: HIBOB_SERVICE_USER_ID and HIBOB_SERVICE_USER_TOKEN")

    headers = build_headers(service_user_id, service_user_token)
    url = "https://api.hibob.com/v1/company/people/fields"

    logger.info("Fetching HiBob field metadata...")
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    fields = response.json()
    if not isinstance(fields, list):
        raise ValueError("Unexpected HiBob field metadata response format")

    custom_fields = [field for field in fields if is_custom_hibob_field(field)]
    custom_fields.sort(
        key=lambda field: (
            field.get("categoryDisplayName") or field.get("category") or "",
            field.get("name") or "",
            field.get("id") or "",
        )
    )

    category_counts = {}
    for field in custom_fields:
        category = field.get("categoryDisplayName") or field.get("category") or "unknown"
        category_counts[category] = category_counts.get(category, 0) + 1

    output_data = {
        "source": "https://api.hibob.com/v1/company/people/fields",
        "total_fields_count": len(fields),
        "custom_fields_count": len(custom_fields),
        "custom_field_categories": category_counts,
        "custom_fields": custom_fields,
    }

    save_json_file(output_data, output_path)
    logger.info("Saved %s custom HiBob fields to %s", len(custom_fields), output_path)

    return output_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export HiBob custom field metadata")
    parser.add_argument(
        "--output",
        default="var/hibob_custom_fields.json",
        help="Output path for the exported JSON file",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    fetch_hibob_custom_fields(output_path=args.output, debug=args.debug)
