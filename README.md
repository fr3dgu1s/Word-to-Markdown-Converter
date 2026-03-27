# Word to MD — Easy Converter 🚀 
## An Easy way to convert you Functional Spec into Markdown

A local-first tool to convert Microsoft Word documents (`.docx`) into clean, GitHub-style Markdown (`.md`).

---

## ⚠️ Data Governance & Security

> [!IMPORTANT]
> This tool can only convert files tagged as **GENERAL / NON-CONFIDENTIAL**.

Files protected by Microsoft Purview (DLP) or sensitivity labels with encryption **will fail to process** — the local engine cannot decrypt corporate encryption envelopes.

**Workaround for encrypted documents:**

If you have a document authorized for Markdown conversion but currently labeled Confidential:

1. Open the file in the **Microsoft Word Desktop App**.
2. Confirm you have rights to export the content.
3. Select **File → Save a Copy**, set the classification to **GENERAL**, and save as `.docx`.
4. Process the unencrypted copy through this tool.

Users are responsible for ensuring converted content adheres to company data handling and classification policies.

---

## 🛠️ Prerequisites

**Python 3.14** must be installed.

Method 1:

- **Download:** [Python 3.14 Official Release](https://www.python.org/downloads/windows/)
- **Verify:** Open PowerShell and run `python --version` — output must show `3.14.x`

Method 2 (Preferred):

- **On Terminal (Powerhsell):** Type: `python` - This will open Microsoft store and will deploy Python End-to-End, without manual configurations. 
- **Verify:** Open PowerShell and run `python --version` — output must show `3.14.x`
---

## 🚀 Setup & Deployment

### 1. Clone or Download

Download this repository to a local folder, e.g. `C:\temp\Word-to-MD-App`.

### 2. Install Dependencies *(one-time)*

Open a terminal in the project folder and run:

```bash
python -m pip install -r requirements.txt
```

### 3. Start the Backend Server

In the same terminal, run:

```bash
python -m uvicorn server:app
```

Wait for: `Starting FastAPI server on http://127.0.0.1:8000`

> [!NOTE]
> Keep this terminal window open while using the app.

### 4. Launch the Interface
.

Open **Microsoft Edger** or any other browser installed, and on the search bar type: `http://127.0.0.1:8000` - The app will open and you are able to convert the files into markdown format. 

> [!NOTE]
> When you finish using, click on the link on top right and it will stop the python app and close the app session
---

## 💡 Features

**Word to MD Extraction**
Drag and drop a `.docx` file. The backend parses text, isolates embedded images, and automatically repairs complex and merged tables.

**Automated Output & GitHub Portability**
Conversions are written to `C:/temp/Word-to-MD-App/Outputs` automatically.
- Images are saved as PNGs under `Outputs/Images/<doc-name>/`
- The `.md` file uses strict relative paths, so the output directory can be committed directly to GitHub, Azure DevOps, or opened in VS Code with all images resolving natively

**Markdown Editing**
Use the built-in toolbar to format text, inject code blocks, build tables, or add GitHub-style callouts (`[!IMPORTANT]`, `[!NOTE]`).

**Live Preview**
The Visual Preview tab renders syntax highlighting and maps local image paths to simulate the final GitHub render.

**Instant Save**
Clicking **Save** writes your in-browser edits directly back to the `.md` file on disk.

---

## 🔧 Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Failed to Fetch` | Backend is not running or crashed | Check `Logs/app.log` for tracebacks, then restart Step 3 |
| `Address already in use` | A Python process is already bound to port 8000 | Run `taskkill /F /IM python.exe` in PowerShell, then restart the server |
| `Files already in use` | The source `.docx` is open in Word | Close the document in Word before converting |