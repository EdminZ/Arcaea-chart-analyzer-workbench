"""Function laboratory and frequency/movement trajectory, using standard Tk only."""
import bisect,copy,json,math,time
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,simpledialog,messagebox
from .common import ROOT,read,atomic,digest,digest_bytes
from . import difficulty,model2
class LabUI:
 def build_lab(self):
  p=self.pages['Difficulty Functions'];bar=ttk.Frame(p);bar.pack(fill='x')
  for title,fn in [('New model',self.lab_new),('Load active',self.lab_load),('Save draft',self.lab_save),('Validate & activate',self.lab_activate),('Restore version',self.lab_restore),('Export definition',self.lab_export),('Compare on chart',self.lab_compare)]:self.button(bar,title,fn)
  row=ttk.Frame(p);row.pack(fill='x');ttk.Label(row,text='Difficulty definition .json').pack(side='left');self.lab_file=tk.StringVar(value=str(self.store.root/'definitions/working.difficulty.json'));ttk.Entry(row,textvariable=self.lab_file).pack(side='left',fill='x',expand=True);self.button(row,'Browse',self.lab_browse);self.button(row,'Load file',self.lab_open)
  self.lab_file_status=tk.StringVar();ttk.Label(p,textvariable=self.lab_file_status,wraplength=1150).pack(fill='x')
  row=ttk.Frame(p);row.pack(fill='x');self.button(row,'Step-by-step tutorial',lambda:self.open_path(ROOT/'docs/FUNCTIONS_TUTORIAL.html'));self.button(row,'Update current chart',self.update_current)
  ttk.Label(row,text='1 Select a parameter → 2 Enter a value → 3 Compare on chart → 4 Validate & activate → Update',wraplength=850).pack(side='left')
  self.function_status=tk.StringVar();ttk.Label(p,textvariable=self.function_status,wraplength=1150).pack(fill='x')
  pane=ttk.Panedwindow(p,orient='horizontal');pane.pack(fill='both',expand=True);left=ttk.Frame(pane);right=ttk.Frame(pane);pane.add(left,weight=2);pane.add(right,weight=3)
  ttk.Label(left,text='External definition · JSON (advanced editing)').pack(anchor='w');self.definition=self.text(left,18)
  row=ttk.Frame(left);row.pack(fill='x');self.button(row,'Refresh controls from JSON',self.lab_refresh)
  ttk.Label(left,text='Saved drafts do not change active scores. Activation keeps previous versions.\nExisting /1 models remain usable; New model creates the revised /2 format.',wraplength=440).pack(anchor='w')
  config=ttk.LabelFrame(left,text='Movement scale',padding=6);config.pack(fill='x')
  row=ttk.Frame(config);row.pack(fill='x');ttk.Label(row,text='Vertical factor (0–1)').pack(side='left');self.lab_vertical=tk.StringVar(value='0.5');e=ttk.Entry(row,textvariable=self.lab_vertical,width=8);e.pack(side='left');e.bind('<Return>',self.safe(self.lab_vertical_commit));e.bind('<FocusOut>',self.safe(self.lab_vertical_commit))
  self.lab_normalized=tk.BooleanVar(value=True);ttk.Checkbutton(config,text='Shared response scale: maximum 1',variable=self.lab_normalized,command=self.safe(self.lab_normalize_commit)).pack(anchor='w')
  row=ttk.Frame(config);row.pack(fill='x');self.button(row,'Use 2.3 movement defaults',self.lab_movement_defaults)
  ttk.Label(config,text='Corrected distance = sqrt(dx² + (factor × dy)²).\n0 ignores vertical motion; 1 keeps the old coordinate scale.\nDefault 0.5 is a starting assumption, not device calibration.',wraplength=430).pack(anchor='w')
  ttk.Label(left,text='Context: distance 0.2–0.3 over 80–160 ms gives speeds 1.25–3.75 before vertical correction. The initial speed limit is 4; excess speeds are capped and logged.\nIntensity q is per hand; interval weight = q × duration in seconds. Normalizing the two curves together preserves their relative scale.',wraplength=440).pack(anchor='w',pady=6)
  row=ttk.Frame(right);row.pack(fill='x');ttk.Label(row,text='Movement response').pack(side='left');self.lab_channel=tk.StringVar(value='tap');box=ttk.Combobox(row,textvariable=self.lab_channel,values=('tap','arc'),state='readonly',width=8);box.pack(side='left');box.bind('<<ComboboxSelected>>',self.safe(self.lab_refresh))
  self.lab_mode=tk.StringVar(value='expression');box=ttk.Combobox(row,textvariable=self.lab_mode,values=('expression','points'),state='readonly',width=12);box.pack(side='left');box.bind('<<ComboboxSelected>>',self.safe(self.lab_switch_mode))
  self.lab_expr=tk.StringVar();ent=ttk.Entry(right,textvariable=self.lab_expr);ent.pack(fill='x');ent.bind('<Return>',self.safe(self.lab_commit_expr));ent.bind('<FocusOut>',self.safe(self.lab_commit_expr))
  row=ttk.Frame(right);row.pack(fill='x');self.lab_xmax=tk.StringVar(value='4');self.lab_ymax=tk.StringVar(value='1')
  ttk.Label(row,text='Speed cap / X max').pack(side='left');e=ttk.Entry(row,textvariable=self.lab_xmax,width=8);e.pack(side='left');e.bind('<Return>',self.safe(self.lab_cap_commit));e.bind('<FocusOut>',self.safe(self.lab_cap_commit));ttk.Label(row,text='Y max = 1 when normalized').pack(side='left',padx=8)
  self.button(row,'Plot',self.lab_plot)
  self.lab_canvas=tk.Canvas(right,bg='#101b2b',height=185,highlightthickness=0);self.lab_canvas.pack(fill='both',expand=True);self.lab_canvas.bind('<Configure>',lambda e:self.lab_plot_quiet());self.lab_canvas.bind('<ButtonPress-1>',self.lab_drag_start);self.lab_canvas.bind('<B1-Motion>',self.lab_drag);self.lab_canvas.bind('<ButtonRelease-1>',self.safe(self.lab_drag_end));self.lab_canvas.bind('<Double-1>',self.safe_event(self.lab_add_point));self.lab_canvas.bind('<Button-3>',self.safe_event(self.lab_delete_point));self.lab_drag_index=None;self.lab_drag_points=None;self.lab_curve_scale=1.;self.lab_drag_normalizer=None
  ttk.Label(right,text='Curve mode: drag points; double-click adds; right-click deletes.\nOrigin stays (0,0). Beyond the last point, the curve stays flat. Shared normalization rescales both curves on commit.',wraplength=650).pack(anchor='w')
  self.lab_parameters=self.tree(right,('parameter','value'),3);self.lab_parameters.bind('<<TreeviewSelect>>',self.safe(self.lab_pick_parameter))
  row=ttk.Frame(right);row.pack(fill='x');ttk.Label(row,text='Selected parameter').pack(side='left');self.lab_pvalue=tk.StringVar();ent=ttk.Entry(row,textvariable=self.lab_pvalue,width=12);ent.pack(side='left');ent.bind('<Return>',self.safe(self.lab_set_parameter));ent.bind('<FocusOut>',self.safe(self.lab_set_parameter));self.lab_slider=ttk.Scale(row,from_=0,to=10,command=self.lab_slide);self.lab_slider.pack(side='left',fill='x',expand=True)
  self.parameter_help=tk.StringVar(value='Start with tap_scale: select its row, enter 1.2, then press Enter. Compare before activating.');ttk.Label(right,textvariable=self.parameter_help,wraplength=640).pack(anchor='w')
  settings=ttk.Frame(right);settings.pack(fill='x');self.lab_settings={}
  for i,k in enumerate(('frequency_window_ms','movement_window_ms','peak_min_ms','near_peak_ratio','arc_threshold','sample_ms','arc_step_ms')):
   ttk.Label(settings,text=k).grid(row=i//2,column=(i%2)*2,sticky='w');v=tk.StringVar();self.lab_settings[k]=v;e=ttk.Entry(settings,textvariable=v,width=9);e.grid(row=i//2,column=(i%2)*2+1);e.bind('<Return>',self.safe(lambda key=k:self.lab_setting(key)));e.bind('<FocusOut>',self.safe(lambda key=k:self.lab_setting(key)))
  row=ttk.Frame(right);row.pack(fill='x');ttk.Label(row,text='Compare section (AFF ms):').pack(side='left');self.lab_from=tk.StringVar(value='0');self.lab_to=tk.StringVar(value='999999')
  for v in (self.lab_from,self.lab_to):ttk.Entry(row,textvariable=v,width=10).pack(side='left')
  self.lab_load()
 def safe_event(self,fn):
  def run(event):return self.safe(lambda:fn(event))()
  return run
 def lab_get(self):return difficulty.validate(json.loads(self.definition.get('1.0','end')))
 def lab_put(self,d):self.put(self.definition,d)
 def lab_load(self):
  active=self.store.active_definition();self.lab_file.set(str(self.store.root/'definitions/versions'/(digest(active)+'.json')));self.lab_file_status.set('Loaded active snapshot: '+self.lab_file.get());self.lab_put(active);self.last_definition_bytes=digest_bytes((self.store.root/'definitions/working.difficulty.json').read_bytes());self.lab_refresh()
 def lab_new(self):
  name=simpledialog.askstring('New difficulty model','Model name',initialvalue='My frequency and movement model')
  if name:
   d=read(ROOT/'defaults/difficulty-v2.json');d['name']=name;self.lab_file.set(str(ROOT/'defaults/difficulty-v2.json'));self.lab_file_status.set('New unsaved draft based on '+self.lab_file.get());self.lab_put(d);self.lab_refresh()
 def lab_browse(self):
  path=filedialog.askopenfilename(title='Difficulty definition',filetypes=[('JSON','*.json')])
  if path:self.lab_file.set(path)
 def lab_open(self):
  path=Path(self.lab_file.get()).expanduser().resolve();d=difficulty.validate(read(path));self.lab_put(d);self.lab_file.set(str(path));self.lab_file_status.set('Loaded: '+str(path));self.lab_refresh()
 def lab_restore(self):
  path=filedialog.askopenfilename(initialdir=self.store.root/'definitions/versions',title='Load an earlier model (activation is explicit)',filetypes=[('JSON','*.json')])
  if path:self.lab_file.set(path);self.lab_open()
 def lab_save(self):
  d=self.lab_get();atomic(self.store.root/'definitions/draft.json',d);self.lab_file.set(str(self.store.root/'definitions/draft.json'));self.lab_file_status.set('Saved draft: '+self.lab_file.get());self.function_status.set('Draft saved. Active definition and results unchanged.')
 def lab_export(self):
  d=self.lab_get();path=filedialog.asksaveasfilename(initialfile='difficulty.json',defaultextension='.json')
  if path:atomic(path,d);self.lab_file.set(str(Path(path).resolve()));self.lab_file_status.set('Exported current draft: '+self.lab_file.get())
 def lab_activate(self):
  self.require_idle();d=self.lab_get();self.store.activate_definition(d);self.lab_file_status.set('Active snapshot: '+str(self.store.root/'definitions/versions'/(digest(d)+'.json')));self.last_definition_bytes=digest_bytes((self.store.root/'definitions/working.difficulty.json').read_bytes());self.lab_refresh();self.refresh();self.load_results();self.traj_stale=True;self.trajectory_draw();self.status.set('Definition activated. Existing metrics are stale; update explicitly.')
 def lab_refresh(self):
  d=self.lab_get();self.lab_parameters.delete(*self.lab_parameters.get_children())
  for k,v in d['parameters'].items():self.lab_parameters.insert('','end',iid=k,values=(k,v))
  if d['format']=='arcaea-difficulty/2':
   r=d['responses'][self.lab_channel.get()];self.lab_mode.set(r['type']);self.lab_expr.set(r.get('expression','Curve mode — edit points in the graph'))
   for k,v in self.lab_settings.items():v.set(str(d[k]))
   self.lab_vertical.set(str(d.get('vertical_scale',1)));self.lab_normalized.set(d.get('normalize_response',False));self.lab_xmax.set(str(d['speed_limit']) if d.get('speed_limit') is not None else '');self.lab_ymax.set('1' if d.get('normalize_response',False) else '50')
   self.lab_plot()
  else:self.lab_canvas.delete('all');self.lab_canvas.create_text(20,25,text='Legacy /1 model: edit JSON, or choose New model.',anchor='w',fill='white')
  self.function_status.set(('ACTIVE' if digest(d)==digest(self.store.active_definition()) else 'DRAFT')+' · '+d['name']+' · illustrative, uncalibrated functions')
 def lab_edit(self,mutator):
  d=self.lab_get()
  if d['format']!='arcaea-difficulty/2':return
  old=copy.deepcopy(d);mutator(d);difficulty.validate(d)
  if d!=old:self.lab_put(d);self.function_status.set('DRAFT — Save draft or Validate & activate.');self.lab_plot()
 def lab_commit_expr(self):
  if self.lab_mode.get()=='expression':self.lab_edit(lambda d:d['responses'][self.lab_channel.get()].update(type='expression',expression=self.lab_expr.get()))
 def lab_switch_mode(self):
  mode=self.lab_mode.get();channel=self.lab_channel.get();d=self.lab_get()
  if d['format']!='arcaea-difficulty/2':return
  if d['responses'][channel]['type']==mode:return
  if mode=='points':
   fn=model2.response(d['responses'][channel],d['parameters']);x=float(self.lab_xmax.get() or 4);spec={'type':'points','points':[[i*x/4,fn(i*x/4)] for i in range(5)]}
  else:spec={'type':'expression','expression':'v'}
  d['responses'][channel]=spec;self.lab_put(difficulty.validate(d));self.lab_refresh()
 def lab_vertical_commit(self):self.lab_edit(lambda d:d.update(vertical_scale=float(self.lab_vertical.get())))
 def lab_cap_commit(self):
  value=float(self.lab_xmax.get()) if self.lab_xmax.get().strip() else None
  self.lab_edit(lambda d:d.update(speed_limit=value))
 def lab_normalize_commit(self):
  self.lab_edit(lambda d:d.update(normalize_response=self.lab_normalized.get(),speed_limit=d.get('speed_limit') or 4.))
  self.lab_refresh()
 def lab_movement_defaults(self):
  self.lab_edit(lambda d:d.update(vertical_scale=.5,speed_limit=4.,normalize_response=True));self.lab_refresh()
 def lab_setting(self,key):self.lab_edit(lambda d:d.update({key:float(self.lab_settings[key].get())}))
 def lab_pick_parameter(self):
  ids=self.lab_parameters.selection()
  if ids:
   self.lab_pvalue.set(str(self.lab_get()['parameters'][ids[0]]))
   descriptions={'tap_scale':'Transfer scale relative to arcs. Shared normalization can rescale both curves; compare the draft. Input frequency stays unchanged.','tap_threshold':'Speed below this threshold contributes zero transfer weight. Units: chart-coordinate distance / second.','tap_power':'Exponent after threshold subtraction: above 1 amplifies values >1 and suppresses values between 0 and 1.','arc_scale':'Arc scale relative to transfers. Shared normalization can rescale both curves; stationary holding costs zero.','arc_threshold_speed':'Arc speed cutoff; unrelated to arc_threshold, the invalid-volume path-length cutoff.','arc_power':'Exponent in the nonlinear part of the arc response. Changing it does not uniformly scale all speeds.'}
   self.parameter_help.set(descriptions.get(ids[0],'Custom parameter: inspect where this name appears in your expressions.'))
 def lab_set_parameter(self):
  ids=self.lab_parameters.selection()
  if not ids:return
  k=ids[0];v=float(self.lab_pvalue.get());d=self.lab_get();d['parameters'][k]=v;difficulty.validate(d);self.lab_put(d);self.lab_parameters.item(k,values=(k,v));self.lab_plot();self.function_status.set('DRAFT — parameter changed; activate explicitly.')
 def lab_slide(self,value):
  if self.lab_parameters.selection():
   self.lab_pvalue.set(f'{float(value):.5g}');self.safe(self.lab_set_parameter)()
 def lab_transform(self):
  w=max(250,self.lab_canvas.winfo_width());h=max(180,self.lab_canvas.winfo_height());x=float(self.lab_xmax.get() or 4);y=float(self.lab_ymax.get())
  if x<=0 or y<=0:raise ValueError('Graph maxima must be positive')
  return w,h,x,y
 def lab_plot_quiet(self):
  try:self.lab_plot()
  except (ValueError,KeyError,json.JSONDecodeError):pass
 def lab_plot(self):
  d=self.lab_get()
  if d['format']!='arcaea-difficulty/2':return
  if d.get('normalize_response',False):self.lab_ymax.set('1')
  else:
   _,fn,_=model2.response_functions(d);self.lab_ymax.set(str(max([fn(k,(float(self.lab_xmax.get() or 4))*i/200) for k in ('tap','arc') for i in range(201)]+[1.])))
  w,h,xmax,ymax=self.lab_transform();c=self.lab_canvas;c.delete('all');c.create_line(42,15,42,h-30,w-12,h-30,fill='#77889f');c.create_text(48,12,anchor='nw',text=('Transfer' if self.lab_channel.get()=='tap' else 'Arc')+' · corrected speed → relative intensity',fill='white');c.create_text(w-20,h-12,text=f'{xmax:g}',fill='white');c.create_text(20,25,text=f'{ymax:g}',fill='white')
  c.create_text(48,h-12,anchor='w',text='Corrected units / second',fill='#9eb2c9')
  specs=copy.deepcopy(d['responses'])
  if self.lab_drag_points is not None:specs[self.lab_channel.get()]={'type':'points','points':self.lab_drag_points}
  mapped={**d,'responses':specs};raw,evaluate,scale=model2.response_functions(mapped)
  if self.lab_drag_normalizer is not None:scale=self.lab_drag_normalizer
  self.lab_curve_scale=scale
  for channel,color in [('tap','#69c9ff'),('arc','#ff9c6c')]:
   def fn(v):
    value=raw[channel](min(v,d['speed_limit']) if d.get('speed_limit') is not None else v)/scale
    return min(1.,value) if d.get('normalize_response',False) else value
   coords=[]
   for i in range(201):
    x=xmax*i/200;y=fn(x);coords.extend((42+x/xmax*(w-54),h-30-min(y,ymax)/ymax*(h-45)))
   c.create_line(*coords,fill=color,width=2 if channel==self.lab_channel.get() else 1)
  spec=specs[self.lab_channel.get()]
  if spec['type']=='points':
   for x,y in spec['points']:
    px=42+x/xmax*(w-54);py=h-30-(y/scale)/ymax*(h-45);
    if x>xmax or y/scale>ymax:continue
    c.create_oval(px-5,py-5,px+5,py+5,fill='#e7eff9')
 def lab_point_at(self,event):
  w,h,x,y=self.lab_transform();return [max(0,min(x,(event.x-42)/(w-54)*x)),max(0,min(y,(h-30-event.y)/(h-45)*y))*self.lab_curve_scale]
 def lab_drag_start(self,event):
  try:
   d=self.lab_get();spec=d['responses'][self.lab_channel.get()]
   if spec['type']!='points':return
   w,h,x,y=self.lab_transform();pts=spec['points'];i=min(range(len(pts)),key=lambda i:math.hypot(42+pts[i][0]/x*(w-54)-event.x,h-30-pts[i][1]/self.lab_curve_scale/y*(h-45)-event.y))
   if math.hypot(42+pts[i][0]/x*(w-54)-event.x,h-30-pts[i][1]/self.lab_curve_scale/y*(h-45)-event.y)<15 and i>0:self.lab_drag_index=i;self.lab_drag_points=copy.deepcopy(pts);self.lab_drag_normalizer=self.lab_curve_scale
  except Exception as e:self.function_status.set(str(e))
 def lab_drag(self,event):
  if self.lab_drag_index is None:return
  i=self.lab_drag_index;pts=self.lab_drag_points;p=self.lab_point_at(event);p[0]=max(pts[i-1][0]+1e-5,min(pts[i+1][0]-1e-5 if i+1<len(pts) else float('inf'),p[0]));pts[i]=p;self.lab_plot_quiet()
 def lab_drag_end(self):
  if self.lab_drag_points is None:return
  pts=self.lab_drag_points;self.lab_drag_points=None;self.lab_drag_index=None;self.lab_drag_normalizer=None;self.lab_edit(lambda d:d['responses'][self.lab_channel.get()].update(points=pts))
 def lab_add_point(self,event):
  if self.lab_mode.get()!='points':return
  p=self.lab_point_at(event)
  def edit(d):
   pts=d['responses'][self.lab_channel.get()]['points']
   if all(abs(a[0]-p[0])>1e-5 for a in pts):pts.append(p);pts.sort()
  self.lab_edit(edit)
 def lab_delete_point(self,event):
  if self.lab_mode.get()!='points':return
  p=self.lab_point_at(event)
  def edit(d):
   pts=d['responses'][self.lab_channel.get()]['points'];i=min(range(len(pts)),key=lambda i:abs(pts[i][0]-p[0]))
   if i>0 and len(pts)>2:pts.pop(i)
  self.lab_edit(edit)
 def lab_compare(self):
  if not self.chart or self.dirty:raise ValueError('Open and save a chart first')
  d=self.lab_get();c=self.chart;a=float(self.lab_from.get());b=float(self.lab_to.get())
  if b<=a:raise ValueError('Section end must exceed start')
  def run(log):
   active=self.store.trial(c,self.store.active_definition());trial=self.store.trial(c,d);self.events.put(('trial',(active,trial,a,b)));return 'Draft compared; active results unchanged.'
  self.task('Compare difficulty models',run)
 def lab_show_comparison(self,payload):
  active,trial,a,b=payload;win=tk.Toplevel(self.root);win.title('Active / draft comparison');win.geometry('950x700');text=self.text(win,10)
  self.put(text,{'active':active['metrics'],'draft':trial['metrics'],'section_ms':[a,b],'note':'Metrics above cover the full chart. Graph shows selected section. Nothing was activated or saved as a metric result.'})
  row=ttk.Frame(win);row.pack(fill='both',expand=True)
  values=[x.get('movement',x.get('displacement')) for r in (active,trial) for x in r['series'] if a<=x['time_ms']<=b and x['included']];values=[v for v in values if v is not None];limits=(min([0.]+values),max([1.]+values))
  for label,r in [('Active',active),('Draft',trial)]:
   f=ttk.Frame(row);f.pack(side='left',fill='both',expand=True);ttk.Label(f,text=label).pack();canvas=tk.Canvas(f,bg='#101b2b',width=430,height=280);canvas.pack(fill='both',expand=True);win.update_idletasks();self.draw_lines(canvas,[(x['time_ms']/1000,x.get('movement',x.get('displacement')) if x['included'] else None) for x in r['series'] if a<=x['time_ms']<=b],label+' movement',limits)
 def build_trajectory(self):
  p=self.pages['Trajectory'];bar=ttk.Frame(p);bar.pack(fill='x');self.button(bar,'Load current result',self.trajectory_load);self.button(bar,'Play / Pause',self.trajectory_toggle);self.button(bar,'Jump to operation',self.trajectory_jump)
  self.traj_status=tk.StringVar(value='Generate a v2 difficulty result to inspect its trajectory.');ttk.Label(p,textvariable=self.traj_status).pack(fill='x')
  row=ttk.Frame(p);row.pack(fill='x');self.traj_vars={}
  for label,value,width in [('x','frequency',22),('y','movement',22),('smoothing_ms','10',5),('trail_ms','1500',6),('x_max','',6),('y_max','',6)]:
   ttk.Label(row,text=label).pack(side='left');v=tk.StringVar(value=value);self.traj_vars[label]=v;ttk.Entry(row,textvariable=v,width=width).pack(side='left')
  self.button(row,'Apply view',self.trajectory_apply);ttk.Label(p,text='X uses frequency; Y uses movement. Blank maxima = automatic. View changes do not alter scores. Click the trail to seek.').pack(anchor='w')
  self.traj_canvas=tk.Canvas(p,bg='#101b2b',highlightthickness=0);self.traj_canvas.pack(fill='both',expand=True);self.traj_canvas.bind('<Configure>',lambda e:self.trajectory_draw());self.traj_canvas.bind('<Button-1>',self.safe_event(self.trajectory_seek_click))
  self.traj_time=tk.DoubleVar(value=0);self.traj_scale=ttk.Scale(p,from_=0,to=1,variable=self.traj_time,command=lambda _:self.trajectory_draw());self.traj_scale.pack(fill='x')
  self.traj_points=[];self.traj_playing=False;self.traj_result=None;self.traj_last=time.monotonic();self.root.after(33,self.trajectory_tick)
 def trajectory_load(self):
  self.traj_playing=False;self.traj_points=[];self.traj_result=None
  if not self.chart:self.trajectory_draw();return
  path=self.store.folder(self.chart)/'metrics.json'
  if not path.exists():self.traj_status.set('No result. Update difficulty first.');self.trajectory_draw();return
  r=read(path)
  if r.get('format')!='arcaea-metrics/2':self.traj_status.set('Legacy result: create/activate a v2 model and Update difficulty.');self.trajectory_draw();return
  self.traj_result=r;self.traj_stale=not self.store.fresh(self.chart,'difficulty');axes=r['definition']['axes']
  settings=self.store.root/'trajectory-view.json'
  if settings.exists():axes={**axes,**read(settings)}
  for k,v in self.traj_vars.items():v.set(str(axes.get(k,'')))
  self.trajectory_apply();self.traj_scale.configure(from_=self.traj_points[0][0],to=self.traj_points[-1][0]);self.traj_time.set(self.traj_points[0][0]);self.trajectory_draw()
 def trajectory_apply(self):
  if not self.traj_result:return
  axes={k:v.get() for k,v in self.traj_vars.items()}
  for k in ('smoothing_ms','trail_ms'):axes[k]=float(axes[k])
  for k in ('x_max','y_max'):
   if axes[k] and (not math.isfinite(float(axes[k])) or float(axes[k])<=0):raise ValueError('Axis maximum must be positive or blank')
  d=copy.deepcopy(self.traj_result['definition']);d['axes']=axes;model2.validate(d);points=model2.trajectory_points(self.traj_result,axes)
  valid=[p for p in points if p[1] is not None];self.traj_bounds=(min([p[1] for p in valid]+[0.]),max([p[1] for p in valid]+[1.]),min([p[2] for p in valid]+[0.]),max([p[2] for p in valid]+[1.]));self.traj_points=points;self.traj_times=[p[0] for p in points];self.traj_axes=axes;atomic(self.store.root/'trajectory-view.json',axes);self.trajectory_draw()
 def trajectory_draw(self):
  if not hasattr(self,'traj_canvas'):return
  c=self.traj_canvas;c.delete('all');self.traj_drawn=[]
  if not self.traj_points:return
  w=max(c.winfo_width(),400);h=max(c.winfo_height(),300);t=self.traj_time.get();axes=self.traj_axes
  xmin,auto_x,ymin,auto_y=self.traj_bounds;xmax=float(axes['x_max']) if axes.get('x_max') else auto_x;ymax=float(axes['y_max']) if axes.get('y_max') else auto_y
  def xy(p):return (55+(p[1]-xmin)/(xmax-xmin)*(w-80),h-45-(p[2]-ymin)/(ymax-ymin)*(h-85))
  c.create_line(55,25,55,h-45,w-20,h-45,fill='#8293a8');c.create_text(w/2,h-18,text='Input frequency · '+axes['x'],fill='white');c.create_text(60,15,text='Movement · '+axes['y'],anchor='w',fill='white');c.create_text(w-45,h-32,text=f'{xmax:.3g}',fill='#9eb2c9');c.create_text(25,45,text=f'{ymax:.3g}',fill='#9eb2c9')
  i=bisect.bisect_right(self.traj_times,t)-1;i=max(0,min(i,len(self.traj_points)-1));lo=bisect.bisect_left(self.traj_times,t-axes['trail_ms']);last=None
  for p in self.traj_points[lo:i+1]:
   if p[1] is None:last=None;continue
   pt=xy(p);alpha=max(.12,1-(t-p[0])/max(1,axes['trail_ms']));color='#%02x%02x%02x'%(int(16+80*alpha),int(27+170*alpha),int(43+200*alpha))
   if last:c.create_line(*last,*pt,fill=color,width=2)
   self.traj_drawn.append((pt[0],pt[1],p[0]));last=pt
  current=list(self.traj_points[i])
  if i+1<len(self.traj_points) and current[1] is not None and self.traj_points[i+1][1] is not None:
   q=self.traj_points[i+1];fraction=(t-current[0])/(q[0]-current[0]);current=[t,*[current[k]+fraction*(q[k]-current[k]) for k in (1,2)]]
  if current[1] is not None:
   x,y=xy(current);c.create_oval(x-6,y-6,x+6,y+6,fill='#fff2b3',outline='')
  stale=self.dirty or getattr(self,'traj_stale',False);self.traj_status.set(('STALE · ' if stale else '')+f'AFF {t/1000:.3f} s · '+('excluded / unresolved gap' if current[1] is None else f'X {current[1]:.3f}  Y {current[2]:.3f}'))
 def trajectory_toggle(self):
  if not self.traj_points:return
  self.traj_playing=not self.traj_playing;self.traj_last=time.monotonic()
  if self.traj_time.get()>=self.traj_times[-1]:self.traj_time.set(self.traj_times[0])
 def trajectory_tick(self):
  now=time.monotonic()
  if self.traj_playing and self.traj_points:
   t=min(self.traj_times[-1],self.traj_time.get()+(now-self.traj_last)*1000);self.traj_time.set(t);self.trajectory_draw()
   if t>=self.traj_times[-1]:self.traj_playing=False
  self.traj_last=now;self.root.after(33,self.trajectory_tick)
 def trajectory_seek_click(self,event):
  if self.traj_drawn:self.traj_time.set(min(self.traj_drawn,key=lambda p:(p[0]-event.x)**2+(p[1]-event.y)**2)[2]);self.trajectory_draw()
 def trajectory_jump(self):
  if not self.seq:return
  u=min(self.seq['units'],key=lambda u:abs(u['start_ms']-self.traj_time.get()));self.unit_filter.set('');self.populate_units();self.units.selection_set(u['unit_id']);self.units.see(u['unit_id']);self.pick_unit();self.tabs.select(self.pages['Sequence Editor'])
 def volume_view(self):
  self.require_idle()
  if not self.chart or self.dirty:raise ValueError('Open and save a sequence first')
  report=self.store.analysis(self.chart);win=tk.Toplevel(self.root);win.title('Invalid judgment volume');win.geometry('850x650');t=self.text(win);self.put(t,report)
  def export():
   path=filedialog.asksaveasfilename(initialfile=self.store.output_stem(self.chart)+'.invalid-volume.json',defaultextension='.json')
   if path:atomic(path,report['invalid_volume'])
  self.button(win,'Save separate JSON',export)
