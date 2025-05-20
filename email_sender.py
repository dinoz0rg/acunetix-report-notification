"""Email notification functionality for Acunetix Report Sender."""
import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import List, Optional, Union

from models import EmailConfig, ScanResult

logger = logging.getLogger(__name__)


def build_email_html(scan_results: List[ScanResult], title: str = "Acunetix Scan Report") -> str:
    """Build HTML content for the email.
    
    Args:
        scan_results: List of scan results to include in the email.
        title: Email subject/title.
        
    Returns:
        str: HTML-formatted email content.
    """
    if not scan_results:
        return """
        <html>
          <body>
            <p>No new scan results to report.</p>
          </body>
        </html>
        """
    
    # Build the table rows for scan results
    rows = ""
    for result in scan_results:
        severity_str = ", ".join(f"{k}: {v}" for k, v in result.severity_counts.items())
        rows += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">{result.description}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{severity_str}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{result.start_date}</td>
        </tr>
        """
    
    return f"""
    <html>
      <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
            th {{ background-color: #f2f2f2; text-align: left; padding: 8px; border: 1px solid #ddd; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .footer {{ font-size: 12px; color: #777; margin-top: 20px; }}
        </style>
      </head>
      <body>
        <h2>{title}</h2>
        <p>Please find below the summary of the latest Acunetix scan results:</p>
        
        <table>
          <thead>
            <tr>
              <th>Target</th>
              <th>Vulnerabilities</th>
              <th>Scan Date</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>
        
        <div class="footer">
          <p>This is an automated message. Please do not reply to this email.</p>
        </div>
      </body>
    </html>
    """


def send_email(
    config: EmailConfig,
    subject: str,
    html_content: str,
    attachments: Optional[List[Union[str, Path]]] = None,
    to_recipients: Optional[List[str]] = None
) -> bool:
    """Send an email with the scan results.
    
    Args:
        config: Email configuration.
        subject: Email subject.
        html_content: HTML content of the email.
        attachments: List of file paths to attach.
        to_recipients: List of recipient email addresses. If not provided, uses config.recipient.
        
    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    if not to_recipients:
        to_recipients = [config.recipient]
    
    # Create message container
    msg = MIMEMultipart()
    msg['From'] = config.username
    msg['To'] = ", ".join(to_recipients)
    msg['Subject'] = subject
    
    # Attach HTML content
    msg.attach(MIMEText(html_content, 'html'))
    
    # Attach files if provided
    if attachments:
        for file_path in attachments:
            file_path = Path(file_path)
            if file_path.exists() and file_path.is_file():
                try:
                    with open(file_path, 'rb') as f:
                        part = MIMEApplication(f.read(), Name=file_path.name)
                        part['Content-Disposition'] = f'attachment; filename="{file_path.name}"'
                        msg.attach(part)
                    logger.info(f"Attached file: {file_path.name}")
                except Exception as e:
                    logger.error(f"Failed to attach file {file_path}: {e}")
            else:
                logger.warning(f"File not found or is not a file: {file_path}")
    
    try:
        # Connect to SMTP server
        with smtplib.SMTP(config.smtp_server, config.smtp_port) as server:
            if config.use_tls:
                server.starttls()
            
            # Login if credentials are provided
            if config.username and config.password:
                server.login(config.username, config.password)
            
            # Send email
            server.send_message(msg)
            logger.info(f"Email sent successfully to {', '.join(to_recipients)}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to send email: {e}", exc_info=True)
        return False
