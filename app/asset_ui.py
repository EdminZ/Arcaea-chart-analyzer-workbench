"""Explicit path controls and portable arc execution-path assets."""
import copy,json
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog
from .common import ROOT,read,atomic,digest,digest_bytes
from . import arc_paths,recognition,adapters
class AssetUI:
 def browse_interface(self,key):
  path=filedialog.askopenfilename(parent=self.root,filetypes=[('JSON profile','*.json')] if key=='recognition_profile' else [('Python script','*.py')])
  if path:self.settings_vars[key].set(path)
 def check_recognition_profile(self):
  path=Path(self.settings_vars['recognition_profile'].get()).expanduser().resolve();data=recognition.validate(read(path));self.put(self.recognition_text,data);self.recognition_loaded=path;self.recognition_token=digest_bytes(path.read_bytes());self.profile_status.set('Loaded '+str(path)+' · reference-timing arc recognition; endpoint relaxation is configurable.')
 def save_recognition_profile(self):
  data=recognition.validate(json.loads(self.recognition_text.get('1.0','end')));path=getattr(self,'recognition_loaded',None)
  if path is None:raise ValueError('Load a profile first')
  if ROOT/'defaults' in path.parents:raise ValueError('Use Save profile as to create a workspace copy of bundled defaults')
  if digest_bytes(path.read_bytes())!=self.recognition_token:raise ValueError('Profile changed externally; reload it before saving')
  atomic(path,data);self.recognition_token=digest_bytes(path.read_bytes());self.profile_status.set('Profile saved. Validate & save interfaces to select it for future allocation runs.')
 def save_recognition_profile_as(self):
  data=recognition.validate(json.loads(self.recognition_text.get('1.0','end')));path=filedialog.asksaveasfilename(parent=self.root,initialdir=self.store.root,initialfile='recognition.json',defaultextension='.json')
  if path:
   atomic(path,data);self.settings_vars['recognition_profile'].set(str(Path(path).resolve()));self.check_recognition_profile()
 def build_arc_assets(self):
  p=self.pages['Arc Paths'];self.arc_data=None;self.arc_token=None;self.arc_loaded=None;self.arc_chart=None;self.arc_selected=None
  row=ttk.Frame(p);row.pack(fill='x');ttk.Label(row,text='Arc path .json').pack(side='left');self.arc_path=tk.StringVar();ttk.Entry(row,textvariable=self.arc_path).pack(side='left',fill='x',expand=True);self.button(row,'Browse',self.arc_browse);self.button(row,'Load file',self.arc_load)
  row=ttk.Frame(p);row.pack(fill='x');self.button(row,'Recognize arc paths',self.arc_recognize);self.button(row,'Create from current sequence',self.arc_create);self.button(row,'Save edited asset',self.arc_save);self.button(row,'Save asset as',self.arc_save_as);self.button(row,'Apply reviewed selected path',self.arc_apply)
  self.arc_status=tk.StringVar(value='Open a chart first. Arc assets store source and execution paths separately; reference-timing recognition is available; gameplay feasibility is unverified.');ttk.Label(p,textvariable=self.arc_status,wraplength=1150).pack(fill='x')
  ttk.Label(p,text='Coordinates: original AFF x/y. Gray = source; blue = candidate execution. Edit selected points as [[time_ms,x,y], ...], then Save edited asset. Review is a human label, not a game-mechanics certificate.',wraplength=1150).pack(fill='x')
  pane=ttk.Panedwindow(p,orient='horizontal');pane.pack(fill='both',expand=True);left=ttk.Frame(pane);right=ttk.Frame(pane);pane.add(left,weight=1);pane.add(right,weight=3)
  self.arc_tree=self.tree(left,('unit','review','points'),12);self.arc_tree.bind('<<TreeviewSelect>>',self.safe(self.arc_pick));self.arc_canvas=tk.Canvas(right,height=280,bg='#101b2b');self.arc_canvas.pack(fill='both',expand=True);self.arc_canvas.bind('<Configure>',lambda e:self.arc_draw())
  self.arc_reviewed=tk.BooleanVar();ttk.Checkbutton(right,text='I have manually reviewed this execution path',variable=self.arc_reviewed).pack(anchor='w');self.arc_editor=self.text(right,7)
 def arc_has_draft(self):
  if getattr(self,'arc_data',None) is None:return False
  if digest(self.arc_data)!=getattr(self,'arc_saved_digest',None):return True
  if self.arc_selected is not None:
   item=next(p for p in self.arc_data['paths'] if p['unit_id']==self.arc_selected)
   try:return json.loads(self.arc_editor.get('1.0','end'))!=item['points'] or self.arc_reviewed.get()!=(item['review_status']=='manually_reviewed')
   except ValueError:return True
  return False
 def arc_default_path(self):
  if not self.chart:raise ValueError('Open a chart first')
  return self.store.preview_destination(self.chart).with_name(self.store.output_stem(self.chart)+'.arc-paths.json')
 def arc_context(self):
  if not hasattr(self,'arc_path'):return
  self.arc_data=None;self.arc_selected=None;self.arc_loaded=None;self.arc_token=None;self.arc_chart=self.chart;self.arc_tree.delete(*self.arc_tree.get_children());self.put(self.arc_editor,'');self.arc_canvas.delete('all')
  pointer=self.store.folder(self.chart)/'arc-paths-location.json';self.arc_path.set(read(pointer)['path'] if pointer.exists() else str(self.arc_default_path()));self.arc_status.set('Chart changed. Load its arc path asset, or create one from the current sequence.')
 def arc_browse(self):
  path=filedialog.askopenfilename(parent=self.root,filetypes=[('Arc path JSON','*.json')])
  if path:self.arc_path.set(path)
 def arc_install(self,data,path):
  self.arc_data=data;self.arc_saved_digest=digest(data);self.arc_loaded=Path(path).resolve();self.arc_path.set(str(self.arc_loaded));self.arc_token=digest_bytes(self.arc_loaded.read_bytes()) if self.arc_loaded.exists() else None;self.arc_chart=self.chart;self.arc_selected=None;self.arc_tree.delete(*self.arc_tree.get_children());self.put(self.arc_editor,'');self.arc_reviewed.set(False)
  for item in data['paths']:self.arc_tree.insert('','end',iid=item['unit_id'],values=(item['unit_id'],item['review_status'],len(item['points'])))
  self.arc_status.set('Loaded '+str(self.arc_loaded)+' · '+str(len(data['paths']))+' arc paths');self.arc_draw()
 def arc_load(self):
  self.require_idle()
  if not self.chart:raise ValueError('Open a chart first')
  path=Path(self.arc_path.get()).expanduser().resolve();data=arc_paths.validate(read(path),self.chart);self.arc_install(data,path);atomic(self.store.folder(self.chart)/'arc-paths-location.json',{'path':str(path)})
 def arc_create(self):
  self.require_idle()
  if not self.chart or self.seq is None or self.dirty:raise ValueError('Open and save a sequence first')
  path=self.arc_default_path()
  if path.exists():raise ValueError('An arc asset already exists. Load it, or move/rename it before creating a replacement: '+str(path))
  data=arc_paths.from_sequence(self.seq);atomic(path,data);self.arc_install(data,path);atomic(self.store.folder(self.chart)/'arc-paths-location.json',{'path':str(path)})
 def arc_commit_editor(self):
  if self.arc_data is None or self.arc_selected is None:return
  points=json.loads(self.arc_editor.get('1.0','end'));draft=copy.deepcopy(self.arc_data);item=next(p for p in draft['paths'] if p['unit_id']==self.arc_selected)
  changed=points!=item['points'];item['points']=points;item['review_status']='manually_reviewed' if self.arc_reviewed.get() else 'unreviewed'
  if changed:item['review_status']='unreviewed';self.arc_reviewed.set(False)
  self.arc_data=arc_paths.validate(draft,self.chart);self.arc_tree.item(self.arc_selected,values=(self.arc_selected,item['review_status'],len(points)))
 def arc_pick(self):
  if not self.arc_tree.selection() or self.arc_data is None:return
  self.arc_commit_editor();self.arc_selected=self.arc_tree.selection()[0];item=next(p for p in self.arc_data['paths'] if p['unit_id']==self.arc_selected);self.put(self.arc_editor,item['points']);self.arc_reviewed.set(item['review_status']=='manually_reviewed');self.arc_draw()
 def arc_save(self):
  self.require_idle()
  if self.arc_data is None or self.arc_loaded is None:raise ValueError('Load or create an arc asset first')
  self.arc_commit_editor()
  if self.arc_token is None or digest_bytes(self.arc_loaded.read_bytes())!=self.arc_token:raise ValueError('Arc asset changed externally; reload before saving')
  atomic(self.arc_loaded,self.arc_data);self.arc_token=digest_bytes(self.arc_loaded.read_bytes());self.arc_saved_digest=digest(self.arc_data);self.arc_status.set('Saved '+str(self.arc_loaded)+' · editing points clears review; review the new path before applying.');self.arc_draw()
 def arc_save_as(self):
  self.require_idle()
  if self.arc_data is None:raise ValueError('Load or create an arc asset first')
  self.arc_commit_editor();path=filedialog.asksaveasfilename(parent=self.root,initialfile=self.store.output_stem(self.chart)+'.arc-paths.json',defaultextension='.json')
  if path:atomic(path,self.arc_data);self.arc_install(self.arc_data,path);atomic(self.store.folder(self.chart)/'arc-paths-location.json',{'path':str(Path(path).resolve())})
 def arc_apply(self):
  self.require_idle()
  if self.arc_selected is None or self.dirty:raise ValueError('Select an arc path and save any sequence edits first')
  self.arc_save();current,head,token=self.store.load(self.chart)
  if token!=self.token:raise ValueError('Sequence changed externally; reload the chart first')
  result=arc_paths.apply(current,self.arc_data,self.arc_selected);self.store.save_sequence(self.chart,result,token,'Apply reviewed arc path asset');self.arc_data['sequence_hash']=digest(result);atomic(self.arc_loaded,self.arc_data);self.load_chart(self.chart);self.refresh();self.status.set('Arc path applied as a sequence revision. Update difficulty and generate Execution overlay explicitly.')
 def arc_draw(self):
  if not hasattr(self,'arc_canvas'):return
  c=self.arc_canvas;c.delete('all')
  if self.arc_data is None or self.arc_selected is None:return
  item=next(p for p in self.arc_data['paths'] if p['unit_id']==self.arc_selected);pts=item['source_points']+item['points'];xmin=min([0]+[p[1] for p in pts]);xmax=max([1]+[p[1] for p in pts]);ymin=min([0]+[p[2] for p in pts]);ymax=max([1]+[p[2] for p in pts]);w=max(300,c.winfo_width());h=max(180,c.winfo_height())
  c.create_text(12,12,anchor='nw',text=f'AFF x [{xmin:g},{xmax:g}] · y [{ymin:g},{ymax:g}] · '+self.arc_selected,fill='white')
  for key,color in [('source_points','#8795a5'),('points','#62caff')]:
   coords=[]
   for t,x,y in item[key]:coords.extend((30+(x-xmin)/(xmax-xmin)*(w-60),h-25-(y-ymin)/(ymax-ymin)*(h-60)))
   c.create_line(*coords,fill=color,width=2 if key=='points' else 1)

 def arc_recognize(self):
  self.require_idle()
  if not self.chart or self.seq is None or self.dirty:raise ValueError('Open and save a sequence first')
  if self.arc_has_draft():raise ValueError('Save your arc asset edits first')
  c=self.chart
  self.task('Arc path recognition',lambda log:self.store.recognize_arcs(c))
