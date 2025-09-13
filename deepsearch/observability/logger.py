"""
Logger Manager for DeepSearch

Provides centralized logging management using loguru.
"""
import sys
from pathlib import Path
from typing import Optional
from loguru import logger


class LoggerManager:
    """Manages application-wide logging configuration"""
    
    def __init__(self):
        self.log_path = Path("data/logs")
        self.log_level = "INFO"
        self._started = False
        
    def start(self):
        """Initialize and start the logging system"""
        if self._started:
            return
            
        # Create log directory if it doesn't exist
        self.log_path.mkdir(parents=True, exist_ok=True)
        
        # Remove default logger
        logger.remove()
        
        # Add console handler with pretty formatting
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=self.log_level,
            colorize=True
        )
        
        # Add file handler for persistent logs
        log_file = self.log_path / "deepsearch_{time:YYYY-MM-DD}.log"
        logger.add(
            str(log_file),
            rotation="1 day",
            retention="7 days",
            level=self.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            encoding="utf-8"
        )
        
        self._started = True
        logger.info("Logger system started")
        
    def stop(self):
        """Stop the logging system"""
        if not self._started:
            return
            
        logger.info("Logger system stopping")
        logger.remove()
        self._started = False
        
    def set_level(self, level: str):
        """Set the logging level"""
        self.log_level = level
        if self._started:
            # Restart to apply new level
            self.stop()
            self.start()
            
    def get_logger(self, name: Optional[str] = None):
        """Get a logger instance"""
        # loguru uses a single logger instance, so we just return it
        # The name parameter is kept for compatibility
        return logger


# Create singleton instance
logger_manager = LoggerManager()


# Export for convenience
__all__ = ['logger_manager', 'logger']