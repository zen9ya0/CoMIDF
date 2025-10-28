"""
HTTP/HTTPS Protocol Agent
"""
from typing import Dict, Any, Optional
import re

from edge_agent.protocol_agents.base_agent import BaseProtocolAgent
from shared.models.uer_schema import FlowFeatures, ProtocolSpecificFeatures
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class HTTPAgent(BaseProtocolAgent):
    """HTTP protocol agent implementation"""
    
    def get_protocol_name(self) -> str:
        return "HTTP"
    
    def parse_packet(self, packet_data: bytes) -> Optional[Dict[str, Any]]:
        """Parse HTTP request/response"""
        try:
            http_str = packet_data.decode('utf-8', errors='ignore')
            lines = http_str.split('\r\n')
            
            if not lines:
                return None
            
            # Parse first line (request or status line)
            first_line = lines[0]
            is_https = len(packet_data) > 5 and packet_data[:5] == b'\x16\x03\x01'
            
            # Try to detect request line (method + path)
            request_match = re.match(r'^([A-Z]+)\s+(.+?)\s+HTTP/(\d\.\d)$', first_line)
            if request_match:
                method, path, version = request_match.groups()
                return {
                    'type': 'request',
                    'method': method,
                    'path': path,
                    'version': version,
                    'encrypted': is_https,
                    'lines': lines[1:]
                }
            
            # Try to detect status line (response)
            status_match = re.match(r'^HTTP/(\d\.\d)\s+(\d+)\s+(.+)$', first_line)
            if status_match:
                version, status_code, reason = status_match.groups()
                return {
                    'type': 'response',
                    'status_code': int(status_code),
                    'reason': reason,
                    'version': version,
                    'encrypted': is_https,
                    'lines': lines[1:]
                }
            
            return None
        except Exception as e:
            logger.debug(f"Failed to parse HTTP packet: {e}")
            return None
    
    def extract_flow_features(
        self,
        packet: Dict[str, Any],
        flow_stats: Dict[str, Any]
    ) -> FlowFeatures:
        """Extract HTTP flow features"""
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
        """Extract HTTP-specific features"""
        method = None
        status_code = None
        
        if packet.get('type') == 'request':
            method = packet.get('method')
        elif packet.get('type') == 'response':
            status_code = packet.get('status_code')
        
        return ProtocolSpecificFeatures(
            http_method=method,
            http_status_code=status_code,
            metadata={
                'http_version': packet.get('version'),
                'is_request': packet.get('type') == 'request',
                'encrypted': packet.get('encrypted', False)
            }
        )

