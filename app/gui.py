import copy,json,math,os,queue,subprocess,sys,threading,traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from .common import ROOT,read,atomic,digest_bytes,digest
from .store import Store
from . import sequence,difficulty,adapters,metadata
from .lab_ui import LabUI
from .asset_ui import AssetUI
from . import recognition
class Window(AssetUI,LabUI):
 def __init__(self,root,store):
  self.root=root;self.store=store;self.events=queue.Queue();self.cancel=threading.Event();self.busy=False;self.chart=None;self.seq=None;self.token=None;self.undo=[];self.redo=[];self.dirty=False;self.external_seen=None;self.last_definition_bytes=None
  root.title('Arcaea Workbench · Unreleased development · Local sequence laboratory');root.geometry('1320x900');root.minsize(1050,720)
  style=ttk.Style(root)
  if 'clam' in style.theme_names():style.theme_use('clam')
  style.configure('Treeview',rowheight=25);style.configure('TButton',padding=5)
  outer=ttk.Frame(root,padding=10);outer.pack(fill='both',expand=True)
  ttk.Label(outer,text='ARCAEA  /  SEQUENCE LAB',font=('Segoe UI',18,'bold')).pack(anchor='w')
  ttk.Label(outer,text=str(store.root)+'  ·  Original charts protected  ·  Experimental metrics',foreground='#566676').pack(anchor='w',pady=(2,8))
  self.tabs=ttk.Notebook(outer);self.tabs.pack(fill='both',expand=True)
  self.pages={}
  for name in ['Assets & Batch','Chart Data','Sequence Editor','Difficulty Functions','Results & Export','Arc Paths','Trajectory','Interfaces']:
   f=ttk.Frame(self.tabs,padding=8);self.tabs.add(f,text=name);self.pages[name]=f
  self.build_assets();self.build_facts();self.build_editor();self.build_lab();self.build_results();self.build_arc_assets();self.build_trajectory();self.build_interfaces()
  self.status=tk.StringVar(value='Ready. Import a folder or use the bundled example.');ttk.Label(outer,textvariable=self.status,wraplength=1200).pack(fill='x',pady=(8,0))
  root.protocol('WM_DELETE_WINDOW',self.close);root.after(200,self.poll);self.refresh()
 def safe(self,fn):
  def run(*_):
   try:return fn()
   except Exception as e:messagebox.showerror('Action could not complete',str(e),parent=self.root);self.status.set(str(e))
  return run
 def button(self,parent,text,fn):
  b=ttk.Button(parent,text=text,command=self.safe(fn));b.pack(side='left',padx=3,pady=3);return b
 def tree(self,parent,columns,height=12):
  frame=ttk.Frame(parent);frame.pack(fill='both',expand=True);t=ttk.Treeview(frame,columns=columns,show='headings',selectmode='extended',height=height)
  for c in columns:t.heading(c,text=c.replace('_',' ').title());t.column(c,width=110,stretch=True)
  sy=ttk.Scrollbar(frame,orient='vertical',command=t.yview);sx=ttk.Scrollbar(frame,orient='horizontal',command=t.xview);t.configure(yscrollcommand=sy.set,xscrollcommand=sx.set);t.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew');frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1);return t
 def text(self,parent,height=12):
  f=ttk.Frame(parent);f.pack(fill='both',expand=True);t=tk.Text(f,height=height,wrap='none',undo=True,font=('Consolas',10));bar=ttk.Scrollbar(f,command=t.yview);t.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');t.pack(fill='both',expand=True);return t
 def put(self,w,value):w.delete('1.0','end');w.insert('1.0',value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2))
 def require_idle(self):
  if self.busy:raise ValueError('Wait for the current batch, or stop after its current chart.')
 def task(self,title,fn):
  self.require_idle();self.busy=True;self.cancel.clear();self.status.set(title)
  def worker():
   try:r=fn(lambda s:self.events.put(('log',s)));self.events.put(('done',title+' complete. '+str(r or '')))
   except Exception as e:self.events.put(('error',str(e)));self.events.put(('trace',traceback.format_exc()))
  threading.Thread(target=worker,daemon=True).start()
 def build_assets(self):
  p=self.pages['Assets & Batch'];bar=ttk.Frame(p);bar.pack(fill='x')
  self.button(bar,'CSV match report',self.constant_report);self.button(bar,'Load songlist',self.import_songlist);self.button(bar,'Load bundled example',self.demo);self.button(bar,'Refresh',self.refresh);self.button(bar,'Edit label',self.rename)
  paths=ttk.Frame(p);paths.pack(fill='x');paths.columnconfigure(1,weight=1)
  settings=self.store.settings();self.song_path=tk.StringVar(value=settings.get('song_folder',''));self.csv_path=tk.StringVar(value=settings.get('difficulty_csv_path',str(ROOT/'defaults/chart-constants.csv')))
  for i,(label,var,browse,load,action) in enumerate([('Song folder',self.song_path,self.browse_songs,self.import_folder,'Scan folder'),('Difficulty .csv',self.csv_path,self.browse_constants,self.import_constants,'Load table')]):
   ttk.Label(paths,text=label).grid(row=i,column=0,sticky='w');ttk.Entry(paths,textvariable=var).grid(row=i,column=1,sticky='ew',padx=4);ttk.Button(paths,text='Browse',command=self.safe(browse)).grid(row=i,column=2);ttk.Button(paths,text=action,command=self.safe(load)).grid(row=i,column=3)
  bar=ttk.Frame(p);bar.pack(fill='x');self.button(bar,'Generate allocation + preview',lambda:self.batch('generate'));self.button(bar,'New allocation baseline',lambda:self.batch('regenerate'));self.button(bar,'Update difficulty',lambda:self.batch('calculate'));self.button(bar,'Stop after current chart',self.cancel.set)
  bar=ttk.Frame(p);bar.pack(fill='x');ttk.Label(bar,text='Filter').pack(side='left');self.filter=tk.StringVar();ttk.Entry(bar,textvariable=self.filter,width=35).pack(side='left',padx=5);self.filter.trace_add('write',self.safe(self.refresh));self.button(bar,'Select all shown',lambda:self.assets.selection_set(self.assets.get_children()));self.button(bar,'Open selected chart',self.open_selected)
  self.class_filter=tk.StringVar(value='All classes');box=ttk.Combobox(bar,textvariable=self.class_filter,values=('All classes','_2 + _3','_2','_3','_0','_1','_4','Unknown'),state='readonly',width=15);box.pack(side='left');box.bind('<<ComboboxSelected>>',self.safe(self.refresh))
  bar=ttk.Frame(p);bar.pack(fill='x');self.highest=tk.BooleanVar(value=False);ttk.Checkbutton(bar,text='Highest constant per title',variable=self.highest,command=self.safe(self.refresh)).pack(side='left')
  self.range_min=tk.StringVar();self.range_max=tk.StringVar()
  for label,var in [('Constant min (inclusive)',self.range_min),('max',self.range_max)]:
   ttk.Label(bar,text=label).pack(side='left');entry=ttk.Entry(bar,textvariable=var,width=8);entry.pack(side='left',padx=4);entry.bind('<Return>',self.safe(self.refresh))
  self.button(bar,'Apply filters',self.refresh);self.button(bar,'Clear range',self.clear_range)
  ttk.Label(p,text='Highest is chosen within the class/text selection, before the range. Unknown constants hide the whole title in highest mode; range filters omit unknown charts.',wraplength=1150).pack(anchor='w')
  self.assets=self.tree(p,('title','difficulty','constant','allocation','sequence','review','difficulty_result','preview'));self.assets.column('title',width=280);self.assets.bind('<Double-1>',self.safe(self.open_selected))
  self.log=self.text(p,5)
 def ids(self):
  ids=list(self.assets.selection())
  if not ids:raise ValueError('Select charts in Assets & Batch first')
  return ids
 def refresh(self):
  if not hasattr(self,'assets'):return
  selected=set(self.assets.selection());term=self.filter.get().lower()
  choice=self.class_filter.get();classes=None if choice=='All classes' else {None} if choice=='Unknown' else {int(x.strip()[1:]) for x in choice.split('+')}
  try:lower=float(self.range_min.get()) if self.range_min.get().strip() else None;upper=float(self.range_max.get()) if self.range_max.get().strip() else None
  except ValueError:raise ValueError('Enter numeric difficulty bounds, or leave them blank')
  rows=metadata.filter_rows(self.store.catalog(),classes,term,self.highest.get(),lower,upper)
  self.assets.delete(*self.assets.get_children())
  for r in rows:
   st=r['stages'];val=lambda k:st.get(k,{}).get('status','—')
   metric=val('difficulty');preview=val('preview')
   if metric=='complete' and not self.store.fresh(r['id'],'difficulty'):metric='stale'
   if preview=='complete' and not self.store.fresh(r['id'],'preview'):preview='stale'
   self.assets.insert('', 'end',iid=r['id'],values=(r['title'],r['difficulty'],r['metadata'].get('chart_constant') if r['metadata'].get('chart_constant') is not None else '—',val('allocation'),val('sequence'),val('review'),metric,preview))
  self.assets.selection_set([i for i in selected if self.assets.exists(i)])
 def import_songlist(self):
  self.require_idle();path=filedialog.askopenfilename(title='Select songlist JSON (extension optional)')
  if path:self.status.set(self.store.import_songlist(path));self.refresh()
 def clear_range(self):
  self.range_min.set('');self.range_max.set('');self.refresh()
 def browse_songs(self):
  path=filedialog.askdirectory(parent=self.root)
  if path:self.song_path.set(path)
 def browse_constants(self):
  path=filedialog.askopenfilename(parent=self.root,filetypes=[('Difficulty table','*.csv')])
  if path:self.csv_path.set(path)
 def constant_report(self):
  report=read(self.store.root/'constant-match-report.json');win=tk.Toplevel(self.root);win.title('CSV match report');win.geometry('850x620')
  ttk.Label(win,text=f"{report['matched_rows']}/{report['rows']} rows matched · {len(report['unmatched'])} unmatched · {len(report['ambiguous'])} ambiguous",padding=8).pack(anchor='w')
  ttk.Label(win,text='Add an optional song_id column to resolve duplicate or damaged titles, then load the corrected CSV.',wraplength=820,padding=8).pack(anchor='w')
  body=self.text(win);self.put(body,report);body.configure(state='disabled')
 def import_constants(self):
  self.require_idle();message=self.store.import_constants(self.csv_path.get());self.status.set(message);self.refresh();messagebox.showinfo('Difficulty table',message,parent=self.root)
 def import_folder(self):
  self.require_idle();path=Path(self.song_path.get()).expanduser()
  if not self.song_path.get().strip() or not path.is_dir():raise ValueError('Choose an existing song folder first')
  settings=self.store.settings();settings['song_folder']=str(path.resolve());atomic(self.store.root/'workspace.json',settings)
  self.task('Import',lambda log:self.store.scan(path,log,self.cancel.is_set))
 def demo(self):
  def run(log):
   r=self.store.scan(ROOT/'examples',log,self.cancel.is_set);c=(r['imported']+r['existing'])[0]
   return self.store.generate(c,log)
  self.task('Example import and evaluation',run)
 def rename(self):
  self.require_idle();c=self.ids()[0];r=next(r for r in self.store.catalog() if r['id']==c);title=simpledialog.askstring('Chart label','Display name',initialvalue=r['title']);diff=simpledialog.askstring('Difficulty','Difficulty label (manual; no filename guessing)',initialvalue=r['difficulty'])
  if title is not None and diff is not None:self.store.label(c,title,diff);self.refresh()
 def batch(self,mode):
  ids=self.ids()
  if self.dirty:raise ValueError('Save or discard the current editor draft before batch processing')
  if mode=='regenerate' and not messagebox.askyesno('New baseline','Create new allocations? Existing revisions remain archived, but the active sequence will change.'):return
  def run(log):
   total=len(ids);done=0
   for i,c in enumerate(ids):
    if self.cancel.is_set():break
    log(f'{i+1}/{total} · {c[:10]} · {mode}')
    try:
     result=self.store.generate(c,log,mode=='regenerate') if mode in ('generate','regenerate') else self.store.calculate(c);log(str(result));self.log_movement_warnings(c,log);done+=1
    except Exception as e:log('FAILED '+c[:10]+': '+str(e))
   return f'{done}/{total} charts completed. Failures are retained in stage status.'
  self.task('Batch '+mode,run)
 def confirm_leave(self):
  return (not self.dirty and not self.arc_has_draft()) or messagebox.askyesno('Unsaved draft','Discard unsaved sequence or arc-path edits?')
 def open_selected(self):
  self.require_idle()
  if not self.confirm_leave():return
  c=self.ids()[0];self.load_chart(c);self.tabs.select(self.pages['Sequence Editor'])
 def load_chart(self,c):
  self.property_uid=None;self.chart=c;self.undo=[];self.redo=[];self.dirty=False;self.external_seen=None
  try:self.seq,head,self.token=self.store.load(c)
  except FileNotFoundError:self.seq=None;self.token=None
  self.caption.set('Chart '+c[:12]+' · '+('No sequence yet: Generate or Import sequence.' if self.seq is None else 'Revision '+head['revision'][:12]));self.populate_units();self.load_facts();self.load_results();self.trajectory_load();self.arc_context()
 def build_facts(self):
  p=self.pages['Chart Data'];bar=ttk.Frame(p);bar.pack(fill='x');self.button(bar,'Preprocess selected chart',self.preprocess);self.button(bar,'Reload chart data',self.load_facts);self.button(bar,'Analyze invalid volume',self.volume_view);ttk.Label(p,text='Source facts and reference judgement hypotheses are separate from editable execution contacts.').pack(anchor='w')
  self.facts=self.tree(p,('event','type','start_ms','end_ms','length','ticks_tight','ticks_loose','flags'),9);self.facts.bind('<<TreeviewSelect>>',self.safe(self.fact_detail));self.fact_json=self.text(p,10)
 def preprocess(self):
  c=self.chart or self.ids()[0];self.task('Chart preprocessing',lambda log:self.store.preprocess(c)['summary'])
 def load_facts(self):
  self.facts.delete(*self.facts.get_children());self.fact_rows={}
  if not self.chart:return
  path=self.store.folder(self.chart)/'chart-facts.json'
  if not path.exists():self.put(self.fact_json,'Preprocess or generate this chart to inspect source facts.');return
  d=read(path)
  traits={r['source_event_id']:r for r in d['traits']}
  for event in d['source_events']:
   if event['kind'] not in ('tap','hold','arc'):continue
   r=traits.get(event['id'],{});flags=[]
   if r.get('negligible_geometry_candidate'):flags.append('near-stationary geometry')
   if r.get('dense_short_hold_candidate'):flags.append('dense short hold')
   key=str(event['id']);self.fact_rows[key]={'source':event,'interpretation':r or None};counts=r.get('nominal_tick_counts',{})
   self.facts.insert('','end',iid=key,values=(key,event['kind'],event['start_ms'],event['end_ms'],r.get('geometric_length',''),counts.get('tight',''),counts.get('loose',''),', '.join(flags)))
  self.put(self.fact_json,{'summary':d['summary'],'limitations':d['limitations']})
 def fact_detail(self):
  ids=self.facts.selection()
  if ids:self.put(self.fact_json,self.fact_rows[ids[0]])
 def build_editor(self):
  p=self.pages['Sequence Editor'];self.caption=tk.StringVar(value='Open a chart from Assets & Batch.');ttk.Label(p,textvariable=self.caption).pack(anchor='w')
  bar=ttk.Frame(p);bar.pack(fill='x')
  for label,fn in [('Import sequence',self.import_sequence),('Save revision',self.save),('Reload from disk',self.reload),('Undo',self.do_undo),('Redo',self.do_redo),('Mark reviewed',self.reviewed),('History',self.history)]:self.button(bar,label,fn)
  self.autosave=tk.BooleanVar(value=True);ttk.Checkbutton(bar,text='Autosave edits',variable=self.autosave).pack(side='left')
  bar=ttk.Frame(p);bar.pack(fill='x')
  for label,fn in [('Add contact',self.add),('Duplicate',self.duplicate),('Delete',self.delete),('Split',self.split),('Merge',self.merge),('Intervals / masks',self.masks),('Chart + arc paths preview',lambda:self.export_preview(False)),('Execution overlay',lambda:self.export_preview(True))]:self.button(bar,label,fn)
  pane=ttk.Panedwindow(p,orient='horizontal');pane.pack(fill='both',expand=True);left=ttk.Frame(pane);right=ttk.Frame(pane);pane.add(left,weight=3);pane.add(right,weight=2)
  row=ttk.Frame(left);row.pack(fill='x');ttk.Label(row,text='Find ID/time').pack(side='left');self.unit_filter=tk.StringVar();ttk.Entry(row,textvariable=self.unit_filter,width=22).pack(side='left');self.unit_filter.trace_add('write',lambda *_:self.populate_units())
  self.units=self.tree(left,('id','type','start_ms','end_ms','hand','press'));self.units.configure(show='tree headings');self.units.column('#0',width=24,stretch=False);self.units.bind('<<TreeviewSelect>>',self.safe(self.pick_unit))
  ttk.Label(right,text='Properties: select to commit; text commits on Enter/focus loss').pack(anchor='w');form=ttk.Frame(right);form.pack(fill='x');self.props={}
  fields=[('kind',sequence.KINDS),('arc_activation',('auto','count','skip')),('hand',('L','R','unresolved')),('role',('required_contact','waypoint')),('geometry_mode',('source','linear','polyline')),('start_ms',None),('end_ms',None),('start_x',None),('start_y',None),('end_x',None),('end_y',None)]
  for i,(name,choices) in enumerate(fields):
   ttk.Label(form,text=name).grid(row=i,column=0,sticky='w');v=tk.StringVar();self.props[name]=v
   widget=ttk.Combobox(form,textvariable=v,values=choices,state='readonly') if choices else ttk.Entry(form,textvariable=v);widget.grid(row=i,column=1,sticky='ew',pady=2)
   if choices:widget.bind('<<ComboboxSelected>>',self.safe(lambda key=name:self.commit_property(key)))
   else:
    widget.bind('<Return>',self.safe(lambda key=name:self.commit_property(key)));widget.bind('<FocusOut>',self.safe(lambda key=name:self.commit_property(key)))
  form.columnconfigure(1,weight=1);self.press=tk.BooleanVar();ttk.Checkbutton(right,text='Explicit fresh press / attached tap (separate from auto arc onset)',variable=self.press,command=self.safe(lambda:self.commit_property('fresh_press'))).pack(anchor='w')
  ttk.Label(right,text='Waypoints JSON: [[time_ms,x,y], ...]').pack(anchor='w');self.waypoints=self.text(right,4);self.waypoints.bind('<FocusOut>',self.safe(lambda:self.commit_property('waypoints')))
  ttk.Label(right,text='Diagnostics (invalid drafts may be saved)').pack(anchor='w');self.diag=self.text(right,4)
 def populate_units(self):
  if not hasattr(self,'units'):return
  old=self.units.selection();self.units.delete(*self.units.get_children())
  if not self.seq:return
  term=self.unit_filter.get().lower()
  for u in sorted(self.seq['units'],key=lambda u:(u['start_ms'],u['unit_id'])):
   if term and term not in (u['unit_id']+' '+str(u['start_ms'])).lower():continue
   self.units.insert('','end',iid=u['unit_id'],values=(u['unit_id'],u['kind'],u['start_ms'],u['end_ms'],u['hand'] or '?',u['fresh_press']))
   if u['kind']=='arc':
    for n,i in enumerate(u['source_event_ids']):self.units.insert(u['unit_id'],'end',iid=u['unit_id']+'::segment:'+str(n),values=('source '+str(i),'arc segment','','','',''))
  self.units.selection_set([i for i in old if self.units.exists(i)])
  self.put(self.diag,sequence.diagnostics(self.seq)[:100])
 def selected_units(self):
  if self.seq is None:raise ValueError('Load or generate a sequence first')
  ids=list(dict.fromkeys(i.split('::segment:')[0] for i in self.units.selection()))
  if not ids:raise ValueError('Select operations in the sequence list')
  return ids
 def pick_unit(self):
  if not self.units.selection():return
  ids=self.selected_units();u=next(u for u in self.seq['units'] if u['unit_id']==ids[0])
  self.property_uid=u['unit_id']
  for k in ('kind','role','geometry_mode','start_ms','end_ms'):self.props[k].set(str(u[k]))
  self.props['hand'].set(u['hand'] or 'unresolved');self.props['arc_activation'].set(u.get('arc_activation','auto'))
  for label,pos in [('start',u['start_position']),('end',u['end_position'])]:
   self.props[label+'_x'].set(str(pos[0]));self.props[label+'_y'].set(str(pos[1]))
  self.press.set(u['fresh_press']);self.put(self.waypoints,u['waypoints'])
 def change(self,s):
  self.require_idle();sequence.validate(s);self.undo.append(copy.deepcopy(self.seq));self.undo=self.undo[-100:];self.redo=[];self.seq=s;self.dirty=True;self.populate_units();self.pick_unit()
  if self.autosave.get():self.save()
 def commit_property(self,key):
  if self.seq is None or not getattr(self,'property_uid',None):return
  self.require_idle();uid=self.property_uid;s=copy.deepcopy(self.seq);u=next((u for u in s['units'] if u['unit_id']==uid),None)
  if u is None:return
  old=copy.deepcopy(u)
  if key in ('kind','role','geometry_mode','arc_activation'):u[key]=self.props[key].get()
  elif key=='hand':u[key]=None if self.props[key].get()=='unresolved' else self.props[key].get()
  elif key in ('start_ms','end_ms'):u[key]=float(self.props[key].get())
  elif key=='fresh_press':u[key]=self.press.get()
  elif key=='waypoints':u[key]=json.loads(self.waypoints.get('1.0','end'))
  else:
   side,axis=key.split('_');u[side+'_position'][0 if axis=='x' else 1]=float(self.props[key].get())
  if u==old:return
  if key=='role' and u['role']=='waypoint':u['fresh_press']=False
  if u['geometry_mode']=='source' and key in ('start_ms','end_ms','start_x','start_y','end_x','end_y','waypoints'):u['geometry_mode']='polyline'
  self.change(s);self.pick_unit()
 def add(self):
  if self.seq is None:raise ValueError('Load a sequence first')
  s=copy.deepcopy(self.seq);u=sequence.new_unit();s['units'].append(u);self.change(s);self.unit_filter.set('');self.units.selection_set(u['unit_id']);self.pick_unit()
 def duplicate(self):
  ids=self.selected_units();s=copy.deepcopy(self.seq)
  from .common import unique
  for old in [u for u in s['units'] if u['unit_id'] in ids]:
   u=copy.deepcopy(old);u['unit_id']='manual:'+unique();u['origin']='duplicate';u['source_event_ids']=[];u['action_ids']=[];u['geometry_mode']='polyline';u['waypoints']=sequence.points(old,self.seq)[1:-1];s['units'].append(u)
  self.change(s)
 def delete(self):
  ids=self.selected_units();s=copy.deepcopy(self.seq);s['units']=[u for u in s['units'] if u['unit_id'] not in ids];self.change(s)
 def split(self):
  uid=self.selected_units()[0];t=simpledialog.askfloat('Split operation','Split time in AFF milliseconds')
  if t is not None:self.change(sequence.split(self.seq,uid,t))
 def merge(self):self.change(sequence.merge(self.seq,self.selected_units()))
 def json_dialog(self,title,value,apply):
  win=tk.Toplevel(self.root);win.title(title);win.geometry('800x550');t=self.text(win);self.put(t,value)
  def done():apply(json.loads(t.get('1.0','end')));win.destroy()
  self.button(win,'Apply',done)
 def masks(self):
  if self.seq is None:raise ValueError('Open a sequence first')
  def apply(x):s=copy.deepcopy(self.seq);s['exclusions']=x;self.change(s)
  values=self.seq.get('exclusions',[])
  if not values:values=[{'start_ms':0,'end_ms':0,'status':'candidate','reason':'Edit bounds; confirmed excludes, dismissed overrides a fully covered detected candidate'}]
  self.json_dialog('Review intervals: candidate / confirmed / dismissed',values,apply)
 def save(self):
  self.require_idle()
  if self.seq is None:raise ValueError('No sequence')
  self.token=self.store.save_sequence(self.chart,self.seq,self.token,'editor save');self.dirty=False;self.external_seen=None;self.traj_stale=True;self.status.set('Revision saved. Difficulty and preview are now stale; update explicitly.');self.refresh()
 def reload(self):
  self.require_idle()
  if not self.chart:return
  if not self.confirm_leave():return
  p=self.store.sequence_path(self.chart);token=digest_bytes(p.read_bytes());s,head,_=self.store.load(self.chart)
  if head['sequence_hash']!=sequence.fingerprint(s):self.store.adopt_external(self.chart,token)
  self.load_chart(self.chart)
 def do_undo(self):
  self.require_idle()
  if not self.undo:return
  self.redo.append(copy.deepcopy(self.seq));self.seq=self.undo.pop();self.dirty=True;self.populate_units();self.pick_unit()
  if self.autosave.get():self.save()
 def do_redo(self):
  self.require_idle()
  if not self.redo:return
  self.undo.append(copy.deepcopy(self.seq));self.seq=self.redo.pop();self.dirty=True;self.populate_units();self.pick_unit()
  if self.autosave.get():self.save()
 def reviewed(self):
  self.require_idle()
  if not self.chart or self.dirty:raise ValueError('Save a sequence first')
  self.store.stage(self.chart,'review','reviewed',self.store.load(self.chart)[1]['revision']);self.refresh()
 def history(self):
  if not self.chart:raise ValueError('Open chart first')
  folder=self.store.folder(self.chart)/'revisions';path=filedialog.askopenfilename(initialdir=folder,title='Restore sequence revision (choose .json, not .meta.json)',filetypes=[('JSON','*.json')])
  if path:self.change(sequence.validate(read(path)))
 def import_sequence(self):
  self.require_idle()
  if not self.chart:raise ValueError('Open a chart first')
  if not self.confirm_leave():return
  p=filedialog.askopenfilename(filetypes=[('Sequence JSON','*.json')])
  if p:self.store.import_sequence(self.chart,p);self.load_chart(self.chart);self.refresh()
 def export_preview(self,overlay):
  if not self.chart or self.dirty:raise ValueError('Save the sequence first')
  c=self.chart;self.task('Preview export',lambda log:self.store.make_preview(c,overlay))
 def draw_lines(self,canvas,series,label,limits=None):
  canvas.delete('all');w=max(canvas.winfo_width(),400);h=max(canvas.winfo_height(),250);pad=45
  valid=[(x,y) for x,y in series if y is not None and math.isfinite(y)]
  if not valid:canvas.create_text(15,20,text='No valid data',anchor='w',fill='white');return
  x0=min(x for x,y in valid);x1=max(x for x,y in valid);y0=min(0,min(y for x,y in valid));y1=max(y for x,y in valid)
  if limits is not None:y0,y1=limits
  if y1<=y0:y1=y0+1
  canvas.create_line(pad,h-pad,w-15,h-pad,fill='#8293a8');canvas.create_line(pad,20,pad,h-pad,fill='#8293a8')
  canvas.create_text(pad,10,text=label,anchor='w',fill='#c9d8ed');canvas.create_text(pad,h-15,text=f'{x0:.3g}',fill='white');canvas.create_text(w-30,h-15,text=f'{x1:.3g}',fill='white');canvas.create_text(20,30,text=f'{y1:.3g}',fill='white');canvas.create_text(20,h-pad,text=f'{y0:.3g}',fill='white')
  last=None
  for x,y in series:
   if y is None or not math.isfinite(y):last=None;continue
   point=(pad+(x-x0)/max(1e-9,x1-x0)*(w-pad-20),h-pad-(y-y0)/(y1-y0)*(h-pad-30))
   if last:canvas.create_line(*last,point[0],last[1],*point,fill='#60c5ff',width=2)
   last=point
 def build_results(self):
  p=self.pages['Results & Export'];bar=ttk.Frame(p);bar.pack(fill='x')
  self.button(bar,'Update current chart',self.update_current);self.button(bar,'Reload result',self.load_results);self.button(bar,'Movement warnings',self.show_movement_warnings);self.button(bar,'Batch export selected assets',self.export_batch);self.include_stale=tk.BooleanVar();ttk.Checkbutton(bar,text='Include stale metric values',variable=self.include_stale).pack(side='left')
  self.result_state=tk.StringVar(value='No chart open');ttk.Label(p,textvariable=self.result_state).pack(anchor='w');self.result_text=self.text(p,9)
  row=ttk.Frame(p);row.pack(fill='x');ttk.Label(row,text='Time series').pack(side='left');self.result_channel=tk.StringVar(value='movement');self.result_combo=ttk.Combobox(row,textvariable=self.result_channel,width=25);self.result_combo.pack(side='left');self.button(row,'Plot',self.plot_result)
  self.result_graph=tk.Canvas(p,bg='#101b2b',height=300);self.result_graph.pack(fill='both',expand=True)
 def update_current(self):
  if not self.chart or self.dirty:raise ValueError('Open and save a chart first')
  c=self.chart
  def run(log):
   result=self.store.calculate(c);self.log_movement_warnings(c,log);return result
  self.task('Difficulty update',run)
 def log_movement_warnings(self,c,log):
  path=self.store.folder(c)/'movement-warnings.json'
  if path.exists():
   count=len(read(path).get('warnings',[]))
   if count:log(f'WARNING: {count} movement intervals capped/clipped; see Results & Export or {path}')
 def load_results(self):
  if not hasattr(self,'result_text') or not self.chart:return
  p=self.store.folder(self.chart)/'metrics.json'
  if not p.exists():self.result_state.set('No difficulty result. Generate or Update difficulty.');self.put(self.result_text,'');return
  r=read(p);self.result_state.set(('CURRENT' if self.store.fresh(self.chart,'difficulty') else 'STALE — update explicitly')+' · '+r['status']+' · '+r['definition_name']);self.put(self.result_text,{k:v for k,v in r.items() if k not in ('series','coverage','diagnostics','frequency_segments','definition','invalid_volume','movement_warnings')})
  if r['series']:self.result_combo['values']=[k for k in r['series'][0] if k not in ('included','time_ms')]
  self.plot_result()
 def show_movement_warnings(self):
  if not self.chart:raise ValueError('Open a chart first')
  report=read(self.store.folder(self.chart)/'movement-warnings.json');win=tk.Toplevel(self.root);win.title('Movement cap warnings');win.geometry('900x620');body=self.text(win);self.put(body,report);body.configure(state='disabled')
 def plot_result(self):
  if not self.chart:return
  p=self.store.folder(self.chart)/'metrics.json'
  if not p.exists():return
  r=read(p);key=self.result_channel.get();self.draw_lines(self.result_graph,[(x['time_ms']/1000,x.get(key) if x['included'] else None) for x in r['series']],key+' · AFF seconds')
 def export_batch(self):
  ids=self.ids();dest=filedialog.askdirectory(title='Choose parent folder for a new export')
  if dest:
   from .common import unique
   dest=Path(dest)/('arcaea-export-'+unique()[:10]);include=self.include_stale.get();self.task('Batch export',lambda log:self.store.export(ids,dest,include))
 def build_interfaces(self):
  p=self.pages['Interfaces'];ttk.Label(p,text='Recognition and preview adapters · explicit local files. Loading validates configuration; scripts run only during chart processing.',wraplength=1100).pack(anchor='w');self.settings_vars={};form=ttk.Frame(p);form.pack(fill='x');settings=self.store.settings()
  labels={'allocation_script':'Recognition Python script','visualization_script':'Preview Python script','recognition_profile':'Recognition profile .json','beam_width':'Beam width'}
  for i,k in enumerate(labels):
   value=settings.get(k,str(ROOT/'defaults/recognition.json') if k=='recognition_profile' else '')
   if k.endswith('_script'):value=str(adapters.resolve(settings,'allocation' if k=='allocation_script' else 'visualization'))
   ttk.Label(form,text=labels[k]).grid(row=i,column=0,sticky='w');v=tk.StringVar(value=str(value));self.settings_vars[k]=v;ttk.Entry(form,textvariable=v,width=80).grid(row=i,column=1,sticky='ew')
   if k!='beam_width':ttk.Button(form,text='Browse',command=self.safe(lambda key=k:self.browse_interface(key))).grid(row=i,column=2)
   if k=='recognition_profile':ttk.Button(form,text='Load profile',command=self.safe(self.check_recognition_profile)).grid(row=i,column=3)
  form.columnconfigure(1,weight=1);bar=ttk.Frame(p);bar.pack(fill='x');self.button(bar,'Validate & save interfaces',self.save_interfaces);self.button(bar,'Save profile edits',self.save_recognition_profile);self.button(bar,'Save profile as',self.save_recognition_profile_as);self.button(bar,'Open workspace',lambda:self.open_path(self.store.root))
  self.profile_status=tk.StringVar();ttk.Label(p,textvariable=self.profile_status,wraplength=1150).pack(fill='x');ttk.Label(p,text='tolerance_x/y are AFF half-widths (±). Timing tolerance and maximum reachable speed are unset. These are preparation fields; only allocator_preferences affects the existing recognizer.',wraplength=1150).pack(fill='x')
  self.recognition_text=self.text(p,12)
  try:self.check_recognition_profile()
  except (OSError,ValueError) as e:self.profile_status.set('Profile unavailable: '+str(e)+' — browse and load a valid file.')
  ttk.Label(p,text='Allocation CLI: python SCRIPT source.aff -o sequence.json --beam-width N [--preferences flat-preferences.json]. Preview CLI: python SCRIPT source.aff sequence.json -o preview.aff. Custom recognizers using a nonempty preference profile must accept --preferences. Difficulty JSON is loaded on Difficulty Functions; path assets are managed on Arc Paths.',wraplength=1150).pack(fill='x')
 def save_interfaces(self):
  self.require_idle();settings=self.store.settings()
  for k,v in self.settings_vars.items():settings[k]=int(v.get()) if k=='beam_width' else v.get()
  if not 1<=settings['beam_width']<=512:raise ValueError('Beam must be 1–512')
  for kind in ('allocation','visualization'):adapters.resolve(settings,kind)
  profile=Path(settings['recognition_profile']).expanduser().resolve();recognition.validate(read(profile));settings['recognition_profile']=str(profile)
  atomic(self.store.root/'workspace.json',settings);self.status.set('Interfaces saved; future jobs use these scripts.');self.refresh()
 def open_path(self,p):
  p=str(Path(p).resolve())
  if sys.platform=='win32':os.startfile(p)
  else:subprocess.Popen(['open' if sys.platform=='darwin' else 'xdg-open',p])
 def poll(self):
  try:
   while True:
    kind,msg=self.events.get_nowait()
    if kind=='trial':self.lab_show_comparison(msg)
    elif kind in ('log','trace'):self.log.insert('end',msg+'\n');self.log.see('end')
    elif kind in ('done','error'):
     self.busy=False;self.status.set(msg);self.refresh()
     if kind=='error':messagebox.showerror('Job failed',msg)
     if self.chart:self.load_facts();self.load_results();self.trajectory_load()
  except queue.Empty:pass
  except Exception as e:self.status.set('Refresh warning: '+str(e))
  if not self.busy:
   try:
    if self.chart and self.seq is not None:
     p=self.store.sequence_path(self.chart);current=digest_bytes(p.read_bytes())
     if current!=self.token and current!=self.external_seen:
      self.external_seen=current
      if self.dirty or self.arc_has_draft():self.status.set('External sequence changed; unsaved editor draft retained. Reload explicitly to resolve.')
      else:
       self.store.adopt_external(self.chart,current);self.load_chart(self.chart);self.status.set('Valid external sequence change reloaded; metrics are stale.')
    path=self.store.root/'definitions/working.difficulty.json'
    if path.exists():
     data=path.read_bytes();h=digest_bytes(data)
     if self.last_definition_bytes is not None and h!=self.last_definition_bytes:self.function_status.set('Definition file changed on disk. Open external file, inspect, then Validate & activate.')
     self.last_definition_bytes=h
   except Exception as e:self.status.set('External update not loaded: '+str(e))
  self.root.after(1200,self.poll)
 def close(self):
  if self.busy:
   self.cancel.set();messagebox.showinfo('Batch stopping','The current chart will finish safely. Close again after it completes.');return
  if not self.confirm_leave():return
  self.root.destroy()
