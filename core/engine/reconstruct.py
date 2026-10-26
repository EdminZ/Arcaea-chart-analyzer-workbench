"""Geometry and provisional long-note combo schedules; NOT a touch validator.
Usage: python reconstruct.py PARSED_DIRECTORY OUTPUT_DIRECTORY
See MECHANICS.md for evidence, coordinate conventions and unresolved rules.
"""
import argparse
import bisect
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

CURVES={'s':('linear','linear'),'b':('smooth','smooth'),
        'si':('sine','linear'),'so':('cosine','linear'),
        'sisi':('sine','sine'),'siso':('sine','cosine'),
        'sosi':('cosine','sine'),'soso':('cosine','cosine')}


def ease(t, mode):
    if mode=='linear': return t
    if mode=='smooth': return t*t*(3-2*t)
    if mode=='sine': return math.sin(math.pi*t/2)
    if mode=='cosine': return 1-math.cos(math.pi*t/2)
    raise ValueError(mode)


def arc_xy(event, time):
    """Analytic AFF coordinates, no clamping to playable area or hitbox expansion."""
    g=event['geometry']; start,end=event['start_ms'],event['end_ms']
    if not start<=time<=end: raise ValueError('Time outside arc')
    if start==end:
        if (g['x0'],g['y0'])!=(g['x1'],g['y1']): return None
        return [g['x0'],g['y0']]
    fx,fy=CURVES[g['curve']]; t=(time-start)/(end-start)
    return [g['x0']+(g['x1']-g['x0'])*ease(t,fx),
            g['y0']+(g['y1']-g['y0'])*ease(t,fy)]


def plane_xy(aff_xy):
    """Unprojected editor plane: 8.5 world units = 1 analysis unit; x increases right."""
    return [aff_xy[0], (1+4.5*aff_xy[1])/8.5] if aff_xy is not None else None


def floor_xy(lane): return [0.5*lane-0.75,0.0]


def polyline(event, tolerance=0.001, max_step_ms=40):
    """Visualization/length samples only. NOT judgment points or required waypoints.
    Check quarter points as well as midpoint so smoothstep inflections are not missed.
    """
    if tolerance<=0 or max_step_ms<=0: raise ValueError('Positive tolerances required')
    start,end=event['start_ms'],event['end_ms']
    p0=plane_xy(arc_xy(event,start)); p1=plane_xy(arc_xy(event,end))
    if p0 is None or p1 is None: return []
    result=[[start,*p0]]
    def split(a,pa,b,pb,depth):
        err=0.0
        for f in (0.25,0.5,0.75):
            actual=plane_xy(arc_xy(event,a+(b-a)*f))
            chord=[pa[i]+(pb[i]-pa[i])*f for i in (0,1)]
            err=max(err,math.dist(actual,chord))
        if b-a>max_step_ms or err>tolerance:
            if depth>=20: raise ValueError('Geometry refinement limit exceeded')
            mid=(a+b)/2;pm=plane_xy(arc_xy(event,mid))
            split(a,pa,mid,pm,depth+1);split(mid,pm,b,pb,depth+1)
        elif b>a: result.append([b,*pb])
    split(start,p0,end,p1,0)
    return result


def path_length(points):
    return sum(math.dist(a[1:],b[1:]) for a,b in zip(points,points[1:]))


class TimingMap:
    def __init__(self,doc):
        self.groups=defaultdict(list)
        for e in doc['events']:
            if e['kind']=='timing':self.groups[e['group']].append((int(e['args'][0]),e['id'],float(e['args'][1])))
        for v in self.groups.values():v.sort()
    def at(self,group,time):
        v=self.groups[group]
        if not v:return None,'missing_group_timing'
        i=bisect.bisect_right(v,(time,math.inf,math.inf))-1
        if i<0:return None,'no_preceding_timing'
        return v[i][2],None
    def changes_inside(self,group,start,end):
        return [t for t,_,_ in self.groups[group] if start<t<end]


def connections(arcs):
    """Return all candidate predecessors under two reference-inspired policies.
    Never select a hand, collapse branches or equate visual connection with touch continuity.
    """
    ends=sorted((e['end_ms'],e['id'],e) for e in arcs)
    times=[x[0] for x in ends]; result={e['id']:{'tight':[],'loose':[]} for e in arcs}
    for b in arcs:
        t=b['start_ms'];g=b['geometry']
        for _,_,a in ends[bisect.bisect_left(times,t-9):bisect.bisect_right(times,t+9)]:
            if a['id']==b['id'] or a['trace_raw']!=b['trace_raw']:continue
            h=a['geometry'];dt=abs(a['end_ms']-t)
            if abs(h['x1']-g['x0'])<0.1 and abs(h['y1']-g['y0'])<0.01:
                result[b['id']]['loose'].append(a['id'])
            if dt<=1 and h['x1']==g['x0'] and h['y1']==g['y0']:
                result[b['id']]['tight'].append(a['id'])
    return result


def combo_schedule(start,end,bpm,kind,has_predecessor=False,density=1.0,profile='loose'):
    """Reference-inspired nominal combo schedule, NOT a legal input schedule.
    loose: Arcade-plus-style head detection/truncated times/midpoint short holds.
    tight: ArcCreate-style head detection/metadata times/start-time short holds.
    Uses float64, not Unity's exact mixed float arithmetic.
    """
    if profile not in ('loose','tight'):raise ValueError(profile)
    if density<=0 or not math.isfinite(density):raise ValueError('Invalid density')
    if bpm is None:return {'times_ms':None,'status':'unknown_bpm'}
    if end<=start:return {'times_ms':[],'status':'zero_duration'}
    if bpm==0:return {'times_ms':None,'status':'zero_bpm_unresolved'}
    interval=(60000 if abs(bpm)>=255 else 30000)/abs(bpm)/density
    total=math.floor((end-start)/interval)
    skip=0 if kind=='arc' and has_predecessor else 1
    if total<=skip:
        first=start if kind=='hold' and profile=='tight' else start+(end-start)/2
        raw=[first]
    else:raw=[start+i*interval for i in range(skip,total)]
    times=[math.trunc(t) if profile=='loose' else round(t,6) for t in raw]
    return {'times_ms':times,'interval_ms':interval,'status':'reference_hypothesis',
            'fresh_press_requirement':False,'max_validity_certified':False}


def build(doc):
    events={e['id']:e for e in doc['events']};timings=TimingMap(doc)
    density=1.0
    for line in doc['header'].splitlines():
        if line.startswith('TimingPointDensityFactor:'):density=float(line.split(':',1)[1])
    if not math.isfinite(density) or density<=0:raise ValueError('Invalid header density')
    arcs=[e for e in doc['events'] if e['kind']=='arc' and not e['noinput_group']]
    special_ids={e['id'] for e in arcs if e['color_raw']=='3' and e['trace_raw']=='false'
        and e['start_ms']==e['end_ms'] and e['geometry']['y0']==e['geometry']['y1']}
    links=connections([e for e in arcs if e['id'] not in special_ids])
    actions=[];longs=[];issues=[];ignored=Counter();disagreements=[]
    def issue(e,reason,details=None):
        issues.append({'event_id':e['id'],'source_line':e['source_line'],
            'time_ms':e.get('start_ms',int(e['args'][0]) if e['args'] else None),
            'reason':reason,'details':details})
    def action(e,kind,t,pos,child=None):
        a={'action_id':f"{e['id']}:{child if child is not None else kind}",
           'source_event_id':e['id'],'source_line':e['source_line'],'kind':kind,
           'time_ms':t,'position':pos,'requires_fresh_press':True,'hand':None,
           'status':'center_target_only','group':e['group']}
        actions.append(a)
        if pos is None:issue(e,'undefined_zero_duration_geometry')
    for e in doc['events']:
        k=e['kind']; a=e['args']
        if e['noinput_group']:
            if k in ('arc','tap','hold'):ignored[k]+=1
            continue
        if k=='tap':action(e,'floor_tap',e['start_ms'],floor_xy(float(a[1])))
        elif k=='hold':action(e,'hold_activation',e['start_ms'],floor_xy(float(a[2])))
        elif k=='arc':
            if e['id'] in special_ids:
                g=e['geometry'];action(e,'wide_sky_tap',e['start_ms'],plane_xy([(g['x0']+g['x1'])/2,g['y0']]))
            for i,ch in enumerate(e['children']):
                if ch['kind']=='arctap':action(e,'sky_tap',ch['time_ms'],plane_xy(arc_xy(e,ch['time_ms'])),i)
                else:issue(e,'unknown_arc_child',ch)
        if k not in ('hold','arc'):continue
        if k=='arc' and (e['trace_raw']!='false' or e['id'] in special_ids):continue
        start,end=e['start_ms'],e['end_ms'];bpm,problem=timings.at(e['group'],start)
        if problem:issue(e,problem)
        pred=links.get(e['id'],{'tight':[],'loose':[]})
        schedules={p:combo_schedule(start,end,bpm,k,bool(pred[p]),density,p) for p in ('tight','loose')}
        item={'source_event_id':e['id'],'source_line':e['source_line'],'kind':k,
              'start_ms':start,'end_ms':end,'group':e['group'],'bpm_at_start':bpm,
              'predecessor_candidates':pred,'combo_candidates':schedules,
              'contact_requirements_status':'unresolved','hand':None}
        if k=='hold':item['position']=floor_xy(float(a[2]))
        else:
            item['color']=e['color_raw']; item['geometry']=e['geometry']
            item['base_polyline']=polyline(e)
            item['base_curve_length']=path_length(item['base_polyline'])
            item['geometry_status']='analytic_reference_not_projected'
            if start==end and arc_xy(e,start) is None:issue(e,'instantaneous_arc_jump_preserved')
            if e['extensions_raw']:
                issue(e,'arc_smoothness_effect_requires_validation',e['extensions_raw'])
                item['geometry_status']='analytic_base_with_unverified_smoothness'
            for p,ids in pred.items():
                if len(ids)>1:issue(e,'branching_predecessors',{'profile':p,'event_ids':ids})
                if any(events[i]['color_raw']!=e['color_raw'] for i in ids):
                    issue(e,'color_change_at_geometric_connection',{'profile':p,'event_ids':ids})
        changes=timings.changes_inside(e['group'],start,end)
        if changes:issue(e,'timing_events_inside_long_note',changes)
        if schedules['tight']['times_ms']!=schedules['loose']['times_ms']:
            tight=schedules['tight']['times_ms'];loose=schedules['loose']['times_ms']
            max_shift=max((abs(a-b) for a,b in zip(tight,loose)),default=0) if tight is not None and loose is not None and len(tight)==len(loose) else None
            disagreements.append({'event_id':e['id'],'source_line':e['source_line'],
                'time_ms':start,'kind':k,'tight_count':None if schedules['tight']['times_ms'] is None else len(schedules['tight']['times_ms']),
                'loose_count':None if schedules['loose']['times_ms'] is None else len(schedules['loose']['times_ms']),
                'max_shift_ms':max_shift,
                'classification':'count_difference' if max_shift is None else ('timing_shift' if max_shift>=1 else 'sub_ms_representation')})
        longs.append(item)
    # Geometric composite candidates only: do not merge judgments or declare valid shared input.
    starts=defaultdict(list)
    for e in arcs:
        if e['trace_raw']=='false' and e['end_ms']>e['start_ms']:
            starts[e['start_ms']].append(e)
    composites=[]
    for a in actions:
        if a['kind'] not in ('sky_tap','wide_sky_tap') or a['position'] is None:continue
        for dt in (-1,0,1):
            for e in starts[a['time_ms']+dt]:
                pos=plane_xy(arc_xy(e,e['start_ms']))
                if pos is not None and math.dist(a['position'],pos)<1e-9:
                    composites.append({'tap_action_id':a['action_id'],'arc_event_id':e['id'],
                        'time_ms':a['time_ms'],'time_difference_ms':dt,'status':'candidate_requires_contact_validation'})
    # Annotation-only candidates: never infer minimum physical contact count from these alone.
    simultaneous=defaultdict(list)
    for a in actions:simultaneous[a['time_ms']].append(a['action_id'])
    multi=[{'time_ms':t,'action_ids':ids,'status':'multiple_press_candidates_not_contact_count'}
           for t,ids in sorted(simultaneous.items()) if len(ids)>=3]
    summary={'chart':doc['name'],'press_candidates':len(actions),'long_objects':len(longs),
        'arc_segments':sum(l['kind']=='arc' for l in longs),'hold_activations':sum(a['kind']=='hold_activation' for a in actions),
        'composite_candidates':len(composites),'three_plus_press_timestamps':len(multi),
        'timing_disagreements':len(disagreements),'count_disagreements':sum(d['tight_count']!=d['loose_count'] for d in disagreements),
        'timing_shift_at_least_1ms':sum(d['classification']=='timing_shift' for d in disagreements),
        'issue_counts':dict(Counter(i['reason'] for i in issues)), 'noinput_ignored':dict(ignored)}
    actions.sort(key=lambda a:(a['time_ms'],a['action_id']))
    return {'schema_version':'0.2','chart':doc['name'],'sha256':doc['sha256'],
        'coordinate_system':'unprojected_editor_plane_x_aff_y_world_div_8.5',
        'clock':'AFF milliseconds; AudioOffset retained in parsed input, not applied',
        'certified_for_max':False,'multifinger_heuristic_ms':200,
        'scene_controls_not_projected':sorted({e['args'][1] for e in doc['events'] if e['kind']=='scenecontrol'}),
        'automatic_exclusions':[], 'press_candidates':actions,'long_objects':longs,
        'composite_candidates':composites,'multiple_press_candidates':multi,
        'timing_disagreements':disagreements,'issues':issues,'summary':summary}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('output');args=ap.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True);summary=[]
    for p in sorted(Path(args.input).glob('*.json')):
        if p.name=='summary.json':continue
        d=build(json.loads(p.read_text()));summary.append(d['summary'])
        (out/p.name).write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
