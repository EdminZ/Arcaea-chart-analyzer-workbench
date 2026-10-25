"""Conservative, event-driven two-finger assignment prototype (not MAX-certified).
python assign.py PARSED RECONSTRUCTED OUTPUT [--beam-width 64] [--overrides FILE]
"""
import argparse, bisect, csv, itertools, json, math
from collections import Counter, defaultdict
from dataclasses import dataclass,asdict,replace
from preferences import Preferences,context
from input_policy import hidden_events,contact_candidates
from pathlib import Path
from reconstruct import arc_xy,plane_xy

HANDS=('L','R')

@dataclass
class Unit:
    id: str
    kind: str
    start: int
    end: int
    start_pos: tuple
    end_pos: tuple
    sources: tuple
    actions: tuple=()
    color: str | None=None
    segments: tuple=()
    fresh_press: bool=False

    def at(self,t):
        if not self.segments:return self.start_pos
        for e in self.segments:
            if e['start_ms']<=t<=e['end_ms'] and e['end_ms']>e['start_ms']:return tuple(plane_xy(arc_xy(e,t)))
        # <=1 ms gap within an exact-coordinate chain: stay at the shared endpoint.
        before=[e for e in self.segments if e['end_ms']<=t and e['end_ms']>e['start_ms']]
        if before:return tuple(plane_xy(arc_xy(before[-1],before[-1]['end_ms'])))
        return self.start_pos


def make_units(doc,recon,include_hidden=False):
    events={e['id']:e for e in doc['events']}
    hidden=set() if include_hidden else set(hidden_events(doc))
    recon={**recon,'long_objects':[x for x in recon['long_objects'] if x['source_event_id'] not in hidden],
           'press_candidates':[x for x in recon['press_candidates'] if x['source_event_id'] not in hidden]}
    canonical={};duplicates=defaultdict(list);zero=[];aliases=[]
    for l in recon['long_objects']:
        if l['kind']!='arc':continue
        e=events[l['source_event_id']]
        if e['end_ms']<e['start_ms']:continue
        if e['end_ms']==e['start_ms']:zero.append(e['id'])
        shape=(tuple(sorted(e['geometry'].items())),e['color_raw'],tuple(e['extensions_raw']),e['end_ms']==e['start_ms'])
        key=next((k for ds in (0,-1,1,-2,2) for de in (0,-1,1,-2,2)
                  if (k:=(e['start_ms']+ds,e['end_ms']+de,*shape)) in canonical
                  and (max(abs(ds),abs(de))<=1 or canonical[k]['group']!=e['group'])),None)
        if key is None:
            key=(e['start_ms'],e['end_ms'],*shape);canonical[key]=dict(e)
        elif (canonical[key]['start_ms'],canonical[key]['end_ms'])!=(e['start_ms'],e['end_ms']):
            aliases.append({'source_id':e['id'],'canonical_id':canonical[key]['id'],'reason':'coincident_identical_shape_endpoint_rounding','start_difference_ms':e['start_ms']-canonical[key]['start_ms'],'end_difference_ms':e['end_ms']-canonical[key]['end_ms']})
            canonical[key]['start_ms']=min(canonical[key]['start_ms'],e['start_ms'])
            canonical[key]['end_ms']=max(canonical[key]['end_ms'],e['end_ms'])
        duplicates[canonical[key]['id']].append(e['id'])
    arcs=sorted(canonical.values(),key=lambda e:(e['start_ms'],e['id']))
    ends=defaultdict(list);before=defaultdict(list);after=defaultdict(list)
    for e in arcs:ends[(e['end_ms'],e['color_raw'])].append(e)
    for e in arcs:
        g=e['geometry']
        for dt in (-1,0,1):
            for p in ends[(e['start_ms']-dt,e['color_raw'])]:
                pg=p['geometry']
                # One AFF decimal rounding quantum; link ownership only, never edit coordinates.
                close=max(abs(pg['x1']-g['x0']),abs(pg['y1']-g['y0']))<=.010000001
                if close and p['id']!=e['id'] and p['start_ms']<=e['start_ms'] and p['end_ms']<=e['end_ms'] and (p['start_ms'],p['end_ms'])!=(e['start_ms'],e['end_ms']):
                    before[e['id']].append(p['id']);after[p['id']].append(e['id'])
    next_id={};prev_id={}
    for e in arcs:
        ps=before[e['id']]
        if len(ps)==1 and len(after[ps[0]])==1:
            prev_id[e['id']]=ps[0];next_id[ps[0]]=e['id']
    lookup={e['id']:e for e in arcs};units=[];used=set()
    for e in arcs:
        if e['id'] in prev_id:continue
        chain=[];i=e['id']
        while i not in used:
            used.add(i);chain.append(lookup[i])
            if i not in next_id:break
            i=next_id[i]
        positive=[e for e in chain if e['end_ms']>e['start_ms']]
        if not positive:continue
        first,last=positive[0],positive[-1]
        units.append(Unit('A'+str(first['id']),'arc',first['start_ms'],last['end_ms'],
            tuple(plane_xy(arc_xy(first,first['start_ms']))),tuple(plane_xy(arc_xy(last,last['end_ms']))),
            tuple(i for e in chain for i in duplicates[e['id']]),color=first['color_raw'],segments=tuple(chain)))
    assert len(used)==len(arcs),'Unexpected cyclic chain'
    releases=[]
    long_by_id={x['source_event_id']:x for x in recon['long_objects']}
    from adjacent_arcs import reduce_pairs
    units,adjacent=reduce_pairs(units,recon)
    hold_groups={}
    for a in recon['press_candidates']:
        if a['kind']!='hold_activation':continue
        e=events[a['source_event_id']];key=(e['start_ms'],e['end_ms'],tuple(a['position']))
        if key not in hold_groups:
            u=Unit('H'+str(e['id']),'hold',e['start_ms'],e['end_ms'],tuple(a['position']),tuple(a['position']),(),fresh_press=True)
            hold_groups[key]=u;units.append(u)
        u=hold_groups[key];u.sources+= (e['id'],);u.actions+=(a['action_id'],)
    # Hold maintenance has no exertion cost, but reserves its owner until the
    # source end. Judgment leniency alone never authorizes early release.
    # Only exact-time/exact-position sky taps at an unambiguous chain START merge.
    starts=defaultdict(list)
    for u in units:
        if u.kind=='arc':starts[(u.start,u.start_pos)].append(u)
    composite=[]
    for a in recon['press_candidates']:
        if a['kind']=='hold_activation':continue
        if a['position'] is None:continue
        pos=tuple(a['position']);targets=starts[(a['time_ms'],pos)] if a['kind'] in ('sky_tap','wide_sky_tap') else []
        if targets and not targets[0].actions:
            u=targets[0];u.actions+=(a['action_id'],);u.fresh_press=True
            composite.append({'unit_id':u.id,'action_id':a['action_id'],'status':'assumed_tap_then_arc' if len(targets)==1 else 'coincident_arc_heads_one_tap_owner_review'})
        else:
            units.append(Unit('T'+a['action_id'],a['kind'],a['time_ms'],a['time_ms'],pos,pos,
                (a['source_event_id'],),(a['action_id'],),fresh_press=True))
    units.sort(key=lambda u:(u.start,u.id))
    joins=[{'predecessor_id':a,'successor_id':b,
            'gap_ms':lookup[b]['start_ms']-lookup[a]['end_ms']}
           for a,b in next_id.items()]
    bridges=[{'unit_id':u.id,'source_ids':[e['id'] for e in u.segments if e['end_ms']-e['start_ms']<=1]}
             for u in units if u.kind=='arc' and any(e['end_ms']-e['start_ms']<=1 for e in u.segments)]
    return units,{'adjacent_arc_groups':adjacent,'single_tick_releases':releases,'hidden_input_policy':'exclude_fully_hidden_source_events_for_intent_review_only','hidden_source_event_ids':sorted(hidden),'zero_duration_arc_ids':zero,'composites':composite,'chain_joins':joins,'continuity_bridges':bridges,'rounded_duplicate_arcs':aliases,
                  'unpositioned_actions':[a['action_id'] for a in recon['press_candidates'] if a['position'] is None]}

@dataclass(slots=True)
class History:
    parent: object
    decisions: tuple

@dataclass(slots=True)
class State:
    last: tuple=(-1,-1)
    presses: tuple=(None,None)
    missing: int=0
    cost: float=0.0
    history: object=None
    run_last: tuple=(-1,-1)
    press_history: tuple=((),())
    pattern: tuple=(-1,-1) # phrase ID, template (A0/A1/P0/P1/P2/P3)


def obstruction(left,right):
    """Soft 2D arm overlap proxy. Not a physical collision certificate."""
    def distance(p,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
        t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0
        return math.dist(p,(a[0]+t*dx,a[1]+t*dy))
    # Contact near the opposite forearm; includes collinear ground overlap.
    clearance=min(distance(left,(1,0),right),distance(right,(0,0),left))
    return max(0,1-clearance/.12)**2


def transition(state,index,hand,units,prefs=None,ctx=None):
    prefs=prefs or Preferences();ctx=ctx or {'run_predecessors':{},'resets':[]}
    u=units[index];prev_idx=state.last[hand];extra=0.0
    if prev_idx>=0:
        prev=units[prev_idx]
        if prev.end>u.start:return None
        dt=(u.start-prev.end)/1000;d=math.dist(prev.end_pos,u.start_pos)
        if dt<=0 and d>1e-9:return None
        if dt>0:extra+=d/dt
    else:
        # Initial idle hand position is a declared tie preference, not measured travel.
        extra+=.02*abs(u.start_pos[0]-(.0 if hand==0 else 1.0))
    # Two separate simultaneous colored chains cannot both own the same color.
    other_idx=state.last[1-hand]
    if u.color is not None and other_idx>=0:
        other=units[other_idx]
        if other.end>u.start and other.color==u.color:return None
    slot=ctx.get('flow_slots',{}).get(index)
    pair_repeat=False
    if slot is not None and state.pattern[0]==slot[0]:
        ordinal=slot[1];mode=state.pattern[1]
        expected=(ordinal+mode)%2 if mode<2 else ((ordinal+mode-2)//2)%2
        if hand!=expected:extra+=prefs.flow_consistency_weight
        if mode>=2 and ordinal>0:
            prior_expected=((ordinal-1+mode-2)//2)%2
            pair_repeat=(expected==prior_expected==hand and
                         ctx['run_predecessors'].get(index)==prev_idx and prev_idx>=0)
    # Smooth spatial relief, with no .08 coordinate classification cliff.
    pair_strength=math.exp(-(math.dist(units[prev_idx].start_pos,u.start_pos)/prefs.pair_distance_scale)**2) if pair_repeat else 0.0
    pair_factor=1-prefs.pair_relief*pair_strength
    last_press=state.presses[hand]
    if u.fresh_press and last_press is not None:
        dt=(u.start-last_press)/1000
        if dt<=0:return None
        recent=[t for t in state.press_history[hand] if u.start-t<600]
        load=min(1.0,max(0.0,(len(recent)-1)/3))
        extra+=(.12/dt)**2*(1-prefs.burst_relief*.75*(1-load))*pair_factor
    # Weak side preference; never a hard left/right/color mapping.
    extra+=.005*(max(0,u.start_pos[0]-.5) if hand==0 else max(0,.5-u.start_pos[0]))
    if u.color in ('0','1') and HANDS[hand]!=prefs.color_hands[int(u.color)]:
        extra+=prefs.arc_color_weight*(.25+min(2,(u.end-u.start)/1000))
    predecessor=ctx['run_predecessors'].get(index)
    if predecessor is not None and state.run_last==(predecessor,hand):
        dt=u.start-units[predecessor].start
        recent=[t for t in state.press_history[hand] if u.start-t<600]
        sustained=min(1.0,max(0.0,(len(recent)-1)/3))
        extra+=prefs.alternate_weight*(prefs.alternate_below_ms/dt)**2*(.45+.55*sustained)*pair_factor
    wrong=max(0,u.start_pos[0]-.5) if hand==0 else max(0,.5-u.start_pos[0])
    # A natural posture is a preference only when both hands can prepare it.
    # Use the SAME readiness multiplier for competing assignments, to avoid
    # rewarding a hand merely because its own available time is shorter.
    available=[u.start-units[j].end for j in state.last if j>=0 and units[j].start<u.start]
    slack=min(available) if available else 500
    readiness=min(1.0,max(0.0,slack/200))**2
    x,y=u.start_pos
    # Superellipse distance from a low home region approximates rounded rectangles.
    def comfort(h):
        return ((abs(x-(.1 if h==0 else .9))/.65)**4+(abs(y)/.8)**4)**.25
    imbalance=max(0.0,comfort(hand)-comfort(1-hand))
    gap=ctx.get('local_gaps',{}).get(index,300)
    low_load=min(1.0,max(0.0,(gap-80)/220))
    extra+=prefs.comfort_weight*imbalance*low_load*(2 if u.kind in ('floor_tap','hold') else 1)
    # Cross-body ground reach rises quadratically; the sky cost fades smoothly.
    groundness=math.exp(-(max(0.0,y)/.35)**2)
    extra+=prefs.ground_aversion_weight*wrong**2*groundness*(.25+.75*low_load)
    if other_idx>=0 and ctx.get('last_reset',{}).get(index,-1)<=units[other_idx].end and units[other_idx].start<u.start:
        other=units[other_idx];op=other.at(min(max(u.start,other.start),other.end))
        own_side=(op[0]<=.5) if 1-hand==0 else (op[0]>=.5)
        recently_active=math.exp(-max(0,u.start-other.end)/250)
        if own_side:
            # This is spatial preference only: occupancy remains a hard constraint.
            extra+=prefs.territory_weight*wrong*groundness*recently_active
    if other_idx>=0 and ctx.get('last_reset',{}).get(index,-1)<=units[other_idx].end and units[other_idx].start<u.start:
        op=units[other_idx].at(min(u.start,units[other_idx].end))
        extra+=prefs.obstruction_weight*obstruction(u.start_pos,op) if hand==0 else prefs.obstruction_weight*obstruction(op,u.start_pos)
    if index in ctx.get('natural_starts',()):extra+=prefs.natural_start_weight*wrong*readiness
    if index in ctx.get('checkpoints',()):extra+=prefs.checkpoint_weight*wrong*readiness
    last=list(state.last);last[hand]=index
    presses=list(state.presses)
    if u.fresh_press:presses[hand]=u.start
    history=list(state.press_history)
    if u.fresh_press:history[hand]=tuple(t for t in history[hand] if u.start-t<600)+(u.start,)
    return State(tuple(last),tuple(presses),state.missing,state.cost+extra,state.history,(index,hand),tuple(history),state.pattern)


def solve(units,beam_width=64,forced=None,excluded=None,prefs=None):
    prefs=prefs or Preferences();ctx=context(units,prefs)
    if beam_width<1:raise ValueError('Beam width must be positive')
    forced=forced or {};excluded=set(excluded or ());packets=defaultdict(list)
    for i,u in enumerate(units):packets[u.start].append(i)
    beam=[State()]
    for time,indices in sorted(packets.items()):
        next_states={}
        if time in ctx['reset_times']:
            # True global idle: start a fresh decision state; history retains prior output.
            beam=[replace(st,last=(-1,-1),presses=(None,None),run_last=(-1,-1),press_history=((),()),pattern=(-1,-1)) for st in beam]
        origins=beam
        slot=ctx.get('flow_slots',{}).get(indices[0]) if len(indices)==1 else None
        if slot is not None:
            origins=[]
            for st in beam:
                if st.pattern[0]==slot[0]:origins.append(st)
                else:
                    for mode in ctx['template_modes'][slot[0]]:
                        origins.append(replace(st,pattern=(slot[0],mode),cost=st.cost+(prefs.pair_strategy_prior if mode>=2 else 0)))
        for origin in origins:
            # Always retain omission as a REVIEW outcome, with lexicographic penalty.
            # At most two assignments per packet, so enumerate subsets in O(m^2), not 3^m.
            usable=[i for i in indices if units[i].id not in excluded]
            for n in range(min(2,len(usable))+1):
                for selected in itertools.combinations(usable,n):
                    if any(units[i].id in forced for i in usable if i not in selected):continue
                    for hands in itertools.permutations((0,1),n):
                        st=origin;valid=True
                        for i,h in zip(selected,hands):
                            if units[i].id in forced and forced[units[i].id]!=HANDS[h]:valid=False;break
                            st=transition(st,i,h,units,prefs,ctx)
                            if st is None:valid=False;break
                        if not valid:continue
                        packet_cost=0.0
                        if n==2:
                            positions=dict(zip(hands,[units[i].start_pos for i in selected]))
                            packet_cost+=prefs.obstruction_weight*obstruction(positions[0],positions[1])
                            for i,h,j in ((selected[0],hands[0],selected[1]),(selected[1],hands[1],selected[0])):
                                x,y=units[i].start_pos;ox=units[j].start_pos[0]
                                wrong=max(0,x-.5) if h==0 else max(0,.5-x)
                                other_home=(ox>=.5) if h==0 else (ox<=.5)
                                if other_home:packet_cost+=prefs.territory_weight*wrong*math.exp(-(max(0,y)/.35)**2)
                        assignment=dict(zip(selected,hands))
                        decisions=tuple((i,assignment.get(i)) for i in indices)
                        missing=origin.missing+len(usable)-n
                        run_last=st.run_last if len(indices)==1 and n==1 else (-1,-1)
                        candidate=State(st.last,st.presses,missing,st.cost+packet_cost,History(origin.history,decisions),run_last,st.press_history,st.pattern)
                        key=(candidate.last,candidate.presses,candidate.run_last,candidate.press_history,candidate.pattern)
                        old=next_states.get(key)
                        if old is None or (candidate.missing,candidate.cost)<(old.missing,old.cost):next_states[key]=candidate
        if not next_states:raise ValueError(f'Forced assignments infeasible at {time} ms')
        beam=sorted(next_states.values(),key=lambda s:(s.missing,s.cost,s.last))[:beam_width]
    best=min(beam,key=lambda s:(s.missing,s.cost))
    def unpack(st):
        result={};node=st.history
        while node is not None:
            for i,h in node.decisions:result[i]=None if h is None else HANDS[h]
            node=node.parent
        return result
    chosen=unpack(best)
    alternatives=[unpack(s) for s in beam[:8] if s.missing==best.missing and s.cost<=best.cost+max(1,abs(best.cost)*.02)]
    agreement={i:sum(a.get(i)==h for a in alternatives)/len(alternatives) for i,h in chosen.items()}
    return chosen,{'objective':best.cost,'unresolved_units':best.missing,'beam_width':beam_width,
        'retained_final_alternatives':len(alternatives),'agreement_with_retained_alternatives':agreement}


def review_windows(units,assignment,excluded,gap=200):
    intervals=[]
    for i,u in enumerate(units):
        if assignment[i] is None:
            intervals.append({'start_ms':u.start,'end_ms':u.end,'unit_ids':[u.id],
                'reason':'manual_exclusion' if u.id in excluded else 'unresolved_under_conservative_model'})
    # Group close unresolved occurrences for review only. Not a true contact-count verdict.
    out=[]
    for x in sorted(intervals,key=lambda x:x['start_ms']):
        if out and x['reason']==out[-1]['reason'] and x['start_ms']-out[-1]['end_ms']<=gap:
            out[-1]['end_ms']=max(out[-1]['end_ms'],x['end_ms']);out[-1]['unit_ids']+=x['unit_ids']
        else:out.append(x)
    return out


def plan(doc,recon,beam_width=64,overrides=None,prefs=None):
    prefs=prefs or Preferences()
    overrides=overrides or {}
    units,meta=make_units(doc,recon,include_hidden=overrides.get('include_hidden_inputs',False))
    known={u.id for u in units};forced=overrides.get('force_hands',{});excluded=set(overrides.get('exclude_units',[]))
    if (set(forced)|excluded)-known:raise ValueError('Override contains unknown unit id')
    if set(forced)&excluded:raise ValueError('Cannot force and exclude the same unit')
    if any(v not in HANDS for v in forced.values()):raise ValueError('Hand must be L or R')
    demand=contact_candidates(units) # independent of assignment and hold cost
    assignment,stats=solve(units,beam_width,forced,excluded,prefs)
    ctx=context(units,prefs)
    windows=review_windows(units,assignment,excluded)
    unresolved_details=[]
    for i,u in enumerate(units):
        if assignment[i] is not None or u.id in excluded:continue
        reasons={}
        for h in HANDS:
            prior=[v for j,v in enumerate(units) if assignment[j]==h and v.start<=u.start]
            prev=max(prior,key=lambda v:(v.start,v.id)) if prior else None
            other_active=[v.id for j,v in enumerate(units) if assignment[j] not in (None,h)
                          and v.start<=u.start<v.end and u.color is not None and v.color==u.color]
            if prev and prev.end>u.start:reasons[h]={'reason':'finger_reserved','unit_id':prev.id}
            elif prev and prev.start==u.start:reasons[h]={'reason':'simultaneous_operation','unit_id':prev.id}
            elif prev and prev.end==u.start and math.dist(prev.end_pos,u.start_pos)>1e-9:reasons[h]={'reason':'zero_time_displacement','unit_id':prev.id}
            elif other_active:reasons[h]={'reason':'same_color_owned_by_other_finger','unit_ids':other_active}
            else:reasons[h]={'reason':'search_tradeoff_or_beam_pruning'}
        unresolved_details.append({'unit_id':u.id,'time_ms':u.start,'reasons_by_hand':reasons})
    rows=[];action_map={};arc_map={};hold_map={}
    for i,u in enumerate(units):
        h=assignment[i]
        row={'unit_id':u.id,'kind':u.kind,'start_ms':u.start,'end_ms':u.end,
             'start_position':u.start_pos,'end_position':u.end_pos,'source_event_ids':u.sources,
             'action_ids':u.actions,'hand':h,'finger':('L1' if h=='L' else 'R1') if h else None,
             'status':'manual_excluded' if u.id in excluded else ('candidate' if h else 'unresolved'),
             'fresh_press':u.fresh_press,'arc_color':u.color,
             'retained_alternative_agreement':stats['agreement_with_retained_alternatives'][i],
             'needs_review':any(w['start_ms']<=u.end and w['end_ms']>=u.start for w in windows),
             'start_x':u.start_pos[0],'start_y':u.start_pos[1],
             'end_x':u.end_pos[0],'end_y':u.end_pos[1]}
        rows.append(row)
        for a in u.actions:action_map[a]=h
        if u.kind=='arc':
            for e in u.sources:arc_map[e]=h
        if u.kind=='hold':
            for e in u.sources:hold_map[e]=h
    records=[]
    for e in doc['events']:
        if e['kind'] not in ('arc','tap','hold'):continue
        record={'source_event_id':e['id'],'source_line':e['source_line'],'kind':e['kind'],
            'start_ms':e['start_ms'],'end_ms':e['end_ms'],'group':e['group'],'hand':None,
            'status':'noinput' if e['noinput_group'] else 'noninput_geometry','arctaps':[]}
        if e['id'] in meta['hidden_source_event_ids']:
            record['status']='hidden_source_excluded_by_review_policy'
        elif not e['noinput_group']:
            if e['kind']=='hold':record.update(hand=hold_map.get(e['id']),status='candidate' if hold_map.get(e['id']) else 'unresolved')
            elif e['kind']=='tap':
                h=action_map.get(f"{e['id']}:floor_tap");record.update(hand=h,status='candidate' if h else 'unresolved')
            elif e['id'] in arc_map:record.update(hand=arc_map[e['id']],status='candidate' if arc_map[e['id']] else 'unresolved')
            elif f"{e['id']}:wide_sky_tap" in action_map:
                h=action_map[f"{e['id']}:wide_sky_tap"]
                record.update(hand=h,status='candidate' if h else 'unresolved',operation_kind='wide_sky_tap')
            elif e['id'] in meta['zero_duration_arc_ids']:record['status']='zero_duration_no_combo_model'
            for j,ch in enumerate(e['children']):
                if ch['kind']=='arctap':
                    h=action_map.get(f"{e['id']}:{j}")
                    record['arctaps'].append({'child_index':j,'time_ms':ch['time_ms'],'hand':h,'status':'candidate' if h else 'unresolved'})
        records.append(record)
    for group in meta['adjacent_arc_groups']:
        group['support_assignments']=[{'action_id':a,'hand':action_map.get(a)} for a in group['support_action_ids']]
        if group['support_action_ids']:
            for record in records:
                if record['source_event_id'] in group['source_event_ids']:
                    record.update(status='provisional_colorless_supported_by_taps',hand=None,
                                  support_assignments=group['support_assignments'])
    paths={h:[] for h in HANDS}
    for i,u in enumerate(units):
        h=assignment[i]
        if h is None:continue
        entry={'unit_id':u.id,'start_ms':u.start,'end_ms':u.end,'kind':u.kind,
               'start_position':u.start_pos,'end_position':u.end_pos,
               'geometry_event_ids':list(u.sources) if u.kind=='arc' else [],
               'path_type':'provisional_colorless_midpoint_path' if u.color=='neutral' else 'analytic_arc_chain' if u.kind=='arc' else ('stationary_hold' if u.kind=='hold' else 'point')}
        previous=paths[h][-1] if paths[h] else None
        entry['incoming_movement']=None
        if previous:
            a,b=previous['end_ms'],u.start
            blocked=any(w['start_ms']<=b and w['end_ms']>=a for w in windows)
            resets=[r for r in ctx['resets'] if a<=r['start_ms'] and r['end_ms']<=b]
            neutral=(0.0 if h=='L' else 1.0,0.0)
            travel=math.dist(previous['end_position'],u.start_pos)
            entry['incoming_movement']={'from_unit':previous['unit_id'],'available_ms':b-a,
                'distance':travel,'neutral_resets':resets,
                'status':'review_gap_do_not_score' if blocked else 'reset_gap_unmodelled' if resets else 'inferred_repositioning'}
        paths[h].append(entry)
    del stats['agreement_with_retained_alternatives']
    stats.update(chart=doc['name'],units=len(units),assigned_units=sum(h is not None for h in assignment.values()),
                 manual_excluded_units=len(excluded),review_windows=len(windows),composite_units=len(meta['composites']),
                 zero_duration_arcs=len(meta['zero_duration_arc_ids']))
    return {'schema_version':'snapshot-1.2','chart':doc['name'],'sha256':doc['sha256'],'certified_for_max':False,
        'preferences':asdict(prefs),'manual_overrides':overrides,
        'flow_context':{'reset_threshold_ms':ctx['reset_threshold_ms'],'resets':ctx['resets'],'reset_motion_policy':'direct_transfer_no_forced_neutral_detour','hold_policy':'full_source_duration','reset_state_policy':'clear_assignment_state_keep_archival_history_reset_travel_unscored','execution_templates':['LR','RL','LLRR','LRRL','RRLL','RLLR'],
            'tap_runs':[[units[i].id for i in run] for run in ctx['runs']],
            'spatial_double_taps':[[units[a].id,units[b].id] for b,a in ctx['pair_predecessors'].items()]},
        'model':'conservative_full_contact_beam','configuration':{'repeat_tau_seconds':.12,'repeat_power':2,
            'movement_cost':'distance / available_seconds','side_preference_weight':.005,
            'multifinger_review_gap_ms':200,'retained_color_reuse':False,'join_endpoint_time_tolerance_ms':1},
        'multitouch':demand,'summary':stats,'units':rows,'source_assignments':records,'paths':paths,'review_windows':windows,
        'unresolved_details':unresolved_details,'extraction':meta}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('parsed');ap.add_argument('reconstructed');ap.add_argument('output');ap.add_argument('--beam-width',type=int,default=64);ap.add_argument('--overrides')
    ap.add_argument('--preferences',help='JSON overrides for execution preferences')
    args=ap.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    prefs=Preferences(**json.loads(Path(args.preferences).read_text(encoding='utf-8'))) if args.preferences else Preferences()
    all_overrides=json.loads(Path(args.overrides).read_text(encoding='utf-8')) if args.overrides else {}
    corpus_hashes={json.loads(p.read_text(encoding='utf-8'))['sha256'] for p in Path(args.parsed).glob('*.json') if p.name!='summary.json'}
    if set(all_overrides)-corpus_hashes:raise ValueError('Override chart hash is not in this corpus; possible stale file')
    summaries=[]
    for p in sorted(Path(args.parsed).glob('*.json')):
        if p.name=='summary.json':continue
        doc=json.loads(p.read_text(encoding='utf-8'));recon=json.loads((Path(args.reconstructed)/p.name).read_text(encoding='utf-8'))
        if doc['sha256']!=recon['sha256']:raise ValueError('Mismatched chart versions')
        result=plan(doc,recon,args.beam_width,all_overrides.get(doc['sha256']),prefs)
        (out/p.name).write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        with (out/p.with_suffix('.csv').name).open('w',newline='',encoding='utf-8-sig') as f:
            fields=('unit_id','kind','start_ms','end_ms','hand','finger','status','needs_review','start_x','start_y','end_x','end_y','source_event_ids','action_ids','retained_alternative_agreement')
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(result['units'])
        with (out/(p.stem+'-transitions.csv')).open('w',newline='',encoding='utf-8-sig') as f:
            fields=('hand','time_ms','from_unit','to_unit','available_ms','distance','distance_per_second','status')
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for hand,entries in result['paths'].items():
                for e in entries:
                    m=e['incoming_movement']
                    if m is None:continue
                    rate=m['distance']/(m['available_ms']/1000) if m['available_ms']>0 and m['status']=='inferred_repositioning' else None
                    w.writerow(dict(hand=hand,time_ms=e['start_ms'],from_unit=m['from_unit'],to_unit=e['unit_id'],
                        available_ms=m['available_ms'],distance=m['distance'],distance_per_second=rate,status=m['status']))
        summaries.append(result['summary']);print(json.dumps(result['summary']),flush=True)
    (out/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
if __name__=='__main__':main()
