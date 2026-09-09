"""Local single-user API. Run one uvicorn worker, bound to loopback."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
DATA = ROOT / 'data'
JOBS = DATA / 'web-jobs'
REPORT = DATA / 'processed' / 'unified_legislation_log.xlsx'
app = FastAPI(title='Regulatory Monitor', version='1.0.0')
pool = ThreadPoolExecutor(max_workers=1)
guard = Lock()
active = None

@app.middleware('http')
async def local_origin(request: Request, call_next):
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin:
        from urllib.parse import urlparse
        if urlparse(origin).netloc != request.headers.get('host'):
            return JSONResponse({'detail': 'Cross-origin write denied'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

def clean(value):
    return '' if pd.isna(value) or str(value) in ('N/A', 'nan', 'None') else str(value)

def records():
    if not REPORT.exists():
        return []
    output = []
    for i, row in enumerate(pd.read_excel(REPORT).to_dict('records')):
        status = {'Verified Match': 'matched', 'Portal Entry Only': 'missing', 'Official Submission Only': 'submission', 'Submission (Unverified)': 'review'}.get(row.get('Processing_Status'), 'review')
        ria = any(clean(row.get(k)) not in ('', 'No', 'לא') for k in ('RIA_Submission_Full_Report_URL', 'RIA_Portal_Standard_URL'))
        exemption = any(clean(row.get(k)) not in ('', 'No', 'לא') for k in ('RIA_Portal_Exemption_URL', 'RIA_Submission_Exemption_URL'))
        output.append({'id': str(i), 'title': clean(row.get('נושא')) or clean(row.get('Regulation_Title')),
            'ministry': clean(row.get('Responsible_Ministry')), 'date': clean(row.get('Portal_Publish_Date')) or clean(row.get('Submission_Date')),
            'status': status, 'score': float(row.get('Similarity_Score', 0)) if pd.notna(row.get('Similarity_Score')) else 0,
            'ria': 'exempt' if exemption else 'available' if ria else 'missing',
            'summary': clean(row.get('סיכום AI')) or clean(row.get('Portal_Description')),
            'url': clean(row.get('Portal_Web_Page')), 'submissionDate': clean(row.get('Submission_Date'))})
    return output

@app.get('/api/health')
def health():
    return {'status': 'ok', 'mode': 'local', 'googleConfigured': bool(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')), 'aiEnabled': os.environ.get('ENABLE_AI', 'false').lower() == 'true'}

@app.get('/api/regulations')
def regulations():
    return records()

class RunRequest(BaseModel):
    since: date

def read_job(job_id):
    if not job_id.isalnum():
        raise HTTPException(404, 'Run not found')
    path = JOBS / f'{job_id}.json'
    if not path.exists():
        raise HTTPException(404, 'Run not found')
    return json.loads(path.read_text(encoding='utf-8'))

def save_job(job):
    JOBS.mkdir(parents=True, exist_ok=True)
    path = JOBS / f"{job['id']}.json"
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)

def execute(job, since):
    global active
    job['status'] = 'running'
    save_job(job)
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        with (JOBS / f"{job['id']}.log").open('w', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-u', '-m', 'src.master_sync', '--since', since], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
            for line in process.stdout:
                log.write(line)
                log.flush()
                if line.startswith('[STEP '):
                    job['stage'] = int(line[6]) - 1
                    save_job(job)
            code = process.wait()
        if code:
            raise RuntimeError(f"שלב {job['stage'] + 1} נכשל. בדקו את ההרשאות והחיבור למקורות; הלוג נשמר מקומית.")
        job.update(status='completed', stage=5)
    except Exception as exc:
        job.update(status='failed', error=str(exc))
    finally:
        job['finishedAt'] = datetime.now(timezone.utc).isoformat()
        save_job(job)
        with guard:
            active = None

@app.post('/api/runs', status_code=202)
def start_run(body: RunRequest):
    global active
    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        raise HTTPException(422, 'יש להגדיר GOOGLE_APPLICATION_CREDENTIALS בקובץ .env המקומי לפני ניטור חי.')
    if body.since > date.today():
        raise HTTPException(422, 'תאריך ההתחלה אינו יכול להיות בעתיד')
    with guard:
        if active:
            raise HTTPException(409, 'כבר מתבצעת הרצה')
        job = {'id': uuid4().hex, 'status': 'queued', 'stage': 0, 'startedAt': datetime.now(timezone.utc).isoformat()}
        active = job['id']
        save_job(job)
    pool.submit(execute, job, body.since.isoformat())
    return job

@app.get('/api/runs/{job_id}')
def run_status(job_id: str):
    job = read_job(job_id)
    if job['status'] in ('running', 'queued') and active != job_id:
        job.update(status='failed', error='השרת הופעל מחדש. יש להתחיל הרצה חדשה.')
    return job

@app.get('/api/export')
def export():
    if not REPORT.exists():
        raise HTTPException(404, 'Run monitoring first')
    return FileResponse(REPORT, filename='regulatory-monitor.xlsx')

@app.post('/api/monday')
async def monday(file: UploadFile = File(...)):
    payload = await file.read(10 * 1024 * 1024 + 1)
    if len(payload) > 10 * 1024 * 1024:
        raise HTTPException(413, 'הקובץ גדול מ־10 MB')
    if not (file.filename or '').lower().endswith('.xlsx'):
        raise HTTPException(422, 'יש להעלות קובץ Excel מסוג xlsx')
    try:
        from zipfile import ZipFile
        with ZipFile(io.BytesIO(payload)) as archive:
            if sum(x.file_size for x in archive.infolist()) > 50 * 1024 * 1024:
                raise ValueError('Expanded file too large')
        df = pd.read_excel(io.BytesIO(payload), header=2)
        df.columns = df.columns.astype(str).str.strip()
        if 'תאריך פנייה רשמית' not in df.columns:
            raise ValueError('נדרש ייצוא Monday עם כותרות בשורה השלישית ועמודת תאריך פנייה רשמית')
        starts = pd.to_datetime(df['תאריך פנייה רשמית'], errors='coerce', dayfirst=True)
        if 'תאריך פנייה רשמי מעוכב מעודכן' in df:
            starts = pd.to_datetime(df['תאריך פנייה רשמי מעוכב מעודכן'], errors='coerce', dayfirst=True).fillna(starts)
        decisions = df.get('האם הוחלט לייעץ', pd.Series('', index=df.index)).fillna('')
        df['מועד יעד מחושב'] = starts + pd.to_timedelta(decisions.map(lambda x: 74 if str(x).strip() == 'הוחלט לייעץ' else 14), unit='D')
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter', engine_kwargs={'options': {'strings_to_formulas': False, 'strings_to_urls': False}}) as writer:
            df.to_excel(writer, index=False, sheet_name='Tracking')
            writer.sheets['Tracking'].right_to_left()
            writer.sheets['Tracking'].set_column(0, len(df.columns), 25)
        return StreamingResponse(io.BytesIO(out.getvalue()), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': 'attachment; filename="monday-tracking.xlsx"'})
    except Exception as exc:
        raise HTTPException(422, f'לא ניתן לעבד את הקובץ: {exc}') from exc

dist = ROOT / 'frontend' / 'dist'
if dist.exists():
    app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
