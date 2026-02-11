#!/usr/bin/env bash
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-db}"
SEED_FILE="${SEED_FILE:-open5gs/seed/subscribers.js}"

if [[ ! -f "$SEED_FILE" ]]; then
  echo "[seed] Seed file not found: $SEED_FILE"
  exit 1
fi

echo "[seed] Waiting for Mongo to respond..."
for i in {1..30}; do
  if sudo docker exec "$DB_CONTAINER" mongosh --quiet --eval "db.adminCommand('ping')" >/dev/null 2>&1; then
    echo "[seed] Mongo is ready."
    break
  fi
  sleep 1
  if [[ $i -eq 30 ]]; then
    echo "[seed] Mongo did not become ready in time."
    exit 1
  fi
done

echo "[seed] Copying seed file into container..."
sudo docker cp "$SEED_FILE" "${DB_CONTAINER}:/tmp/subscribers.js"

echo "[seed] Applying subscribers seed..."
sudo docker exec "$DB_CONTAINER" mongosh --quiet --file "/tmp/subscribers.js"

echo "[seed] Done."

