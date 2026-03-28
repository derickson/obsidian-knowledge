#!/bin/bash
export PATH="/home/dave/.nvm/versions/node/v22.22.1/bin:$PATH"
echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---"
ob sync --path /home/dave/dev/obsidian-knowledge/vaults/AgentKnowledge
