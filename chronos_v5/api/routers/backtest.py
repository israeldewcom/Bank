from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import FileResponse
from chronos_v5.backtest_engine import BacktestEngine
from chronos_v5.backtest_upload import generate_backtest_pdf
from chronos_v5.api.dependencies import get_api_key
import pandas as pd
import tempfile
import os

router = APIRouter()

@router.post("/run", dependencies=[Depends(get_api_key)])
async def run_backtest(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "Only CSV files accepted")
    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    df = pd.read_csv(tmp_path)
    engine = BacktestEngine(df)
    results = engine.run()
    report_path = generate_backtest_pdf(results, "backtest_report.pdf")
    return FileResponse(report_path, media_type='application/pdf', filename='backtest_report.pdf')
