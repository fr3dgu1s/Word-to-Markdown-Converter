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
C:/temp/Word-to-MD-App/Outputs
```

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