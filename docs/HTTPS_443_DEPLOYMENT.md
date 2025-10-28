# CoMIDF HTTPS 443 部署指南

## 概述

CoMIDF Edge Agent 通过反向代理（Nginx）机制，始终使用 HTTPS 443 端口上报到 Cloud Platform。这种方式适合企业防火墙只允许 443 端口出站的环境。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Edge Agent                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │ HTTP PA  │  │ MQTT PA  │  │ CoAP PA  │                   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                   │
│       │             │             │                          │
│       └─────────────┴─────────────┘                          │
│                    ↓                                           │
│              FAL (UER 标准化)                                 │
│                    ↓                                           │
│         Secure Connector (HTTPS 443)                         │
│                    ↓                                           │
└────────────────────┬──────────────────────────────────────────┘
                     ↓
        Internet (TCP 443 only)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                  Nginx Reverse Proxy                        │
│              (HTTPS 443 → Internal Backend)                │
│                    │                                          │
│         ┌──────────┴──────────┐                             │
│         ↓                     ↓                             │
│  ┌─────────────┐      ┌──────────────┐                      │
│  │  Ingress    │      │ Key Manager  │                      │
│  │  :8080      │      │  :9090       │                      │
│  └─────┬───────┘      └──────────────┘                      │
│        ↓                                                      │
│    Kafka → GC → PR → AFL                                     │
└─────────────────────────────────────────────────────────────┘
```

## 优势

### 1. 防火墙友好
- ✅ 仅需开放 443 端口（HTTPS）
- ✅ 符合企业安全策略
- ✅ 无需特殊端口配置

### 2. 安全性
- ✅ 端到端 TLS 加密
- ✅ SSL/TLS 证书验证
- ✅ 支持 mTLS（可选）

### 3. 可扩展性
- ✅ 负载均衡
- ✅ 高可用部署
- ✅ 易于横向扩展

## 部署步骤

### 1. 设置 SSL 证书

```bash
cd /opt/CoMIDF
chmod +x nginx/setup_ssl.sh
./nginx/setup_ssl.sh
```

选择证书方式：
- Let's Encrypt (生产环境)
- 自签名证书 (测试环境)
- 现有证书 (已有证书)

### 2. 配置 Nginx

编辑 `cloud-platform/nginx/nginx.conf`:

```nginx
upstream comidf_ingress {
    server ingress:8080;
}

server {
    listen 443 ssl http2;
    server_name your-cloud.example.com;
    
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    
    location /api/fal/uer {
        proxy_pass http://comidf_ingress;
        # ... 其他配置
    }
}
```

### 3. 启动服务

```bash
cd cloud-platform

# 使用生产配置
docker-compose -f docker-compose.prod.yml up -d

# 检查日志
docker-compose logs -f nginx
```

### 4. 配置 Edge Agent

使用生产配置：

```bash
cp edge-agent/agent.yaml edge-agent/agent_production.yaml

# 编辑配置
nano edge-agent/agent_production.yaml
```

关键配置：

```yaml
uplink:
  mssp_url: "https://your-cloud.example.com"  # HTTPS!
  fal_endpoint: "/api/fal/uer"
  token: "YOUR-TOKEN"
  tls:
    mtls: false  # Nginx 处理 SSL
    verify: true  # 验证证书
```

### 5. 测试连接

```bash
# 从 Edge Agent 测试
curl https://your-cloud.example.com/health

# 测试 SSL 证书
openssl s_client -connect your-cloud.example.com:443

# 测试上传 UER
curl -X POST https://your-cloud.example.com/api/fal/uer \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: TENANT" \
  -H "X-Agent-ID: test" \
  -d '{"ts":"...","src":{"ip":"1.1.1.1"},"dst":{"ip":"2.2.2.2"},"proto":{"l7":"HTTP"},"detector":{"score":0.5,"conf":0.8}}'
```

## Nginx 配置详解

### 位置块: `/api/fal/uer`

- 代理到 Ingress 服务 (端口 8080)
- 保持原始请求头
- 支持大文件上传（10MB）
- 超时设置 60 秒

### 位置块: `/api/fal/uer/_bulk`

- 批量上传端点
- 大文件支持（50MB）
- 更长超时（120 秒）
- 无缓冲模式

### SSL 配置

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers 'HIGH:!aNULL:!MD5';
ssl_prefer_server_ciphers off;
ssl_session_cache shared:SSL:10m;
```

## 防火墙配置

### Edge Agent 端

**出站规则**:
```
允许: TCP 443 (HTTPS) → Cloud Platform
拒绝: 其他所有端口
```

### Cloud Platform 端

**入站规则**:
```
允许: TCP 443 (HTTPS) from Edge Agents
允许: TCP 22 (SSH) from Admin IPs
拒绝: 其他所有端口
```

## 证书管理

### 自动续期 (Let's Encrypt)

```bash
# 测试续期
sudo certbot renew --dry-run

# 设置自动续期
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### 手动更新证书

```bash
# 更新证书
sudo certbot renew

# 重载 Nginx
sudo docker exec comidf-nginx nginx -s reload
```

## 故障排除

### 问题 1: SSL 握手失败

**症状**: `SSL handshake failed`

**检查**:
```bash
# 查看证书
openssl x509 -in nginx/ssl/fullchain.pem -text

# 测试连接
openssl s_client -connect your-cloud.example.com:443

# Nginx 日志
docker logs comidf-nginx
```

**解决**:
```bash
# 重新生成证书
./nginx/setup_ssl.sh
docker-compose restart nginx
```

### 问题 2: 证书到期

**症状**: `certificate has expired`

**检查**:
```bash
openssl x509 -in nginx/ssl/fullchain.pem -noout -dates
```

**解决**:
```bash
# Let's Encrypt 自动续期
sudo certbot renew
docker exec comidf-nginx nginx -s reload
```

### 问题 3: 代理 502 错误

**症状**: Nginx 返回 502 Bad Gateway

**检查**:
```bash
# 检查后端服务
docker-compose ps
docker logs comidf-ingress

# Nginx 配置
docker exec comidf-nginx nginx -t
```

**解决**:
```bash
# 重启后端服务
docker-compose restart ingress
docker exec comidf-nginx nginx -s reload
```

## 安全最佳实践

### 1. SSL/TLS 配置

- ✅ 使用 TLS 1.2+ 和 TLS 1.3
- ✅ 禁用旧协议 (SSLv3, TLS 1.0, TLS 1.1)
- ✅ 使用强密码套件
- ✅ 启用 HSTS

### 2. 证书管理

- ✅ 定期更新证书
- ✅ 监控到期时间
- ✅ 使用证书链
- ✅ 保护私钥文件

### 3. 访问控制

- ✅ IP 白名单（可选）
- ✅ 请求限流
- ✅ User-Agent 验证
- ✅ 请求头检查

### 4. 监控和告警

```bash
# 监控 SSL 证书
watch "openssl s_client -connect your-cloud.example.com:443 2>/dev/null | openssl x509 -noout -dates"

# 设置告警
# 证书到期前 30 天发出通知
```

## 性能优化

### 1. HTTP/2

```nginx
listen 443 ssl http2;
```

- ✅ 多路复用
- ✅ 头部压缩
- ✅ 服务器推送（可选）

### 2. Keep-Alive

```nginx
upstream comidf_ingress {
    server ingress:8080;
    keepalive 32;
}
```

- ✅ 减少连接开销
- ✅ 提高吞吐量

### 3. 缓存策略

```nginx
# 静态资源缓存
location ~* \.(css|js|png|jpg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## 负载均衡

### 多实例部署

```nginx
upstream comidf_ingress {
    least_conn;  # 最少连接算法
    server ingress-1:8080;
    server ingress-2:8080;
    server ingress-3:8080;
    keepalive 32;
}
```

### 健康检查

```nginx
upstream comidf_ingress {
    least_conn;
    server ingress-1:8080 max_fails=3 fail_timeout=30s;
    server ingress-2:8080 max_fails=3 fail_timeout=30s;
    server ingress-3:8080 max_fails=3 fail_timeout=30s;
}
```

## 参考

- [Nginx SSL/TLS 最佳实践](https://nginx.org/en/docs/http/ngx_http_ssl_module.html)
- [Let's Encrypt 文档](https://letsencrypt.org/docs/)
- [部署指南](./DEPLOYMENT.md)

---

**完成**: CoMIDF Edge Agent 现在通过 HTTPS 443 端口安全上报到 Cloud Platform。

