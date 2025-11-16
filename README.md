# OpenAI Status Page Tracker

A Python script that automatically monitors the OpenAI Status Page for new incidents, outages, and service degradation updates. The script uses efficient conditional HTTP requests (ETag-based) to minimize bandwidth and only processes new updates.

## Features

- **Automatic Monitoring**: Continuously checks for updates without manual intervention
- **Efficient Polling**: Uses ETag headers to only fetch data when changes occur (304 Not Modified responses)
- **Event Detection**: Automatically detects:
  - New incidents
  - Status changes (investigating → identified → monitoring → resolved)
- **Clean Output**: Simple, readable console output showing affected services and status messages
- **Scalable Design**: Ready for monitoring multiple status pages (can be extended with async/await)

## Installation

1. Install Python 3.7 or higher
2. Install dependencies:
   
   pip install -r requirements.txt
   
## Usage

### Basic Usage (60-second poll interval)ash
python status_tracker.pyor on Windows:h
py status_tracker.py### Custom Poll Interval
python status_tracker.py 30This checks every 30 seconds (minimum: 10 seconds)

## Output Format

When a new incident or update is detected, the script prints:
