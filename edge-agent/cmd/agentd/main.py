"""
Edge Agent Daemon: Main entry point.
"""
import sys
import os
import yaml
import signal
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.fal import FAL
from core.connector import SecureConnector
from core.storage import SqliteBuffer
from core.feedback import FeedbackHandler
from agents.mqtt_agent import MQTTAgent
from agents.http_agent import HTTPAgent
from agents.coap_agent import CoAPAgent
from agents.zigbee_agent import ZigbeeAgent
from agents.quic_agent import QUICAgent
from agents.modbus_agent import ModbusAgent
from api.local_api import LocalAPI
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EdgeAgent:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
        self.running = False

        # Initialize core components
        self.buffer_store = SqliteBuffer(
            self.config.get("buffer", {}).get("path", "/var/lib/edge-agent/buffer.db")
        )
        self.connector = SecureConnector(self.config, self.buffer_store)
        self.fal = FAL(self.config, self.connector)
        self.feedback_handler = FeedbackHandler(self.config)
        self.feedback_handler.load_policies()

        # Initialize agents
        self.agents = []
        self._init_agents()

        # Metrics callback
        def get_metrics():
            return {
                "buffer_size": self.buffer_store.get_queue_size(),
                "dlq_size": self.buffer_store.get_dlq_size(),
            }

        # Initialize local API
        self.local_api = LocalAPI(
            self.config, self.buffer_store, self.feedback_handler, get_metrics
        )

        # Flush thread
        self.flush_thread = None

    def _load_config(self) -> dict:
        """Load configuration from YAML."""
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)

    def _init_agents(self):
        """Initialize protocol agents."""
        agents_cfg = self.config.get("agents", {})

        if agents_cfg.get("mqtt", {}).get("enabled", False):
            agent = MQTTAgent(agents_cfg.get("mqtt", {}))
            self.agents.append(agent)

        if agents_cfg.get("http", {}).get("enabled", False):
            agent = HTTPAgent(agents_cfg.get("http", {}))
            self.agents.append(agent)

        if agents_cfg.get("coap", {}).get("enabled", False):
            agent = CoAPAgent(agents_cfg.get("coap", {}))
            self.agents.append(agent)

        if agents_cfg.get("zigbee", {}).get("enabled", False):
            agent = ZigbeeAgent(agents_cfg.get("zigbee", {}))
            self.agents.append(agent)

        if agents_cfg.get("quic", {}).get("enabled", False):
            agent = QUICAgent(agents_cfg.get("quic", {}))
            self.agents.append(agent)

        if agents_cfg.get("modbus", {}).get("enabled", False):
            agent = ModbusAgent(agents_cfg.get("modbus", {}))
            self.agents.append(agent)

        logger.info(f"Initialized {len(self.agents)} agents")

    def start(self):
        """Start agent daemon."""
        if self.running:
            logger.warning("Agent already running")
            return

        self.running = True
        logger.info("Starting Edge Agent...")

        # Start agents
        for agent in self.agents:
            agent.start()

        # Start flush thread
        self._start_flush_thread()

        # Start local API
        api_thread = threading.Thread(
            target=lambda: self.local_api.run(port=self.config.get("metrics", {}).get("prometheus_port", 9108) + 198),
            daemon=True
        )
        api_thread.start()

        logger.info("Edge Agent started successfully")

    def stop(self):
        """Stop agent daemon."""
        if not self.running:
            return

        self.running = False
        logger.info("Stopping Edge Agent...")

        # Stop agents
        for agent in self.agents:
            agent.stop()

        # Stop flush thread
        if self.flush_thread:
            self.flush_thread.join(timeout=5)

        logger.info("Edge Agent stopped")

    def _start_flush_thread(self):
        """Start background thread to flush buffer."""

        def flush_loop():
            while self.running:
                try:
                    self.connector.flush_buffer()
                except Exception as e:
                    logger.error(f"Flush error: {e}")
                time.sleep(60)  # Flush every minute

        self.flush_thread = threading.Thread(target=flush_loop, daemon=True)
        self.flush_thread.start()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="CoMIDF Edge Agent")
    parser.add_argument(
        "--config", "-c", default="/etc/agent/agent.yaml", help="Config file path"
    )
    args = parser.parse_args()

    # Create agent
    agent = EdgeAgent(args.config)

    # Signal handlers
    def signal_handler(sig, frame):
        logger.info("Received signal, shutting down...")
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start agent
    try:
        agent.start()
        # Keep running
        while agent.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt, shutting down...")
    finally:
        agent.stop()


if __name__ == "__main__":
    main()

