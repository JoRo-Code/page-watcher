# Page Watcher

A lightweight Python script that monitors web pages for changes and sends email notifications when updates are detected. Perfect for monitoring websites that don't provide RSS feeds or change notifications.

## What it does

The script:
1. **Fetches** the target webpage content
2. **Normalizes** the HTML to readable text (removes scripts, styles, and formatting)
3. **Compares** the current content with the previously saved version
4. **Sends email alerts** via Resend when changes are detected
5. **Stores state** locally to track changes over time

## Features

- **Smart HTML parsing**: Strips JavaScript, CSS, and other noisy elements
- **Efficient change detection**: Uses SHA-256 hashing for fast comparisons
- **Unified diff output**: Shows exactly what changed between versions
- **Email notifications**: Sends alerts via Resend API with both HTML and text formats
- **Configurable**: Customizable timeouts, user agents, and email subjects
- **Cron-friendly**: Designed to run periodically via cron jobs

## Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager
- A [Resend](https://resend.com) account and API key
- A verified sender domain in Resend

## Installation

### 1. Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

### 2. Clone and setup the project

```bash
git clone <your-repo-url>
cd page-watcher

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example environment file and configure it:

```bash
cp env.example .env
```

Edit `.env` with your actual values:

```bash
export WATCH_URL="https://example.com"
export RESEND_API_KEY="re_xxxxxxxxxxxxxxxxxxxxxxxxxxx"
export FROM_EMAIL="Alerts <alerts@yourdomain.com>"
export TO_EMAIL="your@email.com"
export SUBJECT_PREFIX="[Page Watch]"
export USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

**Required variables:**
- `WATCH_URL`: The webpage you want to monitor
- `RESEND_API_KEY`: Your Resend API key (starts with `re_...`)
- `TO_EMAIL`: Where to send alerts (single email or comma-separated list)
- `FROM_EMAIL`: Verified sender identity in Resend

**Optional variables:**
- `STATE_DIR`: Directory to store state files (default: `.watch_state`)
- `REQUEST_TIMEOUT`: HTTP timeout in seconds (default: 20)
- `SUBJECT_PREFIX`: Email subject prefix (default: "[Page Watch]")
- `USER_AGENT`: Custom User-Agent string

### 4. Source the environment

```bash
source .env
```

## Usage

### Manual execution

```bash
# Run the script directly with uv (no need to activate venv)
uv run main.py
```

### Automated monitoring with cron

Set up a cron job to run the script periodically:

```bash
# Edit crontab
crontab -e

# Add this line to run every 30 minutes
*/30 * * * * cd /path/to/page-watcher && source .env && uv run main.py >> /var/log/page-watcher.log 2>&1

# Or every hour
0 * * * * cd /path/to/page-watcher && source .env && uv run main.py >> /var/log/page-watcher.log 2>&1
```

### Multiple pages

To monitor multiple websites, create separate cron entries with different state directories:

```bash
# First website
*/30 * * * * cd /path/to/page-watcher && export STATE_DIR=".watch_state_site1" && source .env && uv run main.py

# Second website  
*/30 * * * * cd /path/to/page-watcher && export STATE_DIR=".watch_state_site2" && source .env && uv run main.py
```

## How it works

1. **Initialization**: On first run, the script saves the current page content and exits quietly
2. **Monitoring**: On subsequent runs, it fetches the current content and compares it to the saved version
3. **Change detection**: If content differs, it generates a unified diff showing what changed
4. **Notification**: Sends an email via Resend with the diff and a link to the monitored page
5. **State update**: Saves the new content for future comparisons

## Output and logging

- **Success**: Script exits with code 0 (no output unless changes detected)
- **Changes**: Prints change detection message and Resend response
- **Errors**: Prints error messages to stderr and exits with non-zero code
- **State files**: Stored in `.watch_state/` directory (or custom `STATE_DIR`)

## Troubleshooting

### Common issues

**"Missing required env var" error**
- Ensure all required environment variables are set
- Check that `.env` file is properly sourced

**Resend API errors**
- Verify your API key is correct
- Ensure your sender domain is verified in Resend
- Check Resend account status and limits

**HTTP fetch failures**
- Verify the URL is accessible
- Check network connectivity
- Consider adjusting `REQUEST_TIMEOUT` for slow sites

**False positives**
- Some sites have dynamic content that changes frequently
- Consider targeting a more stable sub-URL
- Use CSS selectors if the site structure allows

### Debug mode

For troubleshooting, you can run with verbose output:

```bash
uv run main.py 2>&1 | tee debug.log
```

## Best practices

1. **Be respectful**: Check the site's `robots.txt` and terms of service
2. **Reasonable intervals**: Don't run too frequently (30+ minutes recommended)
3. **Target specific content**: Focus on stable sections of dynamic sites
4. **Monitor logs**: Check cron logs for any errors or issues
5. **Test first**: Run manually before setting up automated monitoring

## Dependencies

- `requests`: HTTP client for fetching web pages
- `beautifulsoup4`: HTML parsing and normalization
- `difflib`: Built-in Python module for generating diffs
