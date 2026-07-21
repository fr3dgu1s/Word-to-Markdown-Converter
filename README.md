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

## Features

- Convert single `.docx` files directly into the editor.
- Open existing `.md` or `.txt` files for preview/editing.
- Batch convert entire folders or multi-select files, including `.docx` files
  inside subfolders.
- Live per-file progress with clickable converted results.
- Save extracted images alongside the Markdown so image links remain portable.
- Optional dark/light appearance toggle.

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

The silent launcher automatically creates a project-local `.venv` and installs
or updates dependencies when `requirements.txt` changes. No manual environment
activation is required to use the launcher.

For manual development:

```powershell
# 1. create a virtual environment
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
2. The launcher creates or repairs `.venv` and installs changed requirements
   when needed.
3. A loading page opens in your default browser. It polls the server and
   automatically redirects to <http://127.0.0.1:8000> as soon as the
   converter is ready.

The launcher starts the Python server in the background using `pyw` /
`pythonw`, so no console window is shown. Bootstrap details are written to
`Logs\bootstrap.log`. To stop the app, either click
**Stop Python App** in the UI or double-click
[stop_silent.vbs](stop_silent.vbs).

### Manual start (optional)

If you prefer a terminal (e.g. for development or to see live logs):

```powershell
python server.py serve
```

Then open <http://127.0.0.1:8000>.

`python server.py` with no arguments still starts the web server on
`127.0.0.1:8000`.

## Command-line conversion

`server.py` can also be executed directly as a command-line converter. This is
useful for local batch jobs, PowerShell scripts, scheduled tasks, GitHub
Copilot skills, or any AI command that needs to convert an existing Word file
without opening the browser UI.

By default, converted files are written to `<project folder>\Outputs`. Use
`-o` / `--output-dir` to write Markdown and extracted images somewhere else.
When converting Markdown back to Word, `-o` can be either a `.docx` file path or
a destination folder.

### Quick examples

Run these commands from the project folder:

```powershell
Set-Location "C:\Users\fresantos\Word-to-Markdown-Converter"

# Convert one Word document to Markdown.
python server.py docx-to-md "C:\Docs\spec.docx"

# Convert one Word document to Markdown and choose the output folder.
python server.py docx-to-md "C:\Docs\spec.docx" -o "C:\Docs\converted"

# Convert all .docx files in a folder, including subfolders.
python server.py batch-docx-to-md "C:\Docs" -o "C:\Docs\converted"

# Convert only .docx files directly inside the folder, not subfolders.
python server.py batch-docx-to-md "C:\Docs" --no-recursive

# Convert Markdown back to Word.
python server.py md-to-docx "C:\Docs\converted\spec.md" -o "C:\Docs\spec.docx"

# Auto-detect whether the input is a .docx, Markdown file, or folder.
python server.py convert "C:\Docs\spec.docx"
python server.py convert "C:\Docs\converted\spec.md" -o "C:\Docs\spec.docx"
python server.py convert "C:\Docs" -o "C:\Docs\converted"
```

### Commands

| Command | Alias | Purpose |
| --- | --- | --- |
| `serve` | | Start the local FastAPI server. |
| `docx-to-md` | `word-to-md` | Convert a single `.docx` to Markdown. |
| `batch-docx-to-md` | `batch` | Convert all `.docx` files in a folder. Recursive by default. |
| `md-to-docx` | `md-to-word` | Convert `.md`, `.markdown`, or `.txt` to `.docx`. |
| `convert` | | Auto-detect a `.docx`, Markdown file, or folder. |

Use `python server.py --help` or `python server.py <command> --help` to see the
available arguments for each command.

### Calling from an AI skill or command

For automation, add `--json` so the command returns machine-readable output
with the generated paths. The JSON output is intentionally kept on stdout so
callers can parse it directly.

```powershell
# Single DOCX -> Markdown, returning JSON.
python server.py docx-to-md "C:\Docs\spec.docx" -o "C:\Docs\converted" --json

# Batch folder conversion, returning JSON.
python server.py batch-docx-to-md "C:\Docs" -o "C:\Docs\converted" --json

# Auto-detect input type and return JSON.
python server.py convert "C:\Docs\spec.docx" --json
```

Single-file JSON includes the input path, generated Markdown path, output
directory, and image folder:

```json
{
  "doc_name": "spec",
  "output_file": "C:\\Docs\\converted\\spec.md",
  "image_dir": "spec",
  "output_dir": "C:\\Docs\\converted",
  "input": "C:\\Docs\\spec.docx"
}
```

Batch JSON includes counts plus per-file success and failure lists:

```json
{
  "output_dir": "C:\\Docs\\converted",
  "scanned_folder": "C:\\Docs",
  "scanned_count": 2,
  "converted_count": 2,
  "failed_count": 0,
  "converted_files": [
    {
      "input": "C:\\Docs\\one.docx",
      "output": "C:\\Docs\\converted\\one-BATCH.md"
    }
  ],
  "failed_files": []
}
```

If the caller needs the Markdown content instead of a file path, use
`--print-markdown` with single-file conversion:

```powershell
python server.py docx-to-md "C:\Docs\spec.docx" --print-markdown
```

### Markdown-to-Word behavior

Markdown-to-Word conversion uses Pandoc when `pandoc` is available on `PATH`
because Pandoc gives the best fidelity. If Pandoc is not installed, the app
falls back to `python-docx` and preserves common Markdown structures such as
headings, lists, tables, block quotes, code blocks, links, and images as
readable Word content.

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

The app **always** stores runtime files in the project/app folder that
contains `paths.py` / `server.py`. Folders are created automatically on
first run.

| Path | Purpose |
| --- | --- |
| `<project folder>\Outputs`        | All converted Markdown (single + batch) |
| `<project folder>\Outputs\Images` | Extracted images (one sub-folder per document) |
| `<project folder>\Temp`           | Short-lived upload scratch space |
| `<project folder>\Logs`           | `app.log` and rotated history |

The runtime root is pinned to the project folder. `APP_DATA_ROOT` from
`.env` or the process environment is intentionally ignored so the **Save**
button always writes to the same `Outputs` folder that the running server
serves at `http://127.0.0.1:8000/Outputs`. If you want runtime files in a
different location, move (or symlink) the entire project folder there.

## Usage

### Single file conversion and Markdown preview

1. Drop a single `.docx` file onto the upload zone.
2. Wait for conversion. The Markdown opens in the editor.
3. Edit using the toolbar (headings, bold, italics, lists, callouts,
   code blocks, tables, etc.).
4. Switch to **Visual Preview** to render the Markdown with images.
5. Click **Save** to update `<project folder>\Outputs\<doc-name>.md`,
   or **Copy** to copy Markdown to the clipboard.
6. Click **Open Folder** to reveal the saved file in Windows Explorer.

Drop a single `.md` or `.txt` file to open it directly in the preview tab
without conversion.

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

Use the same upload zone for batch work:

1. Click the upload zone to open the OS folder picker. Markdown Studio queues
   every `.docx` in that folder, including files in subfolders.
2. Or drag a folder, multiple files, or a mix of files and folders onto the
   upload zone.
3. Or click **Select files** below the upload zone to multi-select individual
   files in the OS file picker.

When more than one file is selected and at least one is a `.docx`, Markdown
Studio converts the `.docx` files sequentially so Docling is not overloaded.
Non-`.docx` files are skipped and counted in the status line, for example:
`3 documents queued · 7 non-docx files skipped`.

The batch screen shows live progress, a per-file status list, and failure
details when an individual file cannot be converted. Successfully converted
filenames become clickable; click any ✅ result to open that Markdown in the
existing editor/preview workspace. **Convert More** returns to the upload zone,
and **Open Output Folder** opens `<project folder>\Outputs` in Windows Explorer.

If multiple Markdown files are selected without any `.docx` files, the app
opens the first Markdown file and shows a notice.

## Screenshots / GIFs

No screenshots or GIFs are currently referenced in this README. If UI images
are added later, capture new ones for the folder picker, drag/drop batch flow,
and per-file progress screen.

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
| Browser opens the loading page but never redirects | Dependency installation or the Docling first-run model download might still be in progress. Check `<project folder>\Logs\bootstrap.log`, then `<project folder>\Logs\app.log`. |
| `Document converter failed to initialise` | Re-run `python -m pip install -r requirements.txt`. The first run downloads Docling models — make sure you have internet access. |
| `.docx` won't open / "file already in use" | Close the document in Microsoft Word and try again. |
| Purview / MIP-protected `.docx` fails | Ensure Microsoft Word is installed, signed in to Office 365, and the current user has rights to open/export the file. If policy requires labels, configure `strip_protection_and_save()` with a non-encrypting label GUID. |
| Images don't appear in preview | Ensure conversion completed successfully and that `<project folder>\Outputs\Images\<doc>\` contains PNG files. |

## Acknowledgements

This project uses [Docling](https://github.com/DS4SD/docling) — an
open-source document processing toolkit by Red Hat — for the underlying
`.docx` → Markdown conversion.
