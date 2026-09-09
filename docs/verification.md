# Verification on 2026-09-09

## Passed

- Seven Python regression tests: original DOCX matching engine, Hebrew Excel export, result serialization, missing input, credential/input validation, cross-origin request protection, Monday deadline calculations, failed-job reporting and publication-detail failures.
- Three TypeScript unit tests: Jaccard overlap, combined filtering and CSV formula/quote handling.
- TypeScript compilation and Vite production build.
- Browser checks of the new React UI: overview, demonstration completion, search narrowing ten records to one, record detail dialog and text similarity changing when edited.
- Live Google authentication and discovery of the configured submissions spreadsheet.
- The actual Google Sheets fetcher retrieved 91 official submissions into local storage.
- Selenium opened the live legislation portal, found ten publication cards, validated the date/ministry selectors and extracted ten detail fields from one publication.

## Limits

- A full production run over all 91 submissions, including all document downloads, was not executed. Offline integration tests exercise the matching/reporting path with controlled DOCX inputs.
- Paid Vertex AI generation and Telegram delivery were disabled. No live AI quality or delivery claim is made.
- Docker configuration was authored but not run on the development machine because Docker was unavailable. The verified local launch used Python 3.12 and a compiled React frontend.
- Specialized historical Gantt and regulation-table scripts are retained; complete validation requires the organization's original Monday/history export schemas. The new Monday deadline export is tested independently.
- The public demo intentionally simulates collection and AI stages using labelled synthetic records. Its matching sandbox computes a real Jaccard score in the browser.

GitHub Actions provides the current test/build status on each commit. Dependency versions used during the local verification are recorded in `requirements.lock` and `frontend/pnpm-lock.yaml`.
