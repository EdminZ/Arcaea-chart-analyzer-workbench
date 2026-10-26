import hashlib,json,os,tempfile,uuid
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def now():return datetime.now(timezone.utc).isoformat()
def digest_bytes(b):return hashlib.sha256(b).hexdigest()
def digest(x):return digest_bytes(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def atomic(p,data):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 raw=data if isinstance(data,bytes) else data.encode('utf-8') if isinstance(data,str) else (json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
 fd,name=tempfile.mkstemp(dir=p.parent,prefix='.writing-')
 try:
  with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  os.replace(name,p)
 finally:
  if os.path.exists(name):os.unlink(name)
def unique():return uuid.uuid4().hex
