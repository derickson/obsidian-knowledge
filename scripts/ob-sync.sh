#!/bin/bash
export PATH="/home/dave/.nvm/versions/node/v22.22.1/bin:$PATH"
echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---"
SYNC_OUTPUT=$(ob sync --path /home/dave/dev/obsidian-knowledge/vaults/AgentKnowledge 2>&1)
echo "$SYNC_OUTPUT"
if echo "$SYNC_OUTPUT" | grep -qE "^(New file|Downloading|Upload|Deleting|Push:|Accepted)"; then
    echo "Changes detected, reindexing to Elasticsearch..."
    REINDEX_OUTPUT=$(curl -s -X POST http://localhost:3105/obsidian-knowledge/api/admin/reindex/)
    echo "ES reindex: $REINDEX_OUTPUT"
else
    echo "No changes, skipping ES reindex"
fi
