"""Reusable operation measurements and event-based piecewise-constant signals."""
import bisect,math
from collections import defaultdict
from . import sequence
from .common import digest
VERSION='operation-features/3'
def intervals(events,start,end):
 events[start]+=0;events[end]+=0;ts=sorted(t for t in events if start<=t<=end);value=0.;out=[]
 for a,b in zip(ts,ts[1:]):
  value+=events[a]
  if b>a:out.append([a,b,0. if abs(value)<1e-10 else value])
 return out
class Signal:
 def __init__(self,segments):
  self.rows=segments;self.starts=[r[0] for r in segments];self.area=[0.]
  for a,b,v in segments:self.area.append(self.area[-1]+(b-a)*v/1000)
 def value(self,t):
  i=bisect.bisect_right(self.starts,t)-1
  return self.rows[i][2] if i>=0 and t<self.rows[i][1] else 0.
 def integral(self,t):
  i=bisect.bisect_right(self.starts,t)-1
  if i<0:return 0.
  a,b,v=self.rows[i];return self.area[i]+(min(t,b)-a)*v/1000
 def window(self,t,width):return self.integral(t)-self.integral(t-width)
def merge_ranges(ranges):
 out=[]
 for a,b in sorted(ranges):
  if out and a<=out[-1][1]:out[-1][1]=max(b,out[-1][1])
  else:out.append([a,b])
 return out
def masks_for(s,policy):
 masks=[(x['start_ms'],x['end_ms']) for x in s.get('exclusions',[]) if x['status']=='confirmed']
 dismissed=[x for x in s.get('exclusions',[]) if x['status']=='dismissed']
 if policy=='exclude':
  masks += [(x['start_ms'],x['end_ms']) for x in s.get('multitouch',{}).get('episodes',[]) if not any(y['start_ms']<=x['start_ms'] and y['end_ms']>=x['end_ms'] for y in dismissed)]
 masks += [(u['start_ms'],u['end_ms']) for u in s['units'] if u['hand'] is None]
 return merge_ranges(masks)
def feature_key(s,step):return digest({'version':VERSION,'sequence':s,'arc_step_ms':step})
def extract(s,step=10):
 sequence.validate(s);units=sorted(s['units'],key=lambda u:(u['start_ms'],u['unit_id']))
 if not units:raise ValueError('Empty sequence')
 start=min(u['start_ms'] for u in units);end=max(u['end_ms'] for u in units)
 if end-start>7200000:raise ValueError('Maximum supported span is 2 hours')
 moves=[];arcs=[];press=[];prev={};last_arc={}
 explicit={(u['hand'],u['start_ms'],tuple(u['start_position'])) for u in units if u['fresh_press'] and u['role']!='waypoint'}
 for u in units:
  a,b=u['start_ms'],u['end_ms'];h=u['hand'];uid=u['unit_id']
  activation=u['fresh_press'];reason='fresh_press'
  if u['kind']=='arc' and u['role']!='waypoint':
   old=last_arc.get(h);continuous=old is not None and 0<=a-old['end_ms']<=1 and math.dist(old['end_position'],u['start_position'])<1e-6
   onset=u.get('arc_activation','auto')
   inferred=onset=='count' or (onset=='auto' and not continuous)
   if inferred and not activation and (h,a,tuple(u['start_position'])) not in explicit:activation=True;reason='arc_onset'
   if h is not None:last_arc[h]=u
  if activation and u['role']!='waypoint':press.append({'time':a,'start':a,'end':b,'unit':uid,'hand':h,'reason':reason})
  # Arc samples are analysis intervals, not repeated activations.
  ps=sequence.points(u,s,step=step);length=sum(math.dist(p[1:],q[1:]) for p,q in zip(ps,ps[1:]))
  if u['kind']=='arc':arcs.append({'unit':uid,'sources':u['source_event_ids'],'start':a,'end':b,'length':length,'path_vectors':[[q[1]-p[1],q[2]-p[2]] for p,q in zip(ps,ps[1:])],'hand':h,'fresh_press':u['fresh_press'],'start_position':u['start_position'],'end_position':u['end_position']})
  if h is None:continue
  if h in prev:
   v=prev[h];x=v['end_ms']
   if a>x:moves.append({'a':x,'b':a,'d':math.dist(v['end_position'],u['start_position']),'dx':u['start_position'][0]-v['end_position'][0],'dy':u['start_position'][1]-v['end_position'][1],'arc':False,'hand':h,'unit':uid,'from_unit':v['unit_id']})
  if u['kind']!='hold':
   for p,q in zip(ps,ps[1:]):
    if q[0]>p[0]:moves.append({'a':p[0],'b':q[0],'d':math.dist(p[1:],q[1:]),'dx':q[1]-p[1],'dy':q[2]-p[2],'arc':u['kind']=='arc','hand':h,'unit':uid})
  prev[h]=u
 return {'format':VERSION,'key':feature_key(s,step),'start_ms':start,'contact_end_ms':end,'moves':moves,'presses':press,'arcs':arcs,'unit_ranges':{u['unit_id']:[u['start_ms'],u['end_ms']] for u in units}}
def frequency(presses,width,start,end):
 events=defaultdict(float)
 for t in presses:events[t]+=1;events[min(end,t+width)]-=1
 return Signal(intervals(events,start,end))
def active_stats(signal,blocked=lambda a,b:False):
 hist=defaultdict(float)
 for a,b,v in signal.rows:
  if v>0 and not blocked(a,b):hist[round(v,10)]+=(b-a)/1000
 duration=sum(hist.values())
 if not duration:return {'mean':0.,'mode':0.,'active_s':0.}
 # Highest modal level wins exact duration ties, explicitly and deterministically.
 mode=max(hist,key=lambda v:(round(hist[v],9),v))
 return {'mean':sum(v*t for v,t in hist.items())/duration,'mode':mode,'active_s':duration}
def longest_above(rows,level):
 best=run=0.;last=None
 for a,b,v in rows:
  if v is not None and v>=level and v>0:
   run=(run if last is not None and abs(a-last)<1e-7 else 0)+(b-a);best=max(best,run)
  else:run=0.
  last=b
 return best
def peak(rows,min_width=20,ratio=.9):
 vals=sorted({v for a,b,v in rows if v is not None and v>0})
 lo,hi=0,len(vals)-1;best=0.
 while lo<=hi:
  mid=(lo+hi)//2
  if longest_above(rows,vals[mid])+1e-7>=min_width:best=vals[mid];lo=mid+1
  else:hi=mid-1
 return {'height':best,'near_peak_duration_s':longest_above(rows,best*ratio)/1000 if best else 0.,'raw_max':max(vals,default=0.)}
def movement_distance(move,vertical_scale=1):
 return math.hypot(move['dx'],vertical_scale*move['dy'])
def volume_report(features,chart,threshold=.25,profile='tight',vertical_scale=1):
 traits={t['source_event_id']:t for t in chart.get('traits',[])};records=[];warnings=[]
 def add(kind,ids,units,length=None):
  counts=[traits[i].get('nominal_tick_counts',{}).get(profile) for i in ids]
  count=sum(counts) if all(isinstance(n,(int,float)) and n>=0 for n in counts) else None
  if count is None:warnings.append('Unavailable judgment count for '+str(ids))
  records.append({'kind':kind,'source_event_ids':ids,'unit_ids':units,'cumulative_distance':length,'judgments':count,'effective_count':min(1,count) if count is not None else None,'invalid_volume':max(0,count-1) if count is not None else None})
 for i,t in traits.items():
  if t['kind']=='hold':add('hold',[i],[])
 # Union split pieces sharing sources and contact-continuous arc operations.
 arcs=features['arcs'];parent=list(range(len(arcs)))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def join(i,j):parent[find(i)]=find(j)
 seen={};last={}
 for i,a in enumerate(arcs):
  for sid in a['sources']:
   if sid in seen:join(i,seen[sid])
   seen[sid]=i
  h=a['hand']
  if h is not None and h in last:
   j=last[h];b=arcs[j]
   if not a['fresh_press'] and abs(a['start']-b['end'])<=1 and math.dist(a['start_position'],b['end_position'])<1e-6:join(i,j)
  if h is not None:last[h]=i
 groups=defaultdict(list)
 for i,a in enumerate(arcs):groups[find(i)].append(a)
 for group in groups.values():
  length=sum(sum(math.hypot(dx,vertical_scale*dy) for dx,dy in a['path_vectors']) if 'path_vectors' in a else a['length'] for a in group)
  if length>=threshold:continue
  ids=sorted({i for a in group for i in a['sources'] if i in traits and traits[i]['kind']=='arc'})
  if not ids:
   warnings.append('Manual/unsourced low-movement arc has no AFF judgment count');continue
  add('arc',ids,[a['unit'] for a in group],length)
 known=[r for r in records if r['invalid_volume'] is not None]
 return {'format':'arcaea-invalid-volume/1','profile':profile,'judgment_status':'reference_hypothesis','arc_distance_threshold':threshold,'vertical_scale':vertical_scale,'records':records,'invalid_volume':sum(r['invalid_volume'] for r in known),'selected_judgments':sum(r['judgments'] for r in known),'effective_count':sum(r['effective_count'] for r in known),'complete':len(known)==len(records) and not warnings,'warnings':warnings,'scope':'Holds from AFF; qualifying connected arcs from edited sequence. Separate from frequency activations; no automatic subtraction from heatmaps.'}
