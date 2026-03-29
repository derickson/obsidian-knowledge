#!/bin/bash
export PATH="/home/dave/.nvm/versions/node/v22.22.1/bin:$PATH"

VAULTS_JSON="/home/dave/dev/obsidian-knowledge/vaults.json"
BACKEND="http://localhost:3105/obsidian-knowledge"

# Iterate over each sync-enabled vault
for VAULT_ID in $(jq -r '.vaults | to_entries[] | select(.value.sync_enabled == true) | .key' "$VAULTS_JSON"); do
    SYNC_PATH=$(jq -r ".vaults.\"$VAULT_ID\".sync_path" "$VAULTS_JSON")

    echo "--- $(date '+%Y-%m-%d %H:%M:%S') [$VAULT_ID] ---"
    SYNC_OUTPUT=$(ob sync --path "$SYNC_PATH" 2>&1)
    echo "$SYNC_OUTPUT"

    if echo "$SYNC_OUTPUT" | grep -qE "^(New file|Downloading|Upload|Deleting|Push:|Accepted)"; then
        echo "Changes detected, reindexing $VAULT_ID..."
        REINDEX_OUTPUT=$(curl -s -X POST "$BACKEND/api/admin/reindex/?vault=$VAULT_ID")
        echo "ES reindex: $REINDEX_OUTPUT"
    else
        echo "No changes for $VAULT_ID, skipping ES reindex"
    fi
done
