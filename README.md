# Word to MD - Easy Converter 🚀

A professional, local-first AI tool to convert Microsoft Word Documents (`.docx`) into clean, GitHub-style Markdown (`.md`).

---

## ⚠️ Data Governance & Security

**CRITICAL: DATA CLASSIFICATION LIMITATION**

This version of the tool is authorized for **GENERAL / NON-CONFIDENTIAL** files only.

- **Encrypted/Confidential Files:** Files protected by Microsoft Purview (DLP) or sensitivity labels with encryption **will fail to process**. The local engine cannot bypass corporate encryption envelopes in this release.
- **Workaround:** If you have a document authorized for Markdown conversion but currently labeled as Confidential, you must:
  1. Open the file in the Microsoft Word Desktop App.
  2. Ensure you have the rights to export the content.
  3. **Save a Copy** with the classification set to **GENERAL** as a `.docx` file.
  4. Process the unencrypted copy through this tool.
- **Compliance:** Users are responsible for ensuring that content being converted adheres to company data handling and classification policies.

---

## 🛠️ Prerequisites

To run this application, you must have **Python 3.14** installed.

1. **Download:** [Python 3.14 Official Release](https://www.python.org/downloads/windows/)
2. **Verification:** Open PowerShell and type `python --version`. It must show `3.14.x`.

---

## 🚀 Step-by-Step Deployment

Follow these exact steps to get the studio running on your machine:

### 1. Clone or Download

Download this repository to a folder on your local drive (e.g., `C:\temp\Word-to-MD-App`).

### 2. Install the AI Engine (One-time Setup)

Open your terminal in the project folder and run:
```bash
pip install -r requirements.txt
```

### 3. Start the Backend Server

In the same terminal window, run:
```bash
python -m uvicorn server:app
```

Wait for the message: `Application startup complete.` You must keep this window open while using the app.

### 4. Launch the Interface

Navigate to the folder in Windows File Explorer and double-click `index.html`.  
The app will open in your default browser at `http://127.0.0.1:8000`.

---

## 💡 Usage Guide

- **Word to MD:** Drag and drop a `.docx` file into the dashed area. The AI will extract text, headers, and complex tables.
- **MD Viewer:** Drag and drop an existing `.md` file to instantly visualize it with professional formatting.
- **Copy/Save:** Use the top-right buttons to copy the result or save a new `.md` file to your drive.

---

## 🔧 Support & Troubleshooting

- **"Failed to Fetch":** Your Python terminal is closed. Restart Step 3.
- **"Address already in use":** Close all terminals and run `taskkill /F /IM python.exe` in PowerShell, then restart the server.
- **"Files already in use":** Close the open Word Document before trying to convert to MD format.