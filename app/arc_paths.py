"""Portable AFF-coordinate execution-path assets, separate from source geometry."""
import copy,math
from . import sequence
from .common import digest
FORMAT='arcaea-arc-paths/1'
def validate(data,source_hash=None):
 d=copy.deepcopy(data)
 if d.get('format')!=FORMAT or d.get('coordinate_system')!='AFF' or d.get('time_unit')!='ms':raise ValueError('Expected arcaea-arc-paths/1 with AFF coordinates and ms times')
 h=d.get('source_sha256','')
 if len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('Invalid source SHA256')
 if source_hash and h!=source_hash:raise ValueError('Arc paths belong to a different chart')
 if not isinstance(d.get('paths'),list) or len(d['paths'])>200000:raise ValueError('Invalid paths list')
 seen=set()
 for path in d['paths']:
  uid=path.get('unit_id')
  if not isinstance(uid,str) or not uid or uid in seen:raise ValueError('Path unit IDs must be unique')
  seen.add(uid)
  if not isinstance(path.get('source_event_ids'),list) or any(not isinstance(i,int) or isinstance(i,bool) for i in path['source_event_ids']):raise ValueError('Invalid arc source references')
  if path.get('review_status') not in ('unreviewed','manually_reviewed'):raise ValueError('Invalid review status')
  for key in ('points','source_points'):
   ps=path.get(key)
   if not isinstance(ps,list) or not 2<=len(ps)<=1000000:raise ValueError(key+' needs at least two [time,x,y] points')
   last=None
   for row in ps:
    if not isinstance(row,list) or len(row)!=3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e10 for v in row):raise ValueError('Path points must contain finite [time,x,y] values')
    if last and (row[0]<last[0] or (key=='points' and path['review_status']=='manually_reviewed' and row[0]==last[0] and row[1:]!=last[1:])):raise ValueError('Path times must increase; zero-time spatial jumps are invalid')
    last=row
  if path['points'][0][0]!=path['source_points'][0][0] or path['points'][-1][0]!=path['source_points'][-1][0]:raise ValueError('Execution path must preserve source start/end times')
 return d

def from_sequence(s):
 paths=[]
 def aff(points):
  out=[]
  for t,x,y in points:
   row=[t,x,(8.5*y-1)/4.5]
   if out and abs(t-out[-1][0])<1e-9:
    if math.dist(row[1:],out[-1][1:])<1e-7:continue
   out.append(row)
  return out
 for u in s['units']:
  if u['kind']!='arc':continue
  source=copy.deepcopy(u)
  if u['source_event_ids']:source['geometry_mode']='source'
  paths.append({'unit_id':u['unit_id'],'source_event_ids':u['source_event_ids'],'review_status':'unreviewed','points':aff(sequence.points(u,s,10)),'source_points':aff(sequence.points(source,s,10))})
 return validate({'format':FORMAT,'coordinate_system':'AFF','time_unit':'ms','source_sha256':s['sha256'],'sequence_hash':digest(s),'paths':paths})

def apply(s,data,uid):
 d=validate(data,s['sha256']);path=next(p for p in d['paths'] if p['unit_id']==uid)
 if path['review_status']!='manually_reviewed':raise ValueError('Review this path and mark it manually_reviewed before applying')
 if d.get('sequence_hash')!=digest(s):raise ValueError('Sequence changed since this path asset was created; rebuild/review paths against the current sequence')
 result=copy.deepcopy(s);u=next(u for u in result['units'] if u['unit_id']==uid)
 if u['kind']!='arc' or path['source_event_ids']!=u['source_event_ids']:raise ValueError('Arc source identity changed')
 ps=[[t,x,(1+4.5*y)/8.5] for t,x,y in path['points']]
 if ps[0][0]!=u['start_ms'] or ps[-1][0]!=u['end_ms']:raise ValueError('Arc times changed')
 u.update(geometry_mode='polyline',start_position=ps[0][1:],end_position=ps[-1][1:],waypoints=ps[1:-1])
 if s['units'][next(i for i,v in enumerate(s['units']) if v['unit_id']==uid)]['fresh_press'] and math.dist(u['start_position'],next(v['start_position'] for v in s['units'] if v['unit_id']==uid))>1e-8:raise ValueError('An attached explicit input fixes the arc start position')
 sequence.validate(result)
 errors=[x for x in sequence.diagnostics(result) if x['level']=='error']
 if errors:raise ValueError('Path creates an execution conflict: '+errors[0]['message'])
 return result
