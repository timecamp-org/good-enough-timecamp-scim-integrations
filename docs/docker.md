# Docker Support

For easy deployment and consistent environments, you can run the application using Docker.

```bash
docker compose build

# Run specific commands using predefined services:

docker compose run --rm fetch-bamboohr
docker compose run --rm fetch-azuread
docker compose run --rm fetch-ldap
docker compose run --rm fetch-factorial

docker compose run --rm prepare-timecamp

docker compose run --rm sync-users

docker compose run --rm display-tree # (optional)
docker compose run --rm remove-empty-groups # (optional)

# Run any script with custom arguments (optional)
docker compose run --rm timecamp-scim python timecamp_sync_users.py --dry-run --debug
docker compose run --rm sync-users --dry-run
docker compose run --rm sync-users --debug

# HTTP Service (run scripts via REST API on port 8181)
docker compose up -d http-service

# Sample sync command
docker compose run --rm fetch-ldap && docker compose run --rm prepare-timecamp && docker compose run --rm sync-users --debug

# Sample visualization command
docker compose run --rm fetch-ldap && docker compose run --rm prepare-timecamp && docker compose run --rm display-tree --html var/structure.html
```