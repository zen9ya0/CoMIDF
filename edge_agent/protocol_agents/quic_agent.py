"""
QUIC Protocol Agent - Detects and analyzes QUIC traffic
"""
from typing import Dict, Any, Optional

from edge_agent.protocol_agents.base_agent import BaseProtocolAgent
from shared.models.uer_schema import FlowFeatures, ProtocolSpecificFeatures
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class QUICAgent(BaseProtocolAgent):
    """QUIC protocol agent implementation"""
    
    def get_protocol_name(self) -> str:
        return "QUIC"
    
    def parse_packet(self, packet_data: bytes) -> Optional[Dict[str, Any]]:
        """Parse QUIC packet"""
        try:
            if len(packet_data) < 1:
                return None
            
            # QUIC header starts with first byte flags
            first_byte = packet_data[0]
            header_form = (first_byte >> 7) & 0x1  # Long or short header
            
            if header_form == 1:  # Long header
                if len(packet_data) < 5:
                    return None
                
                # Parse long header
                first_bit = (first_byte >> 6) & 0x1
                fixed_bit = first_bit
                packet_type = (first_byte >> 4) & 0x3
                version = None
                
                if len(packet_data) >= 5:
                    version = int.from_bytes(packet_data[1:5], byteorder='big')
                
                return {
                    'header_type': 'long',
                    'packet_type': packet_type,
                    'version': version,
                    'fixed_bit': fixed_bit
                }
            else:  # Short header
                return {
                    'header_type': 'short',
                    'key_phase': (first_byte >> 2) & 0x1,
                    'packet_number_length': first_byte & 0x3
                }
        except Exception as e:
            logger.debug(f"Failed to parse QUIC packet: {e}")
            return None
    
    def extract_flow_features(
        self,
        packet: Dict[str, Any],
        flow_stats: Dict[str, Any]
    ) -> FlowFeatures:
        """Extract QUIC flow features"""
        return FlowFeatures(
            packet_count=flow_stats.get('packet_count', 1),
            byte_count=flow_stats.get('byte_count', 0),
            duration_ms=flow_stats.get('duration_ms', 0.0),
            mean_packet_length=flow_stats.get('mean_packet_length', 0.0),
            mean_inter_arrival_time=flow_stats.get('mean_iat', 0.0),
            entropy=flow_stats.get('entropy', 0.0),
            flow_direction=flow_stats.get('direction', 'bidirectional')
        )
    
    def extract_protocol_features(
        self,
        packet: Dict[str, Any]
    ) -> ProtocolSpecificFeatures:
        """Extract QUIC-specific features"""
        version = packet.get('version')
        initial_packet_count = 1 if packet.get('packet_type') == 0 else 0
        
        return ProtocolSpecificFeatures(
            quic_version=str(version) if version else None,
            initial_packet_count=initial_packet_count,
            metadata={
                'header_type': packet.get('header_type'),
                'packet_type': packet.get('packet_type'),
                'encrypted': True  # QUIC is always encrypted
            }
        )

