"""External declarative formula engine. No eval, imports or executable plugins."""
import ast,bisect,copy,math,operator
from .common import digest
from . import sequence
FUNCS={'abs':abs,'min':min,'max':max,'sqrt':math.sqrt,'exp':math.exp,'log':math.log,'log10':math.log10,'sin':math.sin,'cos':math.cos,'tanh':math.tanh,'clamp':lambda x,a,b:max(a,min(b,x))}
FEATURES={'t','movement','arc_movement','frequency','nonarc_frequency','occupancy','window_s','step_s','pi','e'}
class Expression:
 def __init__(self,text,names):
  if not isinstance(text,str) or len(text)>2000:raise ValueError('Expression too long')
  self.tree=ast.parse(text,mode='eval').body
  if sum(1 for _ in ast.walk(self.tree))>200:raise ValueError('Expression too complex')
  allowed=(ast.Expression,ast.Constant,ast.Name,ast.Load,ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.Compare,ast.IfExp,ast.Call,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.Mod,ast.USub,ast.UAdd,ast.Not,ast.And,ast.Or,ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.Eq,ast.NotEq)
  for n in ast.walk(self.tree):
   if not isinstance(n,allowed):raise ValueError('Unsupported syntax: '+type(n).__name__)
   if isinstance(n,ast.Constant) and (isinstance(n.value,bool) or not isinstance(n.value,(int,float)) or not math.isfinite(n.value) or abs(n.value)>1e12):raise ValueError('Invalid constant')
   if isinstance(n,ast.Name) and n.id not in set(names)|set(FUNCS):raise ValueError('Unknown variable: '+n.id)
   if isinstance(n,ast.Call) and (not isinstance(n.func,ast.Name) or n.func.id not in FUNCS or n.keywords or len(n.args)>8):raise ValueError('Only listed mathematical functions are allowed')
 def __call__(self,env):
  def run(n,depth=0):
   if depth>35:raise ValueError('Expression nesting limit')
   f=lambda a:run(a,depth+1)
   if isinstance(n,ast.Constant):return float(n.value)
   if isinstance(n,ast.Name):return env[n.id]
   if isinstance(n,ast.IfExp):return f(n.body if f(n.test) else n.orelse)
   if isinstance(n,ast.UnaryOp):
    a=f(n.operand);return -a if isinstance(n.op,ast.USub) else not a if isinstance(n.op,ast.Not) else a
   if isinstance(n,ast.BoolOp):
    return all(f(v) for v in n.values) if isinstance(n.op,ast.And) else any(f(v) for v in n.values)
   if isinstance(n,ast.Compare):
    a=f(n.left)
    for op,b in zip(n.ops,n.comparators):
     b=f(b);ok={ast.Lt:operator.lt,ast.LtE:operator.le,ast.Gt:operator.gt,ast.GtE:operator.ge,ast.Eq:operator.eq,ast.NotEq:operator.ne}[type(op)](a,b)
     if not ok:return False
     a=b
    return True
   if isinstance(n,ast.BinOp):
    a,b=f(n.left),f(n.right)
    if isinstance(n.op,ast.Pow) and (abs(b)>16 or abs(a)>1e12):raise ValueError('Power outside supported bounds')
    v={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow,ast.Mod:operator.mod}[type(n.op)](a,b)
   elif isinstance(n,ast.Call):v=FUNCS[n.func.id](*[f(a) for a in n.args])
   else:raise ValueError('Unsupported expression')
   if isinstance(v,complex) or not math.isfinite(v) or abs(v)>1e100:raise ValueError('Non-finite or excessive function result')
   return v
  try:return float(run(self.tree))
  except (ArithmeticError,ValueError,KeyError,TypeError) as e:raise ValueError('Function evaluation failed: '+str(e)) from e

def validate(definition):
 if definition.get("format")=="arcaea-difficulty/2":
  from . import model2
  return model2.validate(definition)
 d=copy.deepcopy(definition)
 if d.get('format')!='arcaea-difficulty/1':raise ValueError('Unsupported difficulty format')
 if not isinstance(d.get('name'),str) or not d['name'].strip():raise ValueError('Definition needs a name')
 if not 10<=d.get('step_ms',0)<=1000 or not 20<=d.get('window_ms',0)<=10000:raise ValueError('step_ms 10–1000, window_ms 20–10000')
 if d.get('denominator') not in ('chart_span','included_time'):raise ValueError('Invalid denominator')
 if d.get('candidate_policy') not in ('exclude','include_flagged'):raise ValueError('Invalid candidate policy')
 params=d.get('parameters',{})
 if len(params)>40 or len(d.get('channels',{}))>20 or len(d.get('temporal',{}))>20 or len(d.get('metrics',{}))>30:raise ValueError('Definition is too large')
 for k,v in params.items():
  if not k.isidentifier() or k in FEATURES or k in FUNCS or k in {'duration_s','included_s','total_distance','arc_distance','press_count','nonarc_press_count'}:raise ValueError('Invalid/reserved parameter '+k)
  if not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e9:raise ValueError('Invalid parameter '+k)
 names=set(params)|FEATURES
 for k,v in d.get('channels',{}).items():
  if not k.isidentifier() or k in names or k in FUNCS:raise ValueError('Invalid channel name '+k)
  Expression(v,names);names.add(k)
 for k,v in d.get('temporal',{}).items():
  if not k.isidentifier() or k in names or k in FUNCS:raise ValueError('Invalid temporal channel '+k)
  if v.get('input') not in set(d['channels'])|set(list(d.get('temporal',{}))[:list(d.get('temporal',{})).index(k)]):raise ValueError('Temporal input must be an earlier channel')
  if v.get('operator') not in ('mean','max','integral','time_above') or not 10<=v.get('window_ms',0)<=10000:raise ValueError('Invalid temporal operator/window')
  Expression(str(v.get('threshold',0)),set(params))(params);names.add(k)
 summary={'duration_s','included_s','total_distance','arc_distance','press_count','nonarc_press_count','pi','e'}|set(params)
 for k in list(d['channels'])+list(d.get('temporal',{})):summary.update(k+'_'+suffix for suffix in ('mean','max','integral'))
 for k,v in d.get('metrics',{}).items():
  if not k.isidentifier() or k in {'speed_capped_intervals','response_clipped_intervals','volume_invalid','volume_status','peak_near_s','movement_near_s','song_id','rating_class','display_rating','chart_constant','constant_source','constant_csv_hash','chart_id','title','difficulty_label','allocation_version','metric_status','calibrated','sequence_revision','sequence_hash','review_status','status','definition_hash','definition_name','metric_sequence_revision','included_fraction','preview_mode','error'}:raise ValueError('Invalid/reserved metric name')
  Expression(v,summary)
 # A basic numerical probe catches unconditional domain errors before activation.
 env={k:1. for k in FEATURES};env.update(params);env.update(pi=math.pi,e=math.e)
 for k,v in d['channels'].items():env[k]=Expression(v,set(env))(env)
 probe={k:1. for k in summary};probe.update(params);probe.update(pi=math.pi,e=math.e)
 for v in d['metrics'].values():Expression(v,set(probe))(probe)
 return d

def calculate(s,chart,d):
 if d.get("format")=="arcaea-difficulty/2":
  from . import model2
  return model2.calculate(s,chart,d)
 d=validate(d);issues=sequence.diagnostics(s)
 if any(x['level']=='error' for x in issues):raise ValueError('Sequence has reservation/zero-time conflicts; fix or explicitly exclude those regions')
 units=sorted(s['units'],key=lambda u:(u['start_ms'],u['unit_id']))
 if not units:raise ValueError('Empty sequence')
 start=min(u['start_ms'] for u in units);end=max(u['end_ms'] for u in units);duration=(end-start)/1000
 if duration<=0:raise ValueError('Need a positive chart span')
 if duration>7200:raise ValueError('Maximum supported chart span: 2 hours')
 masks=[(e['start_ms'],e['end_ms']) for e in s.get('exclusions',[]) if e['status']=='confirmed']
 dismissed=[e for e in s.get('exclusions',[]) if e['status']=='dismissed']
 if d['candidate_policy']=='exclude':
  for e in s.get('multitouch',{}).get('episodes',[]):
   if not any(x['start_ms']<=e['start_ms'] and x['end_ms']>=e['end_ms'] for x in dismissed):masks.append((e['start_ms'],e['end_ms']))
 # Unresolved required operations create gaps, not invented movements.
 masks += [(u['start_ms'],u['end_ms']) for u in units if u['hand'] is None]
 def blocked(a,b):return any(x<=b and y>=a for x,y in masks)
 resets=[(r['start_ms'],r['end_ms']) for r in s.get('flow_context',{}).get('resets',[])]
 moves=[];prev={};press=[];nonarc=[];occ=[]
 for u in units:
  a,b=u['start_ms'],u['end_ms'];h=u['hand']
  if h is None or blocked(a,b):continue
  if u['fresh_press'] and u['role']!='waypoint':
   press.append(a)
   if u['kind']!='arc':nonarc.append(a)
  if b>a and u['role']!='waypoint':occ.append((a,b))
  if h in prev:
   v=prev[h];x=v['end_ms'];y=a
   if y>x and not blocked(x,y) and not any(x<=ra and rb<=y for ra,rb in resets):moves.append((x,y,math.dist(v['end_position'],u['start_position']),False))
  if u['kind']!='hold':
   ps=sequence.points(u,s)
   for p,q in zip(ps,ps[1:]):
    if q[0]>p[0]:moves.append((p[0],q[0],math.dist(p[1:],q[1:]),u['kind']=='arc'))
  prev[h]=u
 step=d['step_ms'];n=math.ceil((end-start)/step)
 if n>200000:raise ValueError('Too many samples; increase step_ms')
 rows=[{'time_ms':start+i*step,'t':i*step/1000,'movement':0.,'arc_movement':0.,'frequency':0.,'nonarc_frequency':0.,'occupancy':0.,'window_s':d['window_ms']/1000,'step_s':min(step,end-(start+i*step))/1000,'included':not blocked(start+i*step,min(end,start+(i+1)*step))} for i in range(n)]
 for a,b,distance,isarc in moves:
  lo=max(0,int((a-start)//step));hi=min(n-1,int((b-start)//step))
  for i in range(lo,hi+1):
   r=rows[i];overlap=max(0,min(b,r['time_ms']+r['step_s']*1000)-max(a,r['time_ms']))
   v=distance*overlap/(b-a)/r['step_s'];r['movement']+=v
   if isarc:r['arc_movement']+=v
 for a,b in occ:
  for i in range(max(0,int((a-start)//step)),min(n,int(math.ceil((b-start)/step)))):
   r=rows[i];r['occupancy']+=max(0,min(b,r['time_ms']+r['step_s']*1000)-max(a,r['time_ms']))/(r['step_s']*1000)
 channels={k:Expression(v,set(d['parameters'])|FEATURES|set(list(d['channels'])[:j])) for j,(k,v) in enumerate(d['channels'].items())}
 for r in rows:
  t=r['time_ms']+r['step_s']*1000;win=d['window_ms']
  r['frequency']=(bisect.bisect_right(press,t)-bisect.bisect_right(press,t-win))/(win/1000)
  r['nonarc_frequency']=(bisect.bisect_right(nonarc,t)-bisect.bisect_right(nonarc,t-win))/(win/1000)
  env={**d['parameters'],**r,'pi':math.pi,'e':math.e}
  for k,expr in channels.items():
   value=expr(env) if r['included'] else None;r[k]=value;env[k]=value if value is not None else 0
 # Bounded trailing windows over sampled channels; linear-time prefix sums/deque.
 from collections import deque
 for k,spec in d.get('temporal',{}).items():
  inp=spec['input'];op=spec['operator'];count=max(1,math.ceil(spec['window_ms']/step));threshold=Expression(str(spec.get('threshold',0)),set(d['parameters']))(d['parameters'])
  sums=[0.];durations=[0.];above=[0.];maximum=deque()
  for i,r in enumerate(rows):
   v=r[inp];dt=r['step_s'] if v is not None else 0
   sums.append(sums[-1]+(v or 0)*dt);durations.append(durations[-1]+dt);above.append(above[-1]+(dt if v is not None and v>threshold else 0))
   lo=max(0,i-count+1)
   while maximum and maximum[0][0]<lo:maximum.popleft()
   if v is not None:
    while maximum and maximum[-1][1]<=v:maximum.pop()
    maximum.append((i,v))
   if not r['included']:r[k]=None
   elif op=='max':r[k]=maximum[0][1] if maximum else 0
   elif op=='integral':r[k]=sums[-1]-sums[lo]
   elif op=='time_above':r[k]=above[-1]-above[lo]
   else:r[k]=(sums[-1]-sums[lo])/max(1e-12,durations[-1]-durations[lo])
 included=sum(r['step_s'] for r in rows if r['included']);denom=duration if d['denominator']=='chart_span' else included
 if denom<=0:raise ValueError('No included time after masks')
 summary={'duration_s':duration,'included_s':included,'total_distance':sum(r['movement']*r['step_s'] for r in rows if r['included']),'arc_distance':sum(r['arc_movement']*r['step_s'] for r in rows if r['included']),'press_count':len(press),'nonarc_press_count':len(nonarc),'pi':math.pi,'e':math.e,**d['parameters']}
 for k in list(channels)+list(d.get('temporal',{})):
  vals=[(r[k],r['step_s']) for r in rows if r[k] is not None];integral=sum(v*dt for v,dt in vals)
  summary.update({k+'_mean':integral/denom,k+'_max':max((v for v,dt in vals),default=0),k+'_integral':integral})
 metrics={k:Expression(v,set(summary))(summary) for k,v in d['metrics'].items()}
 return {'format':'arcaea-metrics/1','status':'experimental_partial' if masks else 'experimental','calibrated':False,'definition_hash':digest(d),'definition_name':d['name'],'sequence_hash':digest(s),'chart_facts_hash':digest(chart),'metrics':metrics,'summary':summary,'series':rows,'diagnostics':issues,'coverage':{'masked_intervals':masks,'reset_transfers_unscored':resets,'included_fraction':included/duration},'limitations':['AFF judgement schedules are hypotheses, not official input requirements.','Arc movement uses analytic reference geometry, not a solved minimum-contact path.','Mask boundaries conservatively exclude intersecting whole operations and sample bins.','Scores are an editable demonstration; block metric not implemented.']}
