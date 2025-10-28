"""
DNS Protocol Agent - Detects and analyzes DNS traffic
"""
from typing import Dict, Any, Optional
import struct

from edge_agent.protocol_agents.base_agent import BaseProtocolAgent
from shared.models.uer_schema import FlowFeatures, ProtocolSpecificFeatures
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class DNSAgent(BaseProtocolAgent):
    """DNS protocol agent implementation"""
    
    def get_protocol_name(self) -> str:
        return "DNS"
    
    def parse_packet(self, packet_data: bytes) -> Optional[Dict[str, Any]]:
        """Parse DNS packet"""
        try:
            if len(packet_data) < 12:
                return None
            
            # Parse DNS header
            header = struct.unpack('!HHHHHH', packet_data[:12])
            transaction_id, flags, qdcount, ancount, nscount, arcount = header
            
            # Parse flags
            qr = (flags >> 15) & 0x1  # Query/Response
            opcode = (flags >> 11) & 0xF
            aa = (flags >> 10) & 0x1
            tc = (flags >> 9) & 0x1
            rd = (flags >> 8) & 0x1
            ra = (flags >> 7) & 0x1
            rcode = flags & 0xF
            
            # Query types
            query_type = None
            question_type = 0
            if qdcount > 0 and len(packet_data) > 12:
                # Skip domain name (simplified)
                pos = 12
                while pos < len(packet_data) and packet_data[pos] != 0:
                    pos += packet_data[pos] + 1
                if pos + 4 < len(packet_data):
                    question_type = struct.unpack('!H', packet_data[pos+1:pos+3])[0]
            
            return {
                'transaction_id': transaction_id,
                'is_response': qr == 1,
                'opcode': opcode,
                'response_code': rcode,
                'question_count': qdcount,
                'answer_count': ancount,
                'question_type': question_type,
                'flags': {
                    'aa': aa,
                    'tc': tc,
                    'rd': rd,
                    'ra': ra
                }
            }
        except Exception as e:
            logger.debug(f"Failed to parse DNS packet: {e}")
            return None
    
    def extract_flow_features(
        self,
        packet: Dict[str, Any],
        flow_stats: Dict[str, Any]
    ) -> FlowFeatures:
        """Extract DNS flow features"""
        return FlowFeatures(
            packet_count=flow_stats.get('packet_count', 1),
            byte_count=flow_stats.get('byte_count', 0),
            duration_ms=flow_stats.get('duration_ms', 0.0),
            mean_packet_length=flow_stats.get('mean_packet_length', len(packet.get('raw_data', b''))),
            mean_inter_arrival_time=flow_stats.get('mean_iat', 0.0),
            entropy=flow_stats.get('entropy', 0.0),
            flow_direction=flow_stats.get('direction', 'bidirectional')
        )
    
    def extract_protocol_features(
        self,
        packet: Dict[str, Any]
    ) -> ProtocolSpecificFeatures:
        """Extract DNS-specific features"""
        query_type_names = {
            1: 'A', 2: 'NS', 5: 'CNAME', 15: 'MX', 16: 'TXT',
            28: 'AAAA', 33: 'SRV', 43: 'DS', 257: 'CAA'
        }
        
        query_type = query_type_names.get(packet.get('question_type', 0), 'UNKNOWN')
        
        return ProtocolSpecificFeatures(
            dns_query_type=query_type if not packet.get('is_response') else None,
            dns_response_code=packet.get('response_code') if packet.get('is_response') else None,
            dns_ttl_variance=packet.get('ttl_variance'),
            metadata={
                'transaction_id': packet.get('transaction_id'),
                'opcode': packet.get('opcode'),
                'answer_count': packet.get('answer_count', 0),
                'authoritative': packet.get('flags', {}).get('aa', False),
                'truncated': packet.get('flags', {}).get('tc', False)
            }
        )

