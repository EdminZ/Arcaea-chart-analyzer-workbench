"""Exact song ID/class matching; displayed ratings never imply chart constants."""
import copy, re, csv, io, math, unicodedata
from collections import defaultdict
from pathlib import Path
CLASSES={0:'PST',1:'PRS',2:'FTR',3:'BYD',4:'ETR',5:'INS'}
def index(data):
 if not isinstance(data,dict) or not isinstance(data.get('songs'),list):raise ValueError('Expected a songlist JSON object with songs')
 result={}
 for song in data['songs']:
  sid=song.get('id')
  if not isinstance(sid,str) or not sid:raise ValueError('Song missing ID')
  for d in song.get('difficulties',[]):
   cls=d.get('ratingClass')
   if not isinstance(cls,int):raise ValueError('Invalid ratingClass')
   key=(sid,cls)
   if key in result:raise ValueError('Duplicate song/class: '+str(key))
   title=d.get('title_localized',song.get('title_localized',{}))
   result[key]={'song_id':sid,'rating_class':cls,'difficulty_name':('INS' if cls==3 and d.get('ratingClassAlias')==1 else CLASSES.get(cls,str(cls))), 'title':title.get('en',sid), 'display_rating':str(d['rating'])+('+' if d.get('ratingPlus') else ''), 'chart_constant':d.get('chartConstant'), 'title_aliases':list(title.values())+list(song.get('title_localized',{}).values()), 'raw_difficulty':copy.deepcopy(d)}
 # Filename convention: ETR uses _3; keep _4 as a compatibility alias.
 for (sid,cls),entry in list(result.items()):
  if cls==4 and (sid,3) not in result:
   result[sid,3]={**copy.deepcopy(entry),'rating_class':3,'source_rating_class':4}
 return result
def identify(path):
 p=Path(path);stem=p.stem if p.suffix=='.aff' else p.name;folder=p.parent.name.removeprefix('dl_')
 m=re.fullmatch(r'(.+)_([0-9]+)',stem)
 if m:return m[1],int(m[2])
 if stem.isdigit():return folder,int(stem)
 return None,None
def match(aliases,entries):
 found={}
 for path in aliases:
  key=identify(path)
  if key in entries:found[key]=entries[key]
 if len(found)==1:return copy.deepcopy(next(iter(found.values())))
 return {'match_status':'ambiguous' if found else 'unmatched','chart_constant':None}
def visible(row,classes):return classes is None or row.get('metadata',{}).get('rating_class') in classes

def title_key(value):
 return ''.join(c for c in unicodedata.normalize('NFKC',value).casefold() if c.isalnum())
def read_constants(raw):
 """Validate all rows before replacing a workspace's previous table."""
 try:text=raw.decode('utf-8-sig');encoding='utf-8-sig'
 except UnicodeDecodeError:text=raw.decode('cp1252');encoding='cp1252'
 reader=csv.DictReader(io.StringIO(text));headers=reader.fieldnames or []
 if not all(k in headers for k in ('PST','PRS','FTR','BYD/INS','ETR')):raise ValueError('CSV requires PST, PRS, FTR, BYD/INS and ETR columns')
 title_column=next((k for k in headers if k not in ('PST','PRS','FTR','BYD/INS','ETR','song_id')),None)
 if title_column is None and 'song_id' not in headers:raise ValueError('CSV requires a title column or song_id')
 rows=[]
 for line,row in enumerate(reader,2):
  if not any(v for v in row.values()):continue
  if None in row:raise ValueError(f'Extra CSV cells at line {line}')
  values={}
  for name,cls in [('PST',0),('PRS',1),('FTR',2),('BYD/INS',3),('ETR',3)]:
   value=(row.get(name) or '').strip()
   if not value:continue
   try:number=float(value)
   except ValueError:raise ValueError(f'Invalid {name} constant at line {line}: {value}')
   if not math.isfinite(number) or number<0:raise ValueError(f'Constant must be finite and nonnegative at line {line}')
   if cls in values:raise ValueError(f'Both BYD/INS and ETR populated at line {line}; only one _3 constant is allowed')
   values[cls]=number
  rows.append({'line':line,'title':(row.get(title_column) or '').strip(),'song_id':(row.get('song_id') or '').strip(),'values':values})
 if not rows:raise ValueError('CSV contains no rows')
 return rows,encoding

def apply_constants(entries,raw):
 rows,encoding=read_constants(raw);aliases=defaultdict(set);exact=defaultdict(set);ids={sid for sid,cls in entries}
 for (sid,cls),entry in entries.items():
  for title in entry.get('title_aliases',[entry['title']]):
   exact[unicodedata.normalize('NFKC',title).casefold()].add(sid)
   key=title_key(title)
   if key:aliases[key].add(sid)
 candidates=defaultdict(list);report={'encoding':encoding,'rows':len(rows),'matched_rows':0,'unmatched':[],'ambiguous':[]}
 for row in rows:
  matches=({row['song_id']} & ids) if row['song_id'] else (exact.get(unicodedata.normalize('NFKC',row['title']).casefold(),set()) or aliases.get(title_key(row['title']),set()))
  if not row['song_id'] and set(row['title'])<=set('? '):matches=set()
  detail={'line':row['line'],'title':row['title'],'song_id':row['song_id']}
  if len(matches)!=1:
   report['ambiguous' if matches else 'unmatched'].append({**detail,'candidates':sorted(matches)});continue
  candidates[next(iter(matches))].append(row)
 result=copy.deepcopy(entries)
 # The CSV is authoritative; a missing cell is unknown, never an integer-rating fallback.
 for entry in result.values():entry['chart_constant']=None;entry['constant_source']='unmatched CSV'
 for sid,group in candidates.items():
  if len(group)>1:
   report['ambiguous'].extend({'line':r['line'],'title':r['title'],'candidates':[sid],'reason':'Multiple CSV rows resolve to the same song; use unique song_id rows'} for r in group);continue
  row=group[0];report['matched_rows']+=1
  for cls,value in row['values'].items():
   for key in [(sid,cls)]+([(sid,4)] if cls==3 and (sid,4) in result else []):
    if key in result:result[key].update(chart_constant=value,constant_source='unofficial wiki CSV',constant_csv_line=row['line'])
 return result,report

def filter_rows(rows,classes=None,term='',highest=False,lower=None,upper=None):
 """Highest within the class/text selection, then inclusive numeric range."""
 for value in (lower,upper):
  if value is not None and not math.isfinite(value):raise ValueError('Range bounds must be finite')
 if lower is not None and upper is not None and lower>upper:raise ValueError('Minimum difficulty must not exceed maximum')
 rows=[r for r in rows if visible(r,classes) and term.casefold() in (r['title']+' '+r['difficulty']).casefold()]
 if highest:
  groups=defaultdict(list)
  for r in rows:groups[r['metadata'].get('song_id') or title_key(r['title']) or r['id']].append(r)
  chosen=[]
  for group in groups.values():
   # Unknown constants cannot establish a highest chart, so exclude incomplete groups.
   if any(r['metadata'].get('chart_constant') is None for r in group):continue
   chosen.append(max(group,key=lambda r:(r['metadata']['chart_constant'],r['metadata'].get('rating_class',-1),r['id'])))
  chosen_ids={r['id'] for r in chosen};rows=[r for r in rows if r['id'] in chosen_ids]
 if lower is not None or upper is not None:
  rows=[r for r in rows if r['metadata'].get('chart_constant') is not None and (lower is None or r['metadata']['chart_constant']>=lower) and (upper is None or r['metadata']['chart_constant']<=upper)]
 return rows
