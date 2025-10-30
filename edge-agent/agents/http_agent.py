"""
HTTP/TLS Protocol Agent: Monitor HTTP(S) traffic and detect anomalies.
"""
import time
import random
from datetime import datetime, timezone
from typing import Dict
from agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)


class HTTPAgent(BaseAgent):
    def __init__(self, cfg: dict):
        super().__init__("http", cfg)
        self.pcap = cfg.get("pcap", "/dev/net/tap0")
        # In production, use pcap or wiretap

    def collect(self) -> Dict:
        """
        Collect HTTP/TLS packets.
        Returns raw feature dict.
        """
        # Mock implementation
        features = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "src_ip": "192.168.1.5",
            "dst_ip": "203.0.113.10",
            "src_port": random.randint(30000, 60000),
            "dst_port": 443,
            "features": {
                "len_mean": random.randint(500, 3000),
                "iat_mean": random.uniform(0.1, 5.0),
                "pkt": random.randint(3, 20),
                "http_method": random.choice(["GET", "POST", "PUT"]),
                "status_code": random.choice([200, 404, 500]),
            },
        }
        return features

    def detect(self, raw: Dict) -> Dict:
        """
        Detect HTTP/TLS anomalies.
        """
        features = raw.get("features", {})
        score = 0.0
        conf = 0.90
        attck_hints = []

        # Detect suspicious patterns
        if features.get("status_code") == 500:
            score = 0.6  # Server errors

        if features.get("http_method") == "POST" and features.get("len_mean", 0) > 5000:
            score = 0.75  # Large POST requests
            attck_hints.append("T1041")  # Data Exfiltration

        if features.get("status_code") == 404:
            score = 0.4  # Possible scanning

        # Add some randomness
        score += random.uniform(0.0, 0.15)

        return {
            "score": min(score, 1.0),
            "conf": conf,
            "model": "http-v1",
            "entities": ["hostname"],
            "attck_hint": attck_hints,
            "features": features,
        }

