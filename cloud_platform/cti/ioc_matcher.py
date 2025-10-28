"""
CTI (Cyber Threat Intelligence) Module - IOC matching and threat enrichment
"""
from typing import Dict, List, Any, Optional
import ipaddress

from shared.models.uer_schema import UnifiedEventReport
from shared.utils.logger import get_logger

logger = get_logger(__name__, "cti.log")


class IOCHandler:
    """Handles IOC matching and threat intelligence"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # IOC databases (in production, these would be external feeds)
        self.ip_iocs: Dict[str, Dict[str, Any]] = {}
        self.domain_iocs: Dict[str, Dict[str, Any]] = {}
        self.url_iocs: Dict[str, Dict[str, Any]] = {}
        
        # Load IOC feeds
        self._load_ioc_feeds()
    
    def _load_ioc_feeds(self):
        """Load IOC feeds from CTI sources"""
        # In production, would connect to OpenCTI, MISP, OTX, etc.
        logger.info("Loading IOC feeds from CTI sources...")
        
        # Example IOC data
        self.ip_iocs['192.168.1.100'] = {
            'source': 'custom',
            'type': 'malicious_ip',
            'description': 'Known malicious IP',
            'confidence': 0.95
        }
    
    def check_ioc_match(
        self,
        uer: UnifiedEventReport
    ) -> List[Dict[str, Any]]:
        """Check if UER matches any IOCs"""
        matches = []
        
        # Check source IP
        if uer.source_ip in self.ip_iocs:
            ioc_data = self.ip_iocs[uer.source_ip]
            matches.append({
                'ioc_type': 'source_ip',
                'ioc_value': uer.source_ip,
                'source': ioc_data.get('source', 'unknown'),
                'confidence': ioc_data.get('confidence', 0.5),
                'description': ioc_data.get('description', ''),
                'mitre_id': ioc_data.get('mitre_id', [])
            })
            logger.info(f"IOC match for source IP: {uer.source_ip}")
        
        # Check destination IP
        if uer.destination_ip in self.ip_iocs:
            ioc_data = self.ip_iocs[uer.destination_ip]
            matches.append({
                'ioc_type': 'destination_ip',
                'ioc_value': uer.destination_ip,
                'source': ioc_data.get('source', 'unknown'),
                'confidence': ioc_data.get('confidence', 0.5),
                'description': ioc_data.get('description', ''),
                'mitre_id': ioc_data.get('mitre_id', [])
            })
            logger.info(f"IOC match for destination IP: {uer.destination_ip}")
        
        return matches
    
    def enrich_with_ioc_data(
        self,
        uer: UnifiedEventReport,
        ioc_matches: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Enrich UER with IOC data"""
        if not ioc_matches:
            return {}
        
        # Extract MITRE ATT&CK IDs
        mitre_ids = []
        for match in ioc_matches:
            if 'mitre_id' in match and match['mitre_id']:
                mitre_ids.extend(match['mitre_id'])
        
        # Calculate overall IOC confidence
        ioc_confidence = max([m.get('confidence', 0.0) for m in ioc_matches]) if ioc_matches else 0.0
        
        return {
            'ioc_hit': True,
            'ioc_matches': len(ioc_matches),
            'ioc_sources': list(set([m.get('source', 'unknown') for m in ioc_matches])),
            'mitre_attack_ids': list(set(mitre_ids)),
            'ioc_confidence': ioc_confidence
        }
    
    def add_ioc_feed(
        self,
        ioc_type: str,
        ioc_value: str,
        source: str,
        confidence: float,
        description: str = "",
        mitre_ids: Optional[List[str]] = None
    ):
        """Add IOC to database (for testing/demo)"""
        ioc_data = {
            'source': source,
            'confidence': confidence,
            'description': description,
            'mitre_id': mitre_ids or []
        }
        
        if ioc_type == 'ip':
            self.ip_iocs[ioc_value] = ioc_data
        elif ioc_type == 'domain':
            self.domain_iocs[ioc_value] = ioc_data
        elif ioc_type == 'url':
            self.url_iocs[ioc_value] = ioc_data
        
        logger.info(f"Added IOC: {ioc_type}={ioc_value} from {source}")


class CTIModule:
    """Main CTI module for IOC matching"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ioc_handler = IOCHandler(config)
    
    async def check_threat_intelligence(
        self,
        uer: UnifiedEventReport
    ) -> Dict[str, Any]:
        """Check UER against CTI feeds"""
        logger.debug(f"Checking CTI for UER {uer.event_id}")
        
        # Check IOC matches
        ioc_matches = self.ioc_handler.check_ioc_match(uer)
        
        if ioc_matches:
            # Enrich with IOC data
            enrichment = self.ioc_handler.enrich_with_ioc_data(uer, ioc_matches)
            
            logger.info(
                f"CTI match found for UER {uer.event_id}: "
                f"{len(ioc_matches)} IOCs matched from {len(enrichment.get('ioc_sources', []))} sources"
            )
            
            return {
                'ioc_matched': True,
                'ioc_matches': ioc_matches,
                'enrichment': enrichment
            }
        
        return {
            'ioc_matched': False,
            'ioc_matches': [],
            'enrichment': {}
        }

