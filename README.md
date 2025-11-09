# YTUploader

A Python application that automates uploading videos to YouTube Studio without using the YouTube Data API. The tool reuses browser session cookies, fetches metadata from Google Sheets, optionally downloads videos from Google Drive, and supports multi-account scheduling.

## Features

- Load browser cookies for hundreds of accounts and channels.
- Pull upload metadata (title, description, hashtags, tags, filenames) from Google Sheets rows marked `New`.
- Download source files from local storage or Google Drive links/IDs.
- Automate the full YouTube Studio upload flow with Selenium, including toggles such as **Altered content** and **Made for Kids**.
- Schedule uploads at fixed times or randomise the order each day.
- Clean up uploaded video files and rotate logs daily.

## Requirements

- Python 3.10+
- Google service account credentials with access to the spreadsheet and Google Drive files.
- Chrome browser and matching ChromeDriver binary accessible in `PATH`.

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and adjust to your environment:

```bash
cp config.example.yaml config.yaml
```

Key settings:

- `accounts`: List of account names and cookie file paths. Export cookies using your preferred method (e.g., browser extensions) into JSON files.
- `google`: Spreadsheet metadata and service-account JSON path.
- `sheet_mapping`: Column names to map spreadsheet data to uploader fields, including optional `altered_content` and `made_for_kids` boolean columns.
- `schedule`: Daily times in HH:MM (24-hour) when uploads should run.
- `selenium`: WebDriver behaviour (headless mode, user agent, download dir).
- `cleanup`: Log retention and whether to remove uploaded video files.

## Running

```bash
python -m yt_uploader.main config.yaml
```

The scheduler will run continuously, triggering uploads according to the configured schedule. Logs are written to the `logs/` directory and mirrored to stdout for visibility. The application configures a timed rotating log handler that keeps at most one day of history, automatically removing older log files to satisfy the 24-hour retention requirement.

## Google Sheet Workflow

1. Each row represents a video.
2. Set `UploadYT` column to `New` for rows awaiting upload.
3. Optionally provide columns for `altered_content` (values such as `Yes` or `No`) and `made_for_kids` (`Yes`/`No`).
4. After successful upload, the app sets `UploadYT` to `Done` and writes the resulting `YTUrl`.

## Cookie Management

Place cookie JSON exports in the `cookies/` directory with filenames matching account names (e.g., `main-account.json`). The application loads cookies before launching YouTube Studio and updates their timestamps to balance account usage.

## Notes

- The Selenium selectors may require adjustment if YouTube updates its Studio interface.
- Ensure accounts are configured with channel defaults (language, monetisation) compatible with headless automation.
- Always comply with YouTube's Terms of Service when automating uploads.
