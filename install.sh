#!/bin/bash
#
# CoMIDF 自动安装脚本
# 支持 Ubuntu/Debian/CentOS
#

set -e

echo "╔════════════════════════════════════════╗"
echo "║   CoMIDF 自动安装脚本                    ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检测操作系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        echo "无法检测操作系统"
        exit 1
    fi
}

# 安装依赖
install_dependencies() {
    echo -e "${YELLOW}→ 安装系统依赖...${NC}"
    
    case $OS in
        ubuntu|debian)
            sudo apt update
            sudo apt install -y python3.11 python3.11-venv python3-pip git curl wget
            ;;
        centos|rhel)
            sudo yum install -y python3 python3-pip git curl wget
            ;;
        *)
            echo -e "${RED}不支持的操作系统: $OS${NC}"
            exit 1
            ;;
    esac
    
    echo -e "${GREEN}✓ 系统依赖已安装${NC}"
}

# 安装 Docker
install_docker() {
    if command -v docker &> /dev/null; then
        echo -e "${GREEN}✓ Docker 已安装${NC}"
        return
    fi
    
    echo -e "${YELLOW}→ 安装 Docker...${NC}"
    
    case $OS in
        ubuntu|debian)
            curl -fsSL https://get.docker.com -o get-docker.sh
            sudo sh get-docker.sh
            sudo usermod -aG docker $USER
            rm get-docker.sh
            ;;
        centos|rhel)
            sudo yum install -y yum-utils
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install -y docker-ce docker-ce-cli containerd.io
            sudo systemctl start docker
            sudo systemctl enable docker
            ;;
    esac
    
    echo -e "${GREEN}✓ Docker 已安装${NC}"
}

# 安装 Docker Compose
install_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        echo -e "${GREEN}✓ Docker Compose 已安装${NC}"
        return
    fi
    
    echo -e "${YELLOW}→ 安装 Docker Compose...${NC}"
    
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    
    echo -e "${GREEN}✓ Docker Compose 已安装${NC}"
}

# 设置 Python 环境
setup_python_env() {
    echo -e "${YELLOW}→ 设置 Python 环境...${NC}"
    
    # Edge Agent
    cd edge-agent
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    cd ..
    
    # Cloud Platform
    cd cloud-platform
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    cd ..
    
    echo -e "${GREEN}✓ Python 环境已设置${NC}"
}

# 配置服务
configure_services() {
    echo -e "${YELLOW}→ 配置服务...${NC}"
    
    # 创建目录
    sudo mkdir -p /etc/comidf/agent
    sudo mkdir -p /var/lib/comidf/agent
    
    # 复制配置文件
    sudo cp edge-agent/agent.yaml /etc/comidf/agent/
    
    # 创建 .env 文件
    cat > cloud-platform/.env << EOF
# Auto-generated configuration
POSTGRES_PASSWORD=comidf_pass_$(openssl rand -hex 8)
KAFKA_BROKERS=kafka:9092
REDIS_PASSWORD=$(openssl rand -hex 16)
LOG_LEVEL=INFO
EOF
    
    echo -e "${GREEN}✓ 服务已配置${NC}"
}

# 主函数
main() {
    detect_os
    echo -e "${GREEN}检测到操作系统: $OS $VER${NC}"
    
    install_dependencies
    install_docker
    install_docker_compose
    setup_python_env
    configure_services
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   ✓ 安装完成！                           ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "下一步:"
    echo "  1. 编辑配置文件:"
    echo "     - /etc/comidf/agent/agent.yaml"
    echo "     - cloud-platform/.env"
    echo ""
    echo "  2. 启动服务:"
    echo "     ./deploy.sh"
    echo ""
    echo "  3. 查看文档:"
    echo "     cat DEPLOYMENT.md"
    echo ""
}

main

