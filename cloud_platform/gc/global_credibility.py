"""
Global Credibility (GC) - Bayesian + Dempster-Shafer fusion for trust evaluation
"""
from typing import Dict, List, Any, Optional
import numpy as np

from shared.models.uer_schema import UnifiedEventReport, CloudProcessingResult
from shared.config.constants import BAYESIAN_PRIOR, DEMPSTER_CONFLICT_THRESHOLD
from shared.utils.logger import get_logger

logger = get_logger(__name__, "global_credibility.log")


class BayesianFusion:
    """Bayesian fusion for combining multiple evidence sources"""
    
    def __init__(self, prior: float = BAYESIAN_PRIOR):
        self.prior = prior
    
    def calculate_posterior(self, likelihood: float, prior: Optional[float] = None) -> float:
        """Calculate Bayesian posterior probability"""
        if prior is None:
            prior = self.prior
        
        # Simplified Bayesian update
        posterior = (likelihood * prior) / (
            (likelihood * prior) + ((1 - likelihood) * (1 - prior))
        )
        
        return posterior
    
    def update_credibility(
        self,
        current_credibility: float,
        new_evidence: float
    ) -> float:
        """Update credibility score with new evidence"""
        return self.calculate_posterior(new_evidence, current_credibility)


class DempsterShaferFusion:
    """Dempster-Shafer theory for uncertainty management"""
    
    def __init__(self, conflict_threshold: float = DEMPSTER_CONFLICT_THRESHOLD):
        self.conflict_threshold = conflict_threshold
    
    def calculate_belief_and_plausibility(
        self,
        evidences: List[Dict[str, float]]
    ) -> tuple[float, float]:
        """
        Calculate belief (lower bound) and plausibility (upper bound)
        """
        if not evidences:
            return 0.0, 1.0
        
        # Extract mass functions (simplified)
        mass_belief = []
        mass_plausibility = []
        
        for evidence in evidences:
            belief = evidence.get('belief', 0.0)
            plausibility = evidence.get('plausibility', 1.0)
            mass_belief.append(belief)
            mass_plausibility.append(plausibility)
        
        # Dempster's combination rule (simplified)
        if not mass_belief:
            return 0.0, 1.0
        
        # Calculate combined belief (minimum aggregation)
        combined_belief = min(mass_belief) if mass_belief else 0.0
        
        # Calculate combined plausibility (maximum aggregation)
        combined_plausibility = max(mass_plausibility) if mass_plausibility else 1.0
        
        # Detect conflict
        conflict = sum(1 for e in evidences if e.get('confidence', 0.0) < self.conflict_threshold)
        if conflict > len(evidences) / 2:
            logger.warning(f"High conflict detected in evidence: {conflict}/{len(evidences)}")
        
        return combined_belief, combined_plausibility


class GlobalCredibility:
    """Global Credibility module for trust-based fusion"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.bayesian_fusion = BayesianFusion(prior=BAYESIAN_PRIOR)
        self.ds_fusion = DempsterShaferFusion(
            conflict_threshold=DEMPSTER_CONFLICT_THRESHOLD
        )
        
        # Agent trust scores
        self.agent_trust_scores: Dict[str, float] = {}
        self.agent_accuracy_history: Dict[str, List[float]] = {}
        
    def get_agent_trust_score(self, agent_id: str) -> float:
        """Get current trust score for an agent"""
        return self.agent_trust_scores.get(agent_id, 0.5)  # Default 0.5
    
    def update_agent_trust(
        self,
        agent_id: str,
        accuracy: float
    ):
        """Update agent trust score based on accuracy"""
        # Track accuracy history
        if agent_id not in self.agent_accuracy_history:
            self.agent_accuracy_history[agent_id] = []
        
        self.agent_accuracy_history[agent_id].append(accuracy)
        
        # Keep only recent history (last 100)
        if len(self.agent_accuracy_history[agent_id]) > 100:
            self.agent_accuracy_history[agent_id] = self.agent_accuracy_history[agent_id][-100:]
        
        # Calculate weighted trust
        history = self.agent_accuracy_history[agent_id]
        current_trust = self.agent_trust_scores.get(agent_id, 0.5)
        
        # Update trust: w(t+1) = α * w(t) + (1-α) * acc
        alpha = 0.7
        new_trust = alpha * current_trust + (1 - alpha) * np.mean(history[-10:])
        
        self.agent_trust_scores[agent_id] = new_trust
        logger.debug(f"Updated trust for agent {agent_id}: {new_trust:.3f}")
    
    async def process_uer(self, uer: UnifiedEventReport) -> Dict[str, Any]:
        """
        Process UER through Global Credibility analysis
        """
        logger.info(f"Processing UER {uer.event_id} through Global Credibility")
        
        # Get agent trust score
        agent_trust = self.get_agent_trust_score(uer.agent_id)
        
        # Prepare evidence from UER
        evidences = []
        
        # Edge agent risk score as evidence
        evidences.append({
            'source': 'edge_agent',
            'belief': uer.edge_agent_risk_score * agent_trust,
            'plausibility': uer.edge_agent_risk_score,
            'confidence': agent_trust
        })
        
        # Flow features as evidence
        entropy_evidence = min(uer.flow_features.entropy / 8.0, 1.0)  # Normalize to [0, 1]
        evidences.append({
            'source': 'flow_entropy',
            'belief': entropy_evidence * 0.8,
            'plausibility': entropy_evidence,
            'confidence': 0.8
        })
        
        # Perform Dempster-Shafer fusion
        belief, plausibility = self.ds_fusion.calculate_belief_and_plausibility(evidences)
        
        # Perform Bayesian fusion
        posterior = self.bayesian_fusion.calculate_posterior(belief)
        
        logger.debug(
            f"UER {uer.event_id}: belief={belief:.3f}, "
            f"plausibility={plausibility:.3f}, posterior={posterior:.3f}"
        )
        
        return {
            'global_credibility': posterior,
            'belief': belief,
            'plausibility': plausibility,
            'agent_trust': agent_trust,
            'evidence_count': len(evidences)
        }

