#!/bin/bash

# Docker entrypoint script for TimeCamp SCIM integrations
set -e

case "$1" in
    "fetch-bamboohr")
        exec python fetch_bamboohr.py "${@:2}"
        ;;
    "fetch-azuread")
        exec python fetch_azuread.py "${@:2}"
        ;;
    "fetch-ldap")
        exec python fetch_ldap.py "${@:2}"
        ;;
    "fetch-factorial")
        exec python fetch_factorialhr.py "${@:2}"
        ;;
    "prepare-timecamp")
        exec python prepare_timecamp_json_from_fetch.py "${@:2}"
        ;;
    "sync-users")
        exec python timecamp_sync_users.py "${@:2}"
        ;;
    "sync-time-off")
        exec python timecamp_sync_time_off.py "${@:2}"
        ;;
    "display-tree")
        exec python scripts/display_timecamp_tree.py "${@:2}"
        ;;
    "remove-empty-groups")
        exec python scripts/remove_empty_groups.py "${@:2}"
        ;;
    "help"|"--help"|"-h")
        echo "TimeCamp SCIM Integrations Docker Container"
        echo ""
        echo "Available commands:"
        echo "  fetch-bamboohr        - Fetch users from BambooHR"
        echo "  fetch-azuread         - Fetch users from Azure AD/Entra ID"
        echo "  fetch-ldap            - Fetch users from LDAP"
        echo "  fetch-factorial       - Fetch vacation data from FactorialHR"
        echo "  prepare-timecamp      - Transform fetched data for TimeCamp"
        echo "  sync-users            - Synchronize users with TimeCamp"
        echo "  sync-time-off         - Synchronize time-off data with TimeCamp"
        echo "  display-tree          - Display TimeCamp group structure"
        echo "  remove-empty-groups   - Clean up empty groups"
        echo ""
        echo "You can also run any Python script directly:"
        echo "  docker run --rm --env-file .env -v ./var:/app/var timecamp-scim python script.py"
        echo ""
        echo "For dry-run or debug mode, add --dry-run and/or --debug after the command:"
        echo "  docker run --rm --env-file .env -v ./var:/app/var timecamp-scim sync-users --dry-run --debug"
        ;;
    *)
        # If it doesn't match any of our commands, pass through to python
        exec python "$@"
        ;;
esac 