"""Configuration loading and validation for Acunetix Report Sender."""
import configparser
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from packages.models import AppConfig, ConfigError

logger = logging.getLogger(__name__)


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """
    Load and validate configuration from a file.
    
    Args:
        config_path: Path to the configuration file. If None, uses default location.
        
    Returns:
        AppConfig: The loaded and validated configuration.
        
    Raises:
        ConfigError: If there's an error loading or validating the configuration.
    """
    if config_path is None:
        config_path = Path("config/config.ini")
    
    if not config_path.exists():
        error_msg = f"Configuration file not found: {config_path.absolute()}"
        logger.error(error_msg)
        raise ConfigError(error_msg)
    
    config = configparser.ConfigParser()
    try:
        config.read(config_path)
        _validate_config(config)
        return AppConfig.from_dict(config)
    except ConfigError:
        raise
    except Exception as e:
        error_msg = f"Failed to load configuration: {e}"
        logger.error(error_msg, exc_info=True)
        raise ConfigError(error_msg) from e


def _validate_config(config: configparser.ConfigParser) -> None:
    """
    Validate the configuration values.
    
    Args:
        config: The ConfigParser instance to validate.
        
    Raises:
        ConfigError: If any required configuration is missing or invalid.
    """
    required_sections = {
        'acunetix': ['url', 'apikey', 'report_template_id'],
        'email': ['username', 'password', 'recipient'],
        'paths': ['reports_dir', 'processed_file'],
        'settings': []  # All settings have defaults
    }
    
    # Check required sections
    for section, required_keys in required_sections.items():
        if section not in config:
            raise ConfigError(f"Missing required section in config: [{section}]")
        
        # Check required keys in section
        for key in required_keys:
            if key not in config[section]:
                raise ConfigError(f"Missing required config value: [{section}] {key}")
    
    # Validate URL format
    try:
        url = config['acunetix']['url']
        if not (url.startswith('http://') or url.startswith('https://')):
            raise ConfigError(f"Invalid URL format in config: {url}")
    except Exception as e:
        raise ConfigError(f"Invalid URL in configuration: {e}") from e
    
    # Validate numeric values
    try:
        int(config['settings'].get('report_max_retries', '10'))
        int(config['settings'].get('report_retry_delay', '10'))
        int(config['settings'].get('scan_check_delay', '3600'))
    except ValueError as e:
        raise ConfigError(f"Invalid numeric value in settings: {e}") from e


def get_default_config() -> str:
    """
    Get the default configuration as a string.
    
    Returns:
        str: The default configuration in INI format.
    """
    return """[acunetix]
# Acunetix API settings
url = https://acunetix.example.com/api/v1
apikey = your_api_key_here
report_template_id = 11111111-1111-1111-1111-111111111111
verify_ssl = false
timeout = 30
max_retries = 3
backoff_factor = 0.3

[email]
# Email notification settings
username = your_email@example.com
password = your_email_password
recipient = recipient@example.com
smtp_server = smtp.example.com
smtp_port = 587
use_tls = true

[paths]
# File system paths
reports_dir = ./reports
processed_file = ./data/processed_scans.json

[settings]
# Application settings
scan_check_delay = 3600  # seconds
report_max_retries = 10
report_retry_delay = 10  # seconds
request_timeout = 30  # seconds
"""
