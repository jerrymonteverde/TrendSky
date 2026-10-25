# Deployment and operations

## Local stack

Follow README configuration and run `docker compose up --build -d --wait --wait-timeout 180`. Database health gates migration; successful migration gates API; API health gates the web. `docker compose ps -a` should show a successful exited migration job and healthy long-running services. PostgreSQL 18 stores its data under the mounted `/var/lib/postgresql` volume.

Database init scripts run **only on an empty volume**. Do not delete an existing volume to apply configuration changes. Password changes require explicit SQL role rotation and synchronized application configuration. Run migrations once per release; take a backup first. Roll back application code only if compatible with the current schema. Review migration downgrades before using them; the initial downgrade deletes the source registry.

## Ubuntu VPS and HTTPS

Requires a domain you control, correct A/AAAA DNS, ports 80/443 open and adequate memory for image builds (more than runtime limits). Set `APP_ENV=production`, `SITE_DOMAIN` and `CORS_ORIGINS` to the HTTPS origin. Run:

```bash
docker compose --profile production up --build -d --wait --wait-timeout 180
```

Caddy obtains/manages TLS for a public domain. `localhost` uses local certificates and is not a verified public HTTPS deployment. Persist `caddy_data`, `caddy_config` and `postgres_data`. Public containers have restart policies and bounded Docker logs. Resource limits are initial caps, not measured capacity recommendations. Analytical jobs will run separately.

## Backups and recovery

From a private shell on the deployment host, create a restricted backup directory and dump using the container's local database administrator. No password is passed as a command-line argument:

```bash
umask 077
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U postgres -d "$POSTGRES_DB" -Fc' > backups/trendsky.dump
docker compose exec -T db sh -c 'pg_dumpall -U postgres --globals-only' > backups/roles.sql
```

Globals contain password hashes: encrypt backups, restrict access and keep encrypted off-host copies with a retention schedule. Validate dumps with `pg_restore --list`, then practice restoring into an isolated database before relying on them. Restore globals under an administrator, then restore the database with the correct owner mappings. Do not test restores against production. These procedures are documented, not executed here.

## Failure diagnosis

`docker compose logs --tail=100 migrate api web` identifies migration/connectivity failures. Health 503 distinguishes unavailable database versus schema. A web “status unavailable” message means the API contract could not be verified; it does not mean zero observed activity. Avoid `docker compose config` without `--quiet` in shared logs because expanded environment values may contain secrets.
