# MIP-protected file round trip

This app supports converting and editing Microsoft Purview / MIP-protected
Word files when the signed-in user has the right to do so.

## How it works

For every cloud file the API:

1. Resolves and downloads the source file via Microsoft Graph.
2. Asks `MipHelper.exe inspect` whether the file is protected.
3. If **not protected**: runs the existing Docling conversion path.
4. If **protected**:
   - Captures the original sensitivity label and protection metadata.
   - Calls `MipHelper.exe unprotect` to create a decrypted **working copy**
     under a private temp folder.
   - Runs the same Docling-based edit / convert flow.
   - Calls `MipHelper.exe protect` to reapply the original label and
     protection to the edited output.
   - Only then uploads the result back to SharePoint / OneDrive.
   - Always deletes the decrypted working copy and helper temp files.

If MIP denies access at any step, the API returns **HTTP 422** with a
human-readable reason. The edited file is never uploaded if the original
protection cannot be reapplied.

## Required configuration

Copy `.env.example` to `.env` and fill in the values you need.

```
MIP_HELPER_PATH=C:\path\to\MipHelper.exe
MIP_USER_UPN=user@yourtenant.com
```

`MIP_HELPER_PATH` is optional if the helper is at
`MipHelper/bin/Release/net8.0/MipHelper.exe`. `MIP_USER_UPN` is forwarded to
the helper for delegated MIP actions.

## Logging stages

The server logs the following lifecycle events for every cloud file:

| Stage                  | Log line example                        |
| ---------------------- | --------------------------------------- |
| Normal conversion      | `[CONVERT] mode=normal | file=...`      |
| Protected detected     | `[MIP] detected | file=... | label=...` |
| MIP decrypt allowed    | `[MIP] decrypt allowed | working=...`   |
| Edit completed         | `[CONVERT] edit done | chars=...`       |
| Protection reapplied   | `[MIP] reapplied | label=...`           |
| Upload completed       | `[CONVERT] uploaded | url=...`          |
| MIP denied             | `[MIP] denied | reason=...`             |
| Cleanup completed      | `[MIP] cleanup done`                    |

## Constraints

- The MIP helper requires an approved MIP SDK application registration
  (https://aka.ms/mipsdkapponboarding).
- Without onboarding, the helper falls back to a transparent passthrough
  (see [`MipHelper/README.md`](MipHelper/README.md)). That mode is suitable
  for orchestration testing only and must NOT be used to "bypass" labels in
  production.
- The app never strips, downgrades, or rewrites a sensitivity label.
- The app never uploads an edited file when reapplying protection fails.
