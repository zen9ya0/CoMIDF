"""
Base class for Protocol Agents (PA).
"""
import time
import threading
from abc import ABC, abstractmethod
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, name: str, cfg: dict):
        self.name = name
        self.cfg = cfg
        self.enabled = cfg.get("enabled", False)
        self.threshold = cfg.get("thresholds", {}).get("score_alert", 0.7)
        self.running = False
        self.thread: Optional[threading.Thread] = None

    @abstractmethod
    def collect(self) -> Dict:
        """Collect raw data/features from protocol stream."""
        pass

    @abstractmethod
    def detect(self, raw: Dict) -> Dict:
        """
        Detect anomalies and return detection results.
        
        Returns:
            {
                "score": float,      # 0.0 - 1.0, suspiciousness
                "conf": float,        # 0.0 - 1.0, model confidence
                "model": str,         # Model name
                "entities": List[str], # Relevant entities
                "attck_hint": List[str], # MITRE ATT&CK techniques
                "features": Dict      # Additional features
            }
        """
        pass

    def start(self):
        """Start agent in background thread."""
        if not self.enabled:
            logger.info(f"{self.name} agent is disabled")
            return

        if self.running:
            logger.warning(f"{self.name} agent is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info(f"{self.name} agent started")

    def stop(self):
        """Stop agent."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info(f"{self.name} agent stopped")

    def _run_loop(self):
        """Main collection and detection loop."""
        logger.info(f"{self.name} agent loop started")
        while self.running:
            try:
                raw = self.collect()
                if raw:
                    det = self.detect(raw)
                    # Only report if score exceeds threshold
                    if det.get("score", 0.0) >= self.threshold:
                        logger.info(
                            f"{self.name} detected: score={det['score']:.2f}, conf={det['conf']:.2f}"
                        )
                    else:
                        logger.debug(f"{self.name} normal: score={det['score']:.2f}")
            except Exception as e:
                logger.error(f"{self.name} error in loop: {e}")
            time.sleep(0.1)  # Small delay to avoid tight loop

    def set_threshold(self, value: float):
        """Update alert threshold dynamically."""
        old = self.threshold
        self.threshold = value
        logger.info(f"{self.name} threshold: {old:.2f} -> {value:.2f}")

