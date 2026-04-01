#!/usr/bin/env bash
set -euo pipefail

echo "Killing all local ob sync processes..."
pkill -9 -f "ob sync" 2>/dev/null && echo "Killed ob sync processes." || echo "No ob sync processes found."

echo "Redeploying Docker services..."
make redeploy

echo "Done. Sync should be unblocked."
