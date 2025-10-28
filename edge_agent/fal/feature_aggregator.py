"""
Feature Aggregation Layer (FAL) - Aggregates features from multiple protocol agents
"""
from typing import Dict, List, Any, Optional
from collections import defaultdict
import statistics
import time

from shared.models.uer_schema import UnifiedEventReport
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class FlowStatistics:
    """Tracks flow statistics for aggregation"""
    
    def __init__(self):
        self.packet_lengths: List[int] = []
        self.inter_arrival_times: List[float] = []
        self.packet_timestamps: List[float] = []
        self.total_bytes = 0
        self.packet_count = 0
        self.direction = 'unknown'
        self.flow_key = None
    
    def add_packet(self, length: int, timestamp: Optional[float] = None):
        """Add packet to flow statistics"""
        self.packet_lengths.append(length)
        self.total_bytes += length
        self.packet_count += 1
        
        if timestamp:
            self.packet_timestamps.append(timestamp)
            if len(self.packet_timestamps) > 1:
                iat = timestamp - self.packet_timestamps[-2]
                self.inter_arrival_times.append(iat)
    
    def get_mean_packet_length(self) -> float:
        """Calculate mean packet length"""
        if not self.packet_lengths:
            return 0.0
        return statistics.mean(self.packet_lengths)
    
    def get_mean_inter_arrival_time(self) -> float:
        """Calculate mean inter-arrival time"""
        if not self.inter_arrival_times:
            return 0.0
        return statistics.mean(self.inter_arrival_times) * 1000  # Convert to ms
    
    def get_duration(self) -> float:
        """Get total flow duration"""
        if len(self.packet_timestamps) < 2:
            return 0.0
        return (self.packet_timestamps[-1] - self.packet_timestamps[0]) * 1000  # ms
    
    def calculate_entropy(self) -> float:
        """Calculate packet length entropy"""
        if not self.packet_lengths:
            return 0.0
        
        # Discretize packet lengths into bins
        bins = defaultdict(int)
        for length in self.packet_lengths:
            bins[length // 10] += 1  # 10-byte bins
        
        total = len(self.packet_lengths)
        entropy = 0.0
        
        for count in bins.values():
            prob = count / total
            if prob > 0:
                entropy -= prob * (prob.bit_length() - 1)
        
        return entropy


class FeatureAggregationLayer:
    """Aggregates features and creates UERs for multiple protocols"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.flow_cache: Dict[str, FlowStatistics] = {}
        self.cache_timeout = config.get('flow_cache_timeout', 600)  # 10 minutes
        self.last_cleanup = time.time()
    
    def create_flow_key(self, src_ip: str, dst_ip: str, src_port: int, dst_port: int) -> str:
        """Create a unique key for flow identification"""
        # Normalize: use smaller IP first
        ips = sorted([src_ip, dst_ip])
        ports = sorted([src_port, dst_port])
        return f"{ips[0]}:{ports[0]}-{ips[1]}:{ports[1]}"
    
    def get_or_create_flow(
        self,
        flow_key: str,
        src_ip: str,
        dst_ip: str,
        src_port: int,
        dst_port: int
    ) -> FlowStatistics:
        """Get existing flow or create new one"""
        if flow_key not in self.flow_cache:
            flow_stats = FlowStatistics()
            flow_stats.flow_key = flow_key
            # Determine direction based on IP
            flow_stats.direction = 'outbound' if src_ip != dst_ip else 'bidirectional'
            self.flow_cache[flow_key] = flow_stats
        
        return self.flow_cache[flow_key]
    
    def aggregate_features(
        self,
        packets: List[Dict[str, Any]],
        protocol_agent
    ) -> Dict[str, Any]:
        """Aggregate features from multiple packets in a flow"""
        if not packets:
            return {}
        
        # Group packets by flow
        flows: Dict[str, List[Dict]] = defaultdict(list)
        for packet in packets:
            flow_key = self.create_flow_key(
                packet['src_ip'],
                packet['dst_ip'],
                packet['src_port'],
                packet['dst_port']
            )
            flows[flow_key].append(packet)
        
        # Aggregate statistics for each flow
        aggregated_features = {}
        for flow_key, flow_packets in flows.items():
            if not flow_packets:
                continue
            
            # Get or create flow statistics
            flow_stats = self.get_or_create_flow(
                flow_key,
                flow_packets[0]['src_ip'],
                flow_packets[0]['dst_ip'],
                flow_packets[0]['src_port'],
                flow_packets[0]['dst_port']
            )
            
            # Add all packets to statistics
            for packet in flow_packets:
                flow_stats.add_packet(
                    len(packet.get('data', b'')),
                    packet.get('timestamp', time.time())
                )
            
            # Calculate aggregated features
            aggregated_features[flow_key] = {
                'packet_count': flow_stats.packet_count,
                'byte_count': flow_stats.total_bytes,
                'duration_ms': flow_stats.get_duration(),
                'mean_packet_length': flow_stats.get_mean_packet_length(),
                'mean_inter_arrival_time': flow_stats.get_mean_inter_arrival_time(),
                'entropy': flow_stats.calculate_entropy(),
                'direction': flow_stats.direction
            }
        
        self.cleanup_old_flows()
        return aggregated_features
    
    def cleanup_old_flows(self):
        """Remove flows that haven't been updated recently"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cache_timeout:
            return
        
        # Remove flows older than timeout
        flows_to_remove = []
        for flow_key, flow_stats in self.flow_cache.items():
            if flow_stats.packet_timestamps:
                last_packet_time = flow_stats.packet_timestamps[-1]
                if current_time - last_packet_time > self.cache_timeout:
                    flows_to_remove.append(flow_key)
        
        for key in flows_to_remove:
            del self.flow_cache[key]
        
        self.last_cleanup = current_time
        logger.debug(f"Cleaned up {len(flows_to_remove)} old flows")

