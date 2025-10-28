"""
Priority Reporter (PR) - Determines alert priority and reporting decisions
"""
from typing import Dict, List, Any, Optional
from datetime import datetime

from shared.config.constants import AlertPriority
from shared.models.uer_schema import UnifiedEventReport, CloudProcessingResult
from shared.utils.logger import get_logger

logger = get_logger(__name__, "priority_reporter.log")


class PriorityReporter:
    """Determines alert priority and reporting decisions"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.report_threshold = config.get('report_threshold', 0.7)
        self.high_priority_threshold = config.get('high_priority_threshold', 0.85)
        
    def calculate_priority(
        self,
        global_credibility: float,
        threat_indicators: List[Dict[str, Any]],
        ioc_matches: List[Dict[str, Any]]
    ) -> str:
        """
        Calculate alert priority based on multiple factors
        
        Returns: 'low', 'medium', 'high', or 'critical'
        """
        priority_score = 0.0
        
        # Factor 1: Global credibility
        priority_score += global_credibility * 0.4
        
        # Factor 2: Threat indicators
        if threat_indicators:
            max_indicator_confidence = max(
                [ti.get('confidence', 0.0) for ti in threat_indicators]
            )
            priority_score += max_indicator_confidence * 0.3
        
        # Factor 3: IOC matches
        if ioc_matches:
            ioc_weight = min(len(ioc_matches) * 0.1, 0.3)
            priority_score += ioc_weight
        
        # Determine priority level
        if priority_score >= 0.9:
            return AlertPriority.CRITICAL
        elif priority_score >= self.high_priority_threshold:
            return AlertPriority.HIGH
        elif priority_score >= self.report_threshold:
            return AlertPriority.MEDIUM
        else:
            return AlertPriority.LOW
    
    def should_report(
        self,
        priority: str,
        global_credibility: float
    ) -> bool:
        """Determine if alert should be reported"""
        # Always report critical and high priority
        if priority in [AlertPriority.CRITICAL, AlertPriority.HIGH]:
            return True
        
        # Report medium if credibility is high enough
        if priority == AlertPriority.MEDIUM and global_credibility > 0.75:
            return True
        
        # Don't report low priority
        return False
    
    def create_final_report(
        self,
        uer: UnifiedEventReport,
        gc_result: Dict[str, Any],
        threat_indicators: List[Dict[str, Any]],
        ioc_matches: List[Dict[str, Any]],
        threat_description: Optional[str]
    ) -> CloudProcessingResult:
        """Create final processing result with reporting decision"""
        
        # Calculate priority
        priority = self.calculate_priority(
            gc_result.get('global_credibility', 0.0),
            threat_indicators,
            ioc_matches
        )
        
        # Decide if should report
        should_report = self.should_report(
            priority,
            gc_result.get('global_credibility', 0.0)
        )
        
        # Create processing result
        result = CloudProcessingResult(
            original_uer=uer,
            global_credibility=gc_result.get('global_credibility', 0.0),
            global_plausibility=gc_result.get('plausibility', 0.0),
            threat_indicators=threat_indicators,
            agent_trust_score=gc_result.get('agent_trust', 0.5),
            recalibration_threshold=gc_result.get('recalibration_threshold', 0.5),
            cti_matches=ioc_matches,
            ioc_confidence=max([m.get('confidence', 0.0) for m in ioc_matches]) if ioc_matches else 0.0,
            threat_description_nl=threat_description,
            final_risk_score=gc_result.get('global_credibility', 0.0),
            alert_priority=priority.value,
            should_report=should_report
        )
        
        return result

