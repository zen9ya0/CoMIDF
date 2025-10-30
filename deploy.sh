#!/bin/bash
#
# CoMIDF 一键部署脚本
#

set -e

echo "╔════════════════════════════════════════╗"
echo "║   CoMIDF 一键部署                       ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker 未安装${NC}"
    echo "请先运行: ./install.sh"
    exit 1
fi

# 启动 Cloud Platform
echo -e "${YELLOW}→ 启动 Cloud Platform...${NC}"
cd cloud-platform
docker-compose up -d
cd ..

# 等待服务启动
echo -e "${YELLOW}→ 等待服务就绪...${NC}"
sleep 10

# 检查服务
echo -e "${YELLOW}→ 检查服务状态...${NC}"
docker-compose -C cloud-platform ps

# 构建 Edge Agent
echo -e "${YELLOW}→ 构建 Edge Agent...${NC}"
cd edge-agent
docker build -t comidf-edge:latest .
cd ..

# 启动 Edge Agent
echo -e "${YELLOW}→ 启动 Edge Agent...${NC}"
docker run -d \
  --name comidf-edge \
  --restart unless-stopped \
  -v $(pwd)/edge-agent/agent.yaml:/etc/agent/agent.yaml \
  -p 8600:8600 \
  comidf-edge:latest || echo "Edge Agent 可能已经在运行"

# 等待服务启动
sleep 5

# 验证
echo -e "${YELLOW}→ 验证部署...${NC}"

# 检查 Edge Agent
if curl -s http://localhost:8600/health > /dev/null; then
    echo -e "${GREEN}✓ Edge Agent 运行中${NC}"
else
    echo -e "${RED}✗ Edge Agent 未响应${NC}"
fi

# 检查 Cloud Platform
if curl -s http://localhost:8080/health > /dev/null; then
    echo -e "${GREEN}✓ Cloud Platform 运行中${NC}"
else
    echo -e "${RED}✗ Cloud Platform 未响应${NC}"
fi

# 显示服务信息
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "服务状态:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker ps --filter "name=comidf" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✓ 部署完成！${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "访问地址:"
echo "  - Edge Agent API: http://localhost:8600"
echo "  - Cloud Ingress: http://localhost:8080"
echo ""
echo "查看日志:"
echo "  docker logs comidf-edge"
echo "  docker-compose -f cloud-platform/docker-compose.yml logs -f"
echo ""
echo "停止服务:"
echo "  docker stop comidf-edge"
echo "  docker-compose -f cloud-platform/docker-compose.yml down"
echo ""

