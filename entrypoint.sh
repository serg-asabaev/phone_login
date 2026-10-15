#!/bin/sh
set -e

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
TRIES=0
until python -c "import socket; socket.create_connection(('${DB_HOST}', int('${DB_PORT}')), 2)" 2>/dev/null; do
    TRIES=$((TRIES + 1))
    if [ "$TRIES" -ge 30 ]; then
        echo "PostgreSQL is not available, giving up." >&2
        exit 1
    fi
    sleep 1
done
echo "PostgreSQL is up."

python manage.py migrate --noinput

exec "$@"
