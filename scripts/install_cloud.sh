#!/bin/bash
# CoMIDF Cloud Platform Installation Script
# Dual NIC setup for management and data interfaces

set -e

echo "========================================="
echo "CoMIDF Cloud Platform Installation"
echo "========================================="
echo ""

# Resolve project root (repo root is one directory above this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root (use sudo)"
    exit 1
fi

# Function to get network interfaces
get_interfaces() {
    ip link show | grep -E '^[0-9]+:' | grep -v lo | awk -F: '{print $2}' | awk '{print $1}'
}

# Display available interfaces
echo "Available network interfaces:"
echo "----------------------------"
interfaces=$(get_interfaces)
index=0
declare -a iface_list

while IFS= read -r line; do
    if [ -n "$line" ]; then
        index=$((index + 1))
        iface_list[index]=$line
        echo "$index) $line"
    fi
done <<< "$interfaces"

echo ""
echo "Please select interfaces for dual NIC setup:"
echo ""

# Get management interface
echo -n "Management interface (for UI/API/SSH) - Enter number: "
read mgmt_num
mgmt_iface=${iface_list[$mgmt_num]}

if [ -z "$mgmt_iface" ]; then
    echo "Error: Invalid interface selection"
    exit 1
fi

# Get data interface
echo -n "Data interface (for Kafka/UER Gateway) - Enter number: "
read data_num
data_iface=${iface_list[$data_num]}

if [ -z "$data_iface" ]; then
    echo "Error: Invalid interface selection"
    exit 1
fi

# Get IP addresses
echo ""
echo "Enter IP addresses (optional, leave empty for auto-detect):"
echo -n "Management IP for $mgmt_iface: "
read mgmt_ip
echo -n "Data IP for $data_iface: "
read data_ip

# Create network configuration
echo ""
echo "Creating network configuration..."

mkdir -p /etc/comidf

cat > /etc/comidf/cloud_net_config.yaml <<EOF
mgmt_iface: $mgmt_iface
data_iface: $data_iface
mgmt_ip: $mgmt_ip
data_ip: $data_ip
config_path: /etc/comidf/cloud_net_config.yaml
EOF

# Get IPs if not provided
if [ -z "$mgmt_ip" ]; then
    mgmt_ip=$(ip addr show $mgmt_iface | grep -oP 'inet \K[\d.]+' | head -1)
    echo "  Detected management IP: $mgmt_ip"
fi

if [ -z "$data_ip" ]; then
    data_ip=$(ip addr show $data_iface | grep -oP 'inet \K[\d.]+' | head -1)
    echo "  Detected data IP: $data_ip"
fi

# Create cloud platform configuration
echo ""
echo "Creating Cloud Platform configuration..."

cat > /etc/comidf/cloud_config.yaml <<EOF
# Cloud Platform Configuration
name: "CoMIDF Cloud Platform"
version: "1.0.0"

# Network
network:
  management_interface: $mgmt_iface
  data_interface: $data_iface
  management_ip: $mgmt_ip
  data_ip: $data_ip
  data_port: 9092
  management_port: 8443

# Components
components:
  uer_gateway:
    enabled: true
    host: $data_ip
    port: 9092
  
  global_credibility:
    enabled: true
    bayesian_prior: 0.5
  
  priority_reporter:
    enabled: true
    report_threshold: 0.7
    high_priority_threshold: 0.85
  
  active_feedback_loop:
    enabled: true
    trust_alpha: 0.7
    recalibration_rate: 0.1
  
  cti:
    enabled: true
    sources: ["custom"]
  
  llm:
    enabled: false
    model: "gpt-3.5-turbo"

# Kafka (if used)
kafka:
  enabled: false
  bootstrap_servers: "$data_ip:9093"

# Database
database:
  type: "postgresql"
  host: "localhost"
  port: 5432
  name: "comidf"
  user: "comidf_user"

# Logging
logging:
  level: "INFO"
  path: "/var/log/comidf"
EOF

echo "✓ Network configuration saved to /etc/comidf/cloud_net_config.yaml"
echo "✓ Platform configuration saved to /etc/comidf/cloud_config.yaml"
echo ""
echo "========================================="
echo "Cloud Platform installation completed!"
echo "========================================="
echo ""
echo "Summary:"
echo "  Management interface: $mgmt_iface ($mgmt_ip)"
echo "  Data interface: $data_iface ($data_ip)"
echo ""
echo "Next steps:"
echo "  - Installing dependencies and preparing environment..."

# ---------------------------------------------------------------
# Prepare environment directories
# ---------------------------------------------------------------
mkdir -p /etc/comidf
mkdir -p /var/log/comidf
chown "$USER":"$USER" /var/log/comidf || true
mkdir -p /etc/comidf/certs

# ---------------------------------------------------------------
# Python venv & dependencies
# ---------------------------------------------------------------
if [ ! -d "$ROOT_DIR/venv" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv "$ROOT_DIR/venv"
fi

echo "Activating venv and installing requirements..."
. "$ROOT_DIR/venv/bin/activate"
pip install --upgrade pip >/dev/null
pip install -r "$ROOT_DIR/requirements.txt"

# ---------------------------------------------------------------
# Environment variables (OAuth / Session / DB)
# ---------------------------------------------------------------
echo ""
echo "Configure optional Google OAuth (press Enter to skip):"
read -p "GOOGLE_CLIENT_ID: " GOOGLE_CLIENT_ID
read -p "GOOGLE_CLIENT_SECRET: " GOOGLE_CLIENT_SECRET

# Generate session secret if not provided
if command -v openssl >/dev/null 2>&1; then
  SESSION_SECRET_GENERATED=$(openssl rand -hex 32)
else
  SESSION_SECRET_GENERATED=$(python3 - <<'PY'
import secrets; print(secrets.token_hex(32))
PY
)
fi

# Default DB to sqlite under /etc/comidf
DATABASE_URL_DEFAULT="sqlite:////etc/comidf/comidf.db"

# ---------------------------------------------------------------
# Generate self-signed TLS certs (server)
# ---------------------------------------------------------------
CERT_DIR="/etc/comidf/certs"
SERVER_KEY="$CERT_DIR/server.key"
SERVER_CRT="$CERT_DIR/server.crt"
if [ ! -f "$SERVER_KEY" ] || [ ! -f "$SERVER_CRT" ]; then
  echo "Generating self-signed TLS certificate..."
  openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$SERVER_KEY" -out "$SERVER_CRT" -days 825 \
    -subj "/CN=$(hostname)"
  chmod 600 "$SERVER_KEY"
fi

cat > /etc/comidf/cloud_env.sh <<EOF
# CoMIDF Cloud environment
export PYTHONPATH=/opt/CoMIDF
export DATABASE_URL="${DATABASE_URL:-$DATABASE_URL_DEFAULT}"
export SESSION_SECRET="${SESSION_SECRET:-$SESSION_SECRET_GENERATED}"
export SESSION_COOKIE_NAME="comidf_session"
export SESSION_COOKIE_SECURE="true"
export SESSION_COOKIE_SAMESITE="lax"
export GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID}"
export GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET}"
export SSL_CERT_FILE="$SERVER_CRT"
export SSL_KEY_FILE="$SERVER_KEY"
export CLOUD_HTTPS_PORT="8443"
EOF

chmod 600 /etc/comidf/cloud_env.sh || true

# ---------------------------------------------------------------
# Create run script
# ---------------------------------------------------------------
cat > "$ROOT_DIR/scripts/run_cloud.sh" <<'EOF'
#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"
if [ -f /etc/comidf/cloud_env.sh ]; then
  . /etc/comidf/cloud_env.sh
fi
. "$ROOT_DIR/venv/bin/activate"
PORT="${CLOUD_HTTPS_PORT:-8443}"
if [ -n "$SSL_CERT_FILE" ] && [ -n "$SSL_KEY_FILE" ]; then
  exec python -m uvicorn cloud_platform.uer_gateway.receiver:app \
    --host 0.0.0.0 --port "$PORT" \
    --ssl-certfile "$SSL_CERT_FILE" --ssl-keyfile "$SSL_KEY_FILE"
else
  echo "Warning: SSL certs not set, starting without TLS." >&2
  exec python -m uvicorn cloud_platform.uer_gateway.receiver:app --host 0.0.0.0 --port "$PORT"
fi
EOF

chmod +x "$ROOT_DIR/scripts/run_cloud.sh"

echo ""
echo "========================================="
echo "Cloud Platform installation completed!"
echo "========================================="
echo ""
echo "Environment saved to: /etc/comidf/cloud_env.sh"
echo "TLS cert: $SERVER_CRT"
echo "HTTPS port: ${CLOUD_HTTPS_PORT:-8443}"
echo "To start the service, run:"
echo "  $ROOT_DIR/scripts/run_cloud.sh"
echo ""

