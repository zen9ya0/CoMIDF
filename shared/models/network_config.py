"""
Network configuration models for dual NIC setup
"""
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
import yaml


class CloudNetworkConfig(BaseModel):
    """Cloud Platform network configuration"""
    mgmt_iface: str  # Management interface for UI/API/SSH
    data_iface: str  # Data interface for Kafka/UER Gateway
    
    mgmt_ip: Optional[str] = None
    data_ip: Optional[str] = None
    
    config_path: str = "/etc/comidf/cloud_net_config.yaml"
    
    def save(self) -> None:
        """Save configuration to file"""
        config_dir = Path(self.config_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w') as f:
            yaml.dump(self.dict(), f)
    
    @classmethod
    def load(cls) -> 'CloudNetworkConfig':
        """Load configuration from file"""
        config_path = "/etc/comidf/cloud_net_config.yaml"
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)


class EdgeNetworkConfig(BaseModel):
    """Edge Agent network configuration"""
    mgmt_iface: str  # Management interface for TLS and registration
    sniff_iface: str  # Packet capture interface
    
    mgmt_ip: Optional[str] = None
    sniff_ip: Optional[str] = None
    
    config_path: str = "/etc/comidf/agent_net_config.yaml"
    
    def save(self) -> None:
        """Save configuration to file"""
        config_dir = Path(self.config_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w') as f:
            yaml.dump(self.dict(), f)
    
    @classmethod
    def load(cls) -> 'EdgeNetworkConfig':
        """Load configuration from file"""
        config_path = "/etc/comidf/agent_net_config.yaml"
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)

