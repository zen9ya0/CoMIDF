"""
CoMIDF Project Constants
"""
from enum import Enum


class ProtocolType(str, Enum):
    """Supported protocol types"""
    MQTT = "MQTT"
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    COAP = "CoAP"
    MODBUS = "Modbus"
    ZIGBEE = "Zigbee"
    DNS = "DNS"
    QUIC = "QUIC"
    GRPC = "gRPC"
    NETFLOW = "NetFlow"
    SFLOW = "sFlow"


class ThreatType(str, Enum):
    """Threat classification types"""
    MALICIOUS_COMMUNICATION = "malicious_communication"
    DATA_EXFILTRATION = "data_exfiltration"
    UNUSUAL_BEHAVIOR = "unusual_behavior"
    PROTOCOL_ANOMALY = "protocol_anomaly"
    UNKNOWN_TRAFFIC = "unknown_traffic"
    IOC_MATCH = "ioc_match"


class AlertPriority(str, Enum):
    """Alert priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentStatus(str, Enum):
    """Edge Agent status"""
    REGISTERING = "registering"
    ACTIVE = "active"
    IDLE = "idle"
    ERROR = "error"
    OFFLINE = "offline"


class TenantStatus(str, Enum):
    """Tenant status"""
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


# Network configuration constants
DEFAULT_MANAGEMENT_PORT = 8443
DEFAULT_DATA_PORT = 9092
DEFAULT_KAFKA_PORT = 9093

# Trust and learning parameters
DEFAULT_TRUST_ALPHA = 0.7  # Weight for trust decay
DEFAULT_RECALIBRATION_UPDATE_RATE = 0.1  # Rate for threshold updates

# AI fusion parameters
BAYESIAN_PRIOR = 0.5  # Prior probability for Bayesian inference
DEMPSTER_CONFLICT_THRESHOLD = 0.5  # Threshold for DS combination

# Performance thresholds
MAX_UER_SIZE_BYTES = 10 * 1024  # 10KB max UER size
MAX_PACKET_SAMPLE_SIZE = 1500  # Standard MTU
PACKET_BUFFER_SIZE = 1000  # Buffer size for packet capture

