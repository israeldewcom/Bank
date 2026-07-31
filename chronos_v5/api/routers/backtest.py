# chronos_v5/api/routers/backtest.py
# SECURITY FIX: previously accepted any CSV with no size limit before
# loading it fully into memory via pandas — a straightforward memory-
# exhaustion DoS vector. Now enforces MAX_UPLOAD_BYTES while streaming the
# upload, rejecting oversized files before they're fully read. The temp
# file is also now cleaned up in a finally block instead of leaking on disk
# (delete=False with no removal afterward).
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import FileResponse
from chronos_v5.backtest_engine import BacktestEngine
from chronos_v5.backtest_upload import generate_backtest_pdf
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.models import User
import pandas as pd
import tempfile
import os

router = APIRouter()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB

@router.post("/run")
async def run_backtest(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "Only CSV files accepted")

    tmp_path = None
    total_bytes = 0
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp_path = tmp.name
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, f"File exceeds maximum allowed size of {MAX_UPLOAD_BYTES // (1024*1024)} MB")
                tmp.write(chunk)

        df = pd.read_csv(tmp_path)
        engine = BacktestEngine(df)
        results = engine.run()
        report_path = generate_backtest_pdf(results, "backtest_report.pdf")
        return FileResponse(report_path, media_type='application/pdf', filename='backtest_report.pdf')
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
