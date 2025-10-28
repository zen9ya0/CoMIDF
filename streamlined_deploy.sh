#!/bin/bash
#
# CoMIDF 优化的一键部署脚本
# 3 步完成安装
#

set -e

echo "╔════════════════════════════════════════╗"
echo "║   CoMIDF 优化安装流程                    ║"
echo "╚════════════════════════════════════════╝"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 步骤 1: 环境检查
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}步骤 1/3: 环境检查${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

CHECK_OK=true

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠ Docker 未安装，将自动安装...${NC}"
    CHECK_OK=false
else
    echo -e "${GREEN}✓ Docker: $(docker --version | cut -d' ' -f3)${NC}"
fi

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}⚠ Docker Compose 未安装${NC}"
    CHECK_OK=false
else
    echo -e "${GREEN}✓ Docker/hub: available
fi

# 安装依赖（如果需要）
if [ "$CHECK_OK" = false ]; then
    echo -e "${YELLOW}→ 自动安装依赖...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${GREEN}✓ 依赖已安装${NC}"
fi

# 步骤 2: 配置（如果是首次）
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}步骤 2/3: 配置（首次运行）${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 检查配置是否存在
if [ ! -f cloud-platform/.env ]; then
    echo -e "${YELLOW}→ 首次配置...${NC}"
    
    # 生成随机密码
    POSTGRES_PASS=$(openssl rand -base64 32)
    REDIS_PASS=$(openssl rand -base64 32)
    
    # 创建 .env
    cat > cloud-platform/.env << EOF
POSTGRES_PASSWORD=$POSTGRES_PASS
REDIS_PASSWORD=$REDIS_PASS
LOG_LEVEL=INFO
EOF
    echo -e "${GREEN}✓ 配置已生成${NC}"
else
    echo -e "${GREEN}✓ 配置已存在${NC}"
fi

# 步骤 3: 部署
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}步骤 3/3: 部署服务${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 启动 Cloud Platform
echo -e "${YELLOW}→ 启动 Cloud Platform...${NC}"
cd cloud-platform
docker-compose up -d
cd ..
echo -e "${GREEN}✓ Cloud Platform 已启动${NC}"

# 等待服务就绪
sleep 5

# 构建 Edge Agent
echo -e "${YELLOW}→ 构建 Edge Agent...${NC}"
cd edge-agent
if [ "$(docker images -q comidf-edge:latest 2>/dev/null)" ]; then
    echo -e "${GREEN}✓ Edge Agent 镜像已存在${NC}"
else
    docker build -t comidf-edge:latest .
fi
cd ..

# 启动 Edge Agent
echo -e "${YELLOW}→ 启动 Edge Agent...${NC}"
if [ "$(docker ps -q -f name=comidf-edge)" ]; then
    echo -e "${YELLOW}⚠ Edge Agent 已在运行${NC}"
else
    docker run -d \
      --name comidf-edge \
      --restart unless-stopped \
      -v $(pwd)/edge-agent/agent.yaml:/etc/agent/agent.yaml \
      -p 8600:8600 \
      comidf-edge:latest
fi

sleep 3

# 验证
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}验证服务${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if curl -s http://localhost:8600/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Edge Agent: 运行中${NC}"
else
    echo -e "${RED}✗ Edge Agent: 未响应${NC}"
fi

if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Cloud Platform: 运行中${NC}"
else
    echo -e "${RED}✗ Cloud Platform: 未响应${NC}"
fi

# 显示服务状态
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✓ 部署完成！${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "服务状态:"
docker ps --filter "name=comidf" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "访问地址:"
echo "  - Edge Agent:  http://localhost:8600"
echo "  - Cloud Platform: http://localhost:8080"
echo ""
echo "查看日志:"
echo "  docker logs comidf-edge -f"
echo "  docker-compose -f cloud-platform/docker-compose.yml logs -f"
echo ""

