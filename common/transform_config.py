import copy
import json
import os
from typing import Any, Dict, Optional, Tuple, List


def load_transform_config(config_value: str) -> Optional[Dict[str, Any]]:
    """
    Load a transform configuration from JSON string or file path.
    Returns None when no config is provided.
    """
    if not config_value:
        return None

    config_value = config_value.strip()
    if not config_value:
        return None

    if config_value.startswith("{") or config_value.startswith("["):
        return json.loads(config_value)

    if not os.path.exists(config_value):
        raise FileNotFoundError(f"Transform config file not found: {config_value}")

    with open(config_value, "r") as file_handle:
        return json.load(file_handle)


def apply_transform_config(data: Any, config: Optional[Dict[str, Any]]) -> Tuple[Any, bool]:
    """
    Apply transform rules to any JSON-like object.
    Returns (new_data, changed).
    """
    if not config:
        return data, False

    if isinstance(data, list):
        changed_any = False
        output: List[Any] = []
        for item in data:
            updated_item, changed = apply_transform_config(item, config)
            output.append(updated_item)
            changed_any = changed_any or changed
        return output, changed_any

    if not isinstance(data, dict):
        return data, False

    if not _matches_filter(data, config.get("filter")):
        return data, False

    output = copy.deepcopy(data)
    changed = False

    for rule in config.get("transform", []):
        if not isinstance(rule, dict):
            continue
        action = rule.get("action")
        property_path = rule.get("property")
        if not property_path:
            continue

        if action == "replace_all":
            new_value = rule.get("value")
            current_value = _get_value(output, property_path)
            if current_value != new_value:
                if _set_value(output, property_path, new_value):
                    changed = True

    return output, changed


def _matches_filter(data: Dict[str, Any], filter_config: Optional[Dict[str, Any]]) -> bool:
    if not filter_config:
        return True

    if "and" in filter_config:
        rules = filter_config.get("and", [])
        return all(_matches_filter(data, rule) for rule in rules)

    if "or" in filter_config:
        rules = filter_config.get("or", [])
        return any(_matches_filter(data, rule) for rule in rules)

    property_path = filter_config.get("property")
    string_rules = filter_config.get("string")
    if not property_path or not isinstance(string_rules, dict):
        return False

    value = _get_value(data, property_path)
    if value is None:
        return False

    if not isinstance(value, str):
        value = str(value)

    if "equals" in string_rules:
        return value == str(string_rules.get("equals", ""))
    if "starts_with" in string_rules:
        return value.startswith(str(string_rules.get("starts_with", "")))
    if "ends_with" in string_rules:
        return value.endswith(str(string_rules.get("ends_with", "")))
    if "contains" in string_rules:
        return str(string_rules.get("contains", "")) in value

    return False


def _get_value(data: Any, property_path: str) -> Any:
    if not property_path:
        return None

    parts = [part for part in property_path.split(".") if part]
    current: Any = data

    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
            continue

        if isinstance(current, list):
            index = _to_index(part)
            if index is None or index >= len(current):
                return None
            current = current[index]
            continue

        return None

    return current


def _set_value(data: Any, property_path: str, value: Any) -> bool:
    parts = [part for part in property_path.split(".") if part]
    if not parts:
        return False

    current: Any = data
    for part in parts[:-1]:
        if isinstance(current, dict):
            if part not in current or not isinstance(current[part], (dict, list)):
                current[part] = {}
            current = current[part]
            continue

        if isinstance(current, list):
            index = _to_index(part)
            if index is None or index >= len(current):
                return False
            if not isinstance(current[index], (dict, list)):
                current[index] = {}
            current = current[index]
            continue

        return False

    last = parts[-1]
    if isinstance(current, dict):
        current[last] = value
        return True
    if isinstance(current, list):
        index = _to_index(last)
        if index is None or index >= len(current):
            return False
        current[index] = value
        return True

    return False


def _to_index(value: str) -> Optional[int]:
    if value.isdigit():
        return int(value)
    return None
