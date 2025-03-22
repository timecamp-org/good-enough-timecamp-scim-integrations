import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str = 'timecamp_sync', debug: bool = False) -> logging.Logger:
    """Set up and return a logger instance.
    
    Args:
        name: Logger name
        debug: If True, console handler will log DEBUG messages, otherwise INFO
    """
    logger = logging.getLogger(name)
    
    # Only add handlers if they haven't been added yet
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Create formatters and handlers
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Rotating file handler (10 MB per file, keep 5 backup files)
        file_handler = RotatingFileHandler(
            'logs/sync.log',
            maxBytes=10*1024*1024,
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    else:
        # Update existing console handler's log level if debug mode changes
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
                handler.setLevel(logging.DEBUG if debug else logging.INFO)
    
    return logger 