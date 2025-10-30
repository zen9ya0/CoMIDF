"""
CoAP Protocol Agent: Monitor CoAP (IoT) traffic.
"""
import time
import random
from datetime import datetime, timezone
from typing import Dict
from agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)


class CoAPAgent(BaseAgent):
    def __init__(self, cfg: dict):
        super().__init__("coap", cfg)

    def collect(self) -> Dict:
        """Collect CoAP packets."""
        features = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "src_ip": "192.168.1.20",
            "dst_ip": "10.0.0.50",
            "src_port": random.randint(50000, 55000),
            "dst_port": 5683,
            "device_id": f"coap-device-{random.randint(1, 50)}",
            "features": {
                "len_mean": random.randint(20, 200),
                "iat_mean": random.uniform(1.0, 30.0),
                "pkt": random.randint(1, 5),
                "coap_code": random.choice(["GET", "POST"]),
            },
        }
        return features

    def detect(self, raw: Dict) -> Dict:
        """Detect CoAP anomalies."""
        features = raw.get("features", {})
        score = 0.0
        conf = 0.80
        attck_hints = []

        if features.get("len_mean", 0) > 500:
            score = 0.6  # Unusually large CoAP messages

        if features.get("iat_mean", 0) < 0.1:
            score = 0.7  # High frequency

        score += random.uniform(0.0, 0.2)

        return {
            "score": min(score, 1.0),
            "conf": conf,
            "model": "coap-v1",
            "entities": ["device_id"],
            "attck_hint": attck_hints,
            "features": features,
        }

