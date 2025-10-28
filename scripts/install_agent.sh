#!/bin/bash
# CoMIDF Edge Agent Installation Script
# Dual NIC setup for management and capture interfaces

set -e

echo "========================================="
echo "CoMIDF Edge Agent Installation"
echo "========================================="
echo ""

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
echo -n "Management interface (for TLS/registration) - Enter number: "
read mgmt_num
mgmt_iface=${iface_list[$mgmt_num]}

if [ -z "$mgmt_iface" ]; then
    echo "Error: Invalid interface selection"
    exit 1
fi

# Get sniff interface
echo -n "Packet capture interface (for libpcap) - Enter number: "
read sniff_num
sniff_iface=${iface_list[$sniff_num]}

if [ -z "$sniff_iface" ]; then
    echo "Error: Invalid interface selection"
    exit 1
fi

# Get IP addresses
echo ""
echo "Enter IP addresses (optional, leave empty for auto-detect):"
echo -n "Management IP for $mgmt_iface: "
read mgmt_ip
echo -n "Sniff IP for $sniff_iface: "
read sniff_ip

# Cloud Platform endpoint
echo ""
echo -n "Cloud Platform endpoint [https://cloud.comidf.example.com]: "
read cloud_endpoint
cloud_endpoint=${cloud_endpoint:-"https://cloud.comidf.example.com"}

# Agent and tenant IDs
echo -n "Agent ID (leave empty for auto-generated): "
read agent_id
agent_id=${agent_id:-$(uuidgen)}

echo -n "Tenant ID: "
read tenant_id

if [ -z "$tenant_id" ]; then
    echo "Error: Tenant ID is required"
    exit 1
fi

# Create network configuration
echo ""
echo "Creating network configuration..."

mkdir -p /etc/comidf

cat > /etc/comidf/agent_net_config.yaml <<EOF
mgmt_iface: $mgmt_iface
sniff_iface: $sniff_iface
mgmt_ip: $mgmt_ip
sniff_ip: $sniff_ip
config_path: /etc/comidf/agent_net_config.yaml
EOF

# Get IPs if not provided
if [ -z "$mgmt_ip" ]; then
    mgmt_ip=$(ip addr show $mgmt_iface | grep -oP 'inet \K[\d.]+' | head -1)
    echo "  Detected management IP: $mgmt_ip"
fi

if [ -z "$sniff_ip" ]; then
    sniff_ip=$(ip addr show $sniff_iface | grep -oP 'inet \K[\d.]+' | head -1)
    echo "  Detected sniff IP: $sniff_ip"
fi

# Create agent configuration
echo ""
echo "Creating Edge Agent configuration..."

cat > /etc/comidf/agent_config.yaml <<EOF
# Edge Agent Configuration
agent_id: $agent_id
tenant_id: $tenant_id

# Network configuration
management_interface: $mgmt_iface
sniff_interface: $sniff_iface

# Cloud Platform connection
cloud_endpoint: $cloud_endpoint
cloud_port: 443

# Protocol agents to enable
enabled_protocols:
  - MQTT
  - HTTP
  - CoAP
  - Modbus
  - Zigbee
  - DNS
  - QUIC
  - gRPC

# Detection thresholds
risk_threshold: 0.7
anomaly_threshold: 0.5

# Certificate paths (mTLS)
cert_path: /etc/comidf/certs/agent.crt
key_path: /etc/comidf/certs/agent.key
ca_cert_path: /etc/comidf/certs/ca.crt

# JWT secret (should be provided by Cloud Platform)
jwt_secret: "default_secret_change_in_production"

# Feature aggregation
feature_aggregation_window: 60
flow_cache_timeout: 600

# Performance settings
max_packet_buffer_size: 1000
max_uer_size_bytes: 10240

# Debug mode
debug_mode: false
log_level: "INFO"
EOF

echo "✓ Network configuration saved to /etc/comidf/agent_net_config.yaml"
echo "✓ Agent configuration saved to /etc/comidf/agent_config.yaml"
echo ""
echo "========================================="
echo "Edge Agent installation completed!"
echo "========================================="
echo ""
echo "Summary:"
echo "  Agent ID: $agent_id"
echo "  Tenant ID: $tenant_id"
echo "  Management interface: $mgmt_iface ($mgmt_ip)"
echo "  Capture interface: $sniff_iface ($sniff_ip)"
echo "  Cloud endpoint: $cloud_endpoint"
echo ""
echo "Next steps:"
echo "  1. Install Python dependencies: pip install -r requirements.txt"
echo "  2. Start Edge Agent: python edge_agent/main.py"
echo ""

