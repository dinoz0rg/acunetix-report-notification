"""Scan processing logic for Acunetix Report Sender."""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

from models import ScanResult, ScanStatus, ConfigError
from api_client import AcunetixAPI, AcunetixAPIError

logger = logging.getLogger(__name__)


class ScanProcessorError(Exception):
    """Raised when there is an error processing scans."""
    pass


class ScanProcessor:
    """Handles the processing of scans and report generation."""
    
    def __init__(self, config: Any):
        """Initialize the scan processor.
        
        Args:
            config: Application configuration.
        """
        self.config = config
        self.api = AcunetixAPI(config.acunetix)
        self.processed_scans: Set[str] = set()
        self._load_processed_scans()
    
    def _load_processed_scans(self) -> None:
        """Load the set of previously processed scans from disk."""
        processed_file = self.config.paths.processed_file
        try:
            if processed_file.exists():
                with open(processed_file, 'r') as f:
                    self.processed_scans = set(json.load(f))
                logger.info(f"Loaded {len(self.processed_scans)} processed scans from {processed_file}")
            else:
                logger.info("No existing processed scans file found, starting fresh")
        except Exception as e:
            logger.warning(f"Could not load processed scans: {e}")
            self.processed_scans = set()
    
    def _save_processed_scans(self) -> None:
        """Save the set of processed scans to disk."""
        processed_file = self.config.paths.processed_file
        try:
            # Ensure the directory exists
            processed_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the processed scans
            with open(processed_file, 'w') as f:
                json.dump(list(self.processed_scans), f)
            logger.debug(f"Saved {len(self.processed_scans)} processed scans to {processed_file}")
        except Exception as e:
            logger.error(f"Failed to save processed scans: {e}", exc_info=True)
    
    def _wait_for_scan_completion(self, scan_id: str, max_checks: int = 10) -> bool:
        """Wait for a scan to complete.
        
        Args:
            scan_id: The ID of the scan to wait for.
            max_checks: Maximum number of status checks to perform.
            
        Returns:
            bool: True if the scan completed successfully, False otherwise.
        """
        for check in range(max_checks):
            try:
                scan_data = self.api.fetch_scan(scan_id)
                status = scan_data.get('current_session', {}).get('status')
                
                if status == ScanStatus.COMPLETED.value:
                    logger.info(f"Scan {scan_id} has completed successfully")
                    return True
                elif status == ScanStatus.FAILED.value:
                    logger.error(f"Scan {scan_id} has failed")
                    return False
                else:
                    logger.info(
                        f"Scan {scan_id} status: {status} "
                        f"(check {check + 1}/{max_checks})"
                    )
            except AcunetixAPIError as e:
                logger.error(f"Error checking scan {scan_id} status: {e}")
                return False
            
            # Wait before checking again
            time.sleep(self.config.settings.scan_check_delay)
        
        logger.warning(f"Scan {scan_id} did not complete within the expected time")
        return False
    
    def _generate_scan_report(self, scan_data: Dict[str, Any]) -> Optional[ScanResult]:
        """Generate a report for a single scan.
        
        Args:
            scan_data: The scan data from the API.
            
        Returns:
            Optional[ScanResult]: The scan result if successful, None otherwise.
        """
        scan_id = scan_data.get('scan_id')
        target_id = scan_data.get('target_id')
        scan_status = scan_data.get('current_session', {}).get('status')
        
        if not scan_id or not target_id:
            logger.error(f"Invalid scan data: missing scan_id or target_id")
            return None
        
        # Skip if we've already processed this scan
        if scan_id in self.processed_scans:
            logger.info(f"Skipping already processed scan: {scan_id}")
            return None
        
        # Skip scheduled scans
        if scan_status == ScanStatus.SCHEDULED.value:
            logger.info(f"Skipping scheduled scan: {scan_id}")
            return None
            
        # Skip if scan is not completed
        if scan_status != ScanStatus.COMPLETED.value:
            logger.info(f"Skipping incomplete scan {scan_id} with status: {scan_status}")
            return None
        
        try:
            # Generate the report
            report_data = self.api.generate_report(target_id)
            report_id = report_data.get('report_id')
            
            if not report_id:
                logger.error(f"Failed to generate report for scan {scan_id}")
                return None
            
            # Wait for the report to be ready
            report = self._wait_for_report(report_id)
            if not report:
                logger.error(f"Failed to generate report for scan {scan_id}")
                return None
            
            # Generate a filename for the report
            target_name = scan_data.get('target', {}).get('description', 'report')
            safe_name = "".join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in target_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"{safe_name}_{timestamp}.html"
            report_path = self.config.paths.reports_dir / report_filename
            
            # Get the download URL from the report
            download_url = None
            if isinstance(report, dict):
                # Check for direct download URL first
                if 'download' in report and isinstance(report['download'], str):
                    download_url = report['download']
                # Check for download items list
                elif 'download' in report and isinstance(report['download'], list) and report['download']:
                    item = report['download'][0]
                    if isinstance(item, dict):
                        download_url = item.get('url')
                    elif isinstance(item, str):
                        download_url = item
                # Check for direct download_url field
                elif 'download_url' in report:
                    download_url = report['download_url']
                # If no URL found but we have a report_id, construct the download URL
                elif 'report_id' in report:
                    # Just return the report ID, let the API client construct the full URL
                    download_url = report['report_id']
            elif isinstance(report, str):
                # If the report is just a URL string or ID
                download_url = report
                
            # Log the download URL for debugging
            if download_url:
                logger.debug(f"Using download URL: {download_url}")
            else:
                logger.warning(f"Could not determine download URL from report data: {report}")
            
            if not download_url:
                logger.error(f"Could not find download URL in report data: {report}")
                return None
            
            # Ensure reports directory exists
            report_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download the report
            logger.info(f"Downloading report from {download_url} to {report_path}")
            if not self.api.download_report(download_url, report_path):
                logger.error(f"Failed to download report for scan {scan_id}")
                return None
            
            # Create the scan result
            result = ScanResult(
                scan_id=scan_id,
                target_id=target_id,
                description=target_name,
                start_date=scan_data.get('current_session', {}).get('start_date', ''),
                report_path=report_path,
                severity_counts=scan_data.get('current_session', {}).get('severity_counts', {}),
                current_session=scan_data.get('current_session', {})
            )
            
            logger.info(f"Generated report for scan {scan_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing scan {scan_id}: {e}", exc_info=True)
            return None
    
    def _wait_for_report(self, report_id: str, max_attempts: int = 10) -> Optional[Dict[str, Any]]:
        """Wait for a report to be generated.
        
        Args:
            report_id: The ID of the report to wait for.
            max_attempts: Maximum number of status checks to perform.
            
        Returns:
            Optional[Dict[str, Any]]: The report data if successful, None otherwise.
        """
        for attempt in range(max_attempts):
            try:
                report = self.api.get_report_status(report_id)
                if not report:
                    logger.warning(f"No report data received for {report_id}")
                    continue
                
                status = report.get('status')
                if status == 'completed':
                    logger.info(f"Report {report_id} is ready")
                    return report
                elif status in ('failed', 'cancelled'):
                    logger.error(f"Report generation {status} for report {report_id}")
                    return None
                
                logger.info(
                    f"Report {report_id} status: {status} "
                    f"(attempt {attempt + 1}/{max_attempts})"
                )
                
            except AcunetixAPIError as e:
                logger.error(f"Error checking report {report_id} status: {e}")
                return None
            
            # Wait before checking again
            time.sleep(self.config.settings.report_retry_delay)
        
        logger.warning(f"Report {report_id} did not complete within the expected time")
        return None
    
    def mark_as_processed(self, scan_id: str) -> None:
        """Mark a scan as processed.
        
        Args:
            scan_id: The ID of the scan to mark as processed.
        """
        if scan_id not in self.processed_scans:
            self.processed_scans.add(scan_id)
            self._save_processed_scans()
            logger.info(f"Marked scan {scan_id} as processed")
    
    def process_scans(self) -> List[ScanResult]:
        """Process all available scans.
        
        Returns:
            List[ScanResult]: List of processed scan results.
        """
        results = []
        
        try:
            # Fetch all scans
            scan_data = self.api.fetch_all_scans()
            scans = scan_data.get('scans', [])
            
            if not scans:
                logger.info("No scans found to process")
                return results
            
            logger.info(f"Found {len(scans)} scans to process")
            
            # Process each scan
            for scan in scans:
                try:
                    result = self._generate_scan_report(scan)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error processing scan {scan.get('scan_id')}: {e}", exc_info=True)
            
            return results
            
        except AcunetixAPIError as e:
            logger.error(f"API error while processing scans: {e}")
            raise ScanProcessorError(f"Failed to process scans: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error while processing scans: {e}", exc_info=True)
            raise ScanProcessorError(f"Unexpected error while processing scans: {e}") from e
