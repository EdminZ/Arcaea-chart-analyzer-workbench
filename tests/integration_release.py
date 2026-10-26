"""Reproducible release check; temporary workspaces do not touch user assets."""
import csv,json,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import model2,signals,sequence
from app.common import ROOT,read,atomic,digest_bytes
from app.store import Store

def main():
 report={};start=time.monotonic()
 with tempfile.TemporaryDirectory() as temp:
  root=Path(temp);store=Store(root/'workspace');c=store.scan(ROOT/'examples')['imported'][0];store.import_sequence(c,ROOT/'examples/workbench-demo_2.sequence.json');original=store.source(c).read_bytes();t=time.monotonic();metrics=store.calculate(c);report['synthetic_demo_seconds']=time.monotonic()-t;report['synthetic_demo_metrics']=metrics;r=read(store.folder(c)/'metrics.json');points=model2.trajectory_points(r);assert len(points)==len(r['series']);report['trajectory_points']=len(points);store.export([c],root/'export');assert (root/'export/workbench-demo_2.invalid-volume.json').exists();assert store.source(c).read_bytes()==original
  # Invalid activation cannot replace active; draft comparison cannot overwrite result.
  before=(store.folder(c)/'metrics.json').read_bytes();d=store.active_definition();d['parameters']['tap_scale']=2;store.trial(c,d);assert (store.folder(c)/'metrics.json').read_bytes()==before
  source=root/'batch';source.mkdir()
  for i in range(100):(source/f'test_{i}.aff').write_text(f'AudioOffset:{i}\n-\ntiming(0,120,4);\n(0,1);\n(1000,4);\n',encoding='utf-8')
  ids=store.scan(source)['imported'];assert len(ids)==100
  for cid in ids:
   units=[]
   for t,x in [(0,0),(1000,1)]:
    u=sequence.new_unit(t);u.update(hand='L',start_position=[x,0],end_position=[x,0]);units.append(u)
   s={'format':sequence.FORMAT,'sha256':cid,'units':units,'arc_geometry':[],'exclusions':[],'flow_context':{'resets':[]},'multitouch':{'episodes':[]}};store.save_sequence(cid,s);store.calculate(cid)
  store.export(ids,root/'batch-export');rows=list(csv.DictReader((root/'batch-export/summary.csv').read_text(encoding='utf-8-sig').splitlines()));assert len(rows)==100 and all(r['status']=='current' for r in rows);assert len(list((root/'batch-export').glob('*.invalid-volume.json')))==100;report['batch_current_rows']=100
 report['total_seconds']=time.monotonic()-start;print(json.dumps(report,indent=2));return report
if __name__=='__main__':main()
