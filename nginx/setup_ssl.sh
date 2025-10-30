#!/bin/bash
#
# Setup SSL certificates for CoMIDF Nginx reverse proxy
#

set -e

echo "╔════════════════════════════════════════╗"
echo "║   CoMIDF SSL 证书设置                   ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 创建目录
mkdir -p nginx/ssl nginx/logs

echo "选择 SSL 证书方式:"
echo "1) Let's Encrypt (生产环境推荐)"
echo "2) 自签名证书 (测试/开发)"
echo "3) 使用现有证书"
read -p "请选择 [1-3]: " choice

case $choice in
    1)
        # Let's Encrypt
        echo "→ 使用 Let's Encrypt"
        
        read -p "域名: " DOMAIN
        read -p "Email: " EMAIL
        
        # 安装 certbot
        sudo apt install -y certbot python3-certbot-nginx
        
        # 获取证书
        sudo certbot certonly --nginx -d "$DOMAIN" -m "$EMAIL" --agree-tos
        
        # 复制证书到项目目录
        sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem nginx/ssl/
        sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem nginx/ssl/
        sudo chmod 644 nginx/ssl/fullchain.pem
        sudo chmod 600 nginx/ssl/privkey.pem
        
        echo "✓ Let's Encrypt 证书已安装"
        ;;
        
    2)
        # 自签名证书
        echo "→ 生成自签名证书"
        
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout nginx/ssl/privkey.pem \
            -out nginx/ssl/fullchain.pem \
            -subj "/CN=your-cloud.example.com/O=CoMIDF/C=TW"
        
        chmod 644 nginx/ssl/fullchain.pem
        chmod 600 nginx/ssl/privkey.pem
        
        echo "✓ 自签名证书已生成"
        echo "⚠ 警告: 自签名证书仅用于测试"
        ;;
        
    3)
        # 使用现有证书
        echo "→ 使用现有证书"
        
        read -p "证书文件路径: " CERT_FILE
        read -p "私钥文件路径: " KEY_FILE
        
        cp "$CERT_FILE" nginx/ssl/fullchain.pem
        cp "$KEY_FILE" nginx/ssl/privkey.pem
        
        chmod 644 nginx/ssl/fullchain.pem
        chmod 600 nginx/ssl/privkey.pem
        
        echo "✓ 现有证书已复制"
        ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "证书信息:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
openssl x509 -in nginx/ssl/fullchain.pem -noout -subject -dates
echo ""
echo "证书文件:"
ls -lh nginx/ssl/
echo ""

