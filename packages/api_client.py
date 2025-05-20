"""Acunetix API client with retry logic and error handling."""
import json
import logging
import time
import urllib3
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from packages.models import ScanStatus, ScanResult, AcunetixConfig

# Suppress only the InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class AcunetixAPIError(Exception):
    """Raised when there is an error with the Acunetix API."""
    pass


class AcunetixAPI:
    """Handles all interactions with the Acunetix API."""
    
    def __init__(self, config: AcunetixConfig):
        """Initialize the Acunetix API client.
        
        Args:
            config: Acunetix configuration settings.
        """
        self.config = config
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create and configure a requests session with retry logic.
        
        Returns:
            requests.Session: Configured session object.
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=[408, 429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        # Mount the retry strategy to both http and https
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Configure session with SSL verification
        session.verify = False  # Disable SSL verification as we're using self-signed certs
        session.headers.update({
            "X-Auth": self.config.api_key,
            "Content-Type": "application/json",
            "User-Agent": "Acunetix-Report-Sender/1.0"
        })
        
        return session
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """Make an API request with retry logic and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments to pass to requests.request()
            
        Returns:
            Dict[str, Any]: Parsed JSON response
            
        Raises:
            AcunetixAPIError: If the request fails after all retries
        """
        url = f"{self.config.url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Set default timeout if not specified
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.config.timeout
        
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                logger.debug(f"Making {method} request to {url} (attempt {attempt + 1}/{self.config.max_retries + 1})")
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                
                # Return parsed JSON if response has content, otherwise return empty dict
                return response.json() if response.content else {}
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                
                # Log the error
                error_msg = f"API request failed (attempt {attempt + 1}/{self.config.max_retries + 1}): {e}"
                
                # Add response details if available
                if hasattr(e, 'response') and e.response is not None:
                    error_msg += f" (Status: {e.response.status_code})"
                    try:
                        error_details = e.response.json().get('message', e.response.text)
                        error_msg += f" - {error_details}"
                    except ValueError:
                        error_msg += f" - {e.response.text[:200]}"
                
                if attempt < self.config.max_retries:
                    # Calculate backoff time
                    backoff_time = self.config.backoff_factor * (2 ** attempt)
                    error_msg += f". Retrying in {backoff_time:.1f}s..."
                    logger.warning(error_msg)
                    time.sleep(backoff_time)
                else:
                    logger.error(error_msg, exc_info=True)
        
        # If we get here, all retries failed
        raise AcunetixAPIError(
            f"API request failed after {self.config.max_retries + 1} attempts: {str(last_exception)}"
        )
    
    def fetch_scan(self, scan_id: str) -> Dict[str, Any]:
        """Fetch details for a specific scan.
        
        Args:
            scan_id: The ID of the scan to fetch.
            
        Returns:
            Dict[str, Any]: Dictionary containing scan details.
            
        Raises:
            ValueError: If scan_id is empty or None.
        """
        if not scan_id:
            raise ValueError("scan_id cannot be empty")
            
        logger.debug(f"Fetching details for scan {scan_id}")
        return self._make_request("GET", f"/scans/{scan_id}")
    
    def fetch_all_scans(self) -> Dict[str, Any]:
        """Fetch all scans from Acunetix.
        
        Returns:
            Dict[str, Any]: Dictionary containing scan data.
        """
        result = self._make_request("GET", "/scans")
        scan_count = len(result.get('scans', []))
        logger.info(f"Fetched {scan_count} scans")
        return result
    
    def generate_report(self, target_id: str) -> Dict[str, Any]:
        """Generate a report for a specific target.
        
        Args:
            target_id: The ID of the target to generate a report for.
            
        Returns:
            Dict[str, Any]: The report generation response.
        """
        if not target_id:
            raise ValueError("target_id cannot be empty")
            
        payload = {
            "template_id": self.config.report_template_id,
            "source": {
                "list_type": "targets",
                "id_list": [target_id]
            }
        }
        
        logger.info(f"Generating report for target {target_id}")
        return self._make_request("POST", "/reports", json=payload)
    
    def get_report_status(self, report_id: str) -> Dict[str, Any]:
        """Get the status of a report.
        
        Args:
            report_id: The ID of the report to check.
            
        Returns:
            Dict[str, Any]: The report status information.
        """
        if not report_id:
            raise ValueError("report_id cannot be empty")
            
        return self._make_request("GET", f"/reports/{report_id}")
    
    def download_report(self, url_suffix: str, file_path: Path) -> bool:
        """Download a report file.
        
        Args:
            url_suffix: The URL or URL suffix for the report download.
            file_path: The local path to save the report to.
            
        Returns:
            bool: True if download was successful, False otherwise.
        """
        if not url_suffix:
            logger.error("Cannot download report: empty URL suffix")
            return False
            
        if not isinstance(file_path, Path):
            logger.error(f"Invalid file path type: {type(file_path).__name__}")
            return False
            
        try:
            # If it's already a full URL, use it as is
            if url_suffix.startswith(('http://', 'https://')):
                full_url = url_suffix
            else:
                # Normalize the URL suffix
                if not url_suffix.startswith('/'):
                    url_suffix = f'/{url_suffix}'
                
                # Get base URL and ensure it doesn't end with /api/v1
                base_url = self.config.url.rstrip('/')
                if base_url.endswith('/api/v1'):
                    base_url = base_url[:-7]  # Remove '/api/v1' from the end
                
                # Remove any leading /api/v1 from the suffix to prevent duplication
                if url_suffix.startswith('/api/v1'):
                    url_suffix = url_suffix[7:]  # Remove '/api/v1'
                
                # Remove any leading slashes to prevent double slashes
                url_suffix = url_suffix.lstrip('/')
                
                # Construct the full URL
                full_url = f"{base_url}/api/v1/{url_suffix}"
                
            logger.debug(f"Constructed download URL: {full_url}")
            
            # Make the request with streaming to handle large files
            with self.session.get(full_url, stream=True, timeout=self.config.timeout) as response:
                response.raise_for_status()
                
                # Write the file in chunks to handle large files
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:  # Filter out keep-alive new chunks
                            f.write(chunk)
            
            logger.info(f"Successfully downloaded report to {file_path}")
            return True
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to download report: {e}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f" (Status: {e.response.status_code})"
            logger.error(error_msg, exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading report: {e}", exc_info=True)
            return False
    
    def delete_reports(self, report_ids: List[str]) -> bool:
        """Delete multiple reports.
        
        Args:
            report_ids: List of report IDs to delete.
            
        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        if not report_ids:
            logger.warning("No report IDs provided for deletion")
            return False
            
        payload = {"report_id_list": report_ids}
        try:
            self._make_request("POST", "/reports/delete", json=payload)
            logger.info(f"Successfully deleted {len(report_ids)} reports")
            return True
        except AcunetixAPIError as e:
            logger.error(f"Failed to delete reports: {e}")
            return False
