"""Provisional close-parallel color-neutral recognition from player feedback.
0.18 AFF separation is a configurable recognition threshold, not a hitbox claim.
Only translation-identical curves are merged; crossing/diverging arcs are not.
"""
from copy import deepcopy
import math
from reconstruct import arc_xy,plane_xy

def reduce_pairs(units,recon,threshold=.18):
    from assign import Unit
    longs={x['source_event_id']:x for x in recon['long_objects']}
    removed=set();added=[];reports=[]
    for i,a in enumerate(units):
        if a.id in removed or a.color not in ('0','1') or len(a.segments)!=1:continue
        candidates=[]
        for b in units[i+1:]:
            if b.id in removed or b.color not in ('0','1') or a.color==b.color or len(b.segments)!=1:continue
            if a.start!=b.start or abs(a.end-b.end)>1:continue
            ga,gb=a.segments[0]['geometry'],b.segments[0]['geometry']
            if ga['curve']!=gb['curve']:continue
            if max(abs(ga['y0']-gb['y0']),abs(ga['y1']-gb['y1']))>1e-8:continue
            dx0=gb['x0']-ga['x0'];dx1=gb['x1']-ga['x1']
            if abs(dx0-dx1)>1e-8 or not 0<abs(dx0)<=threshold+1e-9:continue
            candidates.append(b)
        if len(candidates)!=1:continue
        b=candidates[0];e=deepcopy(a.segments[0]);e['end_ms']=min(a.end,b.end)
        for k in ('x0','x1','y0','y1'):e['geometry'][k]=(a.segments[0]['geometry'][k]+b.segments[0]['geometry'][k])/2
        ticks=[];windows=[]
        for v in (a,b):
            for schedule in longs[v.sources[0]]['combo_candidates'].values():
                ticks+=schedule.get('times_ms') or []
                if schedule.get('interval_ms'):windows.append(min(100,schedule['interval_ms']/2))
        tick_window=min(windows or [0]);ticks=sorted(set(ticks))
        support=[]
        for tap in recon['press_candidates']:
            if tap['kind']!='sky_tap' or tap['position'] is None or not e['start_ms']<=tap['time_ms']<=e['end_ms']:continue
            if math.dist(tap['position'],plane_xy(arc_xy(e,tap['time_ms'])))<=.015:support.append(tap)
        covered=bool(ticks) and all(any(abs(t-tap['time_ms'])<=tick_window for tap in support) for t in ticks)
        report={'source_event_ids':list(a.sources+b.sources),'start_ms':a.start,'end_ms':max(a.end,b.end),
                'status':'provisional_colorless_tap_support' if covered else 'provisional_colorless_shared_contact',
                'recognition_threshold_aff':threshold,'separation_aff':abs(a.start_pos[0]-b.start_pos[0]),
                'support_action_ids':[t['action_id'] for t in support] if covered else [],
                'tick_window_ms':tick_window,'certified':False}
        removed.update((a.id,b.id))
        if not covered:
            start=min(ticks) if ticks else a.start;start=max(a.start,min(e['end_ms'],start))
            u=Unit('N'+str(a.sources[0]),'arc',start,e['end_ms'],tuple(plane_xy(arc_xy(e,start))),tuple(plane_xy(arc_xy(e,e['end_ms']))),a.sources+b.sources,color='neutral',segments=(e,))
            added.append(u);report['unit_id']=u.id;report['first_contact_ms']=start
        reports.append(report)
    return [u for u in units if u.id not in removed]+added,reports
