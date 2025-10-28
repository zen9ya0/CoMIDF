"""
Network utility functions
"""
import subprocess
from typing import List, Tuple
from shared.utils.logger import get_logger

logger = get_logger(__name__)


def get_network_interfaces() -> List[str]:
    """Get list of all non-loopback network interfaces"""
    try:
        result = subprocess.run(
            ["ip", "link", "show"],
            capture_output=True,
            text=True,
            check=True
        )
        
        interfaces = []
        for line in result.stdout.split('\n'):
            if ': ' in line and 'lo:' not in line:
                # Extract interface name (format: "2: eth0: <BROADCAST>...")
                parts = line.split(':')
                if len(parts) >= 2:
                    iface_name = parts[1].strip()
                    # Clean up any trailing characters
                    iface_name = iface_name.split('@')[0]
                    if iface_name and iface_name != 'lo':
                        interfaces.append(iface_name)
        
        return list(set(interfaces))  # Remove duplicates
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get network interfaces: {e}")
        return []
    except FileNotFoundError:
        logger.error("'ip' command not found. Trying alternative method.")
        return _get_interfaces_alternate()


def _get_interfaces_alternate() -> List[str]:
    """Alternative method to get interfaces"""
    try:
        import netifaces
        interfaces = netifaces.interfaces()
        return [iface for iface in interfaces if iface != 'lo']
    except ImportError:
        logger.warning("netifaces not available, returning empty list")
        return []


def get_interface_ip(interface: str) -> str:
    """Get IP address for a network interface"""
    try:
        result = subprocess.run(
            ["ip", "addr", "show", interface],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.split('\n'):
            if 'inet ' in line and '127.0.0.1' not in line:
                # Extract IP from line like "inet 192.168.1.100/24 ..."
                parts = line.strip().split()
                if parts[0] == 'inet':
                    return parts[1].split('/')[0]
        
        return ""
    except (subprocess.CalledProcessError, IndexError):
        return ""


def validate_interface_exists(interface: str) -> bool:
    """Check if a network interface exists"""
    interfaces = get_network_interfaces()
    return interface in interfaces

