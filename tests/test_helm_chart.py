import ast
import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TIMECAMP_CONFIG_ENV = {
    "TIMECAMP_DOMAIN": "domain",
    "TIMECAMP_ROOT_GROUP_ID": "rootGroupId",
    "TIMECAMP_IGNORED_USER_IDS": "ignoredUserIds",
    "TIMECAMP_SHOW_EXTERNAL_ID": "showExternalId",
    "TIMECAMP_SKIP_DEPARTMENTS": "skipDepartments",
    "TIMECAMP_USE_SUPERVISOR_GROUPS": "useSupervisorGroups",
    "TIMECAMP_USE_DEPARTMENT_GROUPS": "useDepartmentGroups",
    "TIMECAMP_DISABLE_NEW_USERS": "disableNewUsers",
    "TIMECAMP_DISABLE_EXTERNAL_ID_SYNC": "disableExternalIdSync",
    "TIMECAMP_DISABLE_ADDITIONAL_EMAIL_SYNC": "disableAdditionalEmailSync",
    "TIMECAMP_UPDATE_EMAIL_ON_EXTERNAL_ID": "updateEmailOnExternalId",
    "TIMECAMP_DISABLE_MANUAL_USER_UPDATES": "disableManualUserUpdates",
    "TIMECAMP_DISABLE_USER_DEACTIVATION": "disableUserDeactivation",
    "TIMECAMP_DISABLE_GROUP_UPDATES": "disableGroupUpdates",
    "TIMECAMP_DISABLE_ROLE_UPDATES": "disableRoleUpdates",
    "TIMECAMP_DISABLE_GROUPS_CREATION": "disableGroupsCreation",
    "TIMECAMP_USE_JOB_TITLE_NAME_USERS": "useJobTitleNameUsers",
    "TIMECAMP_USE_JOB_TITLE_NAME_GROUPS": "useJobTitleNameGroups",
    "TIMECAMP_REPLACE_EMAIL_DOMAIN": "replaceEmailDomain",
    "TIMECAMP_USE_IS_SUPERVISOR_ROLE": "useIsSupervisorRole",
    "TIMECAMP_DISABLED_USERS_GROUP_ID": "disabledUsersGroupId",
    "TIMECAMP_EXCLUDE_REGEX": "excludeRegex",
    "TIMECAMP_CHANGE_GROUPS_REGEX": "changeGroupsRegex",
    "TIMECAMP_PREPARE_TRANSFORM_CONFIG": "prepareTransformConfig",
    "TIMECAMP_REMOVE_EMPTY_GROUPS": "removeEmptyGroups",
    "TIMECAMP_SSL_VERIFY": "sslVerify",
    "TIMECAMP_SYNC_PERSISTENT_SETTINGS": "syncPersistentSettings",
}


def _runtime_timecamp_env_names() -> set[str]:
    source = (REPOSITORY_ROOT / "common" / "utils.py").read_text()
    tree = ast.parse(source)
    names = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "getenv":
            continue
        first_argument = node.args[0]
        if (
            isinstance(first_argument, ast.Constant)
            and isinstance(first_argument.value, str)
            and first_argument.value.startswith("TIMECAMP_")
        ):
            names.add(first_argument.value)

    return names


def test_every_runtime_timecamp_setting_has_a_helm_config_field():
    runtime_settings = _runtime_timecamp_env_names() - {"TIMECAMP_API_KEY"}

    assert runtime_settings == set(TIMECAMP_CONFIG_ENV)


def test_every_timecamp_helm_config_field_is_declared_and_rendered():
    values = (REPOSITORY_ROOT / "helm" / "timecamp-scim" / "values.yaml").read_text()
    template = (
        REPOSITORY_ROOT / "helm" / "timecamp-scim" / "templates" / "_helpers.tpl"
    ).read_text()
    timecamp_values = values.split("  timecamp:\n", 1)[1].split(
        "\n  # BambooHR Configuration", 1
    )[0]
    declared_fields = set(
        re.findall(r"^    ([A-Za-z][A-Za-z0-9]*):", timecamp_values, re.MULTILINE)
    )

    for environment_name, field_name in TIMECAMP_CONFIG_ENV.items():
        expected_template = (
            f"- name: {environment_name}\n"
            f"  value: {{{{ .{field_name} | quote }}}}"
        )

        assert field_name in declared_fields
        assert expected_template in template


def test_okta_hierarchy_root_limit_is_declared_and_rendered():
    values = (REPOSITORY_ROOT / "helm" / "timecamp-scim" / "values.yaml").read_text()
    template = (
        REPOSITORY_ROOT / "helm" / "timecamp-scim" / "templates" / "_helpers.tpl"
    ).read_text()

    assert "maxHierarchyRoots: 0" in values
    assert (
        "- name: OKTA_MAX_HIERARCHY_ROOTS\n"
        "  value: {{ .maxHierarchyRoots | quote }}"
    ) in template
