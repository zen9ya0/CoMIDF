#!/bin/bash
#
# Edge Agent 使用云端密钥安装脚本
#

set -e

echo "╔════════════════════════════════════════╗"
echo "║   CoMIDF Edge Agent 安装                ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 参数
CLOUD_URL="${CLOUD_URL:-https://your-cloud.example.com}"
CREDENTIALS_FILE="${1:-/tmp/comidf_credentials.json}"
INSTALL_DIR="/opt/comidf/edge-agent"

# 1. 检查凭证文件
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo -e "${YELLOW}→ 凭证文件不存在，需要从云端下载${NC}"
    echo ""
    echo "请提供以下信息："
    read -p "Cloud Platform URL: " CLOUD_URL
    read -p "Agent ID: " AGENT_ID
    read -p "API Token: " API_TOKEN
    
    # 下载凭证
    curl -X GET "$CLOUD_URL/api/v1/agents/$AGENT_ID/credentials" \
      -H "Authorization: Bearer $API_TOKEN" \
      -o "$CREDENTIALS_FILE"
fi

# 2. 解析凭证
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo -e "${RED}✗ 无法获取凭证${NC}"
    exit 1
fi

echo -e "${BLUE}→ 解析凭证...${NC}"
AGENT_ID=$(jq -r '.agent_id' "$CREDENTIALS_FILE")
TENANT_ID=$(jq -r '.tenant_id' "$CREDENTIALS_FILE")
API_TOKEN=$(jq -r '.api_token' "$CREDENTIALS_FILE")
MTLS_ENABLED=$(jq -r '.mTLS.enabled' "$CREDENTIALS_FILE")

# 3. 安装目录
echo -e "${BLUE}→ 创建安装目录...${NC}"
sudo mkdir -p "$INSTALL_DIR"/{etc,var/lib,logs}

# 4. 复制文件
echo -e "${BLUE}→ 复制文件...${NC}"
sudo cp -r . "$INSTALL_DIR"/ 2>/dev/null || \
sudo cp -r /opt/CoMIDF/edge-agent "$INSTALL_DIR".parent
sudo chown -R comidf:comidf "$INSTALL_DIR"

# 5. 生成配置文件
echo -e "${BLUE}→ 生成配置文件...${NC}"
cat > /tmp/agent.yaml << EOF
agent:
  id: "$AGENT_ID"
  tenant_id: "$TENANT_ID"
  site: $(jq -r '.site' "$CREDENTIALS_FILE")
  timezone: "Asia/Taipei"

uplink:
  mssp_url: "$CLOUD_URL"
  fal_endpoint: "/api/fal/uer"
  token: "$API_TOKEN"
  tls:
    mtls: $MTLS_ENABLED
EOF

# 保存 mTLS 证书（如果有）
if [ "$MTLS_ENABLED" = "true" ]; then
    echo "  ca_cert: /etc/comidf/agent/ca.pem" >> /tmp/agent.yaml
    echo "  cert: /etc/comidf/agent/agent.pem" >> /tmp/agent.yaml
    echo "  key: /etc/comidf/agent/agent.key" >> /tmp/agent.yaml
    
    # 写入证书文件
    sudo mkdir -p /etc/comidf/agent
    jq -r '.mTLS.ca_cert' "$CREDENTIALS_FILE" | sudo tee /etc/comidf/agent/ca.pem
    jq -r '.mTLS.certificate' "$CREDENTIALS_FILE" | sudo tee /etc/comidf/agent/agent.pem
    jq -r '.mTLS.private_key' "$CREDENTIALS_FILE" | sudo tee /etc/comidf/agent/agent.key
    sudo chmod 600 /etc/comidf/agent/*.{pem,key}
fi

# 合并完整配置
cat >> /tmp/agent.yaml << EOF
  retry:
    backoff_ms: [200, 500, 1000, 2000]
    max_retries: 8

buffer:
  backend: sqlite
  path: /var/lib/comidf/agent/buffer.db
  max_mb: 2048
  flush_batch: 500

privacy:
  id_salt: $(jq -r '.privacy.id_salt' "$CREDENTIALS_FILE")
  strip_fields: ["usernames", "urls", "payload"]

agents:
  http:
    enabled: true
    thresholds:
      score_alert: 0.7
  mqtt:
    enabled: true
    thresholds:
      score_alert: 0.65

metrics:
  prometheus_port: 9108

logging:
  level: info
  json: true
EOF

sudo mv /tmp/agent.yaml "$INSTALL_DIR/etc/agent.yaml"
sudo chown comidf:comidf "$INSTALL_DIR/etc/agent.yaml"

# 6. 安装 Python 依赖
echo -e "${BLUE}→ 安装 Python 依赖...${NC}"
cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# 7. 创建 systemd 服务
echo -e "${BLUE}→ 创建 systemd 服务...${NC}"
sudo tee /etc/systemd/system/comidf-edge.service > /dev/null << 'SVCEOF'
[Unit]
Description=CoMIDF Edge Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=comidf
WorkingDirectory=/opt/comidf/edge-agent
Environment="PYTHONPATH=/opt/comidf/edge-agent"
ExecStart=/opt/comidf/edge-agent/venv/bin/python \
  cmd/agentd/main.py \
  --config /opt/comidf/edge-agent/etc/agent.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SVCEOF

# 创建用户（如果不存在）
if ! id "comidf" &>/dev/null; then
    sudo useradd -r -s /bin/false comidf
fi
sudo chown -R comidf:comidf /opt/comidf

# 8. 启动服务
echo -e "${BLUE}→ 启动服务...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable comidf-edge
sudo systemctl start comidf-edge

# 9. 验证
echo -e "${BLUE}→ 验证安装...${NC}"
sleep 3
if systemctl is-active --quiet comidf-edge; then
    echo -e "${GREEN}✓ 服务已启动${NC}"
    curl -s http://localhost:8600/health | jq .
else
    echo -e "${RED}✗ 服务启动失败${NC}"
    sudo journalctl -u comidf-edge --no-pager -n 20
fi

# 10. 清理凭证文件
echo -e "${YELLOW}⚠ 安全提示：删除临时凭证文件${NC}"
rm -f "$CREDENTIALS_FILE"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✓ 安装完成！${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "服务状态:"
echo "  sudo systemctl status comidf-edge"
echo ""
echo "查看日志:"
echo "  sudo journalctl -u comidf-edge -f"
echo ""
echo "配置文件:"
echo "  $INSTALL_DIR/etc/agent.yaml"
echo ""

