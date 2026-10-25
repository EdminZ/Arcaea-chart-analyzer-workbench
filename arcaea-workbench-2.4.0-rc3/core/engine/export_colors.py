"""Make an ArcCreate Touch-mode color preview; never overwrite the source.
python export_colors.py ORIGINAL_AFF BASE_ASSIGNMENT_JSON REVIEW_JSON OUTPUT_AFF
"""
import argparse,hashlib,json
from collections import defaultdict,Counter
from pathlib import Path
from audit import analyze
from reconstruct import arc_xy,build

def export(original,base,review,out):
    original=Path(original);out=Path(out)
    if original.resolve()==out.resolve():raise ValueError('Output must differ from original')
    doc,_=analyze(original);raw=original.read_bytes();text=raw.decode('utf-8-sig')
    if not doc['sha256']==base['sha256']==review['chart_sha256']:raise ValueError('Chart version mismatch')
    hand_by_unit={x['id']:x['hand'] for x in review['timeline']}
    actions={a:hand_by_unit[u['unit_id']] for u in base['units'] for a in u['action_ids']}
    groups={g['id']:g for g in doc['groups']};bygroup=defaultdict(list)
    for e in doc['events']:bygroup[e['group']].append(e)
    def safe(g):
        return not groups[g]['attributes'] and all(e['kind'] in ('timing','tap','hold','arc') for e in bygroup[g])
    buckets=defaultdict(list);edits=[];counts=Counter();markers=defaultdict(list)
    def marker(t,x,y,g,color=2):
        pts=[(x,y+.04),(x+.025,y),(x,y-.04),(x-.025,y),(x,y+.04)]
        for a,b in zip(pts,pts[1:]):markers[g].append(f'arc({t},{t},{a[0]:.6f},{b[0]:.6f},s,{a[1]:.6f},{b[1]:.6f},{color},none,false);')
    demand_episodes=base.get('multitouch',{}).get('episodes',[])
    def demand_at(t):
        return any((e['start_ms']<=t<e['end_ms'] or e['start_ms']==t==e['end_ms']) for e in demand_episodes)
    hidden=set(base.get('extraction',{}).get('hidden_source_event_ids',[]))
    for e in doc['events']:
        if e['noinput_group'] or e['id'] in hidden:continue
        gid=e['group']
        if e['kind'] in ('tap','hold'):
            action=f"{e['id']}:floor_tap" if e['kind']=='tap' else f"{e['id']}:hold_activation"
            hand=actions.get(action,'unassigned')
            if demand_at(e['start_ms']):
                marker(e['start_ms'],.5*float(e['args'][-1])-.75,-1/4.5,gid);counts['multitouch_candidate_markers']+=1
            if hand in ('left','right') and safe(gid):
                skin='light' if hand=='left' else 'conflict';buckets[(gid,skin)].append(e['source']);edits.append((*e['source_span'],''));counts[e['kind']]+=1
            elif hand=='unassigned':
                marker(e['start_ms'],.5*float(e['args'][-1])-.75,-1/4.5,gid);counts['unassigned_markers']+=1
            else:
                marker(e['start_ms'],.5*float(e['args'][-1])-.75,-1/4.5,gid,{'left':0,'right':1}[hand])
                counts['assigned_markers_in_unsupported_groups']+=1
        elif e['kind']=='arc' and e['children']:
            retained=[]
            for j,ch in enumerate(e['children']):
                hand=actions.get(f"{e['id']}:{j}",'unassigned')
                if ch['kind']=='arctap' and demand_at(ch['time_ms']):
                    pos=arc_xy(e,ch['time_ms'])
                    if pos is not None:marker(ch['time_ms'],*pos,gid);counts['multitouch_candidate_markers']+=1
                if ch['kind']!='arctap' or hand not in ('left','right') or not safe(gid) or e['extensions_raw']:
                    retained.append(ch)
                    if hand=='unassigned' and ch['kind']=='arctap':
                        p=arc_xy(e,ch['time_ms'])
                        if p is not None:marker(ch['time_ms'],*p,gid);counts['unassigned_markers']+=1
                    elif hand in ('left','right') and ch['kind']=='arctap':
                        p=arc_xy(e,ch['time_ms'])
                        if p is not None:marker(ch['time_ms'],*p,gid,{'left':0,'right':1}[hand]);counts['assigned_markers_in_unsupported_groups']+=1
                    continue
                pos=arc_xy(e,ch['time_ms'])
                if pos is None:retained.append(ch);continue
                t=ch['time_ms'];x,y=pos
                # Touch-mode sky textures have the opposite theme hue to floor notes.
                skin='conflict' if hand=='left' else 'light'
                statement=f'arc({t},{t},{x:.17g},{x:.17g},s,{y:.17g},{y:.17g},{e["color_raw"]},{e["args"][8]},true)[arctap('+','.join(ch['args'])+')];'
                buckets[(gid,skin)].append(statement);counts['sky_tap']+=1
            if len(retained)!=len(e['children']):
                replacement='arc('+','.join(e['args'])+')'
                if retained:replacement+='['+','.join(ch['kind']+'('+','.join(ch['args'])+')' for ch in retained)+']'
                edits.append((*e['source_span'],replacement+';'))
    event_by_id={e['id']:e for e in doc['events']}
    for u in base['units']:
        if u['kind']!='arc':continue
        hand=hand_by_unit[u['unit_id']]
        default={'0':'left','1':'right'}.get(str(u.get('arc_color')))
        if default is None or hand not in ('left','right') or hand==default:continue
        x,py=u['start_position'];gid=event_by_id[u['source_event_ids'][0]]['group']
        marker(u['start_ms'],x,(8.5*py-1)/4.5,gid,{'left':0,'right':1,'unassigned':2}[hand]);counts['arc_hand_markers']+=1
    for note in base.get('visual_review_markers',[]):
        x,py=note['position'];gid=event_by_id[note['source_event_ids'][0]]['group']
        marker(note['start_ms'],x,(8.5*py-1)/4.5,gid,2);counts['confirmed_review_markers']+=1
    for start,end,replacement in sorted(edits,reverse=True):text=text[:start]+replacement+text[end:]
    for (gid,skin),notes in sorted(buckets.items()):
        timings=[e['source'] for e in bygroup[gid] if e['kind']=='timing']
        text+='\ntiminggroup('+skin+'){\n'+'\n'.join(timings+notes)+'\n};\n'
    for gid,notes in sorted(markers.items()):
        timings=[e['source'] for e in bygroup[gid] if e['kind']=='timing']
        text+='\ntiminggroup(noinput){\n'+'\n'.join(timings+notes)+'\n};\n'
    out.write_text(text,encoding='utf-8');new,_=analyze(out)
    # Compare input positions/times and long geometry independently of source IDs.
    def presses(d):
        return Counter((a['kind'],a['time_ms'],tuple(round(v,6) for v in a['position']) if a['position'] else None) for a in build(d)['press_candidates'])
    def sustained(d):
        return Counter((e['kind'],tuple(e['args'])) for e in d['events'] if not e['noinput_group'] and (e['kind']=='hold' or e['kind']=='arc' and e['trace_raw']=='false'))
    assert presses(doc)==presses(new),'Input center/time mismatch'
    assert sustained(doc)==sustained(new),'Hold or judged-arc geometry changed'
    assert hashlib.sha256(original.read_bytes()).hexdigest()==doc['sha256']
    return {'chart':doc['name'],'source_sha256':doc['sha256'],'counts':dict(counts),'source_unchanged':True,
            'input_center_time_multiset_preserved':True,'judged_arc_and_hold_geometry_preserved':True,
            'runtime_visual_verification':False,'gameplay_equivalence_certified':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('original');p.add_argument('base');p.add_argument('review');p.add_argument('output');a=p.parse_args()
    print(json.dumps(export(a.original,json.loads(Path(a.base).read_text()),json.loads(Path(a.review).read_text()),a.output),indent=2))
