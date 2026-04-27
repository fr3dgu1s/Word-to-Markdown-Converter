# Word to MD — Easy Converter 🚀

> An easy way to convert your Functional Specs into Markdown

A local-first tool to convert Microsoft Word documents (`.docx`) into clean, GitHub-style Markdown (`.md`).

---

## ⚠️ Data Governance & Security

> [!IMPORTANT]
> This tool can only convert files tagged as **GENERAL / NON-CONFIDENTIAL**.

Files protected by Microsoft Purview (DLP) or sensitivity labels with encryption will fail to process — the local engine cannot decrypt corporate encryption envelopes.

**Workaround for encrypted documents:**

If you have a document authorized for Markdown conversion but currently labeled Confidential:

1. Open the file in the **Microsoft Word Desktop App**
2. Confirm you have rights to export the content
3. Select **File → Save a Copy**, set the classification to **GENERAL**, and save as `.docx`
4. Process the unencrypted copy through this tool

> Users are responsible for ensuring converted content adheres to company data handling and classification policies.

---

## 🪟 Windows setup (recommended)

The app routes all runtime files through `C:/temp/W2MD` so it never depends on
per-user paths. The setup script bootstraps that layout, the `.env` file, and
the C# MIP helper in one go.

### Step 1 — Install prerequisites

- Python 3.10+ (verify with `python --version`)
- .NET SDK 8 or newer (verify with `dotnet --version`)
- Microsoft Visual C++ Redistributable (x64)
- Optional: an Azure account with access to Microsoft Graph and Microsoft
  Purview / MIP if you plan to convert protected cloud files

### Step 2 — Run setup

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-windows.ps1
```

This creates `C:/temp/W2MD`, copies `.env.example` → `.env` if missing,
publishes the MIP helper, and copies `MipHelper.exe` to
`C:/temp/W2MD/MipHelper/MipHelper.exe`.

### Step 3 — Install Python dependencies

```powershell
python -m pip install -r requirements.txt
```

### Step 4 — Start the server

```powershell
python -m uvicorn server:app
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

### Default runtime folders

| Path | Purpose |
| --- | --- |
| `C:/temp/W2MD/Outputs/Single` | Single-file conversions |
| `C:/temp/W2MD/Outputs/Batch`  | Batch conversion outputs |
| `C:/temp/W2MD/Outputs/Images` | Extracted images |
| `C:/temp/W2MD/Temp/Cloud`     | Cloud-mode downloads |
| `C:/temp/W2MD/Temp/Protected` | Decrypted MIP working copies |
| `C:/temp/W2MD/Logs`           | `app.log` and rotated history |
| `C:/temp/W2MD/MipHelper`      | Published `MipHelper.exe` |

Override any of these by editing `.env` (`APP_DATA_ROOT`, `OUTPUTS_ROOT`,
`TEMP_ROOT`, `LOGS_ROOT`, `MIP_HELPER_ROOT`, `MIP_HELPER_PATH`).

### Protected cloud workflow

1. Try Microsoft Graph (MSAL / Azure CLI) first — fastest path.
2. If Graph returns 403 or the file is RMS/IRM-protected, fall back to the
   MIP helper using the signed-in user's credentials.
3. If MIP allows decrypt/export, convert the working copy with Docling.
4. If MIP denies access, return:
   *“Microsoft Purview did not allow this app to decrypt or export the file
   with the current user's permissions.”*
5. The whole pipeline is bounded by a 120-second hard timeout. On timeout
   the app cancels, deletes temp files, and returns:
   *“The conversion exceeded the 2-minute limit and was cancelled.”*

---

## 🛠️ Prerequisites

Python 3.14 must be installed.

**Method 1**

- Download: https://www.python.org/downloads/windows/
- Verify: Run `python --version` → must show `3.14.x`

**Method 2 (Recommended)**

- Open PowerShell and type `python`
- This will launch the Microsoft Store and install Python automatically
- Verify with `python --version`

---

## 🚀 Setup & Deployment

### 1. Clone or Download

Download this repository to a local folder (e.g., `C:\temp\Word-to-MD-App`).

### 2. Install Dependencies (one-time)

```bash
python -m pip install -r requirements.txt
```

### 3. Start the Backend Server

```bash
python -m uvicorn server:app
```

Wait for: `Starting FastAPI server on http://127.0.0.1:8000`

> [!NOTE]
> Keep this terminal window open while using the app.

### 4. Launch the Interface

Open your browser and go to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## ▶ Silent Launch (No Command Line)

If you want to run the app without opening a terminal window:

1. Double-click `launch_silent.vbs`
2. It starts Python in the background and opens the web UI automatically
3. No command prompt window is shown

To stop the backend without terminal commands:

1. Double-click `stop_silent.vbs`

You can still use the in-app **Stop Python App** button as before.

---

## 🛑 Closing the Application

To stop the application:

- Use the **Stop** link/button in the top-right of the app UI
- This will gracefully shut down the Python server and end the session

> [!NOTE]
> You do **not** need to manually cancel or close the terminal.

---

## 💡 Features

### Word to MD Extraction

Drag and drop a `.docx` file. The backend parses text, extracts images, and repairs complex or merged tables.

### Automated Output & GitHub Portability

Outputs are saved to:

```
C:/temp/W2MD/Outputs
```

- Single conversions → `Outputs/Single/`
- Batch conversions → `Outputs/Batch/`
- Images → `Outputs/Images/<doc-name>/`
- Markdown uses relative paths → ready for GitHub / ADO / VS Code

### Markdown Editing

Use the built-in toolbar to:

- Format text
- Insert code blocks
- Create tables
- Add GitHub callouts (`[!IMPORTANT]`, `[!NOTE]`)

### Live Preview

Preview renders Markdown with syntax highlighting and local image mapping to simulate GitHub output.

### Instant Save

Click **Save** to persist changes directly to the `.md` file.

### Protected Document Support (DLP)

For protected `.docx` files, the app now uses a separate module that:

1. Detects protection on the uploaded file
2. Performs an **MSAL sign-in** using the current user identity
3. Attempts to open and re-save an accessible copy via local Microsoft Word (only if user has rights)
4. Converts the accessible copy to Markdown

If the user does not have access rights, conversion is denied.

---

## 🔐 MSAL Configuration for Protected Files

Protected file conversion now supports two secure delegated identity options:

1. **Recommended for internal users**: sign in with Azure CLI (`az login`)
2. **Fallback**: MSAL interactive login using app registration (`MSAL_CLIENT_ID`)

### Option A (Recommended): Azure CLI identity (no app config in this app)

Run once in PowerShell:

```powershell
az login
```

The app will reuse the currently signed-in user token to validate identity.

### Option B: MSAL app registration fallback

Set these environment variables before starting the server:

- `MSAL_CLIENT_ID` (required): App registration client ID
- `MSAL_TENANT_ID` (optional): Tenant ID or `organizations`
- `MSAL_SCOPES` (optional): comma-separated scopes, default `User.Read`
- `MSAL_CACHE_DIR` (optional): local folder for MSAL token cache

Example (PowerShell):

```powershell
$env:MSAL_CLIENT_ID = "<your-app-client-id>"
$env:MSAL_TENANT_ID = "organizations"
```

The app registration must allow delegated user sign-in and Microsoft Graph `User.Read` permission.

---

## 🔧 Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Failed to Fetch` | Backend not running | Check `Logs/app.log` and restart |
| `Address already in use` | Port 8000 in use | Run `taskkill /F /IM python.exe` |
| Files already in use | Word file open | Close the file before converting |

---

## 📦 Third-Party Dependencies

This project uses [Docling](https://github.com/DS4SD/docling) to convert structured documents into Markdown with high fidelity. Docling is an open-source document processing toolkit developed by Red Hat.

Docling is licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

Docling enables local, privacy-first document processing without requiring cloud-based inference.

---

## 🔮 Future Improvements

We plan to introduce a native launcher in future releases, removing the need to start the application via Python/terminal.