"""Versioned interchange contract shared by the two command-line programs."""
import hashlib,json
from pathlib import Path
FORMAT='arcaea-input-sequence/1'
FIELDS=('unit_id','kind','start_ms','end_ms','hand','start_position','end_position','source_event_ids','action_ids','arc_color','fresh_press')
def fingerprint(units):
    data=[{k:v for k,v in u.items() if k!='hand'} for u in units]
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def compact(result,filename):
    units=[{k:u[k] for k in FIELDS} for u in result['units']]
    extraction=result['extraction']
    for g in extraction.get('adjacent_arc_groups',[]):g.pop('support_assignments',None)
    return {'format':FORMAT,'algorithm_version':'snapshot-1.2','chart':filename,'sha256':result['sha256'],
      'coordinate_system':'x=AFF; y=(1+4.5*AFF_y)/8.5; floor_y=0',
      'time_unit':'milliseconds in AFF clock; AudioOffset not applied','certified_for_max':False,
      'preferences':result['preferences'],'configuration':result['configuration'],
      'structure_sha256':fingerprint(units),'units':units,'extraction':extraction,
      'multitouch':result['multitouch'],'review_windows':result['review_windows'],
      'visual_review_markers':result.get('visual_review_markers',[]),'mechanic_review':result.get('mechanic_review',[]),
      'summary':result['summary'],'flow_context':result.get('flow_context',{})}
def write_sequence(path,result):
    # One operation per line, with a standard JSON envelope (not JSONL).
    rest={k:v for k,v in result.items() if k!='units'}
    text=json.dumps(rest,ensure_ascii=False,indent=2)
    text=text[:-2]+',\n  "units": [\n'+',\n'.join('    '+json.dumps(u,ensure_ascii=False,separators=(',',':')) for u in result['units'])+'\n  ]\n}\n'
    Path(path).write_text(text,encoding='utf-8')
def validate(seq,source):
    if seq.get('format')!=FORMAT:raise ValueError('Unsupported sequence format')
    if hashlib.sha256(Path(source).read_bytes()).hexdigest()!=seq.get('sha256'):raise ValueError('Sequence/source SHA-256 mismatch')
    units=seq['units']
    if fingerprint(units)!=seq.get('structure_sha256'):raise ValueError('Operation structure changed; regenerate the sequence')
    ids=[u['unit_id'] for u in units]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate operation IDs')
    for u in units:
        if u['hand'] not in ('L','R',None):raise ValueError('Hand must be L, R or null')
        if u['end_ms']<u['start_ms']:raise ValueError('Negative operation duration')
    for h in ('L','R'):
        ordered=sorted((u for u in units if u['hand']==h),key=lambda u:u['start_ms'])
        for a,b in zip(ordered,ordered[1:]):
            if a['end_ms']>b['start_ms'] or a['start_ms']==b['start_ms']:raise ValueError('Conflicting assignments for '+h+': '+a['unit_id']+', '+b['unit_id'])
    return {'chart_sha256':seq['sha256'],'timeline':[{'id':u['unit_id'],'hand':{'L':'left','R':'right',None:'unassigned'}[u['hand']]} for u in units]}
