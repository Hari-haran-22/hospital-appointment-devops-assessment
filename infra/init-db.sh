#!/bin/sh
set -eu

APP_PASSWORD=$(cat /run/secrets/db_app_password)
psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  --set "app_password=$APP_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE appointment_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'appointment_app') \gexec
SELECT 'CREATE DATABASE appointments_test'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'appointments_test') \gexec
SQL

for database in "$POSTGRES_DB" appointments_test; do
    psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$database" \
      --set "db_name=$database" --file /opt/appointments/schema.sql
done
