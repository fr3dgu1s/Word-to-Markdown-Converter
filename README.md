# Markdown Studio

A local AI-powered Word-to-Markdown converter with a built-in Markdown editor
and preview.

## Purpose

- Convert one or more local `.docx` files to clean Markdown.
- Preview and edit the converted Markdown in the browser.
- Save or download the edited Markdown.
- Save extracted images alongside the Markdown so links work in any viewer.
- Handle Microsoft Purview / MIP protected Word files when Microsoft Word can
  decrypt them for the signed-in user.

## Tech stack

- **Backend:** Python, FastAPI, Docling AI, pywin32
- **Frontend:** Single-file vanilla HTML/JavaScript, no build step

## Prerequisites

- Windows 10 / 11
- Microsoft Word installed and signed in to Office 365 for Purview-protected
  files
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

The easiest way to start the app is the silent launcher — no terminal
required:

1. Double-click [launch_silent.vbs](launch_silent.vbs) (or right-click →
   *Open*).
2. A loading page opens in your default browser. It polls the server and
   automatically redirects to <http://127.0.0.1:8000> as soon as the
   converter is ready.

The launcher starts the Python server in the background using `pyw` /
`pythonw`, so no console window is shown. To stop the app, either click
**Stop Python App** in the UI or double-click
[stop_silent.vbs](stop_silent.vbs).

### Manual start (optional)

If you prefer a terminal (e.g. for development or to see live logs):

```powershell
python -m uvicorn server:app
```

Then open <http://127.0.0.1:8000>.

## Updates and changelog

On startup, the browser UI asks the local server to compare the current local
Git checkout with the latest `main` branch commit on GitHub. If a newer commit
exists online, the app shows an **Update available** banner with a link to the
GitHub compare view and a link to the local [changelog](CHANGELOG.md).

The update check is best-effort: if the machine is offline, GitHub is
unreachable, or the app is not running from a Git checkout, conversion still
works and no update banner is shown.

To update after reviewing the changelog, stop the app and run:

```powershell
git pull origin main
```

## Default folders

By default, the app stores runtime files in the project/app folder that
contains `paths.py`. Folders are created automatically on first run.

| Path | Purpose |
| --- | --- |
| `<project folder>\Outputs`        | All converted Markdown (single + batch) |
| `<project folder>\Outputs\Images` | Extracted images (one sub-folder per document) |
| `<project folder>\Temp`           | Short-lived upload scratch space |
| `<project folder>\Logs`           | `app.log` and rotated history |

`APP_DATA_ROOT` is the source of truth. If you set it in [.env](.env) or as an
environment variable, `Outputs`, `Outputs\Images`, `Temp`, and `Logs` are
created under that folder. If it is not set, the project folder is used.

Example default layout:

```text
APP_DATA_ROOT=<project folder>
OUTPUTS_ROOT=<project folder>\Outputs
IMAGES_ROOT=<project folder>\Outputs\Images
TEMP_ROOT=<project folder>\Temp
LOGS_ROOT=<project folder>\Logs
```

## Single file conversion

1. Drop a `.docx` file onto the upload zone (or click to browse).
2. Wait for conversion. The Markdown opens in the editor.
3. Edit using the toolbar (headings, bold, italics, lists, callouts,
   code blocks, tables, etc.).
4. Switch to **Visual Preview** to render the Markdown with images.
5. Click **Save** to update `<project folder>\Outputs\<doc-name>.md`,
   or **Copy** to copy Markdown to the clipboard.

### Editor commands

The Markdown editor toolbar includes two helpers tailored for documents
exported from Word:

- **Insert Title** — prompts for a title and inserts a centered, large
  HTML title block at the cursor:

  ```html
  <div align="center">
    <span style="font-size: 2.5em; font-weight: 700;">My Title</span>
  </div>
  ```

  Markdown alone cannot reliably center text, so this uses inline HTML.
  The preview renders it correctly. Title text is HTML-escaped.

- **Clean/Fix Table** — cleans the selected Markdown table (or the table
  detected around the cursor when nothing is selected). It fixes common
  artifacts produced by Word-to-Markdown conversion:
  - Removes repeated-title rows where every cell on row 1 is the same
    value (e.g. `| OneLake Security | OneLake Security | … |`).
  - Drops empty rows and stray separator rows.
  - Replaces empty cells with `-`.
  - Detects **field/value metadata** tables (label columns ending with
    `:`, with a spacer column) and rewrites them as a clean two-column
    `Field` / `Details` table — pluralising labels (`Engineer` →
    `Engineers`, `Architect` → `Architects`, `Engineering Manager` →
    `Engineering Managers`) and bolding `Status: Draft`.
  - Detects **Promotion Plan** tables (`CHANNEL / Y/N / CONTENT NEEDED /
    OWNER / TIMING`) and rewrites them with normalised headers and
    aligned columns.
  - For any other table, performs a generic cleanup: trims cells, picks
    the first meaningful row as the header, generates an alignment row,
    bolds the first column.

  If no table is selected and none is detected near the cursor, the UI
  shows: *"No Markdown table selected or detected."*
6. Click **Open Folder** to reveal the file in Windows Explorer.

## Microsoft Purview / MIP protected files

Files with Purview sensitivity labels that apply encryption are not standard
ZIP-based `.docx` packages. Docling cannot read those encrypted bytes directly.

Markdown Studio detects this by opening the upload with Python's `zipfile`
module:

- Valid ZIP package: convert directly with Docling.
- `BadZipFile`: treat as Purview/MIP-protected and route through Microsoft Word.

For protected files, the server keeps one persistent hidden
`Word.Application` COM instance alive for the server process. Word handles MIP
decryption using the already-authenticated Office session, saves a clean
temporary `.docx` copy, and Docling converts that clean temp file. The clean
temp copy is deleted immediately after conversion.

If your organization does not allow removing labels entirely, update
`strip_protection_and_save()` in `server.py` to set your organization's
non-encrypting "General" label instead of calling:

```python
doc.SensitivityLabel.SetLabel("", "")
```

You can find label GUIDs with the AIPService PowerShell module:

```powershell
Connect-AipService
Get-Label | Select DisplayName, Guid
```

Protected-file support requires `pywin32` and Microsoft Word. If Word COM
cannot start, normal non-protected files still convert normally.

### Protected-file conversion flow

```text
browser upload
    |
    v
FastAPI /api/convert
    |
    +-- is_purview_protected() == false --> Docling directly
    |
    +-- is_purview_protected() == true
          |
          v
       persistent Word COM instance
          |
          +-- open protected file
          +-- remove label when policy allows
          +-- SaveAs clean temporary .docx
          |
          v
       Docling converts clean temp file
          |
          v
       clean temp file is deleted
```

## Batch conversion

You have three ways to convert many `.docx` files at once. All three write
results into `<project folder>\Outputs` and use the `-BATCH` suffix in the
filename — e.g. `Security Spec.docx` becomes `Security Spec-BATCH.md` —
to flag that the file still needs review/editing before being treated as
final. Each method skips non-`.docx` files and continues on individual
failures, then shows a summary with success/fail counts and **why each
failed file failed**.

### 1. Selected files (browser upload)

Click **Batch Convert Selected Files**, multi-select files in the picker,
and the browser uploads them to the local server.

### 2. Folder picker (browser upload)

Click **Batch Convert Folder**, pick a folder, and the browser uploads
every `.docx` inside it.

### 3. Scan a folder on disk (no upload)

Best for large folders or files that already live on this machine — the
server reads them directly from disk, no browser upload step:

1. Paste an absolute folder path into the **folder path** field
   (e.g. `C:\Docs\Specs`).
2. Leave **Include subfolders** checked to scan recursively, or uncheck
   for the top level only.
3. Click **Scan Folder & Convert**.

The server enumerates every `.docx` under that path (skipping Word lock
files like `~$Draft.docx`) and converts each one. Because the app only
binds to `127.0.0.1`, this option is safe — no remote caller can reach
the endpoint.

## Stopping the server

You have three options:

- Click **Stop Python App** in the top bar of the UI.
- Double-click [stop_silent.vbs](stop_silent.vbs).
- Press `Ctrl+C` in the terminal if you started the server manually with
  `uvicorn`.

## Logs

- File: `<project folder>\Logs\app.log` (rotates automatically).
- The bottom **Logs** card in the UI streams the latest 100 lines.
- `DELETE /logs/latest` (or the **Clear** button) truncates the log file.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Failed to fetch` in the browser | Server not running — re-launch with [launch_silent.vbs](launch_silent.vbs) (or `python -m uvicorn server:app`). |
| Port already in use | Stop the previous instance with [stop_silent.vbs](stop_silent.vbs) or `taskkill /F /IM pythonw.exe`. For manual mode, pick another port: `python -m uvicorn server:app --port 8001`. |
| Browser opens the loading page but never redirects | The Docling first-run model download is still in progress — wait a minute and refresh. Check `<project folder>\Logs\app.log` if it persists. |
| `Document converter failed to initialise` | Re-run `python -m pip install -r requirements.txt`. The first run downloads Docling models — make sure you have internet access. |
| `.docx` won't open / "file already in use" | Close the document in Microsoft Word and try again. |
| Purview / MIP-protected `.docx` fails | Ensure Microsoft Word is installed, signed in to Office 365, and the current user has rights to open/export the file. If policy requires labels, configure `strip_protection_and_save()` with a non-encrypting label GUID. |
| Images don't appear in preview | Ensure conversion completed successfully and that `<project folder>\Outputs\Images\<doc>\` contains PNG files. |

## Acknowledgements

This project uses [Docling](https://github.com/DS4SD/docling) — an
open-source document processing toolkit by Red Hat — for the underlying
`.docx` → Markdown conversion.
