"""
Unified Event Record (UER) data structures and serialization.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import json


@dataclass
class Endpoint:
    ip: str
    device_id: Optional[str] = None
    port: Optional[int] = None

    def to_dict(self) -> dict:
        return {"ip": self.ip, "device_id": self.device_id, "port": self.port}


@dataclass
class Detector:
    score: float
    conf: float
    model: Optional[str] = None

    def to_dict(self) -> dict:
        return {"score": self.score, "conf": self.conf, "model": self.model}


@dataclass
class UER:
    ts: datetime
    src: Endpoint
    dst: Endpoint
    proto: str
    stats: Dict[str, float]
    detector: Detector
    entities: List[str] = field(default_factory=list)
    attck_hint: List[str] = field(default_factory=list)
    tenant: Optional[str] = None
    site: Optional[str] = None
    uid: Optional[str] = None
    late: bool = False

    def to_dict(self) -> dict:
        uer_dict = {
            "ts": self.ts.isoformat() + "Z",
            "src": self.src.to_dict(),
            "dst": self.dst.to_dict(),
            "proto": {"l7": self.proto.upper()},
            "stats": self.stats,
            "detector": self.detector.to_dict(),
            "entities": self.entities,
            "attck_hint": self.attck_hint,
        }
        if self.tenant:
            uer_dict["tenant"] = self.tenant
        if self.site:
            uer_dict["site"] = self.site
        if self.uid:
            uer_dict["uid"] = self.uid
        if self.late:
            uer_dict["late"] = self.late
        return uer_dict

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "UER":
        # Parse timestamp
        ts_str = data.get("ts", "")
        if isinstance(ts_str, str) and ts_str.endswith("Z"):
            ts_str = ts_str[:-1]
        ts = datetime.fromisoformat(ts_str)

        # Parse endpoints
        src_dict = data.get("src", {})
        src = Endpoint(
            ip=src_dict.get("ip"),
            device_id=src_dict.get("device_id"),
            port=src_dict.get("port"),
        )
        dst_dict = data.get("dst", {})
        dst = Endpoint(
            ip=dst_dict.get("ip"), port=dst_dict.get("port"), device_id=dst_dict.get("device_id")
        )

        # Parse proto
        proto_dict = data.get("proto", {})
        proto = proto_dict.get("l7", "UNKNOWN")

        # Parse detector
        det_dict = data.get("detector", {})
        detector = Detector(
            score=det_dict.get("score", 0.0),
            conf=det_dict.get("conf", 0.0),
            model=det_dict.get("model"),
        )

        return cls(
            ts=ts,
            src=src,
            dst=dst,
            proto=proto,
            stats=data.get("stats", {}),
            detector=detector,
            entities=data.get("entities", []),
            attck_hint=data.get("attck_hint", []),
            tenant=data.get("tenant"),
            site=data.get("site"),
            uid=data.get("uid"),
            late=data.get("late", False),
        )

