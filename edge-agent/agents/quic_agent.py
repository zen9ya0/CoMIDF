"""
QUIC Protocol Agent: Monitor QUIC (HTTP/3) traffic.
"""
import time
import random
from datetime import datetime, timezone
from typing import Dict
from agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)


class QUICAgent(BaseAgent):
    def __init__(self, cfg: dict):
        super().__init__("quic", cfg)
        self.port = 443  # QUIC typically uses UDP 443

    def collect(self) -> Dict:
        """
        Collect QUIC packets.
        Returns raw feature dict.
        """
        # Mock implementation
        # In production: parse QUIC packets (Connection ID, Stream ID, etc.)
        features = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "src_ip": "192.168.1.5",
            "dst_ip": "2001:db8::1",
            "src_port": random.randint(30000, 60000),
            "dst_port": 443,
            "features": {
                "len_mean": random.randint(100, 1200),
                "iat_mean": random.uniform(0.01, 0.5),
                "pkt": random.randint(3, 30),
                "connection_id_len": random.choice([4, 8]),
                "stream_id": random.randint(0, 100),
                "retry_token": random.choice([True, False]),
                "packet_type": random.choice(["Initial", "Handshake", "Protected"]),
                "version": random.choice(["0x00000001", "draft-29", "draft-30"]),
            },
        }
        return features

    def detect(self, raw: Dict) -> Dict:
        """
        Detect QUIC anomalies.
        
        Anomalies:
        - Version downgrade attacks
        - Amplification attacks
        - Reset stream abuse
        - Unusual connection patterns
        """
        features = raw.get("features", {})
        score = 0.0
        conf = 0.85
        attck_hints = []

        # Detect version downgrade (older QUIC versions)
        version = features.get("version", "")
        if version not in ["draft-29", "draft-30", "HTTP/3"]:
            score = 0.7
            attck_hints.append("T1562.004")  # Impair Defenses: Disable or Modify System Firewall

        # Detect excessive reset streams
        pkt_count = features.get("pkt", 0)
        stream_id = features.get("stream_id", 0)
        if pkt_count > 50 and stream_id > 100:
            score = max(score, 0.8)
            attck_hints.append("T1498")  # Denial of Service

        # Detect unusual initial packet patterns
        packet_type = features.get("packet_type", "")
        if packet_type == "Initial" and pkt_count < 2:
            score = max(score, 0.6)
            attck_hints.append("T1046")  # Network Service Scanning

        # High frequency QUIC packets
        if features.get("iat_mean", 0) < 0.001:
            score = max(score, 0.75)
            attck_hints.append("T1499")  # Endpoint Denial of Service

        # Add some randomness
        score += random.uniform(0.0, 0.2)

        return {
            "score": min(score, 1.0),
            "conf": conf,
            "model": "quic-v1",
            "entities": ["connection_id", "stream_id"],
            "attck_hint": attck_hints,
            "features": features,
        }

