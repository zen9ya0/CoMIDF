"""
MQTT Protocol Agent: Monitor MQTT traffic and detect anomalies.
"""
import time
import random
from datetime import datetime, timezone
from typing import Dict
from agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)


class MQTTAgent(BaseAgent):
    def __init__(self, cfg: dict):
        super().__init__("mqtt", cfg)
        self.source = cfg.get("source", "tcp://127.0.0.1:1883")
        # In production, connect to MQTT broker

    def collect(self) -> Dict:
        """
        Collect MQTT packets/events.
        Returns raw feature dict with src_ip, dst_ip, topic, etc.
        """
        # Mock implementation
        # In production: parse MQTT packets
        features = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "src_ip": "192.168.1.10",
            "dst_ip": "10.0.0.100",
            "src_port": 54321,
            "dst_port": 1883,
            "device_id": f"device-{random.randint(1, 100)}",
            "features": {
                "len_mean": random.randint(50, 500),
                "iat_mean": random.uniform(1.0, 100.0),
                "pkt": random.randint(1, 10),
                "topic_pattern": "sensors/temperature",
            },
        }
        return features

    def detect(self, raw: Dict) -> Dict:
        """
        Detect MQTT anomalies using rules or ML model.
        """
        features = raw.get("features", {})

        # Simple rule-based detection
        score = 0.0
        conf = 0.85
        attck_hints = []

        # Check for suspicious patterns
        if features.get("len_mean", 0) > 1000:
            score = 0.7  # Large message size
            attck_hints.append("T1041")  # Data Exfiltration

        if features.get("iat_mean", 0) < 0.01:
            score = 0.8  # High frequency (potential DDoS)
            attck_hints.append("T1499")  # Endpoint Denial of Service

        # Add some randomness for demo
        score += random.uniform(0.0, 0.2)

        return {
            "score": min(score, 1.0),
            "conf": conf,
            "model": "mqtt-v1",
            "entities": ["device_id", "topic"],
            "attck_hint": attck_hints,
            "features": features,
        }

