"""
Active Feedback Loop (AFL) - Adaptive learning and recalibration
"""
from typing import Dict, List, Any, Optional
from collections import deque
from datetime import datetime
import statistics

from shared.config.constants import DEFAULT_TRUST_ALPHA, DEFAULT_RECALIBRATION_UPDATE_RATE
from shared.utils.logger import get_logger

logger = get_logger(__name__, "active_feedback_loop.log")


class ActiveFeedbackLoop:
    """Adaptive learning and recalibration system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Trust parameters
        self.trust_alpha = config.get('trust_alpha', DEFAULT_TRUST_ALPHA)
        
        # Recalibration parameters
        self.recalibration_rate = config.get('recalibration_rate', DEFAULT_RECALIBRATION_UPDATE_RATE)
        
        # Agent performance tracking
        self.agent_performance: Dict[str, deque] = {}  # {agent_id: [accuracy1, accuracy2, ...]}
        self.agent_thresholds: Dict[str, float] = {}  # Dynamic thresholds
        
        # Feedback history
        self.feedback_history: List[Dict[str, Any]] = []
    
    def update_agent_performance(
        self,
        agent_id: str,
        true_positive: bool,
        false_positive: bool,
        true_negative: bool,
        false_negative: bool
    ):
        """Update agent performance metrics"""
        if agent_id not in self.agent_performance:
            self.agent_performance[agent_id] = deque(maxlen=100)
        
        # Calculate accuracy
        total = true_positive + false_positive + true_negative + false_negative
        if total > 0:
            accuracy = (true_positive + true_negative) / total
            self.agent_performance[agent_id].append(accuracy)
            
            logger.debug(
                f"Updated agent {agent_id} accuracy: {accuracy:.3f} "
                f"(TP:{true_positive}, FP:{false_positive}, TN:{true_negative}, FN:{false_negative})"
            )
            
            # Recalibrate threshold
            self._recalibrate_agent_threshold(agent_id)
    
    def _recalibrate_agent_threshold(self, agent_id: str):
        """Recalibrate agent threshold based on performance"""
        if agent_id not in self.agent_performance or len(self.agent_performance[agent_id]) < 10:
            return
        
        accuracies = list(self.agent_performance[agent_id])
        mean_accuracy = statistics.mean(accuracies)
        
        # Current threshold
        current_threshold = self.agent_thresholds.get(agent_id, 0.7)
        
        # Adaptive threshold adjustment
        if mean_accuracy < 0.6:
            # Poor performance: increase threshold (reduce false positives)
            new_threshold = current_threshold + self.recalibration_rate
        elif mean_accuracy > 0.9:
            # Excellent performance: decrease threshold (catch more)
            new_threshold = current_threshold - self.recalibration_rate
        else:
            # Maintain current threshold
            new_threshold = current_threshold
        
        # Keep threshold in reasonable range
        new_threshold = max(0.3, min(0.95, new_threshold))
        
        self.agent_thresholds[agent_id] = new_threshold
        
        logger.info(
            f"Recalibrated agent {agent_id}: threshold {current_threshold:.3f} -> {new_threshold:.3f} "
            f"(mean accuracy: {mean_accuracy:.3f})"
        )
    
    def get_agent_threshold(self, agent_id: str) -> float:
        """Get current threshold for agent"""
        return self.agent_thresholds.get(agent_id, 0.7)  # Default 0.7
    
    def calculate_adaptive_weight(
        self,
        agent_id: str,
        base_weight: float
    ) -> float:
        """Calculate adaptive weight for agent based on performance"""
        if agent_id not in self.agent_performance or len(self.agent_performance[agent_id]) < 5:
            return base_weight
        
        accuracies = list(self.agent_performance[agent_id])
        mean_accuracy = statistics.mean(accuracies)
        
        # Adjust weight based on performance
        # w_i(t+1) = α * w_i(t) + (1-α) * acc_i
        adaptive_weight = self.trust_alpha * base_weight + (1 - self.trust_alpha) * mean_accuracy
        
        return adaptive_weight
    
    def record_feedback(
        self,
        event_id: str,
        agent_id: str,
        predicted_risk: float,
        actual_risk: Optional[float],
        is_threat: Optional[bool]
    ):
        """Record feedback for learning"""
        feedback = {
            'event_id': event_id,
            'agent_id': agent_id,
            'predicted_risk': predicted_risk,
            'actual_risk': actual_risk,
            'is_threat': is_threat,
            'timestamp': datetime.now()
        }
        
        self.feedback_history.append(feedback)
        
        # Keep only recent history
        if len(self.feedback_history) > 1000:
            self.feedback_history = self.feedback_history[-1000:]
        
        logger.debug(f"Recorded feedback for event {event_id}")

