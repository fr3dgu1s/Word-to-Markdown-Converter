# Word-to-Markdown Converter

A small, local-only FastAPI application that converts Word `.docx` files to
Markdown using [Docling](https://github.com/DS4SD/docling). It runs entirely
on your machine — no cloud calls, no authentication, no external services.

## Purpose

- Convert one or more local `.docx` files to clean Markdown.
- Preview and edit the converted Markdown in the browser.
- Save or download the edited Markdown.
- Save extracted images alongside the Markdown so links work in any viewer.

## Prerequisites

- Windows 10 / 11
- Python 3.10 or newer
- The Python packages listed in [requirements.txt](requirements.txt)

## Setup

```powershell
# 1. (optional) create a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. install dependencies
python -m pip install -r requirements.txt
```

The first run downloads Docling model assets (one-time, ~hundreds of MB).

## Run

```powershell
python -m uvicorn server:app
```

Open <http://127.0.0.1:8000>.

## Default folders

The app routes everything through `C:/temp/W2MD` so it never depends on
per-user paths. Folders are created automatically on first run.

| Path | Purpose |
| --- | --- |
| `C:/temp/W2MD/Outputs`        | All converted Markdown (single + batch) |
| `C:/temp/W2MD/Outputs/Images` | Extracted images (one sub-folder per document) |
| `C:/temp/W2MD/Temp`           | Short-lived upload scratch space |
| `C:/temp/W2MD/Logs`           | `app.log` and rotated history |

Override any of these by editing [.env](.env) (`APP_DATA_ROOT`,
`OUTPUTS_ROOT`, `IMAGES_ROOT`, `TEMP_ROOT`, `LOGS_ROOT`).

## Single file conversion

1. Drop a `.docx` file onto the upload zone (or click to browse).
2. Wait for conversion. The Markdown opens in the editor.
3. Edit using the toolbar (headings, bold, italics, lists, callouts,
   code blocks, tables, etc.).
4. Switch to **Visual Preview** to render the Markdown with images.
5. Click **Save** to update `C:/temp/W2MD/Outputs/<doc-name>.md`,
   or **Copy** to copy Markdown to the clipboard.
6. Click **Open Folder** to reveal the file in Windows Explorer.

## Batch conversion

1. Click **Batch Convert Selected Files** (multi-select files) or
   **Batch Convert Folder** (entire folder).
2. The app converts every `.docx`. It skips other file types and continues
   even if individual files fail.
3. A summary shows how many files succeeded, how many failed, and **why
   each failed file failed**.
4. Outputs land directly in `C:/temp/W2MD/Outputs`. Batch outputs include
   `-BATCH` in the filename — e.g. `Security Spec.docx` becomes
   `Security Spec-BATCH.md` — to flag that the file still needs
   review/editing before being treated as final.

## Stopping the server

Click **Stop Python App** in the top bar — or press `Ctrl+C` in the terminal
running `uvicorn`.

## Logs

- File: `C:/temp/W2MD/Logs/app.log` (rotates automatically).
- The bottom **Logs** card in the UI streams the latest 100 lines.
- `DELETE /logs/latest` (or the **Clear** button) truncates the log file.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Failed to fetch` in the browser | Server not running — start it again with `python -m uvicorn server:app`. |
| Port already in use | Stop the previous instance: `taskkill /F /IM python.exe`, or pick a different port: `python -m uvicorn server:app --port 8001`. |
| `Document converter failed to initialise` | Re-run `python -m pip install -r requirements.txt`. The first run downloads Docling models — make sure you have internet access. |
| `.docx` won't open / "file already in use" | Close the document in Microsoft Word and try again. |
| Encrypted / IRM-protected `.docx` fails | This app is local-only and does not handle protected files. Decrypt the document in Word first (open it, save a copy as `.docx`), then convert that copy. |
| Images don't appear in preview | Ensure conversion completed successfully and that `C:/temp/W2MD/Outputs/Images/<doc>/` contains PNG files. |

## Acknowledgements

This project uses [Docling](https://github.com/DS4SD/docling) — an
open-source document processing toolkit by Red Hat — for the underlying
`.docx` → Markdown conversion.
