"""Version 2 difficulty definitions: reusable measurements, separate contact responses."""
import bisect,copy,math
from collections import defaultdict
from .common import digest
from . import sequence,signals
ENGINE='frequency-movement/2.3'
SUMMARY={'frequency_mean','frequency_mode','frequency_peak','movement_peak','total_weight','arc_weight','tap_weight','total_distance','arc_distance','press_count','duration_s','frequency_active_s','peak_duration_s','movement_peak_duration_s','invalid_volume','speed_capped_intervals','response_clipped_intervals','max_interval_speed'}
RESERVED={'song_id','rating_class','display_rating','chart_constant','constant_source','constant_csv_hash','chart_id','title','difficulty_label','allocation_version','metric_status','calibrated','sequence_revision','sequence_hash','review_status','status','definition_hash','definition_name','metric_sequence_revision','included_fraction','preview_mode','error','speed_capped_intervals','response_clipped_intervals','volume_invalid','volume_status','peak_near_s','movement_near_s'}
def expression(text,names):
 from .difficulty import Expression
 return Expression(text,names)
def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def response(spec,params):
 if spec['type']=='expression':
  e=expression(spec['expression'],{'v'}|set(params))
  fn=lambda v:e({**params,'v':v})
 else:
  points=spec['points'];xs=[p[0] for p in points]
  def fn(v):
   if v<=xs[0]:return points[0][1]
   if v>=xs[-1]:return points[-1][1]
   i=bisect.bisect_right(xs,v)-1;a,b=points[i:i+2];return a[1]+(b[1]-a[1])*(v-a[0])/(b[0]-a[0])
 def checked(v):
  value=fn(v)
  if not finite(value) or not 0<=value<=1e12:raise ValueError('Movement response must be finite and nonnegative (maximum 1e12)')
  return value
 return checked
def response_functions(d):
 raw={k:response(spec,d['parameters']) for k,spec in d['responses'].items()}
 limit=d.get('speed_limit');scale=1.
 if d.get('normalize_response',False):
  speeds={limit*i/512 for i in range(513)}
  for spec in d['responses'].values():
   if spec['type']=='points':speeds.update(p[0] for p in spec['points'] if p[0]<=limit)
  scale=max((fn(v) for fn in raw.values() for v in speeds),default=0.) or 1.
 def evaluate(channel,v):
  capped=min(v,limit) if limit is not None else v
  value=raw[channel](capped)/scale
  return min(1.,value) if d.get('normalize_response',False) else value
 return raw,evaluate,scale

def validate(d):
 d=copy.deepcopy(d)
 if d.get('format')!='arcaea-difficulty/2' or not isinstance(d.get('name'),str) or not d['name'].strip():raise ValueError('Invalid v2 definition/name')
 for key,lo,hi in [('sample_ms',1,20),('arc_step_ms',1,50),('frequency_window_ms',20,10000),('movement_window_ms',20,10000),('peak_min_ms',1,10000),('near_peak_ratio',.01,1),('arc_threshold',0,100)]:
  if not finite(d.get(key)) or not lo<=d[key]<=hi:raise ValueError(f'{key} must be in [{lo}, {hi}]')
 if not finite(d.get('vertical_scale',1)) or not 0<=d.get('vertical_scale',1)<=1:raise ValueError('vertical_scale must be in [0, 1]')
 limit=d.get('speed_limit')
 if limit is not None and (not finite(limit) or not .01<=limit<=10000):raise ValueError('speed_limit must be blank/null or in [0.01, 10000]')
 if not isinstance(d.get('normalize_response',False),bool):raise ValueError('normalize_response must be boolean')
 if d.get('normalize_response',False) and limit is None:raise ValueError('Normalized response requires a speed limit')
 if d['sample_ms']>d['peak_min_ms']:raise ValueError('sample_ms must not exceed peak_min_ms')
 if d.get('judgment_profile') not in ('tight','loose'):raise ValueError('Judgment profile must be tight or loose')
 if d.get('candidate_policy') not in ('exclude','include_flagged'):raise ValueError('Invalid candidate policy')
 params=d.get('parameters',{})
 if not isinstance(params,dict) or len(params)>40:raise ValueError('At most 40 parameters')
 for k,v in params.items():
  if not k.isidentifier() or k in SUMMARY|{'v','frequency','movement'} or not finite(v) or abs(v)>1e9:raise ValueError('Invalid parameter '+k)
 if set(d.get('responses',{}))!={'tap','arc'}:raise ValueError('Define tap and arc responses')
 for spec in d['responses'].values():
  if spec.get('type')=='points':
   pts=spec.get('points',[])
   if not 2<=len(pts)<=100:raise ValueError('A response curve needs 2–100 points')
   for i,p in enumerate(pts):
    if len(p)!=2 or not all(finite(v) and 0<=v<=1e12 for v in p) or (i and p[0]<=pts[i-1][0]):raise ValueError('Curve speeds must strictly increase; values must be nonnegative')
   if pts[0]!=[0,0]:raise ValueError('A response curve must start at [0,0]')
  elif spec.get('type')!='expression':raise ValueError('Unknown response type')
  fn=response(spec,params)
  if abs(fn(0))>1e-9:raise ValueError('Stationary movement response must be zero: f(0)=0')
  for v in (.001,.1,1,5,20,100):fn(min(v,limit) if limit is not None else v)
 if d.get('normalize_response',False):response_functions(d)
 metrics=d.get('metrics',{})
 if not isinstance(metrics,dict) or not 1<=len(metrics)<=30:raise ValueError('Define 1–30 summary metrics')
 for name,text in metrics.items():
  if not name.isidentifier() or name in RESERVED:raise ValueError('Reserved metric name: '+name)
  expression(text,SUMMARY|set(params))({**{k:1. for k in SUMMARY},**params})
 axes=d.get('axes',{})
 for key,name in [('x','frequency'),('y','movement')]:expression(axes.get(key,''),{name}|set(params))({name:1.,**params})
 if not finite(axes.get('smoothing_ms')) or not 0<=axes['smoothing_ms']<=20:raise ValueError('Display smoothing radius: 0–20 ms')
 if not finite(axes.get('trail_ms')) or not 0<=axes['trail_ms']<=10000:raise ValueError('Trail length: 0–10000 ms')
 return d

def calculate(s,chart,d,features=None):
 d=validate(d);f=features or signals.extract(s,d['arc_step_ms'])
 if f['key']!=signals.feature_key(s,d['arc_step_ms']):raise ValueError('Feature cache is stale')
 masks=signals.masks_for(s,d['candidate_policy']);starts=[a for a,b in masks]
 def blocked(a,b):
  i=bisect.bisect_right(starts,b)-1
  return i>=0 and masks[i][1]>=a
 checked=copy.deepcopy(s);checked.setdefault('exclusions',[]).extend({'start_ms':a,'end_ms':b,'status':'confirmed'} for a,b in masks)
 issues=sequence.diagnostics(checked)
 if any(x['level']=='error' for x in issues):raise ValueError('Sequence has execution conflicts outside excluded regions; fix them or explicitly exclude the regions')
 start=f['start_ms'];end=f['contact_end_ms']+max(500,d['frequency_window_ms'],d['movement_window_ms']);duration=(end-start)/1000
 if duration/d['sample_ms']*1000>1000000:raise ValueError('Too many display samples; increase sample_ms')
 excluded_units={uid for uid,(a,b) in f['unit_ranges'].items() if blocked(a,b)}
 presses=[p['time'] for p in f['presses'] if p['hand'] is not None and p['unit'] not in excluded_units]
 freq=signals.frequency(presses,d['frequency_window_ms'],start,end)
 # Split at exclusion edges so time statistics do not discard unaffected spans.
 cuts=sorted({start,end,*[x for row in freq.rows for x in row[:2]],*[x for a,b in masks for x in (max(start,a),min(end,b)) if start<=x<=end]})
 freq_rows=[[a,b,freq.value((a+b)/2) if not blocked(a+1e-7,b-1e-7) else None] for a,b in zip(cuts,cuts[1:])]
 stats=signals.active_stats(signals.Signal([[a,b,v or 0.] for a,b,v in freq_rows]));fp=signals.peak(freq_rows,d['peak_min_ms'],d['near_peak_ratio'])
 raw_functions,evaluate,normalizer=response_functions(d);vertical_scale=d.get('vertical_scale',1);limit=d.get('speed_limit');movement_warnings=[];max_speed=0.;capped_count=clipped_count=0
 events={k:defaultdict(float) for k in ('raw','weighted','arc','raw_arc')};total=wa=distance=arc_distance=0.
 for m in f['moves']:
  a,b=m['a'],m['b']
  if m['unit'] in excluded_units or m.get('from_unit') in excluded_units or blocked(a,b):continue
  dt=(b-a)/1000;dist=signals.movement_distance(m,vertical_scale);v=dist/dt;channel='arc' if m['arc'] else 'tap';q=evaluate(channel,v);max_speed=max(max_speed,v)
  capped=limit is not None and v>limit;input_v=min(v,limit) if limit is not None else v
  clipped=d.get('normalize_response',False) and raw_functions[channel](input_v)>normalizer*(1+1e-12)
  capped_count+=int(capped);clipped_count+=int(clipped)
  if capped or clipped:movement_warnings.append({'kind':'speed_cap' if capped else 'response_clip','speed_capped':capped,'response_clipped':clipped,'hand':m['hand'],'unit':m['unit'],'from_unit':m.get('from_unit'),'channel':channel,'start_ms':a,'end_ms':b,'corrected_distance':dist,'raw_speed':v,'used_speed':input_v,'speed_limit':limit})
  total+=q*dt;distance+=dist
  for key,value in [('raw',v),('weighted',q)]+([('arc',q),('raw_arc',v)] if m['arc'] else []):events[key][a]+=value;events[key][b]-=value
  if m['arc']:wa+=q*dt;arc_distance+=dist
 sig={k:signals.Signal(signals.intervals(e,start,end)) for k,e in events.items()}
 volume=signals.volume_report(f,chart,d['arc_threshold'],d['judgment_profile'],vertical_scale);volume.update(sequence_hash=digest(s),chart_facts_hash=digest(chart))
 rows=[];movement_rows=[];step=d['sample_ms']
 for i in range(math.ceil((end-start)/step)):
  a=start+i*step;b=min(end,a+step);included=not blocked(a,b);movement=sig['weighted'].window(a,d['movement_window_ms']);raw=sig['raw'].window(a,d['movement_window_ms'])
  rows.append({'time_ms':a,'step_s':(b-a)/1000,'included':included,'frequency':freq.value(a) if included else None,'frequency_per_s':freq.value(a)/(d['frequency_window_ms']/1000) if included else None,'movement':movement if included else None,'raw_movement':raw if included else None,'speed':sig['raw'].value(a) if included else None,'intensity':sig['weighted'].value(a) if included else None,'arc_intensity':sig['arc'].value(a) if included else None})
  movement_rows.append([a,b,movement if included else None])
 mp=signals.peak(movement_rows,d['peak_min_ms'],d['near_peak_ratio'])
 summary={'frequency_mean':stats['mean'],'frequency_mode':stats['mode'],'frequency_peak':fp['height'],'movement_peak':mp['height'],'total_weight':total,'tap_weight':total-wa,'arc_weight':wa,'total_distance':distance,'arc_distance':arc_distance,'press_count':len(presses),'duration_s':duration,'frequency_active_s':stats['active_s'],'peak_duration_s':fp['near_peak_duration_s'],'movement_peak_duration_s':mp['near_peak_duration_s'],'invalid_volume':volume['invalid_volume'],'speed_capped_intervals':capped_count,'response_clipped_intervals':clipped_count,'max_interval_speed':max_speed}
 has_data=any(u['hand'] is not None and u['role']!='waypoint' and u['unit_id'] not in excluded_units for u in s['units'])
 metrics={k:expression(text,SUMMARY|set(d['parameters']))({**summary,**d['parameters']}) if has_data else None for k,text in d['metrics'].items()}
 return {'format':'arcaea-metrics/2','engine':ENGINE,'status':('experimental_partial' if masks else 'experimental') if has_data else 'no_included_operations','calibrated':False,'definition_hash':digest(d),'definition_name':d['name'],'definition':d,'sequence_hash':digest(s),'chart_facts_hash':digest(chart),'feature_key':f['key'],'metrics':metrics,'summary':summary,'movement_mapping':{'vertical_scale':vertical_scale,'speed_limit':limit,'normalized':d.get('normalize_response',False),'shared_normalizer':normalizer,'normalizer_samples':513 if d.get('normalize_response',False) else 0},'movement_warnings':movement_warnings,'series':rows,'frequency_segments':freq_rows,'invalid_volume':volume,'peaks':{'frequency':fp,'movement':mp},'diagnostics':issues,'coverage':{'masked_intervals':masks,'included_fraction':sum(r['step_s'] for r in rows if r['included'])/duration},'limitations':['Judgment counts are inherited tight/loose reference hypotheses, not certified game counts.','Arc lengths follow the edited execution geometry; minimum judgment-satisfying movement is not solved.','Frequency statistics use exact event intervals; movement peaks use sample_ms resolution.','Excluded operations/transfers intersecting masks are conservatively omitted.','Response parameters are illustrative and uncalibrated; block is not implemented.']}

def trajectory_points(result,axes=None):
 """Triangular smoothing of mapped step intervals, for display only."""
 d=result.get('definition',{});axes=axes or d.get('axes',{});params=d.get('parameters',{})
 fx=expression(axes.get('x','frequency'),{'frequency'}|set(params));fy=expression(axes.get('y','movement'),{'movement'}|set(params))
 rows=result['series'];out=[];radius=float(axes.get('smoothing_ms',10));ts=[r['time_ms'] for r in rows]
 mapped=[None if not r['included'] or r.get('frequency') is None or r.get('movement') is None else (fx({'frequency':r['frequency'],**params}),fy({'movement':r['movement'],**params})) for r in rows]
 def cdf(x):
  if x<=-radius:return 0.
  if x>=radius:return 1.
  return (x+radius)**2/(2*radius**2) if x<=0 else 1-(radius-x)**2/(2*radius**2)
 for i,r in enumerate(rows):
  t=r['time_ms']
  if mapped[i] is None:out.append([t,None,None]);continue
  if radius==0:out.append([t,*mapped[i]]);continue
  lo=max(0,bisect.bisect_right(ts,t-radius)-1);hi=bisect.bisect_left(ts,t+radius);accx=accy=weight=0.
  # Do not blend across an excluded interval.
  for j in range(i-1,lo-1,-1):
   if mapped[j] is None:lo=j+1;break
  for j in range(i+1,hi):
   if mapped[j] is None:hi=j;break
  for j in range(lo,hi):
   if mapped[j] is None:continue
   q=rows[j];w=cdf(q['time_ms']+q['step_s']*1000-t)-cdf(q['time_ms']-t)
   accx+=mapped[j][0]*w;accy+=mapped[j][1]*w;weight+=w
  out.append([t,accx/max(weight,1e-12),accy/max(weight,1e-12)])
 return out
