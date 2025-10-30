"""
Cloud Ingress: Receive UER events from Edge Agents.
"""
import os
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from flask import Flask, request, jsonify, Response
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)


class IngressService:
    def __init__(self, kafka_producer, redis_client):
        self.producer = kafka_producer
        self.redis = redis_client
        self.idempotency_ttl = 86400  # 24 hours

        @app.route("/api/fal/uer", methods=["POST"])
        def ingest_uer():
            return self._ingest_single()

        @app.route("/api/fal/uer/_bulk", methods=["POST"])
        def ingest_bulk():
            return self._ingest_bulk()

        @app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok"})

    def _get_tenant_id(self) -> str:
        """Extract tenant ID from header."""
        return request.headers.get("X-Tenant-ID", "")

    def _get_agent_id(self) -> str:
        """Extract agent ID from header."""
        return request.headers.get("X-Agent-ID", "")

    def _get_schema_version(self) -> str:
        """Extract schema version from header."""
        return request.headers.get("X-Schema-Version", "uer-v1")

    def _is_idempotent(self, uer: dict) -> bool:
        """Check if UER is duplicate using uid."""
        uid = uer.get("uid")
        if not uid:
            return False

        # Check Redis
        exists = self.redis.get(f"uid:{uid}")
        if exists:
            return True

        # Set idempotency key
        self.redis.setex(f"uid:{uid}", self.idempotency_ttl, "1")
        return False

    def _is_late(self, ts_str: str) -> bool:
        """Check if event is late (> 24h old)."""
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age = now - ts
            return age > timedelta(hours=24)
        except:
            return False

    def _validate_uer(self, uer: dict) -> tuple[bool, Optional[str]]:
        """Validate UER structure."""
        required_fields = ["ts", "src", "dst", "proto", "detector"]
        for field in required_fields:
            if field not in uer:
                return False, f"Missing required field: {field}"

        if not uer.get("detector", {}).get("score") is not None:
            return False, "Missing detector.score"

        if not uer.get("detector", {}).get("conf") is not None:
            return False, "Missing detector.conf"

        return True, None

    def _ingest_single(self) -> Response:
        """Ingest single UER."""
        try:
            # Validate headers
            tenant_id = self._get_tenant_id()
            agent_id = self._get_agent_id()

            if not tenant_id or not agent_id:
                return jsonify({"error": "Missing X-Tenant-ID or X-Agent-ID"}), 400

            # Parse UER
            uer = request.get_json()
            if not uer:
                return jsonify({"error": "No JSON body"}), 400

            # Add metadata
            uer["tenant"] = tenant_id
            uer["agent_id"] = agent_id
            uer["ingress_ts"] = datetime.now(timezone.utc).isoformat() + "Z"

            # Check if late
            ts = uer.get("ts", "")
            if self._is_late(ts):
                uer["late"] = True

            # Validate
            valid, error = self._validate_uer(uer)
            if not valid:
                return jsonify({"error": error}), 400

            # Check idempotency
            if self._is_idempotent(uer):
                return jsonify({"status": "duplicate", "uid": uer.get("uid")}), 200

            # Send to Kafka
            topic = f"uer.ingest.{tenant_id}"
            self.producer.send(topic, key=uer.get("uid"), value=json.dumps(uer))

            return jsonify({"status": "ingested", "uid": uer.get("uid")}), 200

        except Exception as e:
            logger.error(f"Ingest error: {e}")
            return jsonify({"error": str(e)}), 500

    def _ingest_bulk(self) -> Response:
        """Ingest multiple UERs (NDJSON format)."""
        try:
            tenant_id = self._get_tenant_id()
            agent_id = self._get_agent_id()

            if not tenant_id or not agent_id:
                return jsonify({"error": "Missing headers"}), 400

            # Parse NDJSON
            lines = request.data.decode("utf-8").strip().split("\n")
            ingested = 0
            errors = []

            for i, line in enumerate(lines):
                try:
                    uer = json.loads(line)
                    uer["tenant"] = tenant_id
                    uer["agent_id"] = agent_id

                    # Validate
                    valid, error = self._validate_uer(uer)
                    if not valid:
                        errors.append({"line": i, "error": error})
                        continue

                    # Send to Kafka
                    topic = f"uer.ingest.{tenant_id}"
                    self.producer.send(topic, key=uer.get("uid"), value=json.dumps(uer))
                    ingested += 1

                except json.JSONDecodeError as e:
                    errors.append({"line": i, "error": f"Invalid JSON: {e}"})
                    continue

            return jsonify({"ingested": ingested, "errors": errors}), 200

        except Exception as e:
            logger.error(f"Bulk ingest error: {e}")
            return jsonify({"error": str(e)}), 500


# Mock Kafka producer for development
class MockKafkaProducer:
    def send(self, topic: str, key: str, value: str):
        logger.info(f"Kafka: {topic} <- {key}: {value[:100]}")


# Mock Redis client for development
class MockRedis:
    def get(self, key: str) -> Optional[str]:
        return None

    def setex(self, key: str, ttl: int, value: str):
        logger.debug(f"Redis SET: {key} = {value} (TTL: {ttl})")


# Initialize for standalone testing
if __name__ == "__main__":
    producer = MockKafkaProducer()
    redis = MockRedis()
    service = IngressService(producer, redis)
    app.run(host="0.0.0.0", port=8080, debug=True)

