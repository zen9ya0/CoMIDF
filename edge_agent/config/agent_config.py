"""
Edge Agent Configuration
"""
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import yaml
from pathlib import Path


class AgentConfig(BaseModel):
    """Edge Agent configuration model"""
    
    # Agent identification
    agent_id: str
    tenant_id: str
    
    # Network configuration
    management_interface: str
    sniff_interface: str
    
    # Cloud Platform connection
    cloud_endpoint: str
    cloud_port: int = 443
    
    # Protocol agents to enable
    enabled_protocols: List[str] = [
        "MQTT", "HTTP", "CoAP", "Modbus", "Zigbee", "DNS", "QUIC", "gRPC"
    ]
    
    # Detection thresholds
    risk_threshold: float = 0.7
    anomaly_threshold: float = 0.5
    
    # Certificate paths (mTLS)
    cert_path: Optional[str] = None
    key_path: Optional[str] = None
    ca_cert_path: Optional[str] = None
    
    # JWT secret
    jwt_secret: str = "default_secret_change_in_production"
    
    # Feature aggregation
    feature_aggregation_window: int = 60  # seconds
    flow_cache_timeout: int = 600  # seconds
    
    # Performance settings
    max_packet_buffer_size: int = 1000
    max_uer_size_bytes: int = 10240
    
    # Additional settings
    debug_mode: bool = False
    log_level: str = "INFO"
    
    config_path: str = "/etc/comidf/agent_config.yaml"
    
    def save(self) -> None:
        """Save configuration to file"""
        config_dir = Path(self.config_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w') as f:
            yaml.dump(self.dict(exclude={'config_path'}), f, default_flow_style=False)
    
    @classmethod
    def load(cls) -> 'AgentConfig':
        """Load configuration from file"""
        config_path = "/etc/comidf/agent_config.yaml"
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    @classmethod
    def create_default(cls, agent_id: str, tenant_id: str) -> 'AgentConfig':
        """Create default configuration"""
        return cls(
            agent_id=agent_id,
            tenant_id=tenant_id,
            management_interface="eth0",
            sniff_interface="eth0",
            cloud_endpoint="https://cloud.comidf.example.com",
            cloud_port=443
        )

