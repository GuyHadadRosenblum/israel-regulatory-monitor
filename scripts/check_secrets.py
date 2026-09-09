"""Check tracked text files without printing secret values."""
from pathlib import Path
import re
import subprocess
import sys

patterns=[re.compile(r'-----BEGIN ' + r'(?:RSA )?PRIVATE KEY-----'),re.compile(r'\b\d{8,12}:' + r'[A-Za-z0-9_-]{30,50}\b'),re.compile(r'\bAIza' + r'[A-Za-z0-9_-]{30,}\b')]
files=subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
failures=[]
for name in filter(None,files):
    path=Path(name)
    if path.suffix in ('.png','.gif','.pdf','.docx'):
        continue
    text=path.read_text(encoding='utf-8',errors='replace')
    if any(p.search(text) for p in patterns):failures.append(name)
if failures:
    print('Potential secret in: '+', '.join(failures))
    sys.exit(1)
print('No private keys or supported token patterns in tracked files.')
