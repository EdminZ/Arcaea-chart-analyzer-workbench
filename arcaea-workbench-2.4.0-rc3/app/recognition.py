"""Validated recognition settings for allocation and reference-timing arc paths."""
import copy,math,sys
from .common import ROOT
FORMAT='arcaea-recognition/1'
def validate(data):
 d=copy.deepcopy(data)
 if d.get('format')!=FORMAT:raise ValueError('Expected arcaea-recognition/1 profile')
 if d.get('coordinate_system')!='AFF':raise ValueError('Recognition tolerances must use original AFF coordinates')
 if d.get('feasibility_order')!='timing_then_space':raise ValueError('Expected timing_then_space feasibility order')
 for k in ('tolerance_x','tolerance_y'):
  v=d.get(k)
  if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=10:raise ValueError(k+' must be finite and within [0,10]')
 for k in ('judgment_time_tolerance_ms','max_contact_speed_aff_per_s'):
  v=d.get(k)
  if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0):raise ValueError(k+' must be null or positive')
 prefs=d.get('allocator_preferences',{})
 if not isinstance(prefs,dict):raise ValueError('allocator_preferences must be an object')
 sys.path.insert(0,str(ROOT/'core/engine'))
 from preferences import Preferences
 try:Preferences(**prefs)
 except TypeError as e:raise ValueError('Unknown allocator preference: '+str(e))
 for k in ('arc_path_enabled','endpoint_relaxation'):
  d.setdefault(k,True)
  if not isinstance(d[k],bool):raise ValueError(k+' must be boolean')
 d.setdefault('endpoint_sample_ms',4)
 v=d['endpoint_sample_ms']
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 1<=v<=20:raise ValueError('endpoint_sample_ms must be within [1,20]')
 return d
