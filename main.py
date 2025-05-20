"""Main entry point for Acunetix Report Sender."""
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from packages.config_loader import load_config, get_default_config
from packages.models import AppConfig, ConfigError
from packages.scan_processor import ScanProcessor, ScanProcessorError
from packages.email_sender import build_email_html, send_email
from packages.helpers import init_all_loggers, get_main_logger, get_error_logger

# Initialize logging
init_all_loggers(logging.INFO)
logger = get_main_logger()
error_logger = get_error_logger()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Acunetix Report Sender')
    parser.add_argument(
        '--config', 
        type=str, 
        default='config/config.ini',
        help='Path to configuration file (default: config/config.ini)'
    )
    parser.add_argument(
        '--init-config',
        action='store_true',
        help='Initialize a default configuration file and exit'
    )
    return parser.parse_args()

def init_config_file(config_path: str) -> None:
    """Initialize a default configuration file.
    
    Args:
        config_path: Path where to create the config file.
    """
    path = Path(config_path)
    if path.exists():
        print(f"Error: Configuration file already exists at {path.absolute()}")
        sys.exit(1)
    
    # Create parent directories if they don't exist
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write default config
    with open(path, 'w') as f:
        f.write(get_default_config())
    
    print(f"Default configuration created at {path.absolute()}")
    print("Please edit the file with your settings before running the application.")

def main() -> None:
    """Main entry point for the application."""
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Handle --init-config flag
        if args.init_config:
            init_config_file(args.config)
            return
        
        # Load configuration
        logger.info(f"Loading configuration from {args.config}")
        config = load_config(Path(args.config))
        
        # Process scans
        logger.info("Starting scan processing")
        processor = ScanProcessor(config)
        scan_results = processor.process_scans()
        
        if scan_results:
            logger.info(f"Generated reports for {len(scan_results)} scans")
            
            # Prepare and send email with results
            logger.info("Sending email notification")
            subject = f"Acunetix Scan Report - {len(scan_results)} scans processed"
            html_content = build_email_html(scan_results)
            
            # Get report paths for attachments
            report_paths = [result.report_path for result in scan_results 
                         if result.report_path and result.report_path.exists()]
            
            # Send email with attachments
            email_sent = send_email(
                config=config.email,
                subject=subject,
                html_content=html_content,
                attachments=report_paths
            )
            
            if email_sent:
                # Only mark scans as processed after successful email sending
                for result in scan_results:
                    processor.mark_as_processed(result.scan_id)
                logger.info("Email sent successfully and scans marked as processed")
            else:
                logger.error("Failed to send email notification - scans will be retried in the next run")
        else:
            logger.info("No new scan results to report")
        
        logger.info("Processing completed successfully")
        
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except ScanProcessorError as e:
        logger.error(f"Scan processing error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
