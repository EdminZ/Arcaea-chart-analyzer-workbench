#!/usr/bin/env python3
"""Color an original AFF from a sequence, always backing up the original first."""
import argparse,hashlib,json,os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'engine'))
from sequence_io import validate
from export_colors import export

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('chart',type=Path);p.add_argument('sequence',type=Path);g=p.add_mutually_exclusive_group(required=True);g.add_argument('-o','--output',type=Path);g.add_argument('--in-place',action='store_true');p.add_argument('--backup-dir',type=Path)
    a=p.parse_args();seq=json.loads(a.sequence.read_text(encoding='utf-8'));labels=validate(seq,a.chart)
    out=a.chart if a.in_place else a.output
    if not a.in_place and (out.exists() or out.resolve()==a.chart.resolve()):raise ValueError('Output must be a new file distinct from the source')
    out.parent.mkdir(parents=True,exist_ok=True);backup_dir=a.backup_dir or out.parent/'backups';backup_dir.mkdir(parents=True,exist_ok=True)
    raw=a.chart.read_bytes();digest=hashlib.sha256(raw).hexdigest();backup=backup_dir/(a.chart.stem+'.'+digest[:16]+'.aff')
    if backup.resolve()==a.chart.resolve():raise ValueError('Backup must differ from source')
    if backup.exists():
        if backup.read_bytes()!=raw:raise ValueError('Existing backup has different contents')
    else:
        with backup.open('xb') as f:f.write(raw)
    fd,name=tempfile.mkstemp(prefix='.color-stage-',suffix='.aff',dir=out.parent);os.close(fd);stage=Path(name)
    try:
        checks=export(a.chart,seq,labels,stage)
        if a.chart.read_bytes()!=raw:raise ValueError('Source changed during export; output cancelled')
        os.replace(stage,out)
    finally:
        if stage.exists():stage.unlink()
    print(json.dumps({'colored_aff':str(out),'backup':str(backup),'backup_sha256':digest,'validation':checks},ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError,AssertionError) as e:print('Error: '+str(e),file=sys.stderr);sys.exit(2)
