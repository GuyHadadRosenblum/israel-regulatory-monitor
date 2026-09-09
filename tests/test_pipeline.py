"""Regression tests exercise the original matching/export engine without network."""
import io
from pathlib import Path
from unittest.mock import Mock
import pandas as pd
import pytest
from docx import Document
from fastapi.testclient import TestClient
from src import cross_reference_engine as engine
from src import friendly_table_generator as reports
from src import web_api

def test_jaccard():
    assert engine.get_similarity('א ב', 'ב ג') == pytest.approx(100 / 3)
    assert engine.get_similarity('', 'מסמך') == 0
    assert engine.get_similarity('מילה מילה', 'מילה') == 100

def test_real_engine_and_excel(tmp_path, monkeypatch):
    raw = tmp_path / 'raw'
    processed = tmp_path / 'processed'
    raw.mkdir()
    processed.mkdir()
    for name, value in {'BASE_DATA_DIR':str(tmp_path),'RAW_DIR':str(raw),'PROCESSED_DIR':str(processed),
        'PORTAL_CSV':str(raw/'portal.csv'),'OFFICIAL_SUBMISSIONS_CSV':str(raw/'submissions.csv'),
        'MERGED_XLSX':str(processed/'unified.xlsx')}.items():
        monkeypatch.setattr(engine,name,value)
    doc = Document()
    doc.add_paragraph('תקנות בטיחות באתרי בנייה מחייבות בדיקה תקופתית ותיעוד הדרכת עובדים')
    doc.save(tmp_path/'document.docx')
    pd.DataFrame([
        {'title':'תקנות בטיחות','office':'משרד העבודה','publish_date':'01/09/2026','main_file_url':'','url':'https://example.com/matched','Local_File_Path':'document.docx','legislation_type':'Secondary Legislation'},
        {'title':'תקנות מים','office':'משרד הבריאות','publish_date':'02/09/2026','main_file_url':'','url':'https://example.com/orphan','Local_File_Path':'document.docx','legislation_type':'Secondary Legislation'},
    ]).to_csv(engine.PORTAL_CSV,index=False)
    pd.DataFrame([{engine.T_TITLE:'תקנות בטיחות',engine.T_OFFICE:'משרד העבודה',engine.T_DATE:'2026-09-01',engine.T_FILE:'','Local_File_Path':'document.docx'}]).to_csv(engine.OFFICIAL_SUBMISSIONS_CSV,index=False)
    monkeypatch.setattr(engine,'download_and_track_file',Mock(side_effect=AssertionError('Unexpected network download')))
    engine.run_cross_reference()
    frame = pd.read_excel(engine.MERGED_XLSX)
    assert set(frame.Processing_Status)=={'Verified Match','Portal Entry Only'}
    assert frame.iloc[0].Similarity_Score==100
    monkeypatch.setattr(reports,'INPUT_FILE',engine.MERGED_XLSX)
    monkeypatch.setattr(reports,'OUTPUT_FILE',str(processed/'summary.xlsx'))
    monkeypatch.setattr(reports,'ENFORCEMENT_FILE',str(processed/'enforcement.xlsx'))
    reports.create_friendly_summary()
    assert len(pd.read_excel(reports.OUTPUT_FILE))==2
    monkeypatch.setattr(web_api,'REPORT',Path(engine.MERGED_XLSX))
    rows=web_api.records()
    assert [r['status'] for r in rows]==['matched','missing']

def test_missing_input_raises(tmp_path,monkeypatch):
    monkeypatch.setattr(engine,'PORTAL_CSV',str(tmp_path/'missing.csv'))
    with pytest.raises(FileNotFoundError):engine.run_cross_reference()

def test_api_requires_credentials(monkeypatch):
    monkeypatch.delenv('GOOGLE_APPLICATION_CREDENTIALS',raising=False)
    with TestClient(web_api.app) as client:
        assert client.get('/api/health').status_code==200
        assert client.post('/api/runs',json={'since':'2026-09-01'}).status_code==422
        assert client.post('/api/runs',json={'since':'bad'}).status_code==422
        assert client.post('/api/runs',json={'since':'2026-09-01'},headers={'Origin':'https://untrusted.example'}).status_code==403

def test_monday_upload_and_due_dates():
    buffer=io.BytesIO()
    pd.DataFrame({'נושא':['א','ב'],'תאריך פנייה רשמית':['01/09/2026','01/09/2026'],'האם הוחלט לייעץ':['לא','הוחלט לייעץ']}).to_excel(buffer,index=False,startrow=2)
    with TestClient(web_api.app) as client:
        response=client.post('/api/monday',files={'file':('monday.xlsx',buffer.getvalue())})
        assert response.status_code==200, response.text
        result=pd.read_excel(io.BytesIO(response.content))
        assert result['מועד יעד מחושב'].dt.strftime('%Y-%m-%d').tolist()==['2026-09-15','2026-11-14']
        assert client.post('/api/monday',files={'file':('bad.xlsx',b'not an excel')}).status_code==422

def test_job_failure_is_not_success(tmp_path,monkeypatch):
    monkeypatch.setattr(web_api,'JOBS',tmp_path)
    process=Mock(stdout=iter(['[STEP 2/5] Source failed\n']))
    process.wait.return_value=1
    monkeypatch.setattr(web_api.subprocess,'Popen',Mock(return_value=process))
    job={'id':'abc','stage':0,'status':'queued'}
    web_api.execute(job,'2026-09-01')
    assert web_api.read_job('abc')['status']=='failed'
    assert web_api.read_job('abc')['stage']==1

def test_detail_fetch_failure_is_not_silent():
    from src.legislation_scraper import get_inner_page_data
    driver=Mock()
    driver.get.side_effect=RuntimeError('Connection failed')
    with pytest.raises(RuntimeError,match='Could not read publication'):
        get_inner_page_data(driver,'https://example.com/publication')
