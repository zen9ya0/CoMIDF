"""
Secure Connector: Upload UER events to Cloud MSSP with mTLS, retry, and buffer.
"""
import requests
import time
import logging
from typing import Dict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class SecureConnector:
    def __init__(self, cfg: dict, buffer_store):
        self.cfg = cfg
        self.store = buffer_store
        self.base_url = cfg.get("uplink", {}).get("mssp_url", "").rstrip("/")
        self.path = cfg.get("uplink", {}).get("fal_endpoint", "/api/fal/uer")
        self.token = cfg.get("uplink", {}).get("token", "")
        self.tls_cfg = cfg.get("uplink", {}).get("tls", {})
        self.backoff = cfg.get("uplink", {}).get("retry", {}).get("backoff_ms", [200, 500, 1000, 2000])
        self.max_retries = cfg.get("uplink", {}).get("retry", {}).get("max_retries", 8)
        self.agent_id = cfg.get("agent", {}).get("id", "")
        self.tenant_id = cfg.get("agent", {}).get("tenant_id", "")

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=0.5,
            status_forcelist=[408, 429, 500, 502, 503, 504],
        )
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _get_headers(self, uer: dict) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "X-Tenant-ID": self.tenant_id,
            "X-Agent-ID": self.agent_id,
            "X-Schema-Version": "uer-v1.1",
        }
        return headers

    def _get_cert(self):
        """Get client certificate for mTLS."""
        if self.tls_cfg.get("mtls", False):
            cert_path = self.tls_cfg.get("cert", "")
            key_path = self.tls_cfg.get("key", "")
            return (cert_path, key_path)
        return None

    def _post(self, uer: dict) -> requests.Response:
        """Send UER to cloud via HTTPS 443."""
        url = f"{self.base_url}{self.path}"
        headers = self._get_headers(uer)

        # TLS configuration
        verify_cert = self.tls_cfg.get("verify", True)
        
        # mTLS (if enabled)
        if self.tls_cfg.get("mtls", False):
            cert = self._get_cert()
            verify = self.tls_cfg.get("ca_cert") or True
        else:
            cert = None
            verify = verify_cert

        # Timeout from config or default
        timeout = self.cfg.get("uplink", {}).get("retry", {}).get("timeout_seconds", 30)

        try:
            response = self.session.post(
                url, 
                headers=headers, 
                json=uer, 
                timeout=timeout, 
                verify=verify, 
                cert=cert
            )
            return response
        except Exception as e:
            logger.error(f"HTTP error: {e}")
            raise

    def send(self, uer: dict):
        """Send UER with exponential backoff retry."""
        for attempt, backoff_ms in enumerate(
            self.backoff
            + [self.backoff[-1]] * (self.max_retries - len(self.backoff))
        ):
            try:
                response = self._post(uer)

                # Success
                if response.status_code < 300:
                    logger.info(f"UER sent successfully: {uer.get('uid', 'no-uid')}")
                    return

                # Retryable errors
                if response.status_code in (408, 429) or response.status_code >= 500:
                    logger.warning(
                        f"Retryable error {response.status_code}, attempt {attempt + 1}/{self.max_retries}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(backoff_ms / 1000.0)
                        continue
                    # Max retries reached, buffer it
                    logger.error("Max retries reached, buffering UER")
                    self.store.enqueue(uer)
                    return

                # Permanent errors
                logger.error(f"Non-retryable error {response.status_code}: {response.text}")
                self.store.dead_letter(
                    uer, reason=f"HTTP {response.status_code}: {response.text[:100]}"
                )
                return

            except requests.exceptions.RequestException as e:
                logger.error(f"Request exception (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(backoff_ms / 1000.0)
                else:
                    # Buffer for later
                    logger.error("Max retries reached, buffering UER")
                    self.store.enqueue(uer)

    def flush_buffer(self):
        """Flush buffered UERs to cloud."""
        batch_size = self.cfg.get("buffer", {}).get("flush_batch", 500)
        uers = self.store.dequeue_batch(batch_size)

        for uer in uers:
            self.send(uer)
            time.sleep(0.01)  # Small delay to avoid rate limiting

        logger.info(f"Flushed {len(uers)} UERs from buffer")

