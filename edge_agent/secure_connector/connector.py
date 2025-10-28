"""
Secure Connector - Handles secure communication between Edge Agent and Cloud Platform
"""
import ssl
import socket
import grpc
from typing import Optional, Dict, Any
import jwt
from datetime import datetime, timedelta

from shared.models.uer_schema import UnifiedEventReport
from shared.utils.logger import get_logger
from shared.config.constants import AgentStatus

logger = get_logger(__name__)


class SecureConnector:
    """Handles secure communication with Cloud Platform"""
    
    def __init__(
        self,
        agent_id: str,
        tenant_id: str,
        cloud_endpoint: str,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        ca_cert_path: Optional[str] = None
    ):
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.cloud_endpoint = cloud_endpoint
        self.cert_path = cert_path
        self.key_path = key_path
        self.ca_cert_path = ca_cert_path
        self.jwt_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.status = AgentStatus.REGISTERING
        
    def authenticate(self, secret_key: str) -> bool:
        """
        Authenticate with Cloud Platform using JWT
        """
        try:
            # Generate JWT token
            payload = {
                'agent_id': self.agent_id,
                'tenant_id': self.tenant_id,
                'exp': datetime.utcnow() + timedelta(hours=24)
            }
            self.jwt_token = jwt.encode(payload, secret_key, algorithm='HS256')
            self.token_expiry = datetime.utcnow() + timedelta(hours=24)
            self.status = AgentStatus.ACTIVE
            
            logger.info(f"Authenticated agent {self.agent_id} with tenant {self.tenant_id}")
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            self.status = AgentStatus.ERROR
            return False
    
    def is_token_valid(self) -> bool:
        """Check if JWT token is still valid"""
        if not self.jwt_token or not self.token_expiry:
            return False
        return datetime.utcnow() < self.token_expiry
    
    def send_uer(self, uer: UnifiedEventReport) -> bool:
        """
        Send Unified Event Report to Cloud Platform
        
        This would use gRPC or HTTPS with mTLS in production
        """
        if not self.is_token_valid():
            logger.warning("JWT token expired, attempting to re-authenticate")
            # In production, would re-authenticate here
            self.authenticate("dummy_secret_for_demo")
        
        try:
            # Serialize UER to JSON
            uer_dict = uer.dict()
            
            # In production, this would use gRPC client or HTTPS with mTLS
            # For now, log the UER
            logger.info(f"Sending UER {uer.event_id} to {self.cloud_endpoint}")
            logger.debug(f"UER data: {uer_dict}")
            
            # Simulate successful transmission
            return True
        except Exception as e:
            logger.error(f"Failed to send UER: {e}")
            return False
    
    def get_credentials(self) -> Dict[str, Any]:
        """Get agent credentials for Cloud Platform registration"""
        return {
            'agent_id': self.agent_id,
            'tenant_id': self.tenant_id,
            'jwt_token': self.jwt_token,
            'cert_path': self.cert_path,
            'key_path': self.key_path
        }


class ReverseProxyConnector(SecureConnector):
    """Handles connection via reverse proxy on TCP/443"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proxy_port = 443
        self.proxy_host = None
    
    def connect_to_proxy(self) -> bool:
        """Establish connection to Cloud Platform reverse proxy"""
        try:
            # Parse endpoint to get proxy host
            if '://' in self.cloud_endpoint:
                protocol, endpoint = self.cloud_endpoint.split('://', 1)
                if '/' in endpoint:
                    endpoint = endpoint.split('/')[0]
                self.proxy_host = endpoint
            else:
                self.proxy_host = self.cloud_endpoint
            
            # Create SSL context for mTLS
            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            
            if self.ca_cert_path:
                context.load_verify_locations(self.ca_cert_path)
            
            if self.cert_path and self.key_path:
                context.load_cert_chain(self.cert_path, self.key_path)
            
            # Connect to proxy
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            wrapped_socket = context.wrap_socket(
                sock,
                server_hostname=self.proxy_host
            )
            
            wrapped_socket.connect((self.proxy_host, self.proxy_port))
            logger.info(f"Connected to proxy at {self.proxy_host}:{self.proxy_port}")
            
            wrapped_socket.close()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to proxy: {e}")
            self.status = AgentStatus.ERROR
            return False

