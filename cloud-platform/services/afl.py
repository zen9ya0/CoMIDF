"""
Active Feedback Loop (AFL): Generate and push policies to Edge Agents.
"""
import json
import time
from collections import defaultdict
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class ActiveFeedbackLoop:
    def __init__(self, cfg: dict, kafka_consumer, kafka_producer):
        self.cfg = cfg
        self.consumer = kafka_consumer
        self.producer = kafka_producer
        self.update_interval = cfg.get("afl", {}).get("update_interval_sec", 300)
        self.precision_window = cfg.get("afl", {}).get("precision_window", 1000)

        # Per-agent statistics
        self.agent_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        self.agent_precision = defaultdict(float)

    def calculate_precision(self, agent_name: str) -> float:
        """Calculate agent precision from recent performance."""
        stats = self.agent_stats[agent_name]
        tp, fp = stats.get("tp", 0), stats.get("fp", 0)

        if tp + fp == 0:
            return 0.5  # Default

        precision = tp / (tp + fp)
        self.agent_precision[agent_name] = precision
        return precision

    def generate_policy(self, agent_name: str, performance: dict) -> dict:
        """
        Generate AFL policy for agent.
        
        Policy format:
        {
            "agent": str,
            "thresholds": {"score_alert": float},
            "sampling": {"rate": float},
            "trust": {"w": float, "decay": float},
            "ts": datetime string
        }
        """
        precision = performance.get("precision", 0.5)
        recall = performance.get("recall", 0.5)

        # Adjust threshold based on performance
        # Better precision -> lower threshold (detect more)
        # Better recall -> higher threshold (reduce false positives)
        base_threshold = 0.7
        threshold = base_threshold - (precision - 0.5) * 0.3 + (recall - 0.5) * 0.2
        threshold = max(0.5, min(0.9, threshold))

        # Sampling rate based on load
        load = performance.get("load", 0.5)
        sampling_rate = 1.0 - (load - 0.5) * 0.3
        sampling_rate = max(0.5, min(1.0, sampling_rate))

        # Trust weight based on precision
        trust_w = 0.5 + precision * 0.4
        trust_decay = 0.9

        policy = {
            "agent": agent_name,
            "thresholds": {"score_alert": round(threshold, 2)},
            "sampling": {"rate": round(sampling_rate, 2)},
            "trust": {"w": round(trust_w, 2), "decay": round(trust_decay, 2)},
            "ts": datetime.now(timezone.utc).isoformat() + "Z",
            "schema": "afl-v1.1",
        }

        logger.info(f"Generated policy for {agent_name}: threshold={threshold:.2f}, trust={trust_w:.2f}")
        return policy

    def push_policy(self, tenant_id: str, policy: dict):
        """Push policy to Edge Agent via Kafka."""
        topic = f"afl.feedback.{tenant_id}"
        payload = {
            "agent": policy["agent"],
            "policy": policy,
        }
        self.producer.send(topic, key=policy["agent"], value=json.dumps(payload))
        logger.info(f"Pushed policy to {topic} for agent {policy['agent']}")

    def pull_policy(self, tenant_id: str, agent_name: str) -> Optional[dict]:
        """Pull policy for agent (Edge can query this)."""
        # In production, fetch from policy store
        performance = {
            "precision": self.agent_precision.get(agent_name, 0.5),
            "recall": 0.7,  # Mock
            "load": 0.5,
        }
        return self.generate_policy(agent_name, performance)

    def update_stats(self, agent_name: str, outcome: str, ground_truth: str):
        """
        Update agent statistics.
        outcome: "alert" | "normal"
        ground_truth: "attack" | "normal"
        """
        stats = self.agent_stats[agent_name]

        if ground_truth == "attack":
            if outcome == "alert":
                stats["tp"] += 1
            else:
                stats["fn"] += 1
        else:
            if outcome == "alert":
                stats["fp"] += 1
            else:
                stats["tn"] += 1

        # Recalculate precision
        self.calculate_precision(agent_name)


# Mock Kafka
class MockProducer:
    def send(self, topic: str, key: str, value: str):
        logger.info(f"Produced to {topic}: {key} <- {value}")


class MockConsumer:
    def __init__(self, topic: str):
        self.topic = topic


if __name__ == "__main__":
    cfg = {"afl": {"update_interval_sec": 300, "precision_window": 1000}}
    consumer = MockConsumer("test")
    producer = MockProducer()

    afl = ActiveFeedbackLoop(cfg, consumer, producer)

    # Simulate some stats
    afl.update_stats("mqtt", "alert", "attack")  # TP
    afl.update_stats("mqtt", "alert", "normal")  # FP
    afl.update_stats("mqtt", "normal", "normal")  # TN

    # Generate policy
    performance = afl.generate_policy("mqtt", {"precision": 0.75, "recall": 0.8, "load": 0.6})
    print(json.dumps(performance, indent=2))

