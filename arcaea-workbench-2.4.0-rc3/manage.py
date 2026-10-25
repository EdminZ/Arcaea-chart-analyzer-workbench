"""Headless commands use the same storage, adapters and metric evaluator as the GUI."""
import argparse,json
from pathlib import Path
from app.store import Store
from app.common import read

def main():
 p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);sub=p.add_subparsers(dest='command',required=True)
 q=sub.add_parser('import');q.add_argument('folder',type=Path)
 sub.add_parser('list')
 q=sub.add_parser('import-songlist');q.add_argument('file',type=Path)
 q=sub.add_parser('import-constants');q.add_argument('file',type=Path)
 for action in ('generate','calculate','preview','recognize-arcs'):
  q=sub.add_parser(action);q.add_argument('chart_ids',nargs='+');q.add_argument('--force',action='store_true') if action=='generate' else None
 q=sub.add_parser('export');q.add_argument('destination',type=Path);q.add_argument('chart_ids',nargs='+');q.add_argument('--include-stale',action='store_true')
 q=sub.add_parser('activate-definition');q.add_argument('file',type=Path)
 q=sub.add_parser('analyze-volume');q.add_argument('chart_id');q.add_argument('--output',type=Path)
 q=sub.add_parser('import-sequence');q.add_argument('chart_id');q.add_argument('file',type=Path)
 a=p.parse_args()
 from app.locking import WorkspaceLock
 lock=WorkspaceLock(a.workspace);s=Store(a.workspace)
 if a.command=='import':result=s.scan(a.folder,print)
 elif a.command=='import-songlist':result=s.import_songlist(a.file)
 elif a.command=='import-constants':result=s.import_constants(a.file)
 elif a.command=='list':result=s.catalog()
 elif a.command=='activate-definition':result=s.activate_definition(read(a.file))
 elif a.command=='analyze-volume':result=s.export_volume(a.chart_id,a.output) if a.output else s.analysis(a.chart_id)
 elif a.command=='import-sequence':result=s.import_sequence(a.chart_id,a.file)
 elif a.command=='export':result=s.export(a.chart_ids,a.destination,a.include_stale)
 else:
  result=[]
  for c in a.chart_ids:
   try:r=s.generate(c,print,a.force) if a.command=='generate' else s.calculate(c) if a.command=='calculate' else s.recognize_arcs(c) if a.command=='recognize-arcs' else s.make_preview(c);result.append({'chart':c,'result':r})
   except Exception as e:result.append({'chart':c,'error':str(e)})
 print(json.dumps(result,ensure_ascii=False,indent=2));lock.close()
if __name__=='__main__':main()
