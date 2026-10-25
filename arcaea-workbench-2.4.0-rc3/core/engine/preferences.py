"""Explicit, tunable execution preferences; these are not game mechanics."""
from dataclasses import dataclass, asdict
from statistics import median

@dataclass(frozen=True)
class Preferences:
    alternate_below_ms: float=200
    alternate_weight: float=12
    arc_color_weight: float=24
    natural_start_weight: float=18
    checkpoint_weight: float=30
    hold_side_weight: float=0 # legacy setting, no longer applied
    comfort_weight: float=9
    burst_relief: float=1
    pair_relief: float=.95
    pair_distance_scale: float=.20
    flow_consistency_weight: float=12
    pair_strategy_prior: float=3
    ground_aversion_weight: float=12
    territory_weight: float=5
    obstruction_weight: float=10
    color_hands: tuple=('L','R')
    reset_min_ms: float=160
    reset_gap_multiplier: float=8
    reset_move_ms: float=500

    def __post_init__(self):
        if self.pair_relief>1 or self.burst_relief>1:raise ValueError('Relief factors must be between zero and one')
        for k,v in asdict(self).items():
            if k=='color_hands':continue
            if not isinstance(v,(int,float)) or not __import__('math').isfinite(v) or v<0:
                raise ValueError(f'Invalid preference {k}')
        if self.alternate_below_ms<=0 or self.reset_move_ms<=0 or self.pair_distance_scale<=0:raise ValueError('Time scales must be positive')
        if tuple(self.color_hands) not in (('L','R'),('R','L')):raise ValueError('color_hands must assign colors 0/1 to opposite hands')

def context(units,prefs):
    """Detect phrase slots and idle gaps; retain legacy pair candidates for comparison."""
    from collections import defaultdict
    packets=defaultdict(list)
    for i,u in enumerate(units):packets[u.start].append(i)
    times=sorted(packets);runs=[];run=[];phrase_starts=set()
    threshold=prefs.reset_min_ms
    resets=[];latest_end=None
    for t in times:
        if latest_end is not None and t-latest_end>=threshold:
            resets.append({'start_ms':latest_end,'end_ms':t})
        latest_end=max([latest_end if latest_end is not None else t]+[units[i].end for i in packets[t]])
    reset_times={r['end_ms'] for r in resets}
    last_reset={i:max((t for t in reset_times if t<=u.start),default=-1) for i,u in enumerate(units)}
    for t in times:
        ids=packets[t];i=ids[0]
        eligible=len(ids)==1 and (units[i].fresh_press or units[i].kind=='arc')
        gap=t-units[run[-1]].start if run else 0
        phrase_boundary=t in reset_times
        if phrase_boundary:phrase_starts.update(ids)
        if not eligible or phrase_boundary or (run and not 0<gap<prefs.alternate_below_ms):
            if len(run)>=3:runs.append(run)
            run=[]
        if eligible:run.append(i)
    if len(run)>=3:runs.append(run)
    predecessors={b:a for run in runs for a,b in zip(run,run[1:])}
    # Admit paired strategies only with repeated close pairs separated by larger travel.
    # Stationary streams and general traversals retain alternating templates.
    import math
    template_modes={}
    for r,run in enumerate(runs):
        modes=[0,1]
        for mode in range(2,6):
            within=[];between=[]
            for k in range(1,len(run)):
                d=math.dist(units[run[k-1]].start_pos,units[run[k]].start_pos)
                target=within if ((k+mode-2)//2)%2==((k-1+mode-2)//2)%2 else between
                target.append(d)
            if len(within)>=2 and between and sum(math.exp(-(d/prefs.pair_distance_scale)**2) for d in within)/len(within)>=.65 and sum(between)/len(between)>=sum(within)/len(within)+.08:
                modes.append(mode)
        template_modes[r]=modes
    checkpoints={i for ids in packets.values() if len(ids)==2 and all(units[j].fresh_press and units[j].kind!='hold' for j in ids) for i in ids}
    starts={run[0] for run in runs}|phrase_starts
    for k,t in enumerate(times):
        if k==0 or t-times[k-1]>=300:starts.update(packets[t])
    # Spatially isolated pairs, not an arbitrary first two notes of a stream.
    import math
    pairs={}
    for k in range(len(times)-1):
        left,right=packets[times[k]],packets[times[k+1]]
        if len(left)!=1 or len(right)!=1:continue
        a,b=left[0],right[0];ua,ub=units[a],units[b]
        if ua.kind not in ('floor_tap','sky_tap','wide_sky_tap') or ub.kind!=ua.kind:continue
        if not 0<ub.start-ua.start<prefs.alternate_below_ms or math.dist(ua.start_pos,ub.start_pos)>.08:continue
        previous=packets[times[k-1]] if k else []
        following=packets[times[k+2]] if k+2<len(times) else []
        before_boundary=not previous or len(previous)!=1 or math.dist(units[previous[0]].start_pos,ua.start_pos)>.2 or ua.start-times[k-1]>=prefs.alternate_below_ms
        after_boundary=not following or len(following)!=1 or math.dist(units[following[0]].start_pos,ub.start_pos)>.2 or times[k+2]-ub.start>=prefs.alternate_below_ms
        if before_boundary and after_boundary:pairs[b]=a
    # A phrase adopts pair relief only when pairs dominate its geometry.
    # Sparse local pairs inside a traversal keep the stream's alternation cost.
    suppressed=[]
    for run in runs:
        candidates=[b for b,a in pairs.items() if b in run and a in run]
        if len(run)>=6 and 2*len(candidates)/len(run)<.6:
            for b in candidates:suppressed.append([pairs.pop(b),b])
    local_gaps={i:(t-times[k-1] if k else 1000) for k,t in enumerate(times) for i in packets[t]}
    return {'last_reset':last_reset,'template_modes':template_modes,'reset_times':reset_times,'suppressed_local_pairs':suppressed,'pair_predecessors':pairs,'local_gaps':local_gaps,'run_predecessors':predecessors,'runs':runs,'resets':resets,'reset_threshold_ms':threshold,
            'natural_starts':starts,'checkpoints':checkpoints,
            'flow_slots':{i:(r,k) for r,run in enumerate(runs) for k,i in enumerate(run)}}
