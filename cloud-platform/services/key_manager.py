"""
Key Manager: Generate and manage Edge Agent credentials.
"""
import secrets
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple
from flask import Flask, request, jsonify
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)


class KeyManager:
    """
    Manage Edge Agent credentials and tokens.
    
    Features:
    - Generate unique agent keys
    - Issue JWT tokens
    - Manage mTLS certificates
    - Track agent registration
    """
    
    def __init__(self, db_connection, cert_authority):
        self.db = db_connection
        self.ca = cert_authority
        
        @app.route("/api/v1/agents/register", methods=["POST"])
        def register_agent():
            return self._register_agent()
        
        @app.route("/api/v1/agents/<agent_id>/credentials", methods=["GET"])
        def get_credentials(agent_id: str):
            return self._get_credentials(agent_id)
        
        @app.route("/api/v1/agents/<agent_id>/rotate", methods=["POST"])
        def rotate_key(agent_id: str):
            return self._rotate_key(agent_id)
    
    def generate_agent_key(self, tenant_id: str, site: str, agent_name: str) -> Tuple[str, Dict]:
        """
        Generate a new agent key with all credentials.
        
        Returns:
            (agent_id, credentials_dict)
        """
        # Generate unique agent ID
        timestamp = datetime.now(timezone.utc).isoformat()
        agent_id = f"{tenant_id}-{site}-{secrets.token_hex(4)}"
        
        # Generate API token
        api_token = secrets.token_urlsafe(64)
        token_hash = hashlib.sha256(api_token.encode()).hexdigest()
        
        # Generate mTLS certificate (if CA is configured)
        cert_data = {}
        if self.ca:
            cert_data = self.ca.generate_client_cert(agent_id)
        
        # Create credentials package
        credentials = {
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "site": site,
            "api_token": api_token,  # Only returned once, then hashed
            "api_token_hash": token_hash,
            "timestamp": timestamp,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
            "mTLS": {
                "enabled": bool(self.ca),
                "certificate": cert_data.get("cert"),
                "private_key": cert_data.get("key"),
                "ca_cert": cert_data.get("ca_cert"),
            },
            "metadata": {
                "name": agent_name,
                "created_by": "system",  # TODO: track user
            }
        }
        
        # Store in database
        self._store_agent_credentials(credentials)
        
        logger.info(f"Generated credentials for agent {agent_id}")
        
        return agent_id, credentials
    
    def _store_agent_credentials(self, creds: dict):
        """Store agent credentials in database."""
        # In production, store in database
        # For now, just log
        logger.info(f"Storing credentials for {creds['agent_id']}")
        # TODO: Store in DB
        pass
    
    def _register_agent(self):
        """Register a new agent and return credentials."""
        try:
            data = request.get_json()
            tenant_id = data.get("tenant_id")
            site = data.get("site", "default")
            agent_name = data.get("name", "Agent")
            
            if not tenant_id:
                return jsonify({"error": "tenant_id required"}), 400
            
            # Generate credentials
            agent_id, credentials = self.generate_agent_key(
                tenant_id=tenant_id,
                site=site,
                agent_name=agent_name
            )
            
            logger.info(f"New agent registered: {agent_id}")
            
            return jsonify({
                "status": "registered",
                "agent_id": agent_id,
                "credentials": credentials,
                "config_template": self._generate_config_template(credentials)
            }), 200
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return jsonify({"error": str(e)}), 500
    
    def _get_credentials(self, agent_id: str):
        """Get agent credentials (for download/refresh)."""
        try:
            # In production, retrieve from database
            # For now, return mock data
            return jsonify({
                "agent_id": agent_id,
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    def _rotate_key(self, agent_id: str):
        """Rotate agent API token."""
        try:
            # Generate new token
            new_token = secrets.token_urlsafe(64)
            new_hash = hashlib.sha256(new_token.encode()).hexdigest()
            
            # In production, update in database
            logger.info(f"Rotated key for agent {agent_id}")
            
            return jsonify({
                "status": "rotated",
                "agent_id": agent_id,
                "new_token": new_token,
                "rotate_at": datetime.now(timezone.utc).isoformat(),
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    def _generate_config_template(self, creds: dict) -> dict:
        """Generate agent.yaml config template."""
        return {
            "agent": {
                "id": creds["agent_id"],
                "tenant_id": creds["tenant_id"],
                "site": creds["site"],
                "timezone": "UTC",
            },
            "uplink": {
                "mssp_url": "https://your-cloud.example.com",
                "fal_endpoint": "/api/fal/uer",
                "token": creds["api_token"],
                "tls": {
                    "mtls": creds["mTLS"]["enabled"],
                    "ca_cert": "/etc/agent/ca.pem",
                    "cert": "/etc/agent/agent.pem" if creds["mTLS"]["enabled"] else "",
                    "key": "/etc/agent/agent.key" if creds["mTLS"]["enabled"] else "",
                },
                "retry": {
                    "backoff_ms": [200, 500, 1000, 2000],
                    "max_retries": 8,
                },
            },
            "buffer": {
                "backend": "sqlite",
                "path": "/var/lib/edge-agent/buffer.db",
                "max_mb": 2048,
                "flush_batch": 500,
            },
            "privacy": {
                "id_salt": secrets.token_hex(32),
                "strip_fields": ["usernames", "urls", "payload"],
            },
            "agents": {
                "http": {"enabled": True, "thresholds": {"score_alert": 0.7}},
                "mqtt": {"enabled": True, "thresholds": {"score_alert": 0.65}},
            },
            "metrics": {"prometheus_port": 9108},
            "logging": {"level": "info", "json": True},
        }
    
    def verify_token(self, tenant_id: str, agent_id: str, token: str) -> bool:
        """Verify agent API token."""
        # In production, check against database
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        # TODO: Validate against stored hash
        return True


class CertificateAuthority:
    """Mock CA for generating mTLS certificates."""
    
    def __init__(self, ca_cert_path: str, ca_key_path: str):
        self.ca_cert_path = ca_cert_path
        self.ca_key_path = ca_key_path
    
    def generate_client_cert(self, client_name: str) -> dict:
        """Generate client certificate for mTLS."""
        # In production, use openssl or cryptography library
        # For now, return placeholder
        return {
            "cert": f"-----BEGIN CERTIFICATE-----\nMOCK_CERT_FOR_{client_name}\n-----END CERTIFICATE-----",
            "key": f"-----BEGIN PRIVATE KEY-----\nMOCK_KEY_FOR_{client_name}\n-----END PRIVATE KEY-----",
            "ca_cert": "-----BEGIN CERTIFICATE-----\nMOCK_CA_CERT\n-----END CERTIFICATE-----",
        }


# Mock database connection
class MockDB:
    def __init__(self):
        self.agents = {}
    
    def store(self, key: str, value: dict):
        self.agents[key] = value
    
    def get(self, key: str):
        return self.agents.get(key)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Initialize
    db = MockDB()
    ca = CertificateAuthority("ca.pem", "ca.key")
    key_manager = KeyManager(db, ca)
    
    # Run server
    app.run(host="0.0.0.0", port=9090, debug=True)

