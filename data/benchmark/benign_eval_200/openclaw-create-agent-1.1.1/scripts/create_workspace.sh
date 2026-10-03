#!/bin/bash
# create_workspace.sh — 创建 Agent workspace 目录结构
# 用法：bash create_workspace.sh <agentId>

set -e

AGENT_ID="${1}"
if [ -z "$AGENT_ID" ]; then
  echo "❌ 用法：bash create_workspace.sh <agentId>"
  exit 1
fi

BASE_DIR="$HOME/.openclaw/agency-agents"
WORKSPACE="$BASE_DIR/$AGENT_ID"

if [ -d "$WORKSPACE" ]; then
  echo "⚠️  workspace 已存在：$WORKSPACE"
  read -p "继续会覆盖部分文件，确认？(y/N) " confirm
  [[ "$confirm" != "y" ]] && echo "已取消" && exit 0
fi

echo "=== 创建 workspace: $WORKSPACE ==="

mkdir -p "$WORKSPACE/memory"
mkdir -p "$WORKSPACE/skills"

echo "✅ 目录结构创建完成"
echo ""
echo "接下来需要写入的文件："
echo "  $WORKSPACE/IDENTITY.md"
echo "  $WORKSPACE/SOUL.md"
echo "  $WORKSPACE/AGENTS.md"
echo "  $WORKSPACE/TOOLS.md"
echo "  $WORKSPACE/USER.md"
echo "  $WORKSPACE/MEMORY.md"
echo "  $WORKSPACE/HEARTBEAT.md"
echo "  $WORKSPACE/BOOTSTRAP.md"
