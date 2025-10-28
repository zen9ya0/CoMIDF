"""
UER Gateway - Receives and validates UERs from Edge Agents
"""
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
import uvicorn

from shared.models.uer_schema import UnifiedEventReport
from shared.utils.logger import get_logger

logger = get_logger(__name__, "uer_gateway.log")

app = FastAPI(title="CoMIDF UER Gateway")


class UERGateway:
    """Unified Event Report Gateway"""
    
    def __init__(self, gc_client, pr_client):
        self.gc_client = gc_client  # Global Credibility client
        self.pr_client = pr_client  # Priority Reporter client
        self.received_count = 0
        self.error_count = 0
    
    async def receive_uer(self, uer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Receive and process a UER"""
        try:
            # Validate UER
            uer = UnifiedEventReport(**uer_data)
            
            # Forward to Global Credibility module
            result = await self.gc_client.process_uer(uer)
            
            self.received_count += 1
            logger.info(f"Processed UER {uer.event_id} from agent {uer.agent_id}")
            
            return {
                "status": "success",
                "event_id": uer.event_id,
                "processing_result": result
            }
        except Exception as e:
            self.error_count += 1
            logger.error(f"Failed to process UER: {e}")
            raise HTTPException(status_code=400, detail=str(e))


# Global gateway instance (would be initialized properly in production)
gateway = None


@app.post("/api/v1/uer/receive")
async def receive_unified_event_report(
    uer_data: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """Receive UER from Edge Agent"""
    if not gateway:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    
    return await gateway.receive_uer(uer_data)


@app.get("/api/v1/uer/stats")
async def get_gateway_stats():
    """Get gateway statistics"""
    if not gateway:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    
    return {
        "received_count": gateway.received_count,
        "error_count": gateway.error_count
    }


def create_gateway(gc_client, pr_client) -> UERGateway:
    """Create and initialize gateway"""
    global gateway
    gateway = UERGateway(gc_client, pr_client)
    return gateway


def start_server(host: str = "0.0.0.0", port: int = 9092):
    """Start UER Gateway server"""
    uvicorn.run(app, host=host, port=port)

