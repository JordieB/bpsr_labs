# Windows Quickstart – BP Timer Standalone Client

## Prerequisites

1. **Python 3.11+** installed and added to `PATH`.
2. **WinDivert** driver available (https://reqrypt.org/windivert.html). Administrator rights are required to start packet capture.
3. Clone this repository and install dependencies:
   ```powershell
   git clone https://github.com/JordieB/bpsr-labs.git
   cd bpsr-labs
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .
   pip install -r requirements-dev.txt  # optional, provides FastAPI mock server
   ```

## Configuration

Create a `.env` file or set environment variables:

| Variable | Description |
| --- | --- |
| `BPTIMER_BASE_URL` | Production ingestion base URL (default `https://api.bptimer.com`). |
| `BPTIMER_API_KEY` | API key linked to your BP Timer account. |
| `CAPTURE_FILTER` | WinDivert filter expression (default captures TCP payloads). |
| `LOG_LEVEL` | Python logging level (`INFO`, `DEBUG`, …). |
| `RETRY_MAX` / `RETRY_BACKOFF_SECONDS` | Retry controls for HTTP POSTs. |
| `METRICS_PATH` | Location of generated metrics JSON file (default `metrics.json`). |
| `DRY_RUN` | Set to `true` to print payloads without sending. |

## Running Live Capture

1. Ensure WinDivert driver DLLs (`WinDivert.dll`, `WinDivert.sys`) are accessible (same folder or system path).
2. Launch an elevated PowerShell prompt (Run as Administrator).
3. Start the client:
   ```powershell
   python -m client.run --mode live
   ```
4. The client prints an opt-in banner, then begins capturing. Press `Ctrl+C` to stop. Metrics are written to `metrics.json`.

If WinDivert cannot be opened the client exits with a helpful error—verify administrative rights and driver presence.

## Offline Validation (Recommended)

1. Start the mock BP Timer API:
   ```powershell
   uvicorn offline_test.mock_bptimer:app --reload
   ```
2. In a separate shell, run the replay pipeline:
   ```powershell
   python -m client.run --mode replay --input offline_test/samples/single_boss.jsonl --target mock
   ```
3. Observe `200 OK` responses in the mock server output. Payloads are logged, and `metrics.json` reflects processed events.

Alternatively you can use the helper script:
```powershell
python -m offline_test.replay --dry-run
```
which prints the JSON body that would be POSTed without touching the network.

## Troubleshooting

- **API errors**: Check `metrics.json` and logs for non-200 responses. `DRY_RUN=true` helps inspect payloads.
- **Permission denied (WinDivert)**: Ensure the driver version matches your system architecture and that the process runs elevated.
- **Missing dependencies**: Re-run `pip install -e .` and verify that `httpx`, `fastapi`, and `uvicorn` are installed if using the mock server.

## Uninstalling / Cleanup

- Stop the mock server (`Ctrl+C`).
- Deactivate the virtual environment and remove the repository folder if no longer needed.
- WinDivert driver does not require explicit uninstall unless installed system-wide.
