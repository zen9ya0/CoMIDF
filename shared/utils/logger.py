"""
Centralized logging for CoMIDF
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Optional


class CoMIDFLogger:
    """Unified logger for CoMIDF components"""
    
    _loggers: Dict[str, logging.Logger] = {}
    _log_dir = Path("/var/log/comidf")
    
    @classmethod
    def setup_logger(
        cls,
        name: str,
        log_file: Optional[str] = None,
        level: int = logging.INFO
    ) -> logging.Logger:
        """Create and configure a logger instance"""
        if name in cls._loggers:
            return cls._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '[%(levelname)s] %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            cls._log_dir.mkdir(parents=True, exist_ok=True)
            file_path = cls._log_dir / log_file
            
            file_handler = logging.handlers.RotatingFileHandler(
                file_path,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(detailed_formatter)
            logger.addHandler(file_handler)
        
        cls._loggers[name] = logger
        return logger
    
    @classmethod
    def get_logger(cls, name: str, log_file: Optional[str] = None) -> logging.Logger:
        """Get existing or create new logger"""
        if name not in cls._loggers:
            return cls.setup_logger(name, log_file)
        return cls._loggers[name]


# Convenience function
def get_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """Get a logger instance"""
    return CoMIDFLogger.get_logger(name, log_file)

