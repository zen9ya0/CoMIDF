"""
Modbus/TCP Protocol Agent: Monitor Industrial Control Systems (ICS).
"""
import time
import random
from datetime import datetime, timezone
from typing import Dict
from agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)


class ModbusAgent(BaseAgent):
    def __init__(self, cfg: dict):
        super().__init__("modbus", cfg)
        self.tcp_port = 502  # Modbus TCP standard port

    def collect(self) -> Dict:
        """
        Collect Modbus/TCP packets.
        Returns raw feature dict.
        """
        # Mock implementation
        # In production: parse Modbus TCP frames (Transaction ID, Unit ID, Function Code)
        features = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "src_ip": "192.168.1.50",
            "dst_ip": "192.168.1.100",
            "src_port": random.randint(30000, 60000),
            "dst_port": 502,
            "device_id": f"plc-unit-{random.randint(1, 10)}",
            "features": {
                "len_mean": random.randint(12, 256),
                "iat_mean": random.uniform(1.0, 100.0),
                "pkt": random.randint(1, 10),
                "function_code": random.choice([1, 2, 3, 4, 5, 6, 15, 16]),  # Read/Write coils/registers
                "unit_id": random.randint(1, 247),
                "transaction_id": random.randint(1, 65535),
                "start_address": random.randint(0, 65535),
                "quantity": random.randint(1, 2000),
            },
        }
        return features

    def detect(self, raw: Dict) -> Dict:
        """
        Detect Modbus anomalies.
        
        Anomalies:
        - Unauthorized register access
        - Suspicious function codes
        - Write operations to read-only areas
        - Excessive polling
        - Broadcast commands
        """
        features = raw.get("features", {})
        score = 0.0
        conf = 0.90  # Higher confidence for ICS protocols
        attck_hints = []

        function_code = features.get("function_code", 0)
        start_addr = features.get("start_address", 0)
        quantity = features.get("quantity", 0)
        unit_id = features.get("unit_id", 0)

        # Detect unauthorized write operations
        write_functions = [5, 6, 15, 16, 22, 23, 24]  # Write coil, register, etc.
        if function_code in write_functions:
            # Check if writing to critical addresses
            if 0 <= start_addr <= 65535:
                # Simulate checking against access control list
                score = 0.6
                attck_hints.append("T0880")  # IMPACT: Manipulation of Control
            else:
                score = 0.8
                attck_hints.append("T0881")  # IMPACT: Unauthorized Command Message

        # Detect broadcast commands (Unit ID 0)
        if unit_id == 0 and function_code in write_functions:
            score = max(score, 0.9)
            attck_hints.append("T0801")  # IMPACT: Loss of Safety

        # Detect excessive polling
        iat_mean = features.get("iat_mean", 0)
        if iat_mean < 0.01:  # Very high frequency
            score = max(score, 0.7)
            attck_hints.append("T0834")  # Impair Process Control

        # Detect unusual function codes
        suspicious_codes = [43, 90, 91, 92]  # Encapsulated interface, etc.
        if function_code in suspicious_codes:
            score = max(score, 0.8)
            attck_hints.append("T0868")  # IMPACT: Unauthorized Command Message

        # Detect large register reads (potential reconnaissance)
        if function_code in [3, 4] and quantity > 125:
            score = max(score, 0.6)
            attck_hints.append("T0874")  # Inhibit Response Function

        # Add some randomness
        score += random.uniform(0.0, 0.15)

        return {
            "score": min(score, 1.0),
            "conf": conf,
            "model": "modbus-v1",
            "entities": ["unit_id", "device_id"],
            "attck_hint": attck_hints,
            "features": features,
        }

