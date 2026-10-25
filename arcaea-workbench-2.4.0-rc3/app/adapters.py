"""Replaceable CLI interfaces; bundled frozen core is default."""
import json,math,subprocess,sys
from pathlib import Path
from .common import ROOT,atomic,digest_bytes,digest
from . import sequence,recognition,aff_compat
CORE=ROOT/'core'
def preprocess(source):
 sys.path.insert(0,str(CORE/'engine'))
 from audit import analyze
 from reconstruct import build
 doc,audit=analyze(source);rec=build(doc)
 if audit.get('warnings'):raise ValueError('AFF parser warnings: '+str(audit['warnings']))
 traits=[]
 for u in rec['long_objects']:
  counts={k:None if v['times_ms'] is None else len(v['times_ms']) for k,v in u['combo_candidates'].items()}
  length=u.get('base_curve_length',0 if u['kind']=='hold' else None)
  traits.append({'source_event_id':u['source_event_id'],'kind':u['kind'],'start_ms':u['start_ms'],'end_ms':u['end_ms'],'nominal_tick_counts':counts,'nominal_tick_schedules':u['combo_candidates'],'geometric_length':length,'minimum_required_movement':None,'negligible_geometry_candidate':u['kind']=='arc' and length is not None and length<=.001,'dense_short_hold_candidate':u['kind']=='hold' and 0<u['end_ms']-u['start_ms']<=200 and max((x for x in counts.values() if x is not None),default=0)>=12,'interpretation_status':'reference_hypothesis_not_judgement_proof'})
 return {'format':'arcaea-chart-facts/1','source_sha256':doc['sha256'],'processor':'frozen-reconstruct-1.2 + facts-2.0','source_events':doc['events'],'groups':doc['groups'],'header':doc.get('header'),'traits':traits,'press_candidates':rec['press_candidates'],'issues':rec['issues'],'summary':rec['summary'],'definitions':{'negligible_geometry_threshold':.001,'dense_short_hold_max_ms':200,'dense_short_hold_min_ticks':12},'limitations':['No minimum-movement judgement solver. Near-stationary flag tests geometric length only.','Nominal tick counts are inherited reference hypotheses; timing changes and game tolerances require review.']}
def resolve(settings,kind):
 raw=settings.get(kind+'_script','')
 p=(ROOT/raw).resolve() if raw and not Path(raw).is_absolute() else Path(raw).resolve() if raw else CORE/('analyze_aff.py' if kind=='allocation' else 'color_aff.py')
 if not p.is_file():raise ValueError('Missing algorithm script: '+str(p))
 return p
def signature(settings,kind):
 p=resolve(settings,kind);files=sorted((p.parent/'engine').glob('*.py'))+[p]
 files+=list((ROOT/'app').glob('*.py'))
 profile=(settings.get('recognition_profile') or str(ROOT/'defaults/recognition.json')) if kind=='allocation' else None
 config=recognition.validate(json.loads(Path(profile).read_text(encoding='utf-8-sig'))) if profile else None
 return digest({'recognition_profile':config,'files':{str(f):digest_bytes(f.read_bytes()) for f in files},'beam':settings.get('beam_width',128) if kind=='allocation' else None})
def invoke(args):
 p=subprocess.run([sys.executable,*map(str,args)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=900)
 if p.returncode:raise ValueError((p.stderr or p.stdout or 'Algorithm failed')[-6000:])
 return p.stdout

def allocate(source,out,settings):
 args=[resolve(settings,'allocation'),source,'-o',out,'--beam-width',str(settings.get('beam_width',128))]
 profile=settings.get('recognition_profile')
 if profile:
  config=recognition.validate(json.loads(Path(profile).read_text(encoding='utf-8-sig')));atomic(Path(out).parent/'recognition-profile.json',config)
  if config.get('allocator_preferences'):
   prefs=Path(out).parent/'allocator-preferences.json';atomic(prefs,config['allocator_preferences']);args+=['--preferences',prefs]
 return invoke(args)
def compatible(base,edited):
 keys=('unit_id','kind','start_ms','end_ms','start_position','end_position','source_event_ids','action_ids','arc_color','fresh_press')
 def facts(u):return {k:u.get(k) for k in keys}
 old={u['unit_id']:u for u in base['units']};new={u['unit_id']:u for u in edited['units']}
 return old.keys()==new.keys() and all(facts(u)==facts(new[k]) and new[k].get('geometry_mode')==('source' if u['kind']=='arc' else 'linear') and not new[k].get('waypoints') for k,u in old.items())
def preview(source,base,s,out,settings):
 errors=[d for d in sequence.diagnostics(s) if d['level']=='error']
 if errors:raise ValueError('Preview blocked by execution conflicts: '+errors[0]['message'])
 if not compatible(base,s) and not arc_compatible(base,s):raise ValueError('Structural edits cannot be represented by the frozen note-coloring adapter. Use Export execution overlay; source AFF is unchanged.')
 import copy
 converted=copy.deepcopy(base);hands={u['unit_id']:u['hand'] for u in s['units']}
 for u in converted['units']:u['hand']=hands[u['unit_id']]
 # Explicit editor review masks supplement, rather than silently erase, original candidates.
 converted.setdefault('visual_review_markers',[])
 for u in s['units']:
  if u['source_event_ids'] and sequence.excluded(s,u['start_ms']):converted['visual_review_markers'].append({'start_ms':u['start_ms'],'position':u['start_position'],'source_event_ids':u['source_event_ids']})
 tmp=Path(out).with_suffix('.input.json');atomic(tmp,converted)
 try:
  result=invoke([resolve(settings,'visualization'),source,tmp,'-o',out])
  overlay_result=None
  if any(u['kind']=='arc' and u['geometry_mode']=='polyline' for u in s['units']):overlay_result=overlay(out,s,out,arcs_only=True)
  changes=aff_compat.normalize_file(out)
  return {'exporter':result,'overlay':overlay_result,'group_compatibility':changes}
 finally:tmp.unlink(missing_ok=True)
def overlay(source,s,out,arcs_only=False):
 """No-input execution geometry, including manually created operations."""
 raw=Path(source).read_bytes();statements=[]
 for u in s['units']:
  if arcs_only and u['kind']!='arc':continue
  color={'L':0,'R':1,None:2}[u['hand']];ps=sequence.points(u,s)
  for a,b in zip(ps,ps[1:]):
   if round(b[0])<=round(a[0]):continue
   statements.append(f'arc({round(a[0])},{round(b[0])},{a[1]:.8f},{b[1]:.8f},s,{(8.5*a[2]-1)/4.5:.8f},{(8.5*b[2]-1)/4.5:.8f},{color},none,false);')
  t=u['start_ms'];x,y=u['start_position'];y=(8.5*y-1)/4.5
  for a,b in [((x-.02,y),(x,y+.03)),((x,y+.03),(x+.02,y)),((x+.02,y),(x,y-.03)),((x,y-.03),(x-.02,y))]:
   statements.append(f'arc({round(t)},{round(t)},{a[0]:.8f},{b[0]:.8f},s,{a[1]:.8f},{b[1]:.8f},{color},none,false);')
 sys.path.insert(0,str(CORE/'engine'))
 from audit import analyze
 doc,_=analyze(Path(source));timing='\n'.join('timing('+','.join(map(str,e['args']))+');' for e in doc['events'] if e['kind']=='timing' and e['group']==0)
 atomic(out,raw+b'\n'+('timinggroup(noinput){\n'+timing+'\n'+'\n'.join(statements)+'\n};\n').encode())
 changes=aff_compat.normalize_file(out)
 return {'mode':'noinput_execution_overlay','original_preserved':not bool(changes),'source_file_unchanged':True,'group_compatibility':changes,'runtime_verified':False,'inter_operation_connections':False}


def arc_compatible(base,s):
 """Arc execution geometry may differ while original note coloring stays valid."""
 import copy
 adjusted=copy.deepcopy(s);old={u['unit_id']:u for u in base['units']}
 for u in adjusted['units']:
  b=old.get(u['unit_id'])
  if b and u['kind']=='arc':
   u.update(start_position=b['start_position'],end_position=b['end_position'],geometry_mode='source',waypoints=[])
 return compatible(base,adjusted)

def recognize_arcs(source,s,settings):
 config=recognition.validate(json.loads(Path(settings.get('recognition_profile') or ROOT/'defaults/recognition.json').read_text(encoding='utf-8-sig')))
 if not config['arc_path_enabled']:return s,None
 try:from .arc_solver import recognize
 except ImportError as e:raise ValueError('Arc recognition needs NumPy and SciPy. Run python -m pip install -r requirements.txt from the Workbench folder.') from e
 return recognize(source,s,config)
