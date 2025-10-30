"""
Global Correlator (GC): Bayesian + Dempster-Shafer fusion engine.
"""
import json
import time
from collections import defaultdict
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class GlobalCorrelator:
    """
    Fusion engine using Bayesian inference and Dempster-Shafer theory.
    """

    def __init__(self, cfg: dict, kafka_consumer, kafka_producer):
        self.cfg = cfg
        self.consumer = kafka_consumer
        self.producer = kafka_producer
        self.window_size = cfg.get("gc", {}).get("window_size_sec", 5)
        self.trust_alpha = cfg.get("gc", {}).get("trust_alpha", 0.9)

        # Agent trust weights (dynamic)
        self.agent_trust = defaultdict(lambda: 0.7)

        # Time window buffer
        self.window_buffer = defaultdict(list)  # key -> list of UERs

    def fuse_evidences(self, evidence_list: List[dict]) -> dict:
        """
        Fuse multiple evidence using Bayesian multiplication.
        
        Args:
            evidence_list: List of UER dicts with detector.{score, conf}
        
        Returns:
            Posterior probability and uncertainty
        """
        if not evidence_list:
            return {"posterior": 0.0, "uncertainty": 1.0, "explanation": "no_evidence"}

        # Calculate weighted average with trust weights
        # P(H|E) = Σᵢ wᵢ * scoreᵢ / Σᵢ wᵢ
        total_weight = 0.0
        weighted_sum = 0.0
        confidences = []

        for uer in evidence_list:
            agent_name = uer.get("proto", {}).get("l7", "unknown").lower()
            trust = self.agent_trust[agent_name]

            det = uer.get("detector", {})
            score = det.get("score", 0.0)
            conf = det.get("conf", 0.0)

            # Weighted average
            weighted_sum += score * trust
            total_weight += trust
            confidences.append(conf)

        # Calculate posterior
        if total_weight > 0:
            posterior = weighted_sum / total_weight
        else:
            posterior = 0.0

        # Uncertainty from confidence spread
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        uncertainty = 1.0 - avg_conf

        # Build explanation
        agent_names = [uer.get("proto", {}).get("l7", "unknown") for uer in evidence_list]
        top_features = self._extract_top_features(evidence_list)

        return {
            "posterior": posterior,
            "uncertainty": uncertainty,
            "confidence": avg_conf,
            "agent_count": len(evidence_list),
            "agents": list(set(agent_names)),
            "top_features": top_features,
            "timestamp": time.time(),
        }

    def _extract_top_features(self, evidence_list: List[dict]) -> List[dict]:
        """Extract most significant features for explanation."""
        features = defaultdict(list)

        for uer in evidence_list:
            stats = uer.get("stats", {})
            for key, value in stats.items():
                features[key].append(value)

        # Calculate variance/anomaly for each feature
        top_features = []
        for key, values in features.items():
            if len(values) > 1:
                mean_val = sum(values) / len(values)
                variance = sum((v - mean_val) ** 2 for v in values) / len(values)
                top_features.append({"name": key, "mean": mean_val, "variance": variance})

        # Sort by variance
        top_features.sort(key=lambda x: x.get("variance", 0), reverse=True)
        return top_features[:5]

    def update_trust(self, agent_name: str, accuracy: float):
        """
        Update agent trust weight.
        w_i^(t+1) = α * w_i^(t) + (1-α) * Acc_i
        """
        old_trust = self.agent_trust[agent_name]
        self.agent_trust[agent_name] = (
            self.trust_alpha * old_trust + (1 - self.trust_alpha) * accuracy
        )
        logger.info(
            f"Agent {agent_name} trust: {old_trust:.3f} -> {self.agent_trust[agent_name]:.3f} (acc={accuracy:.3f})"
        )

    def correlate_window(self, window_key: str, uers: List[dict]) -> dict:
        """Correlate UERs within a time window."""
        if not uers:
            return {}

        # Group by agent
        agents = defaultdict(list)
        for uer in uers:
            agent_name = uer.get("proto", {}).get("l7", "unknown").lower()
            agents[agent_name].append(uer)

        # Fuse evidences
        result = self.fuse_evidences(uers)

        # Add metadata
        result["window_key"] = window_key
        result["window_size"] = len(uers)
        result["detected_agents"] = list(agents.keys())

        return result


# Mock Kafka consumer/producer
class MockConsumer:
    def __init__(self, topic: str):
        self.topic = topic

    def poll(self):
        return None


class MockProducer:
    def send(self, topic: str, value: str):
        logger.info(f"Produced to {topic}: {value[:100]}")


if __name__ == "__main__":
    # Test fusion
    cfg = {"gc": {"window_size_sec": 5, "trust_alpha": 0.9}}
    consumer = MockConsumer("test")
    producer = MockProducer()

    gc = GlobalCorrelator(cfg, consumer, producer)

    # Sample UERs
    evidence = [
        {
            "proto": {"l7": "MQTT"},
            "detector": {"score": 0.78, "conf": 0.86},
            "stats": {"len_mean": 142, "iat_mean": 22},
        },
        {
            "proto": {"l7": "HTTP"},
            "detector": {"score": 0.65, "conf": 0.90},
            "stats": {"len_mean": 1500},
        },
    ]

    result = gc.fuse_evidences(evidence)
    print(json.dumps(result, indent=2))

