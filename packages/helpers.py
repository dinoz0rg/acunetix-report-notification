"""Helper functions for the Acunetix Report Sender."""
import logging
import os
from logging.handlers import TimedRotatingFileHandler


def init_all_loggers(log_level=logging.INFO):
    """Initialize all loggers with the specified log level.
    
    Args:
        log_level: Logging level (default: logging.INFO)
    """
    os.makedirs("log", exist_ok=True)

    formatter = logging.Formatter(u'%(asctime)s %(levelname)s [%(name)s] %(message)s', 
                                datefmt="%Y-%m-%d %H:%M:%S")

    # Initialize main logger
    cmd_logger = logging.getLogger()
    cmd_logger.setLevel(log_level)
    
    # Remove any existing handlers
    for handler in cmd_logger.handlers[:]:
        cmd_logger.removeHandler(handler)

    # Add file handler with rotation
    hdlr = TimedRotatingFileHandler(
        "log/main.log", 
        when="midnight", 
        interval=1, 
        backupCount=7, 
        encoding="utf-8"
    )
    hdlr.setFormatter(formatter)
    cmd_logger.addHandler(hdlr)

    # Add console handler
    hdlr2 = logging.StreamHandler()
    hdlr2.setFormatter(formatter)
    cmd_logger.addHandler(hdlr2)

    # Initialize error logger
    init_error_logger(log_level)


def init_error_logger(log_level=logging.ERROR):
    """Initialize the error logger with the specified log level.
    
    Args:
        log_level: Logging level (default: logging.ERROR)
        
    Returns:
        logging.Logger: The error logger instance
    """
    formatter = logging.Formatter(
        u'%(asctime)s %(levelname)s [%(name)s] %(message)s', 
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    cmd_logger = logging.getLogger("AppErrorLogger")
    
    # Remove any existing handlers
    for handler in cmd_logger.handlers[:]:
        cmd_logger.removeHandler(handler)
    
    cmd_logger.setLevel(log_level)
    
    # Add file handler with rotation
    hdlr = TimedRotatingFileHandler(
        "log/error.log", 
        when="midnight", 
        interval=1, 
        backupCount=7, 
        encoding="utf-8"
    )
    hdlr.setFormatter(formatter)
    cmd_logger.addHandler(hdlr)
    
    return cmd_logger


def get_main_logger():
    """Get the main logger instance.
    
    Returns:
        logging.Logger: The main logger instance
    """
    return logging.getLogger()


def get_error_logger():
    """Get the error logger instance.
    
    Returns:
        logging.Logger: The error logger instance
    """
    return logging.getLogger("AppErrorLogger")
