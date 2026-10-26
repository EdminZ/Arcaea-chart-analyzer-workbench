"""Editable execution document. Original AFF references never authorize chart edits."""
import copy,math
from .common import digest,unique
FORMAT='arcaea-editable-sequence/2'
KINDS=('floor_tap','sky_tap','wide_sky_tap','hold','arc','contact','waypoint')
def convert(base):
 s=copy.deepcopy(base);s['format']=FORMAT;s['baseline_structure_sha256']=base.get('structure_sha256');s.pop('structure_sha256',None)
 s['exclusions']=[];s['review_notes']='';s['baseline_summary']=s.pop('summary',{})
 for u in s['units']:
  u['origin']='allocation';u['role']='waypoint' if u['kind']=='waypoint' else 'required_contact';u['geometry_mode']='source' if u['kind']=='arc' else 'linear';u['waypoints']=[]
 return s
def fingerprint(s):return digest(s)
def new_unit(t=0):
 return {'unit_id':'manual:'+unique(),'kind':'contact','start_ms':t,'end_ms':t,'hand':None,'start_position':[.5,0],'end_position':[.5,0],'source_event_ids':[],'action_ids':[],'arc_color':None,'fresh_press':True,'origin':'manual','role':'required_contact','geometry_mode':'linear','waypoints':[]}
def validate(s):
 if s.get('format')!=FORMAT:raise ValueError('Expected editable sequence format /2')
 ids=set()
 def num(v):
  if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e10:raise ValueError('Times/coordinates must be finite reasonable numbers')
 def pos(v):
  if not isinstance(v,list) or len(v)!=2:raise ValueError('Position must be [x,y]')
  for n in v:num(n)
 if len(s['units'])>200000:raise ValueError('Too many operations')
 for u in s['units']:
  if not isinstance(u['unit_id'],str) or not u['unit_id'] or u['unit_id'] in ids:raise ValueError('Unit IDs must be unique strings')
  ids.add(u['unit_id'])
  if u['kind'] not in KINDS or u['hand'] not in ('L','R',None):raise ValueError('Invalid kind or hand')
  for k in ['start_ms','end_ms']:num(u[k])
  if u['end_ms']<u['start_ms']:raise ValueError('End precedes start: '+u['unit_id'])
  for k in ['start_position','end_position']:pos(u[k])
  if u.get('arc_activation','auto') not in ('auto','count','skip'):raise ValueError('arc_activation must be auto, count or skip')
  if not isinstance(u['fresh_press'],bool):raise ValueError('fresh_press must be boolean')
  if u['role'] not in ('required_contact','waypoint'):raise ValueError('Invalid role')
  if u['geometry_mode'] not in ('source','linear','polyline'):raise ValueError('Invalid geometry mode')
  last=u['start_ms']
  for point in u.get('waypoints',[]):
   if len(point)!=3:raise ValueError('Waypoint is [time_ms,x,y]')
   for n in point:num(n)
   if not last<=point[0]<=u['end_ms']:raise ValueError('Waypoints must be in time order within operation')
   last=point[0]
  if u['role']=='waypoint' and (u['fresh_press'] or u['start_ms']!=u['end_ms']):raise ValueError('A movement waypoint is instantaneous and cannot count as a press')
  if u['geometry_mode']=='source':
   geom={g['id']:g for g in s.get('arc_geometry',[])}
   if not u['source_event_ids'] or any(i not in geom for i in u['source_event_ids']):raise ValueError('Missing source arc geometry')
 for e in s.get('exclusions',[]):
  num(e['start_ms']);num(e['end_ms'])
  if e['end_ms']<e['start_ms']:raise ValueError('Exclusion end precedes start')
  if e.get('status') not in ('candidate','confirmed','dismissed'):raise ValueError('Invalid interval status')
 return s

def excluded(s,a,b=None):
 b=a if b is None else b
 return any(e['status']=='confirmed' and e['start_ms']<=b and e['end_ms']>=a for e in s.get('exclusions',[]))
def diagnostics(s):
 validate(s);out=[]
 for u in s['units']:
  if u['hand'] is None and not excluded(s,u['start_ms'],u['end_ms']):out.append({'level':'warning','unit_id':u['unit_id'],'message':'Unassigned operation'})
 for u in s['units']:
  if u.get('geometry_mode')!='source' and not excluded(s,u['start_ms'],u['end_ms']):
   ps=points(u,s)
   if any(a[0]==b[0] and math.dist(a[1:],b[1:])>1e-9 for a,b in zip(ps,ps[1:])):out.append({'level':'error','unit_id':u['unit_id'],'message':'Internal zero-time displacement in manual geometry'})
 for h in ('L','R'):
  items=sorted((u for u in s['units'] if u['hand']==h and not excluded(s,u['start_ms'],u['end_ms'])),key=lambda u:(u['start_ms'],u['unit_id']))
  end=None;last=None
  for u in items:
   if end is not None and (u['start_ms']<end or u['start_ms']==last['start_ms']):out.append({'level':'error','unit_id':u['unit_id'],'message':h+' reservation conflict with '+last['unit_id']})
   elif last and u['start_ms']==last['end_ms'] and math.dist(u['start_position'],last['end_position'])>1e-9:out.append({'level':'error','unit_id':u['unit_id'],'message':'Zero-time displacement from '+last['unit_id']})
   if end is None or u['end_ms']>=end:end=u['end_ms'];last=u
 return out

def points(u,s,step=20):
 a,b=u['start_ms'],u['end_ms']
 if u.get('geometry_mode')=='source':
  import sys
  from .common import ROOT
  sys.path.insert(0,str(ROOT/'core/engine'))
  from reconstruct import arc_xy,plane_xy
  result=[];geom={g['id']:g for g in s.get('arc_geometry',[])}
  for i in u['source_event_ids']:
   e=geom[i];start=max(a,e['start_ms']);end=min(b,e['end_ms'])
   if end<start:continue
   n=max(1,min(20000,math.ceil((end-start)/step)))
   for j in range(n+1):
    t=start+(end-start)*j/n;p=plane_xy(arc_xy(e,t))
    if p is not None:result.append([t,*p])
  if result:
   # Manual endpoint edits require explicit linear/polyline mode.
   return sorted(result,key=lambda p:p[0])
 return [[a,*u['start_position']],*u.get('waypoints',[]),[b,*u['end_position']]]
def at(u,s,t):
 ps=points(u,s)
 if t<=ps[0][0]:return ps[0][1:]
 for a,b in zip(ps,ps[1:]):
  if t<=b[0]:
   f=(t-a[0])/(b[0]-a[0]) if b[0]>a[0] else 1
   return [a[j]+f*(b[j]-a[j]) for j in (1,2)]
 return ps[-1][1:]
def split(s,uid,t):
 s=copy.deepcopy(s);i=next(i for i,u in enumerate(s['units']) if u['unit_id']==uid);u=s['units'][i]
 if not u['start_ms']<t<u['end_ms']:raise ValueError('Split must be inside a sustained operation')
 p=at(u,s,t);a=copy.deepcopy(u);b=copy.deepcopy(u)
 a['end_ms']=t;a['end_position']=p;b['start_ms']=t;b['start_position']=p;b['unit_id']='manual:'+unique();b['fresh_press']=False;b['arc_activation']='skip';b['action_ids']=[]
 a['waypoints']=[w for w in u['waypoints'] if w[0]<t];b['waypoints']=[w for w in u['waypoints'] if w[0]>t]
 b['origin']='split';s['units'][i:i+1]=[a,b];return validate(s)
def merge(s,ids):
 s=copy.deepcopy(s);items=sorted([u for u in s['units'] if u['unit_id'] in ids],key=lambda u:u['start_ms'])
 if len(items)<2 or len({u['hand'] for u in items})!=1:raise ValueError('Select at least two operations with the same hand')
 if any(u['fresh_press'] for u in items[1:]):raise ValueError('Merge would remove fresh presses; edit their semantics explicitly first')
 for a,b in zip(items,items[1:]):
  if b['kind']=='arc' and (b.get('arc_activation','auto')=='count' or (b.get('arc_activation','auto')=='auto' and (a['kind']!='arc' or not 0<=b['start_ms']-a['end_ms']<=1 or math.dist(a['end_position'],b['start_position'])>=1e-6))):raise ValueError('Merge would remove arc activations; set arc_activation to skip explicitly if intended')
 if any(a['end_ms']>b['start_ms'] for a,b in zip(items,items[1:])):raise ValueError('Overlapping operations cannot merge')
 u=copy.deepcopy(items[0]);u['unit_id']='manual:'+unique();u['origin']='merge';u['kind']='arc' if any(v['kind']=='arc' for v in items) else 'contact';u['geometry_mode']='polyline'
 u['end_ms']=items[-1]['end_ms'];u['end_position']=items[-1]['end_position'];u['waypoints']=[p for v in items for p in points(v,s) if u['start_ms']<p[0]<u['end_ms']]
 u['source_event_ids']=list(dict.fromkeys(i for v in items for i in v['source_event_ids']));u['action_ids']=list(dict.fromkeys(i for v in items for i in v['action_ids']))
 s['units']=[v for v in s['units'] if v['unit_id'] not in ids]+[u];return validate(s)
