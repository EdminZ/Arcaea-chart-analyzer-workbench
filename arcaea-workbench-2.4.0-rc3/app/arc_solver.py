"""Reference-timing arc path recognition; not a certified game judgment model."""
from pathlib import Path
import sys,copy,math
import numpy as np
from scipy.optimize import minimize
from .common import ROOT,digest
from . import sequence,arc_paths,recognition
WEIGHTS=np.array([1.,.5*4.5/8.5])

def geometry_hash(u):
 return digest({k:u.get(k) for k in ('start_ms','end_ms','start_position','end_position','geometry_mode','waypoints','source_event_ids')})

def endpoint_fits(point,centers,tolerance):
 return bool(np.all(np.abs(np.asarray(centers)-point)<=np.asarray(tolerance)+1e-9))

def affpoint(p):return [p[0],(8.5*p[1]-1)/4.5]
def length(ps):return sum(math.dist([a[1],WEIGHTS[1]*a[2]],[b[1],WEIGHTS[1]*b[2]]) for a,b in zip(ps,ps[1:]) if b[0]>a[0])
def optimize(times,centers,fixed,tolerance):
 centers=np.asarray(centers,dtype=float);lo=centers-tolerance;hi=centers+tolerance
 for i in fixed:lo[i]=hi[i]=centers[i]
 dt=np.maximum(np.diff(times)/1000,1e-6)
 def objective(flat):
  pts=flat.reshape(-1,2);diff=np.diff(pts,axis=0)*WEIGHTS;norm=np.sqrt(np.sum(diff*diff,axis=1)+1e-8)
  # Tiny squared-speed term selects smoother timing among nearly equal paths.
  cost=np.sum(norm)+1e-5*np.sum(np.sum(diff*diff,axis=1)/dt)
  g=(diff/norm[:,None]+2e-5*diff/dt[:,None])*WEIGHTS;grad=np.zeros_like(pts);grad[:-1]-=g;grad[1:]+=g
  return cost,grad.ravel()
 result=minimize(objective,centers.ravel(),jac=True,bounds=list(zip(lo.ravel(),hi.ravel())),method='L-BFGS-B',options={'maxiter':5000,'ftol':1e-10,'gtol':1e-6,'maxls':50})
 candidate=result.x.reshape(-1,2);violation=max(float(np.max(lo-candidate)),float(np.max(candidate-hi)),0.)
 if not result.success or violation>1e-7:return centers,False,str(result.message),violation
 return candidate,True,str(result.message),violation

def recognize(source,s,config):
 config=recognition.validate(config)
 if config.get('judgment_time_tolerance_ms') is not None or config.get('max_contact_speed_aff_per_s') is not None:
  raise ValueError('This reference-timing solver requires null timing tolerance and speed limit; nonzero timing/reachability mechanics are not implemented')
 sys.path.insert(0,str(ROOT/'core/engine'))
 from audit import analyze
 from reconstruct import build
 from assign import make_units
 doc,audit=analyze(Path(source))
 if doc['sha256']!=s['sha256']:raise ValueError('Arc recognition source hash mismatch')
 if audit.get('warnings'):raise ValueError('Arc recognition blocked by parser warnings')
 recon=build(doc);units,_=make_units(doc,recon);unitmap={u.id:u for u in units};longs={l['source_event_id']:l for l in recon['long_objects']}
 candidate=copy.deepcopy(s);reports=[];tolerance=np.array([config['tolerance_x'],config['tolerance_y']])
 for u in candidate['units']:
  if u['kind']!='arc':continue
  relaxation=[];prior=copy.deepcopy(u)
  uid=u['unit_id'];cu=unitmap.get(uid);start,end=int(u['start_ms']),int(u['end_ms']);reason=None
  if cu and u.get('arc_solver_geometry_hash')==geometry_hash(u):
   u.update(geometry_mode='source',waypoints=[],start_position=list(cu.start_pos),end_position=list(cu.end_pos))
  if cu is None or u['geometry_mode']!='source':reason='Existing edited/unknown execution path retained'
  elif cu.start!=u['start_ms'] or cu.end!=u['end_ms'] or list(cu.sources)!=u['source_event_ids']:reason='Edited source identity/timing retained'
  elif cu.color not in ('0','1'):reason='Neutral/merged arc requires joint-contact mechanics; retained'
  times={start,end};fixed_times={start,end};attached_times=set();uncertain=[]
  if reason is None:
   for sid in u['source_event_ids']:
    l=longs.get(sid)
    if l is None:continue
    schedule=l['combo_candidates']['tight']
    if schedule.get('times_ms') is None:uncertain.append(sid);continue
    times.update(max(start,min(end,round(t))) for t in schedule['times_ms'])
    if l.get('geometry_status')!='analytic_reference_not_projected':uncertain.append(sid)
   for a in recon['press_candidates']:
    if a['source_event_id'] in u['source_event_ids'] and a['kind'] in ('sky_tap','wide_sky_tap'):
     t=round(a['time_ms']);times.add(t);fixed_times.add(t);attached_times.add(t)
   if uncertain:reason='Uncertain schedule/geometry retained'
  source_ps=[[t,*affpoint([x,y])] for t,x,y in sequence.points(u,s,10)]
  if reason:
   pts=source_ps;success=False;violation=None;anchors=[]
  else:
   ts=sorted(times);centers=[affpoint(cu.at(t)) for t in ts]
   # Preserve the exact reserved endpoints, including existing rounding conventions.
   centers[0]=affpoint(u['start_position']);centers[-1]=affpoint(u['end_position']);fixed=[i for i,t in enumerate(ts) if t in fixed_times]
   arr,success,message,violation=optimize(np.array(ts),centers,fixed,tolerance)
   if not success:reason='Numerical solve did not converge; retained original path';pts=source_ps;anchors=[]
   else:
    if config['endpoint_relaxation'] and len(ts)>2:
     for index,neighbor,label in [(0,1,'start'),(-1,-2,'end')]:
      t=ts[index];blocked=(t in attached_times or (index==0 and u['fresh_press']))
      # Do not move a seam shared with another allocated operation.
      blocked=blocked or any(v['unit_id']!=uid and v['hand']==u['hand'] and t in (v['start_ms'],v['end_ms']) for v in s['units'])
      replacement=arr[neighbor].copy();a,b=sorted((t,ts[neighbor]))
      checks=np.linspace(a,b,max(2,math.ceil((b-a)/config['endpoint_sample_ms'])+1))
      boundaries=[q for sid in u['source_event_ids'] if sid in longs for q in (longs[sid]['start_ms'],longs[sid]['end_ms']) if a<=q<=b]
      checks=sorted(set(list(checks)+boundaries))
      accepted=not blocked and endpoint_fits(replacement,[affpoint(cu.at(q)) for q in checks],tolerance)
      if accepted:arr[index]=replacement
      relaxation.append({'endpoint':label,'relaxed':bool(accepted),'reason':'sampled interval fits tolerance' if accepted else 'required input/shared seam or interval outside tolerance','sample_count':len(checks)})
    pts=[[t,float(p[0]),float(p[1])] for t,p in zip(ts,arr)]
    relaxed_times={ts[0] if r['endpoint']=='start' else ts[-1] for r in relaxation if r['relaxed']}
    anchors=[{'time_ms':t,'center_aff':c,'path_aff':list(p),'fixed':i in fixed and t not in relaxed_times} for i,(t,c,p) in enumerate(zip(ts,centers,arr))]
    converted=[[t,x,(1+4.5*y)/8.5] for t,x,y in pts];u.update(geometry_mode='polyline',start_position=converted[0][1:],end_position=converted[-1][1:],waypoints=converted[1:-1]);u['arc_solver_geometry_hash']=geometry_hash(u)
  if not success:u.clear();u.update(prior)
  reports.append({'unit_id':uid,'optimized':success,'fallback_reason':reason,'constraint_violation':violation,'weighted_source_length':length(source_ps),'weighted_candidate_length':length(pts),'anchors':anchors,'endpoint_relaxation':relaxation})
 sequence.validate(candidate)
 old_errors={(r['unit_id'],r['message']) for r in sequence.diagnostics(s) if r['level']=='error'}
 new_errors=[r for r in sequence.diagnostics(candidate) if r['level']=='error' and (r['unit_id'],r['message']) not in old_errors]
 if new_errors:raise ValueError('Arc recognition introduced conflict: '+new_errors[0]['message'])
 asset=arc_paths.from_sequence(candidate)
 asset['generation']={'algorithm':'reference-box-path/2','profile':config,'not_game_certified':True,'endpoint_interval_check':'sampled','temporal_slack_ms':0}
 asset['recognition_report']=reports
 return candidate,asset
