#!/bin/sh
set -eu
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD must be set}"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 \
  --set=app_password="$APP_DB_PASSWORD" --set=db_name="$POSTGRES_DB" <<'SQL'
CREATE ROLE trendsky_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db_name" TO trendsky_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO trendsky_app;
SQL
