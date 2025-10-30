"""
Feature Abstraction Layer (FAL): Normalize and anonymize protocol features.
"""
import hashlib
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.uer import UER, Endpoint, Detector


class FAL:
    def __init__(self, cfg: dict, connector):
        self.cfg = cfg
        self.connector = connector
        self.salt = cfg.get("privacy", {}).get("id_salt", "")

    def _anonymize(self, device_id: str) -> str:
        """Hash device ID with salt for privacy."""
        if not device_id:
            return ""
        return hashlib.sha256(f"{device_id}{self.salt}".encode()).hexdigest()

    def _generate_uid(self, ts: datetime, src: Endpoint, dst: Endpoint, model: str) -> str:
        """Generate unique ID for UER (idempotency)."""
        nonce = str(uuid.uuid4())
        content = f"{ts.isoformat()}{src.ip}{dst.ip}{model}{nonce}"
        return hashlib.sha256(content.encode()).hexdigest()

    def normalize(self, pa_name: str, raw: dict, det: dict) -> dict:
        """
        Normalize raw protocol features to UER format.
        
        Args:
            pa_name: Protocol agent name (e.g., 'mqtt', 'http')
            raw: Raw features from agent
            det: Detection results (score, conf, etc.)
        
        Returns:
            UER dict ready for uplink
        """
        # Build endpoints
        src = Endpoint(
            ip=raw.get("src_ip", "0.0.0.0"),
            device_id=raw.get("device_id"),
            port=raw.get("src_port"),
        )
        dst = Endpoint(
            ip=raw.get("dst_ip", "0.0.0.0"), port=raw.get("dst_port"), device_id=raw.get("dst_device_id")
        )

        # Anonymize device IDs
        if src.device_id:
            src.device_id = self._anonymize(src.device_id)
        if dst.device_id:
            dst.device_id = self._anonymize(dst.device_id)

        # Parse timestamp
        ts_str = raw.get("ts")
        if isinstance(ts_str, str):
            ts = datetime.fromisoformat(ts_str)
        elif isinstance(ts_str, datetime):
            ts = ts_str
        else:
            ts = datetime.now(timezone.utc)

        # Build UER
        model_name = det.get("model", f"{pa_name}-v1")
        uid = self._generate_uid(ts, src, dst, model_name)

        uer = {
            "uid": uid,
            "ts": ts.isoformat() + "Z",
            "src": src.to_dict(),
            "dst": dst.to_dict(),
            "proto": {"l7": pa_name.upper()},
            "stats": raw.get("features", {}),
            "detector": {
                "score": det.get("score", 0.0),
                "conf": det.get("conf", 0.0),
                "model": model_name,
            },
            "entities": det.get("entities", ["device_id"]),
            "attck_hint": det.get("attck_hint", []),
            "tenant": self.cfg.get("agent", {}).get("tenant_id"),
            "site": self.cfg.get("agent", {}).get("site"),
        }

        return uer

    def anonymize(self, uer: dict) -> dict:
        """Anonymize sensitive fields in UER."""
        # Additional anonymization if needed
        return uer

    def publish(self, uer: dict) -> None:
        """Publish UER via Secure Connector."""
        self.connector.send(uer)

