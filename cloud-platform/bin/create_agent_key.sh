#!/bin/bash
#
# 从 Cloud Platform 生成 Edge Agent 凭证
#

set -e

CLOUD_URL="${CLOUD_URL:-http://localhost:9090}"
OUTPUT_FILE="${1:-/tmp/comidf_agent_credentials.json}"

echo "╔════════════════════════════════════════╗"
echo "║   生成 Edge Agent 凭证                   ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 收集信息
read -p "Tenant ID: " TENANT_ID
read -p "Site name [default]: " SITE
read -p "Agent name [Agent]: " AGENT_NAME

SITE="${SITE:-default}"
AGENT_NAME="${AGENT_NAME:-Agent}"

# 调用 API
echo "→ 正在生成凭证..."
RESPONSE=$(curl -s -X POST "$CLOUD_URL/api/v1/agents/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"tenant_id\": \"$TENANT_ID\",
    \"site\": \"$SITE\",
    \"name\": \"$AGENT_NAME\"
  }")

# 检查错误
if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    ERROR=$(echo "$RESPONSE" | jq -r '.error')
    echo "✗ 错误: $ERROR"
    exit 1
fi

# 保存凭证
echo "$RESPONSE" | jq -r '.credentials' > "$OUTPUT_FILE"

# 显示信息
AGENT_ID=$(echo "$RESPONSE" | jq -r '.agent_id')
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ 凭证已生成"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Agent ID: $AGENT_ID"
echo "凭证文件: $OUTPUT_FILE"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "下一步："
echo ""
echo "1. 下载凭证到 Edge Agent 服务器:"
echo "   scp $OUTPUT_FILE user@edge-agent:/tmp/"
echo ""
echo "2. 在 Edge Agent 上运行安装:"
echo "   ./bin/install_with_key.sh $OUTPUT_FILE"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠ 安全提示：凭证文件包含敏感信息，请妥善保管！"
echo ""

