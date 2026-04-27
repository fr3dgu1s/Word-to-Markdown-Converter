# MipHelper

A C# CLI that owns all Microsoft Information Protection (MIP) SDK calls used
by the Python FastAPI app for protected-file round-trip editing.

## Why a separate process?

The Python app cannot link directly against the MIP SDK. Keeping MIP work in a
small .NET CLI gives us:

- Real MIP SDK access (App Onboarding owns identity + label policy).
- A clean process boundary so Python never touches decrypted bytes longer
  than necessary.
- Stable exit codes the Python orchestrator can branch on.

## Commands

```
MipHelper.exe inspect   --input <path>   --metadata <out.json>
MipHelper.exe unprotect --input <path>   --output <working.docx> --metadata <metadata.json> --user <upn>
MipHelper.exe protect   --input <path>   --output <final.docx>   --metadata <metadata.json> --user <upn>
```

## Exit codes

| Code | Meaning                                    |
| ---- | ------------------------------------------ |
| 0    | Success                                    |
| 10   | `inspect`: file is not protected           |
| 20   | Access denied by Purview policy            |
| 30   | Protection could not be reapplied          |
| 99   | Generic helper failure (see stderr)        |

## Build

```
dotnet build MipHelper.csproj -c Release
```

The Python orchestrator looks for the helper in this order:

1. `MIP_HELPER_PATH` env var (absolute path to `MipHelper.exe`).
2. `MIP_HELPER_DIR` env var.
3. Repo-local `MipHelper/bin/Release/net8.0/MipHelper.exe` or `Debug/net8.0/...`.

## App onboarding

Real label / protection enforcement requires an MIP SDK application
registration. Until you complete onboarding the helper will:

- `inspect`: heuristically flag non-ZIP Office files as protected and emit a
  metadata stub.
- `unprotect`: copy the input to the output unchanged.
- `protect`: copy the input to the output unchanged.

This is enough for the Python pipeline to be wired and tested end-to-end. Fill
in the `TODO (MIP SDK)` blocks in `Program.cs` once your tenant has approved
the app and you have a `mip_data` folder with the SDK runtime files.
