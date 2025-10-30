"""
Active Feedback Loop (AFL) handler: Receive and apply policies from Cloud.
"""
import logging
from typing import Dict, Optional
import json

logger = logging.getLogger(__name__)


class FeedbackHandler:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.policies = {}  # agent_name -> policy
        self.policy_file = "/var/lib/edge-agent/policies.json"

    def apply_policy(self, policy: dict):
        """
        Apply AFL policy to local configuration.
        
        Policy format:
        {
            "agent": "mqtt",
            "thresholds": {"score_alert": 0.72},
            "sampling": {"rate": 0.8},
            "trust": {"w": 0.93, "decay": 0.9},
            "ts": "2025-10-28T02:00:00Z"
        }
        """
        agent_name = policy.get("agent")
        if not agent_name:
            logger.error("Policy missing 'agent' field")
            return False

        self.policies[agent_name] = policy
        self._persist_policy()

        # Update agent thresholds in config
        thresholds = policy.get("thresholds", {})
        if thresholds and "score_alert" in thresholds:
            logger.info(
                f"Updated {agent_name} threshold to {thresholds['score_alert']}"
            )

        return True

    def get_policy(self, agent_name: str) -> Optional[dict]:
        """Get current policy for agent."""
        return self.policies.get(agent_name)

    def get_threshold(self, agent_name: str) -> float:
        """Get alert threshold for agent."""
        policy = self.policies.get(agent_name)
        if policy and policy.get("thresholds", {}).get("score_alert") is not None:
            return policy["thresholds"]["score_alert"]

        # Fallback to config
        agent_cfg = self.cfg.get("agents", {}).get(agent_name, {})
        return agent_cfg.get("thresholds", {}).get("score_alert", 0.7)

    def _persist_policy(self):
        """Persist policies to disk."""
        try:
            with open(self.policy_file, "w") as f:
                json.dump(self.policies, f)
        except Exception as e:
            logger.error(f"Failed to persist policy: {e}")

    def load_policies(self):
        """Load policies from disk."""
        try:
            with open(self.policy_file, "r") as f:
                self.policies = json.load(f)
            logger.info(f"Loaded {len(self.policies)} policies")
        except FileNotFoundError:
            logger.info("No existing policies found")
        except Exception as e:
            logger.error(f"Failed to load policies: {e}")

