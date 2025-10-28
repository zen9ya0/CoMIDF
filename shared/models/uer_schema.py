"""
Unified Event Report (UER) Schema - Core data model for intrusion detection events
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ProtocolInfo(BaseModel):
    """Protocol-specific information"""
    protocol_type: str  # MQTT, HTTP, CoAP, etc.
    version: Optional[str] = None
    port: int
    is_encrypted: bool = False


class FlowFeatures(BaseModel):
    """Flow-based features extracted from network traffic"""
    packet_count: int
    byte_count: int
    duration_ms: float
    mean_packet_length: float
    mean_inter_arrival_time: float
    entropy: float
    flow_direction: str  # inbound, outbound, bidirectional


class ProtocolSpecificFeatures(BaseModel):
    """Protocol-specific features"""
    # MQTT
    mqtt_command_type: Optional[str] = None
    
    # HTTP
    http_method: Optional[str] = None
    http_status_code: Optional[int] = None
    
    # DNS
    dns_query_type: Optional[str] = None
    dns_response_code: Optional[int] = None
    dns_ttl_variance: Optional[float] = None
    
    # QUIC
    quic_version: Optional[str] = None
    initial_packet_count: Optional[int] = None
    
    # Additional fields for protocol-agnostic storage
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ThreatIndicator(BaseModel):
    """Threat indicators and confidence scores"""
    threat_type: str
    confidence: float  # 0.0 to 1.0
    attack_technique: Optional[List[str]] = None  # MITRE ATT&CK IDs
    ioc_hit: bool = False
    ioc_source: Optional[List[str]] = None


class UnifiedEventReport(BaseModel):
    """Core UER model - sent from Edge Agent to Cloud Platform"""
    # Basic identification
    event_id: str
    agent_id: str
    tenant_id: str
    timestamp: datetime
    
    # Network information
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    
    # Protocol and flow features
    protocol_info: ProtocolInfo
    flow_features: FlowFeatures
    protocol_features: ProtocolSpecificFeatures
    
    # Detection results from Edge Agent
    edge_agent_risk_score: float  # 0.0 to 1.0
    edge_agent_anomaly_flags: List[str]
    
    # Metadata
    raw_packet_sample: Optional[bytes] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            bytes: lambda v: v.hex() if v else None
        }


class CloudProcessingResult(BaseModel):
    """Result after Cloud Platform processing"""
    # Original UER
    original_uer: UnifiedEventReport
    
    # Bayesian + Dempster-Shafer fusion
    global_credibility: float  # Bayesian posterior
    global_plausibility: float  # Dempster-Shafer upper bound
    
    # Threat indicators
    threat_indicators: List[ThreatIndicator]
    
    # Trust and learning
    agent_trust_score: float
    recalibration_threshold: float
    
    # AI analysis
    anomaly_cluster_id: Optional[str] = None
    semi_supervised_anomaly_score: Optional[float] = None
    
    # CTI matching
    cti_matches: List[Dict[str, Any]] = Field(default_factory=list)
    ioc_confidence: float = 0.0
    
    # LLM description
    threat_description_nl: Optional[str] = None
    
    # Final decision
    final_risk_score: float
    alert_priority: str  # low, medium, high, critical
    should_report: bool
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

