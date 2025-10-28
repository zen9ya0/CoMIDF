"""
Edge Agent Main Application - Packet capture, analysis, and reporting
"""
import time
import sys
import signal
from typing import List, Optional
from datetime import datetime
import uuid

from edge_agent.config.agent_config import AgentConfig
from edge_agent.protocol_agents.mqtt_agent import MQTTAgent
from edge_agent.protocol_agents.http_agent import HTTPAgent
from edge_agent.fal.feature_aggregator import FeatureAggregationLayer
from edge_agent.secure_connector.connector import SecureConnector, ReverseProxyConnector
from shared.utils.logger import get_logger

logger = get_logger(__name__, "edge_agent.log")


class EdgeAgent:
    """Main Edge Agent application"""
    
    def __init__(self, config_path: Optional[str] = None):
        # Load configuration
        try:
            if config_path:
                with open(config_path, 'r') as f:
                    import yaml
                    config_dict = yaml.safe_load(f)
                    self.config = AgentConfig(**config_dict)
            else:
                self.config = AgentConfig.load()
        except FileNotFoundError:
            logger.error("Configuration file not found. Please run installation script first.")
            sys.exit(1)
        
        # Initialize components
        self.agent_id = self.config.agent_id
        self.tenant_id = self.config.tenant_id
        
        # Initialize protocol agents
        self.protocol_agents = self._initialize_protocol_agents()
        
        # Initialize Feature Aggregation Layer
        fal_config = {
            'flow_cache_timeout': self.config.flow_cache_timeout,
            'feature_aggregation_window': self.config.feature_aggregation_window
        }
        self.feature_aggregator = FeatureAggregationLayer(fal_config)
        
        # Initialize secure connector
        self.connector = ReverseProxyConnector(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            cloud_endpoint=self.config.cloud_endpoint,
            cert_path=self.config.cert_path,
            key_path=self.config.key_path,
            ca_cert_path=self.config.ca_cert_path
        )
        
        # Running state
        self.running = False
        self.packet_count = 0
        
    def _initialize_protocol_agents(self) -> dict:
        """Initialize protocol-specific agents"""
        agents = {}
        
        for protocol in self.config.enabled_protocols:
            try:
                if protocol == "MQTT":
                    agents["MQTT"] = MQTTAgent(
                        agent_id=self.agent_id,
                        tenant_id=self.tenant_id,
                        interface=self.config.sniff_interface
                    )
                elif protocol == "HTTP":
                    agents["HTTP"] = HTTPAgent(
                        agent_id=self.agent_id,
                        tenant_id=self.tenant_id,
                        interface=self.config.sniff_interface
                    )
                # Add more protocol agents here
                logger.info(f"Initialized {protocol} agent")
            except Exception as e:
                logger.error(f"Failed to initialize {protocol} agent: {e}")
        
        return agents
    
    def start(self):
        """Start the Edge Agent"""
        logger.info(f"Starting Edge Agent {self.agent_id}")
        
        # Authenticate with Cloud Platform
        if not self.connector.authenticate(self.config.jwt_secret):
            logger.error("Failed to authenticate with Cloud Platform")
            sys.exit(1)
        
        # Connect to proxy
        if not self.connector.connect_to_proxy():
            logger.error("Failed to connect to Cloud Platform proxy")
            sys.exit(1)
        
        self.running = True
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Edge Agent started successfully")
        
        # Main event loop
        try:
            self._event_loop()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()
    
    def _event_loop(self):
        """Main event processing loop"""
        while self.running:
            try:
                # In production, this would capture real packets using libpcap
                # For now, simulate packet capture
                self._simulate_packet_capture()
                
                time.sleep(0.1)  # Small delay to prevent CPU spinning
            except Exception as e:
                logger.error(f"Error in event loop: {e}")
    
    def _simulate_packet_capture(self):
        """Simulate packet capture for demonstration"""
        # This is a placeholder - in production, use libpcap or similar
        self.packet_count += 1
        
        if self.packet_count % 100 == 0:
            logger.debug(f"Processed {self.packet_count} packets")
    
    def process_packet(self, packet_data: bytes, src_ip: str, dst_ip: str, 
                       src_port: int, dst_port: int, protocol: str) -> Optional[UnifiedEventReport]:
        """Process a captured packet and create UER"""
        try:
            # Select appropriate protocol agent
            agent = self.protocol_agents.get(protocol)
            if not agent:
                logger.debug(f"No agent for protocol {protocol}")
                return None
            
            # Parse and analyze packet
            parsed = agent.parse_packet(packet_data)
            if not parsed:
                return None
            
            # Extract features
            flow_features = agent.extract_flow_features(parsed, {})
            protocol_features = agent.extract_protocol_features(parsed)
            
            # Calculate risk score (simplified for demo)
            risk_score = self._calculate_risk_score(parsed, flow_features, protocol_features)
            anomaly_flags = self._detect_anomalies(parsed, flow_features, protocol_features)
            
            # Create UER
            uer = agent.create_uer(
                packet_data=packet_data,
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=src_port,
                dst_port=dst_port,
                risk_score=risk_score,
                anomaly_flags=anomaly_flags
            )
            
            # Send to Cloud Platform
            if risk_score >= self.config.risk_threshold:
                self.connector.send_uer(uer)
                logger.info(f"Sent UER for high-risk event: {risk_score:.2f}")
            
            return uer
        except Exception as e:
            logger.error(f"Failed to process packet: {e}")
            return None
    
    def _calculate_risk_score(self, parsed: dict, flow_features, protocol_features) -> float:
        """Calculate risk score for packet"""
        # Simplified risk scoring
        score = 0.0
        
        # Protocol-specific risks
        if protocol_features.mqtt_command_type:
            if protocol_features.mqtt_command_type in ['PUBLISH', 'SUBSCRIBE']:
                score += 0.2
        
        # Flow-based risks
        if flow_features.entropy > 7.0:  # High entropy might indicate encryption or exfiltration
            score += 0.3
        
        if flow_features.mean_packet_length > 1000:  # Large packets
            score += 0.2
        
        # Add random variation for demo
        import random
        score += random.random() * 0.2
        
        return min(score, 1.0)
    
    def _detect_anomalies(self, parsed: dict, flow_features, protocol_features) -> List[str]:
        """Detect anomalies in packet"""
        flags = []
        
        if flow_features.entropy > 7.5:
            flags.append("high_entropy")
        
        if flow_features.mean_inter_arrival_time < 10:
            flags.append("rapid_packet_rate")
        
        return flags
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def stop(self):
        """Stop the Edge Agent"""
        logger.info("Stopping Edge Agent...")
        self.running = False
        logger.info("Edge Agent stopped successfully")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="CoMIDF Edge Agent")
    parser.add_argument('--config', '-c', help='Path to configuration file')
    args = parser.parse_args()
    
    agent = EdgeAgent(config_path=args.config)
    agent.start()


if __name__ == "__main__":
    main()

