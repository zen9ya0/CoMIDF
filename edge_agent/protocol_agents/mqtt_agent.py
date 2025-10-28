"""
MQTT Protocol Agent - Detects and analyzes MQTT traffic
"""
from typing import Dict, Any, Optional
import struct

from edge_agent.protocol_agents.base_agent import BaseProtocolAgent
from shared.models.uer_schema import FlowFeatures, ProtocolSpecificFeatures
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class MQTTPacket:
    """MQTT packet parser"""
    
    COMMAND_TYPES = {
        1: "CONNECT", 2: "CONNACK", 3: "PUBLISH",
        4: "PUBACK", 5: "PUBREC", 6: "PUBREL",
        7: "PUBCOMP", 8: "SUBSCRIBE", 9: "SUBACK",
        10: "UNSUBSCRIBE", 11: "UNSUBACK",
        12: "PINGREQ", 13: "PINGRESP", 14: "DISCONNECT"
    }
    
    @staticmethod
    def parse_fixed_header(data: bytes) -> tuple:
        """Parse MQTT fixed header"""
        if len(data) < 2:
            return None
        
        byte1 = data[0]
        message_type = (byte1 >> 4) & 0x0F
        flags = byte1 & 0x0F
        
        remaining_length = 0
        multiplier = 1
        pos = 1
        
        while pos < len(data) and (data[pos] & 0x80):
            remaining_length += (data[pos] & 0x7F) * multiplier
            multiplier *= 128
            pos += 1
        
        if pos < len(data):
            remaining_length += (data[pos] & 0x7F) * multiplier
        else:
            return None
        
        return (message_type, flags, remaining_length, pos + 1)
    
    @staticmethod
    def parse_variable_header(data: bytes, start_pos: int) -> Dict[str, Any]:
        """Parse MQTT variable header based on message type"""
        if start_pos >= len(data):
            return {}
        
        result = {}
        pos = start_pos
        
        # Parse protocol name (for CONNECT)
        if len(data) - pos >= 2:
            proto_len = struct.unpack('!H', data[pos:pos+2])[0]
            pos += 2
            
            if len(data) - pos >= proto_len:
                proto_name = data[pos:pos+proto_len].decode('utf-8', errors='ignore')
                result['protocol_name'] = proto_name
                pos += proto_len
        
        return result


class MQTTAgent(BaseProtocolAgent):
    """MQTT protocol agent implementation"""
    
    def get_protocol_name(self) -> str:
        return "MQTT"
    
    def parse_packet(self, packet_data: bytes) -> Optional[Dict[str, Any]]:
        """Parse MQTT packet"""
        try:
            header_info = MQTTPacket.parse_fixed_header(packet_data)
            if not header_info:
                return None
            
            message_type, flags, remaining_length, var_header_start = header_info
            command_name = MQTTPacket.COMMAND_TYPES.get(message_type, "UNKNOWN")
            
            # Parse variable header if enough data
            var_header = {}
            if var_header_start < len(packet_data):
                var_header = MQTTPacket.parse_variable_header(
                    packet_data, var_header_start
                )
            
            return {
                'message_type': message_type,
                'command_name': command_name,
                'flags': flags,
                'remaining_length': remaining_length,
                'variable_header': var_header,
                'version': var_header.get('protocol_name'),
                'encrypted': False  # MQTT is plaintext unless wrapped in TLS
            }
        except Exception as e:
            logger.debug(f"Failed to parse MQTT packet: {e}")
            return None
    
    def extract_flow_features(
        self,
        packet: Dict[str, Any],
        flow_stats: Dict[str, Any]
    ) -> FlowFeatures:
        """Extract MQTT flow features"""
        # Default flow features
        return FlowFeatures(
            packet_count=flow_stats.get('packet_count', 1),
            byte_count=flow_stats.get('byte_count', len(packet.get('raw_data', b''))),
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
        """Extract MQTT-specific features"""
        command_name = packet.get('command_name', 'UNKNOWN')
        
        return ProtocolSpecificFeatures(
            mqtt_command_type=command_name,
            metadata={
                'mqtt_flags': packet.get('flags'),
                'remaining_length': packet.get('remaining_length'),
                'protocol_version': packet.get('variable_header', {}).get('protocol_name')
            }
        )

