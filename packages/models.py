"""Data models and configuration for Acunetix Report Sender."""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any


class ScanStatus(str, Enum):
    """Enumeration of possible scan statuses."""
    SCHEDULED = 'scheduled'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    STOPPED = 'stopped'


class SeverityLevel(str, Enum):
    """Enumeration of vulnerability severity levels."""
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'
    INFO = 'info'


@dataclass
class ScanResult:
    """Represents the result of a scan."""
    scan_id: str
    target_id: str
    description: str
    start_date: str
    report_path: Path
    severity_counts: Dict[str, int] = field(default_factory=dict)
    current_session: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_completed(self) -> bool:
        """Check if the scan is completed."""
        return self.current_session.get('status') == ScanStatus.COMPLETED.value
    
    @property
    def is_scheduled(self) -> bool:
        """Check if the scan is scheduled."""
        return self.current_session.get('status') == ScanStatus.SCHEDULED.value


class ConfigError(Exception):
    """Raised when there is an error in configuration."""
    pass


@dataclass
class EmailConfig:
    """Email configuration settings."""
    username: str
    password: str
    recipient: str
    smtp_server: str = 'smtp.mail.yahoo.com'
    smtp_port: int = 587
    use_tls: bool = True


@dataclass
class AcunetixConfig:
    """Acunetix API configuration settings."""
    url: str
    api_key: str
    report_template_id: str
    verify_ssl: bool = False
    timeout: int = 30
    max_retries: int = 3
    backoff_factor: float = 0.3


@dataclass
class PathConfig:
    """Path configuration settings."""
    reports_dir: Path
    processed_file: Path
    
    def __post_init__(self):
        """Ensure paths are Path objects and create directories if needed."""
        self.reports_dir = Path(self.reports_dir).resolve()
        self.processed_file = Path(self.processed_file).resolve()
        self.reports_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class Settings:
    """Application settings."""
    scan_check_delay: int = 3600  # seconds
    report_max_retries: int = 10
    report_retry_delay: int = 10  # seconds
    request_timeout: int = 30  # seconds


@dataclass
class AppConfig:
    """Main application configuration."""
    acunetix: AcunetixConfig
    email: EmailConfig
    paths: PathConfig
    settings: Settings
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'AppConfig':
        """Create AppConfig from a dictionary."""
        return cls(
            acunetix=AcunetixConfig(
                url=config_dict['acunetix']['url'],
                api_key=config_dict['acunetix']['apikey'],
                report_template_id=config_dict['acunetix']['report_template_id'],
                verify_ssl=config_dict['acunetix'].getboolean('verify_ssl', False),
                timeout=config_dict['acunetix'].getint('timeout', 30),
                max_retries=config_dict['acunetix'].getint('max_retries', 3),
                backoff_factor=config_dict['acunetix'].getfloat('backoff_factor', 0.3)
            ),
            email=EmailConfig(
                username=config_dict['email']['username'],
                password=config_dict['email']['password'],
                recipient=config_dict['email']['recipient'],
                smtp_server=config_dict['email'].get('smtp_server', 'smtp.mail.yahoo.com'),
                smtp_port=config_dict['email'].getint('smtp_port', 587),
                use_tls=config_dict['email'].getboolean('use_tls', True)
            ),
            paths=PathConfig(
                reports_dir=config_dict['paths']['reports_dir'],
                processed_file=config_dict['paths']['processed_file']
            ),
            settings=Settings(
                scan_check_delay=config_dict['settings'].getint('scan_check_delay', 3600),
                report_max_retries=config_dict['settings'].getint('report_max_retries', 10),
                report_retry_delay=config_dict['settings'].getint('report_retry_delay', 10),
                request_timeout=config_dict['settings'].getint('request_timeout', 30)
            )
        )
