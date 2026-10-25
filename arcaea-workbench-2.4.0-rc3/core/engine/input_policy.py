"""Intent-analysis policy, not an assertion that hidegroup disables game judgement.
Retain source IDs of fully hidden events so consumers can restore them. Dynamic
visibility crossing an event is left untouched. ArcCreate hides rendering only;
these records are presumed alternate/display inputs for this review workflow.
"""
from collections import defaultdict

def hidden_events(doc):
    controls=defaultdict(list)
    for e in doc['events']:
        if e['kind']=='scenecontrol' and e['args'][1]=='hidegroup':
            controls[e['group']].append((int(e['args'][0]),e['id'],float(e['args'][-1])==1))
    for v in controls.values():v.sort()
    excluded=[]
    for e in doc['events']:
        if e['kind'] not in ('arc','tap','hold'):continue
        seq=controls[e['group']];prior=[s for s in seq if s[0]<=e['start_ms']]
        if prior and prior[-1][2] and not any(not hidden and e['start_ms']<t<=e['end_ms'] for t,_,hidden in seq):
            excluded.append(e['id'])
    return excluded

def contact_candidates(units):
    """Conservative full-contact demand, independent of hand-search omissions."""
    changes=defaultdict(lambda:{'start':[],'end':[],'point':[]})
    for u in units:
        if u.end>u.start:
            changes[u.start]['start'].append(u.id);changes[u.end]['end'].append(u.id)
        else:changes[u.start]['point'].append(u.id)
    active=set();out=[];times=sorted(changes)
    for j,t in enumerate(times):
        c=changes[t];active.difference_update(c['end']);active.update(c['start'])
        ids=active|set(c['point'])
        if len(ids)>2:out.append({'start_ms':t,'end_ms':t,'unit_ids':sorted(ids),'contact_count':len(ids)})
        if len(active)>2 and j+1<len(times):out.append({'start_ms':t,'end_ms':times[j+1],'unit_ids':sorted(active),'contact_count':len(active)})
    windows=[]
    for x in out:
        if windows and x['start_ms']-windows[-1]['end_ms']<=200:
            w=windows[-1];w['end_ms']=max(w['end_ms'],x['end_ms']);w['unit_ids']=sorted(set(w['unit_ids'])|set(x['unit_ids']));w['peak_contacts']=max(w['peak_contacts'],x['contact_count'])
        else:windows.append(dict(start_ms=x['start_ms'],end_ms=x['end_ms'],unit_ids=x['unit_ids'],peak_contacts=x['contact_count']))
    return {'model':'full_contact_conservative_upper_demand_not_judgement_proof','episodes':out,'windows':windows,'default_metric_policy':'separate_candidates_from_confirmed_exclusion_masks','path_policy':'do_not_connect_across_excluded_windows'}
