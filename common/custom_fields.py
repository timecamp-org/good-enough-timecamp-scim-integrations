"""
Shared helpers for TimeCamp user custom fields.

Fetch scripts write custom fields into var/users.json as a `custom_fields`
object keyed by the TimeCamp custom field name:

    "custom_fields": {"Job Position": "Developer", "Cost Center": null}

A string value sets the TimeCamp field, null clears it, and a field missing
from the object is left unchanged. The helpers below keep the format the same
for every source system.
"""

import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

NUMBER_PATTERN = re.compile(r'^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$')


def parse_custom_field_mapping(value: Optional[str], setting_name: str) -> List[Tuple[str, str]]:
    """Parse 'source_field:TimeCamp field name' pairs separated by commas.

    The first colon separates the pair, so TimeCamp field names can contain colons.
    """
    if not value or not value.strip():
        return []

    mapping = []
    seen_names = set()
    for entry in value.split(','):
        entry = entry.strip()
        if not entry:
            continue

        source_field, separator, timecamp_name = entry.partition(':')
        source_field = source_field.strip()
        timecamp_name = timecamp_name.strip()
        if not separator or not source_field or not timecamp_name:
            raise ValueError(
                f"{setting_name} entry '{entry}' must use the format 'source_field:TimeCamp field name'"
            )

        if timecamp_name.casefold() in seen_names:
            raise ValueError(
                f"{setting_name} maps more than one source field to TimeCamp custom field '{timecamp_name}'"
            )
        seen_names.add(timecamp_name.casefold())
        mapping.append((source_field, timecamp_name))

    return mapping


def normalize_custom_field_value(value: Any) -> Optional[str]:
    """Convert a source value to the string TimeCamp stores, or None to clear the field."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        items = [normalize_custom_field_value(item) for item in value]
        joined = ', '.join(item for item in items if item is not None)
        return joined or None
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)

    normalized = str(value).strip()
    return normalized or None


def normalize_custom_fields(custom_fields: Any) -> Optional[Dict[str, Optional[str]]]:
    """Normalize a `custom_fields` object from var/users.json.

    Returns None when the user has no `custom_fields` object.
    """
    if custom_fields is None:
        return None
    if not isinstance(custom_fields, dict):
        raise ValueError(
            f"custom_fields must be an object of TimeCamp field names to values, got {type(custom_fields).__name__}"
        )

    normalized = {}
    for name, value in custom_fields.items():
        name = str(name).strip()
        if name:
            normalized[name] = normalize_custom_field_value(value)
    return normalized


def extract_custom_fields(
    record: Any,
    mapping: List[Tuple[str, str]],
    get_value: Callable[[Any, str], Any],
) -> Dict[str, Optional[str]]:
    """Build a `custom_fields` object from a source record and a parsed mapping."""
    return {
        timecamp_name: normalize_custom_field_value(get_value(record, source_field))
        for source_field, timecamp_name in mapping
    }


def is_valid_number(value: str) -> bool:
    """Return True when TimeCamp accepts the value for a number custom field."""
    return bool(NUMBER_PATTERN.match(value))


def custom_field_values_equal(current: Optional[str], desired: Optional[str], field_type: str) -> bool:
    """Compare a stored TimeCamp value with a desired value."""
    if current is None or desired is None:
        return current is None and desired is None
    current = str(current)
    if field_type == 'number' and is_valid_number(current) and is_valid_number(desired):
        return float(current) == float(desired)
    return current == desired
