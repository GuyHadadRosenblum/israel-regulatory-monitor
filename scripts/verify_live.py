"""Read-only live connectivity check; never prints credentials or response bodies."""
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
import requests

def main():
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass
    try:
        response=requests.get('https://www.tazkirim.gov.il/s/?language=iw',timeout=20)
        print('PORTAL_HTTP',response.status_code,flush=True)
    except Exception as exc:
        print('PORTAL_FAILED',type(exc).__name__,flush=True)
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession
    key=os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not key:
        print('SHEETS_NOT_CONFIGURED',flush=True)
        return
    creds=Credentials.from_service_account_file(key,scopes=['https://www.googleapis.com/auth/drive.readonly'])
    session=AuthorizedSession(creds,refresh_timeout=20)
    try:
        response=session.get('https://www.googleapis.com/drive/v3/files',params={'q':"name = 'Regulatory_Monitoring_Log' and trashed = false",'fields':'files(id,name)'},timeout=20)
        print('GOOGLE_HTTP',response.status_code,flush=True)
        if response.ok:print('MATCHING_SHEETS',len(response.json().get('files',[])),flush=True)
    except Exception as exc:
        print('GOOGLE_FAILED',type(exc).__name__,flush=True)

if __name__=='__main__':main()
