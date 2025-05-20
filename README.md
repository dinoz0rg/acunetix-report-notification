# Acunetix Report Sender

A Python application that automatically generates and emails Acunetix scan reports. It monitors scans, creates HTML reports, and sends them via email with findings summaries.

## Quick Start

1. Clone and setup:
```bash
git clone https://github.com/dinoz0rg/acunetix-report-notification.git
cd acunetix-report-sender
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Unix/MacOS:
source venv/bin/activate
pip install -r requirements.txt
```

2. Configure `config/config.ini`:
```ini
[acunetix]
url = https://your-acunetix-server:3443/api/v1
apikey = your-api-key
report_template_id = 11111111-1111-1111-1111-111111111126

[email]
username = your-email@example.com
password = your-email-password
recipient = recipient@example.com
smtp_server = smtp.office365.com
smtp_port = 587
use_tls = true

[paths]
reports_dir = ./reports
processed_file = processed_scans.json

[settings]
report_max_retries = 10
report_retry_delay = 10
scan_check_delay = 3600
```

3. Run the application:
```bash
python main.py
```

## Key Features

- 🔄 Automatic scan monitoring
- 📊 HTML report generation
- 📧 Email notifications with report attachments
- ✅ Duplicate prevention
- 📝 Detailed logging
- ⚙️ Configurable settings

## Requirements

- Python 3.6+
- Acunetix API access
- SMTP server access

## Project Structure

```
.
├── main.py                # Main application
├── api_client.py          # Acunetix API client
├── scan_processor.py      # Scan processing
├── email_sender.py        # Email functionality
├── config_loader.py       # Configuration
├── models.py             # Data models
├── helpers.py            # Utilities
├── config/
│   └── config.ini        # Configuration
└── reports/              # Generated reports
```

## Scheduling

### Windows Task Scheduler
- Create a task to run `python main.py` hourly

### Linux Cron
```bash
0 * * * * cd /path/to/acunetix-report-sender && ./venv/bin/python main.py >> /var/log/acunetix-sender.log 2>&1
```

## Troubleshooting

- Check `log/main.log` and `log/error.log` for issues
- Verify SMTP and API credentials
- Ensure sufficient disk space for reports

## License

MIT License