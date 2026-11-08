#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p secrets
chmod 700 secrets
for name in db_admin_password db_app_password patient_one_token patient_two_token staff_token; do
    if [ ! -f "secrets/$name" ]; then
        openssl rand -hex 32 > "secrets/$name"
        chmod 600 "secrets/$name"
    fi
done
if [ ! -f .env ]; then cp .env.example .env; fi
printf '%s\n' 'Created missing local secrets and .env. Existing values were preserved.'
