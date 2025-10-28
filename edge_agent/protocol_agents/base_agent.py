"""
Base Protocol Agent - Abstract class for all protocol agents
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import struct
import socket

from shared.models.uer_schema import (
    UnifiedEventReport, ProtocolInfo, FlowFeatures, ProtocolSpecificFeatures
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class BaseProtocolAgent(ABC):
    """Base class for all protocol-specific agents"""
    
    def __init__(self, agent_id: str, tenant_id: str, interface: str):
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.interface = interface
        self.packet_count = 0
        
    @abstractmethod
    def parse_packet(self, packet_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse raw packet data and extract protocol-specific features
        
        Args:
            packet_data: Raw packet bytes
            
        Returns:
            Dict containing parsed features or None if parsing fails
        """
        pass
    
    @abstractmethod
    def extract_flow_features(
        self, 
        packet: Dict[str, Any],
        flow_stats: Dict[str, Any]
    ) -> FlowFeatures:
        """Extract flow-based features from packet sequence"""
        pass
    
    @abstractmethod
    def extract_protocol_features(
        self,
        packet: Dict[str, Any]
    ) -> ProtocolSpecificFeatures:
        """Extract protocol-specific features"""
        pass
    
    def create_uer(
        self,
        packet_data: bytes,
        src_ip: str,
        dst_ip: str,
        src_port: int,
        dst_port: int,
        risk_score: float,
        anomaly_flags: list
    ) -> UnifiedEventReport:
        """Create Unified Event Report from parsed packet"""
        from datetime import datetime
        import hashlib
        
        # Parse packet
        parsed = self.parse_packet(packet_data)
        if not parsed:
            raise ValueError("Failed to parse packet")
        
        # Get protocol info
        protocol_info = ProtocolInfo(
            protocol_type=self.get_protocol_name(),
            version=parsed.get('version'),
            port=dst_port if dst_port < 65536 else src_port,
            is_encrypted=parsed.get('encrypted', False)
        )
        
        # Extract flow features
        flow_features = self.extract_flow_features(parsed, {})
        
        # Extract protocol features
        protocol_features = self.extract_protocol_features(parsed)
        
        # Create UER
        import uuid
        event_id = str(uuid.uuid4())
        
        return UnifiedEventReport(
            event_id=event_id,
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            timestamp=datetime.now(),
            source_ip=src_ip,
            destination_ip=dst_ip,
            source_port=src_port,
            destination_port=dst_port,
            protocol_info=protocol_info,
            flow_features=flow_features,
            protocol_features=protocol_features,
            edge_agent_risk_score=risk_score,
            edge_agent_anomaly_flags=anomaly_flags,
            raw_packet_sample=packet_data[:1500] if len(packet_data) > 1500 else packet_data
        )
    
    @abstractmethod
    def get_protocol_name(self) -> str:
        """Return protocol name"""
        pass
    
    def calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy"""
        if not data:
            return 0.0
        
        entropy = 0.0
        data_len = len(data)
        
        # Count byte frequencies
        byte_counts = [0] * 256
        for byte in data:
            byte_counts[byte] += 1
        
        # Calculate entropy
        for count in byte_counts:
            if count > 0:
                probability = count / data_len
                entropy -= probability * (probability.bit_length() - 1)
        
        return entropy

