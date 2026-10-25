import copy,csv,io,json,os,shutil,sqlite3,threading
from contextlib import contextmanager
from pathlib import Path
from .common import ROOT,atomic,read,now,digest,digest_bytes,unique
from . import sequence,difficulty,adapters,metadata,signals,model2
class Store:
 def __init__(self,root):
  self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
  self.lock=threading.RLock()
  with self.db() as db:
   db.executescript('CREATE TABLE IF NOT EXISTS charts(id TEXT PRIMARY KEY,title TEXT,difficulty TEXT,aliases TEXT,created TEXT); CREATE TABLE IF NOT EXISTS stages(chart TEXT,stage TEXT,status TEXT,detail TEXT,updated TEXT,PRIMARY KEY(chart,stage));')
   db.execute("UPDATE stages SET status='interrupted',detail='Previous process ended before completion' WHERE status='running'")
  if not (self.root/'workspace.json').exists():atomic(self.root/'workspace.json',{'format':'arcaea-workspace/2','allocation_script':'core/analyze_aff.py','visualization_script':'core/color_aff.py','beam_width':128})
  if not (self.root/'songlist.json').exists() and (ROOT/'defaults/songlist.json').exists():atomic(self.root/'songlist.json',read(ROOT/'defaults/songlist.json'))
  if not (self.root/'chart-constants.csv').exists() and (ROOT/'defaults/chart-constants.csv').exists():atomic(self.root/'chart-constants.csv',(ROOT/'defaults/chart-constants.csv').read_bytes())
  if (self.root/'songlist.json').exists():self.refresh_metadata()
  definitions=self.root/'definitions';definitions.mkdir(exist_ok=True)
  try:self.active_definition()
  except (OSError,ValueError,KeyError):
   candidates=sorted((definitions/'versions').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
   if (definitions/'working.difficulty.json').exists():candidates.append(definitions/'working.difficulty.json')
   recovered=None
   for candidate in candidates:
    try:recovered=difficulty.validate(read(candidate));break
    except (OSError,ValueError,KeyError):continue
   if recovered is None and candidates:raise ValueError('Difficulty files are invalid. Restore a valid version in definitions/versions; existing files were not reset.')
   if recovered is not None:
    for name in ('active.json','working.difficulty.json'):
     if (definitions/name).exists():shutil.copy2(definitions/name,definitions/('recovered-'+unique()+'-'+name))
    self.activate_definition(recovered);atomic(definitions/'recovery-note.json',{'time':now(),'action':'Recovered valid definition; old files retained'})
   else:self.activate_definition(read(ROOT/'defaults/difficulty-v2.json'))
 @contextmanager
 def db(self):
  db=sqlite3.connect(self.root/'index.sqlite',timeout=30);db.row_factory=sqlite3.Row
  try:
   with db:yield db
  finally:db.close()
 def import_songlist(self,path):
  data=read(path);entries=metadata.index(data)
  atomic(self.root/'songlist.json',data)
  self.refresh_metadata(entries)
  return str(len(entries))+' chart ratings loaded; absent chart constants remain blank'
 def import_constants(self,path):
  raw=Path(path).read_bytes();entries=metadata.index(read(self.root/'songlist.json'))
  _,report=metadata.apply_constants(entries,raw)
  atomic(self.root/'chart-constants.csv',raw)
  settings=self.settings();settings['difficulty_csv_path']=str(Path(path).resolve());atomic(self.root/'workspace.json',settings)
  self.refresh_metadata()
  return f"{report['matched_rows']}/{report['rows']} rows matched; {len(report['unmatched'])} unmatched, {len(report['ambiguous'])} ambiguous. See CSV match report."
 def refresh_metadata(self,entries=None):
  entries=entries if entries is not None else metadata.index(read(self.root/'songlist.json'))
  constants_path=self.root/'chart-constants.csv'
  constant_hash=None
  if constants_path.exists():
   raw=constants_path.read_bytes();entries,report=metadata.apply_constants(entries,raw);constant_hash=digest_bytes(raw);report['csv_hash']=constant_hash;atomic(self.root/'constant-match-report.json',report)
  with self.db() as db:rows=[dict(r) for r in db.execute('SELECT * FROM charts')]
  songlist_hash=digest(read(self.root/'songlist.json')) if (self.root/'songlist.json').exists() else None
  for r in rows:
   info=metadata.match(json.loads(r['aliases']),entries)
   if 'song_id' in info:info['match_status']='matched'
   else:
    keys={metadata.identify(p) for p in json.loads(r['aliases'])};keys.discard((None,None))
    if len(keys)==1:info['song_id'],info['rating_class']=next(iter(keys))
   info['songlist_hash']=songlist_hash;info['constant_csv_hash']=constant_hash
   atomic(self.folder(r['id'])/'metadata.json',info)
   label_path=self.folder(r['id'])/'label.json'
   manual=read(label_path).get('manual',False) if label_path.exists() else False
   if info['match_status']=='matched' and not manual:
    with self.db() as db:db.execute('UPDATE charts SET title=?,difficulty=? WHERE id=?',(info['title'],info['difficulty_name'],r['id']))
 def metadata(self,c):
  p=self.folder(c)/'metadata.json'
  return read(p) if p.exists() else {}
 def output_stem(self,c):
  info=self.metadata(c)
  if info.get('song_id') and info.get('rating_class') is not None:name=info['song_id']+'_'+str(info['rating_class'])
  else:
   with self.db() as db:row=db.execute('SELECT aliases FROM charts WHERE id=?',(c,)).fetchone()
   name=Path(json.loads(row[0])[0]).stem if row else 'chart'
  import re
  return re.sub(r'[^\w. -]','_',name).strip('. ') or 'chart'
 def sequence_path(self,c):
  p=self.folder(c);pointer=p/'sequence-location.json'
  if pointer.exists():return Path(read(pointer)['path'])
  with self.db() as db:row=db.execute('SELECT aliases FROM charts WHERE id=?',(c,)).fetchone()
  aliases=json.loads(row[0]) if row else []
  source=next((Path(a) for a in aliases if Path(a).is_file() and digest_bytes(Path(a).read_bytes())==c),None)
  # Bundled examples remain read-only. Unavailable sources use a workspace mirror.
  parent=source.parent/'_analysis' if source and (ROOT/'examples') not in source.parents else self.root/'results'/self.output_stem(c)
  target=parent/(self.output_stem(c)+'.sequence.json');legacy=p/'working.sequence.json'
  if target.exists():
   if read(target).get('sha256')!=c:raise ValueError('Sequence destination belongs to another chart: '+str(target))
   if legacy.exists() and target.read_bytes()!=legacy.read_bytes():raise ValueError('Both legacy and named sequences exist and differ; resolve before migration')
  elif legacy.exists():atomic(target,legacy.read_bytes())
  atomic(pointer,{'path':str(target),'source_hash':c,'legacy_retained':legacy.exists()})
  return target
 def settings(self):return read(self.root/'workspace.json')
 def folder(self,c):
  if len(c)!=64 or any(x not in '0123456789abcdef' for x in c):raise ValueError('Invalid chart ID')
  return self.root/'charts'/c
 def source(self,c):return self.folder(c)/'source.aff'
 def source_check(self,c):
  if digest_bytes(self.source(c).read_bytes())!=c:raise ValueError('Protected source changed; reimport as new chart')
 def stage(self,c,name,status,detail=''):
  with self.db() as db:db.execute('INSERT OR REPLACE INTO stages VALUES(?,?,?,?,?)',(c,name,status,str(detail),now()))
 def catalog(self):
  with self.db() as db:
   rows=[dict(x) for x in db.execute('SELECT * FROM charts ORDER BY title')]
   for r in rows:r['stages']={s['stage']:dict(s) for s in db.execute('SELECT * FROM stages WHERE chart=?',(r['id'],))}
  for r in rows:r['metadata']=self.metadata(r['id'])
  return rows
 def label(self,c,title,diff):
  with self.db() as db:db.execute('UPDATE charts SET title=?,difficulty=? WHERE id=?',(title,diff,c))
  atomic(self.folder(c)/'label.json',{'title':title,'difficulty':diff,'manual':True})
 def scan(self,folder,progress=lambda x:None,cancel=lambda:False):
  root=Path(folder).resolve();report={'imported':[],'existing':[],'errors':[],'skipped':0}
  if root==self.root or self.root in root.parents:raise ValueError('Choose a source directory outside the workspace')
  for p in root.rglob('*'):
   if cancel():break
   if '_analysis' in p.relative_to(root).parts:continue
   if p.name.endswith(('.preview.aff','.overlay.aff','.workbench.json')):report['skipped']+=1;continue
   if not p.is_file() or p.is_symlink() or self.root==p or self.root in p.parents:continue
   try:
    if p.stat().st_size>32*1024*1024:report['skipped']+=1;continue
    with p.open('rb') as f:prefix=f.read(8192)
    text=prefix.decode('utf-8-sig')
    if '\n-' not in text or not any(x in text for x in ('timing(','arc(','hold(')):report['skipped']+=1;continue
    data=p.read_bytes();cid=digest_bytes(data);dest=self.folder(cid);dest.mkdir(parents=True,exist_ok=True)
    with self.db() as db:
     old=db.execute('SELECT aliases FROM charts WHERE id=?',(cid,)).fetchone()
     aliases=json.loads(old[0]) if old else []
     if str(p) not in aliases:aliases.append(str(p))
     if old:db.execute('UPDATE charts SET aliases=? WHERE id=?',(json.dumps(aliases),cid));report['existing'].append(cid);continue
     atomic(dest/'source.aff',data);title=p.parent.name+' / '+p.stem
     db.execute('INSERT INTO charts VALUES(?,?,?,?,?)',(cid,title,'unknown',json.dumps(aliases),now()))
    atomic(dest/'label.json',{'title':title,'difficulty':'unknown'})
    self.stage(cid,'import','complete',str(p.relative_to(root)));report['imported'].append(cid);progress('Imported '+p.name)
   except UnicodeDecodeError:report['skipped']+=1
   except Exception as e:report['errors'].append({'path':str(p),'error':str(e)})
  if (self.root/'songlist.json').exists():self.refresh_metadata()
  atomic(self.root/'last-import-report.json',report);return report
 def preprocess(self,c):
  self.source_check(c);p=self.folder(c)/'chart-facts.json'
  if p.exists():return read(p)
  self.stage(c,'preprocess','running')
  try:r=adapters.preprocess(self.source(c));atomic(p,r);self.stage(c,'preprocess','complete');return r
  except Exception as e:self.stage(c,'preprocess','failed',e);raise
 def load(self,c):
  p=self.folder(c);head=read(p/'head.json');s=read(self.sequence_path(c));sequence.validate(s)
  if s.get('sha256')!=c:raise ValueError('Sequence source hash does not match chart')
  return s,head,digest_bytes(self.sequence_path(c).read_bytes())
 def save_sequence(self,c,s,expected=None,reason='edit',new_baseline=False):
  with self.lock:
   sequence.validate(s)
   if s.get('sha256')!=c:raise ValueError('Wrong source hash')
   p=self.folder(c);work=self.sequence_path(c)
   if expected is not None and work.exists() and digest_bytes(work.read_bytes())!=expected:raise ValueError('External file change detected. Reload or explicitly save a separate draft before overwriting.')
   rev=unique();record={'revision':rev,'sequence_hash':digest(s),'saved':now(),'reason':reason}
   atomic(p/'revisions'/(rev+'.json'),s);atomic(p/'revisions'/(rev+'.meta.json'),record)
   atomic(work,s);atomic(p/'head.json',record)
   self.stage(c,'sequence','complete',rev);self.stage(c,'review','unreviewed');self.stage(c,'difficulty','stale');self.stage(c,'preview','stale')
   return digest_bytes(work.read_bytes())
 def adopt_external(self,c,expected):
  p=self.sequence_path(c)
  if digest_bytes(p.read_bytes())!=expected:raise ValueError('File changed again; retry reload')
  s=read(p);self.save_sequence(c,s,expected,'external file reload');return self.load(c)
 def baseline(self,c):return read(self.folder(c)/'baseline.json')
 def generate(self,c,progress=lambda x:None,force=False):
  self.source_check(c);facts=self.preprocess(c);p=self.folder(c);settings=self.settings();sig=adapters.signature(settings,'allocation')
  meta=read(p/'allocation.json') if (p/'allocation.json').exists() else {}
  if self.sequence_path(c).exists() and not force:
   if meta.get('signature')!=sig:progress('Existing edits preserved; allocation version changed. Use New allocation baseline explicitly.')
   s,_,_=self.load(c)
  else:
   self.stage(c,'allocation','running');out=p/'runs'/unique()/'baseline.sequence.json';out.parent.mkdir(parents=True)
   try:
    adapters.allocate(self.source(c),out,settings);base=read(out)
    if base.get('sha256')!=c:raise ValueError('Allocator returned incorrect chart hash')
    s=sequence.convert(base);sequence.validate(s)
    s,arc_asset=adapters.recognize_arcs(self.source(c),s,settings)
    # Keep any existing baseline/revisions; install new baseline only after success.
    atomic(p/'baseline.json',base);atomic(p/'allocation.json',{'signature':sig,'settings':settings,'run':str(out.relative_to(p)),'created':now()});self.save_sequence(c,s,reason='allocation')
    if arc_asset is not None:
     asset_path=out.parent/(self.output_stem(c)+'.arc-paths.json');atomic(asset_path,arc_asset);atomic(p/'arc-paths-location.json',{'path':str(asset_path.resolve())})
    self.stage(c,'allocation','complete',sig)
   except Exception as e:self.stage(c,'allocation','failed',e);raise
  results={}
  for kind,fn in [('preview',lambda:self.make_preview(c)),('difficulty',lambda:self.calculate(c))]:
   try:
    if self.fresh(c,kind):results[kind]='already current'
    else:results[kind]=fn()
   except Exception as e:results[kind]='Failed: '+str(e);progress(kind+': '+str(e))
  return results
 def import_sequence(self,c,path):
  base=read(path)
  if base.get('sha256')!=c:raise ValueError('Imported sequence does not match source AFF')
  if base.get('format')=='arcaea-input-sequence/1':
   sequence.validate(sequence.convert(base));atomic(self.folder(c)/'baseline.json',base);s=sequence.convert(base)
  elif base.get('format')==sequence.FORMAT:s=base
  else:raise ValueError('Unsupported sequence format')
  self.preprocess(c);return self.save_sequence(c,s,reason='import sequence')
 def active_definition(self):
  manifest=read(self.root/'definitions/active.json');d=read(self.root/'definitions/versions'/(manifest['hash']+'.json'))
  if digest(d)!=manifest['hash']:raise ValueError('Active definition integrity failure')
  return difficulty.validate(d)
 def activate_definition(self,d):
  d=difficulty.validate(d);p=self.root/'definitions';h=digest(d)
  atomic(p/'versions'/(h+'.json'),d);atomic(p/'working.difficulty.json',d);atomic(p/'active.json',{'hash':h,'activated':now()})
  with self.db() as db:db.execute("UPDATE stages SET status='stale' WHERE stage='difficulty'")
  return h
 def fresh(self,c,kind):
  try:
   s,head,_=self.load(c);p=self.folder(c)
   if kind=='difficulty':
    r=read(p/'metrics-head.json') if (p/'metrics-head.json').exists() and (p/'metrics.json').exists() else read(p/'metrics.json');return (self.active_definition().get('format')!='arcaea-difficulty/2' or r.get('engine')==model2.ENGINE) and r['sequence_hash']==digest(s) and r['definition_hash']==digest(self.active_definition()) and r['chart_facts_hash']==digest(read(p/'chart-facts.json'))
   if kind=='preview':
    r=read(p/'preview.json');return r['sequence_hash']==digest(s) and r['adapter_signature']==adapters.signature(self.settings(),'visualization') and (p/r['file']).exists() and (not r.get('output_hash') or digest_bytes((p/r['file']).read_bytes())==r['output_hash'])
  except (OSError,ValueError,KeyError):return False
 def features(self,c,s,d):
  step=d.get('arc_step_ms',10);key=signals.feature_key(s,step);p=self.folder(c)/'operation-features.json'
  if p.exists():
   cached=read(p)
   if cached.get('key')==key:return cached
  f=signals.extract(s,step);atomic(p,f);return f
 def analysis(self,c):
  self.source_check(c);s,head,token=self.load(c);facts=self.preprocess(c);d=self.active_definition();features=self.features(c,s,d)
  v=signals.volume_report(features,facts,d.get('arc_threshold',.25),d.get('judgment_profile','tight'),d.get('vertical_scale',1))
  v.update(sequence_hash=digest(s),chart_facts_hash=digest(facts),sequence_revision=head['revision'])
  report={'format':'arcaea-chart-analysis/1','created':now(),'invalid_volume':v,'feature_key':features['key']}
  if self.load(c)[2]!=token:raise ValueError('Sequence changed during analysis')
  atomic(self.folder(c)/'chart-analysis.json',report);return report
 def trial(self,c,d):
  self.source_check(c);s,_,_=self.load(c);facts=self.preprocess(c);d=difficulty.validate(d)
  return model2.calculate(s,facts,d,self.features(c,s,d)) if d['format']=='arcaea-difficulty/2' else difficulty.calculate(s,facts,d)
 def export_volume(self,c,destination):
  report=self.analysis(c);atomic(destination,report['invalid_volume']);return str(destination)
 def calculate(self,c):
  self.source_check(c);s,head,token=self.load(c);d=self.active_definition();facts=self.preprocess(c);self.stage(c,'difficulty','running')
  try:
   r=(model2.calculate(s,facts,d,self.features(c,s,d)) if d['format']=='arcaea-difficulty/2' else difficulty.calculate(s,facts,d));r.update(sequence_revision=head['revision'],created=now())
   if self.load(c)[2]!=token or digest(self.active_definition())!=digest(d):raise ValueError('Inputs changed during calculation; discarded outdated result')
   if 'invalid_volume' in r:
    r['invalid_volume']['sequence_revision']=head['revision']
    atomic(self.folder(c)/'chart-analysis.json',{'format':'arcaea-chart-analysis/1','created':now(),'invalid_volume':r['invalid_volume'],'feature_key':r['feature_key']})
   atomic(self.folder(c)/'movement-warnings.json',{'engine':r.get('engine'),'sequence_hash':r['sequence_hash'],'definition_hash':r['definition_hash'],'movement_mapping':r.get('movement_mapping',{}),'warnings':r.get('movement_warnings',[])})
   atomic(self.folder(c)/'metric-history'/(head['revision']+'-'+r['definition_hash']+'.json'),r);atomic(self.folder(c)/'metrics.json',r);atomic(self.folder(c)/'metrics-head.json',{k:r.get(k) for k in ('engine','sequence_hash','definition_hash','chart_facts_hash','sequence_revision')});self.stage(c,'difficulty','complete',r['status']);return r['metrics']
  except Exception as e:self.stage(c,'difficulty','failed',e);raise
 def preview_destination(self,c,overlay=False):
  with self.db() as db:row=db.execute('SELECT aliases FROM charts WHERE id=?',(c,)).fetchone()
  aliases=json.loads(row[0]) if row else []
  source=next((Path(a) for a in aliases if Path(a).is_file() and digest_bytes(Path(a).read_bytes())==c),None)
  parent=source.parent if source and (ROOT/'examples') not in source.parents else self.root/'results'/self.output_stem(c)
  return parent/(self.output_stem(c)+('.overlay.aff' if overlay else '.preview.aff'))
 def preview_destination_check(self,c,target):
  receipt=target.with_name(target.name+'.workbench.json')
  if target.is_symlink() or receipt.is_symlink():raise ValueError('Preview destination or receipt is a symbolic link: '+str(target))
  if target.exists():
   if not receipt.exists():raise ValueError('Preview destination already exists without ownership metadata: '+str(target))
   info=read(receipt)
   if info.get('source_hash')!=c:raise ValueError('Preview destination belongs to another chart: '+str(target))
   if info.get('output_hash')!=digest_bytes(target.read_bytes()):raise ValueError('Preview was edited externally; move it aside before regenerating: '+str(target))
  elif receipt.exists() and read(receipt).get('source_hash')!=c:raise ValueError('Preview receipt belongs to another chart: '+str(receipt))
  return receipt
 def make_preview(self,c,overlay=False):
  self.source_check(c);s,head,token=self.load(c);p=self.folder(c);out=p/'previews'/(head['revision']+('-overlay-' if overlay else '-colored-')+unique()[:8]+'.aff');out.parent.mkdir(parents=True,exist_ok=True);self.stage(c,'preview','running')
  try:
   target=self.preview_destination(c,overlay);self.preview_destination_check(c,target)
   if overlay:
    atomic(out.parent/'backups'/'source.aff',self.source(c).read_bytes());result=adapters.overlay(self.source(c),s,out)
   else:result=adapters.preview(self.source(c),self.baseline(c),s,out,self.settings())
   if self.load(c)[2]!=token:raise ValueError('Sequence changed while exporting preview')
   receipt=self.preview_destination_check(c,target);output_hash=digest_bytes(out.read_bytes());atomic(target,out.read_bytes())
   atomic(receipt,{'source_hash':c,'output_hash':output_hash,'sequence_hash':digest(s),'sequence_revision':head['revision'],'created':now()})
   info={'file':str(target),'archive_file':str(out.relative_to(p)),'output_hash':output_hash,'sequence_hash':digest(s),'sequence_revision':head['revision'],'adapter_signature':adapters.signature(self.settings(),'visualization'),'mode':'execution_overlay' if overlay else 'note_colors_and_arc_paths' if any(u['kind']=='arc' and u['geometry_mode']=='polyline' for u in s['units']) else 'note_colors','diagnostics':result}
   atomic(p/'preview.json',info);self.stage(c,'preview','complete',info['mode']);return str(target)
  except Exception as e:self.stage(c,'preview','failed',e);raise
 def export(self,ids,dest,include_stale=False):
  dest=Path(dest);dest.mkdir(parents=True,exist_ok=True);rows=[];fields=set(self.active_definition()['metrics']);report=[];catalog={r['id']:r for r in self.catalog()}
  stems=[self.output_stem(c) for c in ids]
  if len(set(x.casefold() for x in stems))!=len(stems):raise ValueError('Export names collide; export the conflicting charts separately')
  for c in ids:
   stem=self.output_stem(c);p=self.folder(c);r=catalog[c];row={'chart_id':c,'title':r['title'],'difficulty_label':r['difficulty'],'review_status':r['stages'].get('review',{}).get('status','unreviewed'),'status':'not_calculated'}
   row.update({k:r['metadata'].get(k) for k in ('song_id','rating_class','display_rating','chart_constant','constant_source','constant_csv_hash')})
   try:
    self.source_check(c);s,head,_=self.load(c);row['sequence_revision']=head['revision'];row['sequence_hash']=digest(s);row['allocation_version']=s.get('algorithm_version','unknown');atomic(dest/(stem+'.sequence.json'),s)
    pointer=p/'arc-paths-location.json'
    if pointer.exists():
     asset_path=Path(read(pointer)['path'])
     if asset_path.exists():
      asset=read(asset_path);row['arc_asset_status']='current' if asset.get('sequence_hash')==digest(s) else 'stale'
      if row['arc_asset_status']=='current' or include_stale:atomic(dest/(stem+'.arc-paths.json'),asset)
    if (p/'chart-facts.json').exists():shutil.copy2(p/'chart-facts.json',dest/(stem+'.chart-facts.json'))
    m=read(p/'metrics.json') if (p/'metrics.json').exists() else None;fresh=self.fresh(c,'difficulty')
    if m:
     fields.update(m['metrics'])
     row.update(metric_status=m['status'],calibrated=m['calibrated'])
     row.update(status='current' if fresh else 'stale',definition_hash=m['definition_hash'],definition_name=m['definition_name'],metric_sequence_revision=m['sequence_revision'])
     if fresh or include_stale:
      row.update(m['metrics']);row['included_fraction']=m['coverage']['included_fraction'];fields.update(m['metrics'])
      atomic(dest/(stem+'.metrics.json'),m)
      atomic(dest/(stem+'.movement-warnings.json'),{'engine':m.get('engine'),'sequence_hash':m['sequence_hash'],'definition_hash':m['definition_hash'],'movement_mapping':m.get('movement_mapping',{}),'warnings':m.get('movement_warnings',[])})
      row['speed_capped_intervals']=m.get('summary',{}).get('speed_capped_intervals');row['response_clipped_intervals']=m.get('summary',{}).get('response_clipped_intervals')
      row['peak_near_s']=m.get('summary',{}).get('peak_duration_s');row['movement_near_s']=m.get('summary',{}).get('movement_peak_duration_s')
      if 'invalid_volume' in m:
       atomic(dest/(stem+'.invalid-volume.json'),m['invalid_volume']);row['volume_invalid']=m['invalid_volume']['invalid_volume'];row['volume_status']=m['invalid_volume']['judgment_status']
      if (p/'chart-analysis.json').exists():shutil.copy2(p/'chart-analysis.json',dest/(stem+'.analysis.json'))
      series=m['series'];buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=list(series[0]) if series else ['time_ms']);writer.writeheader();writer.writerows(series);atomic(dest/(stem+'.timeseries.csv'),b'\xef\xbb\xbf'+buf.getvalue().encode())
    if self.fresh(c,'preview'):
     preview=read(p/'preview.json');shutil.copy2(p/preview['file'],dest/(stem+'.preview.aff'));row['preview_mode']=preview['mode']
   except Exception as e:row['error']=str(e)
   rows.append(row);report.append({'chart':c,'status':row['status'],'error':row.get('error')})
  columns=['arc_asset_status','speed_capped_intervals','response_clipped_intervals','peak_near_s','movement_near_s','volume_invalid','volume_status','song_id','rating_class','display_rating','chart_constant','constant_source','constant_csv_hash','chart_id','title','difficulty_label','allocation_version','metric_status','calibrated','sequence_revision','sequence_hash','review_status','status','definition_hash','definition_name','metric_sequence_revision','included_fraction','preview_mode',*sorted(fields),'error']
  def excel(v):
   return "'"+v if isinstance(v,str) and v[:1] in '=+-@\t\r' else v
  buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=columns);writer.writeheader();writer.writerows({k:excel(v) for k,v in r.items()} for r in rows)
  atomic(dest/'summary.csv',b'\xef\xbb\xbf'+buf.getvalue().encode());atomic(dest/'export-report.json',{'created':now(),'include_stale':include_stale,'charts':report});return str(dest/'summary.csv')

 def recognize_arcs(self,c):
  self.source_check(c);s,head,token=self.load(c)
  result,asset=adapters.recognize_arcs(self.source(c),s,self.settings())
  if asset is None:raise ValueError('Arc recognition is disabled in the selected profile')
  path=self.folder(c)/'runs'/unique()/(self.output_stem(c)+'.arc-paths.json')
  self.save_sequence(c,result,token,'Arc path recognition with endpoint pass')
  atomic(path,asset);atomic(self.folder(c)/'arc-paths-location.json',{'path':str(path.resolve())})
  return str(path.resolve())
