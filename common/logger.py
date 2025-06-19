import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str = 'timecamp_sync', debug: bool = False) -> logging.Logger:
    """Set up and return a logger instance.
    
    Args:
        name: Logger name
        debug: If True, console handler will log DEBUG messages, otherwise INFO
    
    Environment Variables:
        DISABLE_FILE_LOGGING: If set to 'true', disables file logging and only logs to console
    """
    logger = logging.getLogger(name)
    
    # Only add handlers if they haven't been added yet
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Check if file logging is disabled
        disable_file_logging = os.getenv('DISABLE_FILE_LOGGING', '').lower() == 'true'
        
        # Create formatters and handlers
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Add file handler only if file logging is not disabled
        if not disable_file_logging:
            # Create logs directory if it doesn't exist
            os.makedirs('var/logs', exist_ok=True)
            
            # Rotating file handler (10 MB per file, keep 5 backup files)
            file_handler = RotatingFileHandler(
                'var/logs/sync.log',
                maxBytes=10*1024*1024,
                backupCount=5
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)
            logger.addHandler(file_handler)
        
        # Console handler (always added)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        logger.addHandler(console_handler)
    else:
        # Update existing console handler's log level if debug mode changes
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
                handler.setLevel(logging.DEBUG if debug else logging.INFO)
    
    return logger 