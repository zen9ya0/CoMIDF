"""
LLM Threat Description Engine - Natural language threat explanation
"""
from typing import Dict, List, Any, Optional

from shared.models.uer_schema import UnifiedEventReport, CloudProcessingResult
from shared.utils.logger import get_logger

logger = get_logger(__name__, "llm_engine.log")


class LLMThreatDescriptionEngine:
    """Generates natural language descriptions of threats"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.use_llm = config.get('use_llm', False)
        self.llm_model = config.get('llm_model', 'gpt-3.5-turbo')
        
        # In production, would initialize LLM client here
        # For demo, we'll use template-based generation
    
    def generate_description(
        self,
        uer: UnifiedEventReport,
        gc_result: Dict[str, Any],
        threat_indicators: List[Dict[str, Any]],
        ioc_matches: List[Dict[str, Any]]
    ) -> str:
        """
        Generate natural language threat description
        
        Example output:
        「來自 10.0.0.5 的 MQTT 流量平均封包大小 142 byte，間隔為 22ms，
        可能為 T1041 資料外洩通道。模型評分為 0.88，置信度 0.91。」
        """
        logger.debug(f"Generating threat description for UER {uer.event_id}")
        
        # Extract key information
        protocol = uer.protocol_info.protocol_type
        src_ip = uer.source_ip
        dst_ip = uer.destination_ip
        risk_score = gc_result.get('global_credibility', 0.0)
        confidence = gc_result.get('belief', 0.0)
        
        # Get flow features
        mean_length = uer.flow_features.mean_packet_length
        mean_iat = uer.flow_features.mean_inter_arrival_time
        
        # Check for IOC matches
        mitre_ids = []
        if ioc_matches:
            for match in ioc_matches:
                if 'mitre_id' in match and match['mitre_id']:
                    mitre_ids.extend(match['mitre_id'])
        
        # Generate description (template-based for demo)
        parts = []
        
        # Source description
        parts.append(f"來自 {src_ip}")
        
        # Protocol description
        if protocol == "MQTT":
            parts.append(f"的 {protocol} 流量")
            if uer.protocol_features.mqtt_command_type:
                parts.append(f"({uer.protocol_features.mqtt_command_type} 指令)")
        elif protocol == "HTTP":
            parts.append(f"的 {protocol} 流量")
            if uer.protocol_features.http_method:
                parts.append(f"({uer.protocol_features.http_method} 方法)")
        else:
            parts.append(f"的 {protocol} 流量")
        
        # Flow features
        if mean_length > 0:
            parts.append(f"平均封包大小 {mean_length:.0f} byte")
        
        if mean_iat > 0:
            parts.append(f"，間隔為 {mean_iat:.1f}ms")
        
        # Threat assessment
        if ioc_matches:
            parts.append("，偵測到已知 IOC")
            if mitre_ids:
                mitre_str = "、".join(mitre_ids[:3])  # Limit to first 3
                parts.append(f"（{mitre_str}）")
        
        # Risk indicators
        if threat_indicators:
            threat_types = [ti.get('threat_type', '') for ti in threat_indicators]
            if threat_types:
                parts.append(f"，威脅類型：{', '.join(threat_types)}")
        
        # Risk assessment
        if risk_score >= 0.9:
            threat_level = "高度威脅"
        elif risk_score >= 0.7:
            threat_level = "中度威脅"
        else:
            threat_level = "低度威脅"
        
        parts.append(f"。風險評分為 {risk_score:.2f} ({threat_level})")
        parts.append(f"，置信度 {confidence:.2f}。")
        
        description = "".join(parts)
        
        # Use LLM if enabled and available
        if self.use_llm:
            try:
                return self._generate_with_llm(
                    uer, gc_result, threat_indicators, ioc_matches
                )
            except Exception as e:
                logger.warning(f"LLM generation failed, using template: {e}")
        
        return description
    
    def _generate_with_llm(
        self,
        uer: UnifiedEventReport,
        gc_result: Dict[str, Any],
        threat_indicators: List[Dict[str, Any]],
        ioc_matches: List[Dict[str, Any]]
    ) -> str:
        """Generate description using actual LLM (placeholder)"""
        # In production, would call OpenAI API or similar
        # For now, return template-based description
        return self.generate_description(uer, gc_result, threat_indicators, ioc_matches)
    
    def format_for_llm_input(
        self,
        uer: UnifiedEventReport,
        gc_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format data for LLM input"""
        return {
            "proto": uer.protocol_info.protocol_type,
            "score": round(gc_result.get('global_credibility', 0.0), 2),
            "conf": round(gc_result.get('belief', 0.0), 2),
            "attck_hint": self._extract_attack_ids(uer),
            "features": {
                "len_mean": round(uer.flow_features.mean_packet_length, 0),
                "iat_mean": round(uer.flow_features.mean_inter_arrival_time, 2)
            },
            "src_ip": uer.source_ip,
            "dst_ip": uer.destination_ip
        }
    
    def _extract_attack_ids(
        self,
        uer: UnifiedEventReport
    ) -> List[str]:
        """Extract MITRE ATT&CK IDs from UER"""
        attack_ids = []
        
        # Check protocol-specific attacks
        if uer.protocol_info.protocol_type == "MQTT":
            if uer.protocol_features.mqtt_command_type == "PUBLISH":
                attack_ids.append("T1041")  # Exfiltration over Other Network Protocol
        
        # Check anomaly flags
        if "high_entropy" in uer.edge_agent_anomaly_flags:
            attack_ids.append("T1001")  # Data Obfuscation
        
        return attack_ids

