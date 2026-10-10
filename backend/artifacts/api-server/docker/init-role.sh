#!/bin/sh
set -eu

if [ -z "${APP_DB_PASSWORD:-}" ]; then
  echo "APP_DB_PASSWORD is required to create the restricted application role." >&2
  exit 1
fi

psql --set=ON_ERROR_STOP=1 --set=app_password="$APP_DB_PASSWORD" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE qp_app LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
GRANT CONNECT ON DATABASE quikpatient TO qp_app;
GRANT USAGE ON SCHEMA public TO qp_app;
SQL
