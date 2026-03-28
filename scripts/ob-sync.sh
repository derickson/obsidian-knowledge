#!/bin/bash
export PATH="/home/dave/.nvm/versions/node/v22.22.1/bin:$PATH"
echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---"
ob sync --path /home/dave/dev/obsidian-knowledge/vaults/AgentKnowledge
echo "Reindexing to Elasticsearch..."
curl -s -X POST http://localhost:3105/obsidian-knowledge/api/admin/reindex/
