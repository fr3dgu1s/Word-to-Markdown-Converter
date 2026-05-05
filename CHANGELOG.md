# Changelog

All notable user-facing changes for the Word-to-Markdown Converter are tracked
here.

## 2026-05-05

### Added

- Added Microsoft Purview / MIP protected-file handling through a persistent
  Microsoft Word COM instance. Protected uploads are detected as non-ZIP `.docx`
  files, saved as clean temporary copies through Word, converted by Docling, and
  cleaned up immediately.
- Added `pywin32` as a dependency for Word COM automation.
- Added an in-app GitHub update check. When the local app checkout is behind
  the latest `main` branch on GitHub, the UI shows an update banner with a link
  to compare the local version with the latest online version.
- Added this changelog so users can review what changed before updating.
- Added a `/changelog` page served by the local FastAPI app.

### Changed

- Runtime folders now default to the project/app folder containing `paths.py`.
  `Outputs`, `Outputs\Images`, `Temp`, and `Logs` are created there unless
  `APP_DATA_ROOT` is set in `.env` or the environment.
- Updated README setup and troubleshooting paths to reflect the project-folder
  runtime default.

### Notes

- The update check is best-effort. If the machine is offline or GitHub is not
  reachable, conversion still works and no update banner is shown.
- Existing `.env` values still override defaults. Remove or update
  `APP_DATA_ROOT` in `.env` if you want to use the project-folder runtime
  layout.
