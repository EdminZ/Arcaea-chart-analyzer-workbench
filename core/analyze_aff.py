#!/usr/bin/env python3
"""Read an original AFF and write an input-operation sequence; Python 3.10+."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'engine'))
from audit import analyze
from reconstruct import build
from assign import plan
from preferences import Preferences
from sequence_io import compact,write_sequence

def build_controls(doc):
    return sorted({e['args'][1] for e in doc['events'] if e['kind']=='scenecontrol'})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('chart',type=Path);p.add_argument('-o','--output',type=Path,required=True);p.add_argument('--beam-width',type=int,default=128);p.add_argument('--preferences',type=Path);p.add_argument('--annotations',type=Path);p.add_argument('--include-hidden',action='store_true',help='Include inputs excluded by the provisional hidden-group policy')
    p.add_argument('--hand-overrides',type=Path,help='JSON with source_sha256 and force_hands mapping')
    a=p.parse_args()
    if a.output.exists():raise ValueError('Output already exists; choose a new filename')
    if a.output.resolve()==a.chart.resolve():raise ValueError('Output must differ from source')
    prefs=Preferences(**json.loads(a.preferences.read_text(encoding='utf-8'))) if a.preferences else Preferences()
    doc,audit=analyze(a.chart)
    if audit.get('warnings'):raise ValueError('Unsupported or malformed events: '+str(doc['warnings']))
    overrides={'include_hidden_inputs':a.include_hidden}
    if a.hand_overrides:
        correction=json.loads(a.hand_overrides.read_text(encoding='utf-8'))
        if correction.get('source_sha256')!=doc['sha256']:raise ValueError('Hand corrections belong to a different original')
        overrides['force_hands']=correction['force_hands']
    result=plan(doc,build(doc),a.beam_width,overrides,prefs)
    if a.annotations:
        annotations=json.loads(a.annotations.read_text(encoding='utf-8'));entry=annotations.get('by_sha256',{}).get(doc['sha256'])
        if entry is None:raise ValueError('Annotations do not contain this exact source hash')
        result['multitouch']['user_confirmed_exclusions']=entry.get('confirmed_metric_exclusions',[])
        result['visual_review_markers']=entry.get('visual_review_markers',[]);result['mechanic_review']=entry.get('mechanic_review',[])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    sequence=compact(result,a.chart.name)
    ids={i for u in result['units'] if u['kind']=='arc' for i in u['source_event_ids']}
    sequence['arc_geometry']=[{k:e[k] for k in ('id','start_ms','end_ms','geometry','color_raw','group')} for e in doc['events'] if e['id'] in ids and e['kind']=='arc']
    sequence['limitations']={'not_an_official_judgement_emulator':True,'scene_controls_not_projected':build_controls(doc),'no_hardware_or_perspective_model':True}
    write_sequence(a.output,sequence)
    print(json.dumps({'sequence':str(a.output),'source_sha256':doc['sha256'],'summary':result['summary']},ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError) as e:print('Error: '+str(e),file=sys.stderr);sys.exit(2)
