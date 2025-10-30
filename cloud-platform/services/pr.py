"""
Policy & Response (PR): Map GC posterior to security actions.
"""
import json
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PolicyResponse:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.threshold_alert = cfg.get("pr", {}).get("thresholds", {}).get("alert", 0.6)
        self.threshold_action = cfg.get("pr", {}).get("thresholds", {}).get("action", 0.85)
        self.two_step = cfg.get("pr", {}).get("two_step_validation", True)

    def evaluate(self, gc_result: dict) -> Dict[str, any]:
        """
        Evaluate GC posterior and determine actions.
        
        Returns:
            {
                "action": "alert" | "isolate" | "monitor",
                "severity": "low" | "medium" | "high" | "critical",
                "posterior": float,
                "reason": str
            }
        """
        posterior = gc_result.get("posterior", 0.0)
        uncertainty = gc_result.get("uncertainty", 1.0)
        agents = gc_result.get("agents", [])

        # Determine action based on posterior
        if posterior >= self.threshold_action:
            action = "isolate" if not self.two_step else "alert"
            severity = "critical" if posterior > 0.9 else "high"
            reason = f"High posterior probability: {posterior:.2f}"
        elif posterior >= self.threshold_alert:
            action = "alert"
            severity = "medium" if posterior > 0.7 else "low"
            reason = f"Suspicious activity detected: {posterior:.2f}"
        else:
            action = "monitor"
            severity = "low"
            reason = f"Below alert threshold: {posterior:.2f}"

        # Calculate severity from uncertainty
        if uncertainty > 0.5 and posterior > self.threshold_alert:
            severity = "medium"  # Reduce severity if high uncertainty

        result = {
            "action": action,
            "severity": severity,
            "posterior": posterior,
            "uncertainty": uncertainty,
            "reason": reason,
            "agents": agents,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }

        return result

    def generate_alert(self, gc_result: dict, pr_result: dict, uer: dict) -> dict:
        """Generate structured alert."""
        alert = {
            "alert_id": f"alert-{int(time.time() * 1000)}",
            "ts": datetime.now(timezone.utc).isoformat() + "Z",
            "tenant": uer.get("tenant"),
            "site": uer.get("site"),
            "severity": pr_result["severity"],
            "action": pr_result["action"],
            "posterior": pr_result["posterior"],
            "agents": pr_result["agents"],
            "attck_hint": uer.get("attck_hint", []),
            "entities": uer.get("entities", []),
            "gc_explanation": gc_result.get("top_features", []),
        }
        return alert


if __name__ == "__main__":
    # Test PR
    cfg = {"pr": {"thresholds": {"alert": 0.6, "action": 0.85}, "two_step_validation": True}
    pr = PolicyResponse(cfg)

    gc_result = {
        "posterior": 0.82,
        "uncertainty": 0.15,
        "agents": ["MQTT", "HTTP"],
        "top_features": [{"name": "len_mean", "mean": 1500, "variance": 100}],
    }

    uer = {
        "tenant": "TENANT-12345",
        "site": "hq-taipei",
        "attck_hint": ["T1041"],
        "entities": ["device_id"],
    }

    pr_result = pr.evaluate(gc_result)
    alert = pr.generate_alert(gc_result, pr_result, uer)

    print(json.dumps(alert, indent=2))

