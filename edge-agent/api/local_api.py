"""
Local REST API for Edge Agent (health, metrics, config, feedback).
"""
import json
import logging
from typing import Dict
from flask import Flask, jsonify, request
import threading
import time

logger = logging.getLogger(__name__)

app = Flask(__name__)


class LocalAPI:
    def __init__(self, config: dict, buffer_store, feedback_handler, metrics_func):
        self.config = config
        self.buffer_store = buffer_store
        self.feedback_handler = feedback_handler
        self.metrics_func = metrics_func
        self.start_time = time.time()

        # Register routes
        @app.route("/health", methods=["GET"])
        def health():
            return self._get_health()

        @app.route("/metrics", methods=["GET"])
        def metrics():
            return self._get_metrics()

        @app.route("/config", methods=["GET"])
        def config():
            return self._get_config()

        @app.route("/feedback", methods=["POST"])
        def feedback():
            return self._post_feedback()

    def run(self, host="127.0.0.1", port=8600, debug=False):
        """Run Flask API server."""
        logger.info(f"Starting local API on {host}:{port}")
        app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)

    def _get_health(self):
        """GET /health - Agent health status."""
        queue_size = self.buffer_store.get_queue_size()
        dlq_size = self.buffer_store.get_dlq_size()
        uptime = int(time.time() - self.start_time)

        return jsonify(
            {
                "status": "ok",
                "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "uptime_sec": uptime,
                "queues": {"buffer": queue_size, "dlq": dlq_size},
            }
        )

    def _get_metrics(self):
        """GET /metrics - Prometheus metrics."""
        queue_size = self.buffer_store.get_queue_size()
        dlq_size = self.buffer_store.get_dlq_size()

        # Simple text format for Prometheus
        metrics_text = f"""# HELP agent_buffer_pending Number of UERs pending in buffer
# TYPE agent_buffer_pending gauge
agent_buffer_pending {queue_size}

# HELP agent_dlq_size Number of UERs in dead letter queue
# TYPE agent_dlq_size gauge
agent_dlq_size {dlq_size}

# HELP agent_uptime_seconds Uptime in seconds
# TYPE agent_uptime_seconds gauge
agent_uptime_seconds {int(time.time() - self.start_time)}
"""

        return metrics_text, 200, {"Content-Type": "text/plain; version=0.0.4"}

    def _get_config(self):
        """GET /config - Current agent configuration."""
        # Return non-sensitive config
        safe_config = {
            "agent_id": self.config.get("agent", {}).get("id"),
            "tenant_id": self.config.get("agent", {}).get("tenant_id"),
            "site": self.config.get("agent", {}).get("site"),
            "agents": {
                name: {"enabled": cfg.get("enabled", False)}
                for name, cfg in self.config.get("agents", {}).items()
            },
        }
        return jsonify(safe_config)

    def _post_feedback(self):
        """POST /feedback - Apply AFL policy from Cloud."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No JSON data"}), 400

            success = self.feedback_handler.apply_policy(data)
            if success:
                return jsonify({"status": "applied", "policy": data}), 200
            else:
                return jsonify({"error": "Invalid policy"}), 400

        except Exception as e:
            logger.error(f"Feedback error: {e}")
            return jsonify({"error": str(e)}), 500

