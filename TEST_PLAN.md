# Test Plan — File Upload Endpoint (`/api/file/upload`)

## Scope

This plan defines tests for the `/api/file/upload` endpoint added in `server.py`.  
This is a **minimal, aligned testing approach** compliant with P3 (LLM-first) and P8 (iteration): we specify clear, concrete checks, implemented once the test harness decision is finalized.

## Test Capabilities Required

We need a test HTTP client to call the upload endpoint without starting the full production server.

- **Preferred choice:** `httpx` as an async HTTP client (already used by the system).
- Alternative choice: `pytest-asyncio` + `httpx` together if we want pytest fixtures.

To finalize: decide whether to add `pytest` explicitly (besides httpx) and write tests as `test_server.py`, or keep it simple with a single-file `test_upload.py`.

## Key Assertions

### 1. Basic Upload
- **Status:** 200 OK on successful upload.
- **Response JSON:** contains `status: "success"`, `filename` (sanitized), `size`, and `path`.
- **File created:** a file matching the sanitized filename in `UPLOAD_DIR`.
- **Content matches:** bytes written equal what we sent.

### 2. Filename Sanitization
- **Characters replaced:** control characters (ord < 32) and `:"/\\|?*\x7f` are replaced with `_`.
- **Original filename preserved apart from replacements** (no truncation or injection).

### 3. Duplicate Handling
- **First upload:** `file.txt` → `file.txt`.
- **Second upload:** another `file.txt` → `file_1.txt`.
- **Third upload:** another `file.txt` → `file_2.txt`.  
Keep incrementing until a free name is found.

### 4. Security / Constraints
- **Empty filename:** 400 error.
- **Missing `file` field:** 400 error.
- **Directory traversal attempted:** sanitized name should strip or replace `..` and `/` to prevent traversal out of `UPLOAD_DIR`.
- **Size limit??**: the code currently has no size limit; if we add one later, tests should cover 400 above the limit and 200 below.

## Helper Fixtures (if using pytest-asyncio)

- **app:** fixture returning the `Starlette` app (`server.create_app()`).
- **upload_dir:** fixture ensuring `UPLOAD_DIR` exists before tests and is cleaned up afterwards.
  - `yield` before cleanup ensures we handle duplicate testing correctly.

## Run Instructions (once implemented)

```bash
# Ensure httpx is installed
pip install httpx

# If using pytest
pip install pytest pytest-asyncio
pytest tests/test_upload.py -v
```

## Implementation Approach (P8: one transformation)

When we proceed to implement:

1. **Create** `tests/test_server.py` or `tests/test_upload.py`.
2. **Add** `pytest` and `pytest-asyncio` to `pyproject.toml` dependencies.
3. **Implement** minimal but complete tests (1–4 above).
4. **Run** tests; they should pass because the endpoint is already written.
5. **Commit** with version bump and update README.md version history.

## Minimalism Note (P5)

- One test file is sufficient.
- Avoid overly complex fixtures; just ensure `UPLOAD_DIR` isolation.
- Do not test unrelated routes; only focus on `/api/file/upload`.