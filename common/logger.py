import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str = 'timecamp_sync') -> logging.Logger:
    """Set up and return a logger instance."""
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
        console_handler.setLevel(logging.DEBUG)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger 