import copy,csv,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from app import model2,signals,sequence
from app.store import Store
from app.common import ROOT,read,atomic
from test_model2 import seq,unit,definition
from test_application import AFF

def configured():return read(ROOT/'defaults/difficulty-v2.json')
def arc(dx=0,dy=1,duration=1000):
 u=unit(0,duration,0,dx,'arc');u['end_position'][1]=dy;return u
class Geometry(unittest.TestCase):
 def test_vertical_scale_does_not_change_horizontal_or_frequency(self):
  d=definition();d['vertical_scale']=.5
  for dx,dy,expected in [(1,0,1),(0,1,.5),(1,1,math.sqrt(1.25))]:
   s=seq([arc(dx,dy)]);old=copy.deepcopy(s);r=model2.calculate(s,{},d);self.assertAlmostEqual(r['summary']['total_distance'],expected);self.assertEqual(r['summary']['press_count'],1);self.assertEqual(s,old)
 def test_factor_endpoints_and_transfer_consistency(self):
  for factor,expected in [(0,0),(1,1),(.5,.5)]:
   d=definition();d['vertical_scale']=factor;b=unit(1000);b['start_position']=[0,1];b['end_position']=[0,1]
   transfer=model2.calculate(seq([unit(0),b]),{},d);sustained=model2.calculate(seq([arc()]),{},d);self.assertAlmostEqual(transfer['metrics']['distance'],expected);self.assertAlmostEqual(sustained['metrics']['Arc'],expected)
 def test_arc_volume_uses_same_corrected_path(self):
  a=arc(0,.4);a['source_event_ids']=[1];f=signals.extract(seq([a]));facts={'traits':[{'kind':'arc','source_event_id':1,'nominal_tick_counts':{'tight':10}}]}
  self.assertEqual(signals.volume_report(f,facts,vertical_scale=1)['invalid_volume'],0);r=signals.volume_report(f,facts,vertical_scale=.5);self.assertEqual(r['invalid_volume'],9);self.assertAlmostEqual(r['records'][0]['cumulative_distance'],.2)
 def test_old_definition_defaults_unchanged(self):
  d=definition();old=copy.deepcopy(d);self.assertEqual(model2.validate(d),old);r=model2.calculate(seq([arc()]),{},d);self.assertEqual(r['metrics']['Arc'],1);self.assertFalse(r['movement_mapping']['normalized']);self.assertIsNone(r['movement_mapping']['speed_limit'])
class Mapping(unittest.TestCase):
 def test_cap_logs_raw_and_used_speed(self):
  d=definition();d['speed_limit']=4;s=seq([unit(0),unit(100,x=1)]);r=model2.calculate(s,{},d);self.assertAlmostEqual(r['metrics']['distance'],.4);w=r['movement_warnings'][0];self.assertEqual(w['raw_speed'],10);self.assertEqual(w['used_speed'],4);self.assertEqual(w['start_ms'],0);self.assertEqual(w['end_ms'],100);self.assertEqual(r['summary']['total_distance'],1)
 def test_no_warning_at_exact_limit(self):
  d=definition();d['speed_limit']=4;r=model2.calculate(seq([unit(0),unit(250,x=1)]),{},d);self.assertEqual(r['movement_warnings'],[])
 def test_shared_normalization_preserves_ratio(self):
  d=configured();raw,fn,scale=model2.response_functions(d)
  self.assertAlmostEqual(fn('arc',4),1)
  for v in (.1,1,2,4):
   self.assertLessEqual(fn('tap',v),1);self.assertLessEqual(fn('arc',v),1);self.assertAlmostEqual(fn('arc',v)/fn('tap',v),raw['arc'](v)/raw['tap'](v))
  self.assertEqual(fn('arc',100),fn('arc',4))
 def test_chart_independent_and_common_rescaling_invariant(self):
  d=configured();s=seq([arc(1,0)]);r=model2.calculate(s,{},d);d['parameters']['tap_scale']*=2;d['parameters']['arc_scale']*=2;r2=model2.calculate(s,{},d);self.assertAlmostEqual(r['metrics']['Arc'],r2['metrics']['Arc']);r3=model2.calculate(seq([arc(3,0)]),{},d);self.assertEqual(r2['movement_mapping']['shared_normalizer'],r3['movement_mapping']['shared_normalizer'])
 def test_narrow_expression_peak_clips_and_warns(self):
  d=configured();d['responses']['tap']={'type':'expression','expression':'100 if abs(v-1.234567) < 0.000001 else v'}
  r=model2.calculate(seq([unit(0),unit(1000,x=1.234567)]),{},d);self.assertEqual(r['summary']['response_clipped_intervals'],1);self.assertAlmostEqual(r['metrics']['distance'],1)
 def test_point_peak_exact_even_between_grid_samples(self):
  d=configured();d['responses']['arc']={'type':'points','points':[[0,0],[1.234567,100],[4,1]]};_,fn,scale=model2.response_functions(d);self.assertEqual(scale,100);self.assertEqual(fn('arc',1.234567),1)
 def test_stationary_zero_and_validation(self):
  d=configured();d['responses']={k:{'type':'expression','expression':'0'} for k in ('tap','arc')};r=model2.calculate(seq([arc(0,0)]),{},d);self.assertEqual(r['metrics']['Arc'],0)
  for key,value in [('vertical_scale',-1),('vertical_scale',1.01),('speed_limit',0),('speed_limit',float('inf')),('speed_limit',None),('normalize_response','true')]:
   d=configured();d[key]=value
   with self.assertRaises(ValueError):model2.validate(d)
class Persistence(unittest.TestCase):
 def test_factor_change_reuses_geometry_and_exports_warnings(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);src=root/'songs';src.mkdir();(src/'x.aff').write_text(AFF);st=Store(root/'workspace');cid=st.scan(src)['imported'][0];s=seq([unit(0),unit(100,x=1)]);s['sha256']=cid;st.save_sequence(cid,s);st.calculate(cid);self.assertEqual(len(read(st.folder(cid)/'movement-warnings.json')['warnings']),1)
   d=st.active_definition();d['vertical_scale']=.25;st.activate_definition(d)
   with patch('app.signals.extract',side_effect=AssertionError('unnecessary geometry recomputation')):st.calculate(cid)
   st.export([cid],root/'out');r=list(csv.DictReader((root/'out/summary.csv').read_text(encoding='utf-8-sig').splitlines()))[0];self.assertEqual(r['speed_capped_intervals'],'1');self.assertTrue((root/'out/x.movement-warnings.json').exists())
   d['speed_limit']=20;st.activate_definition(d);st.calculate(cid);self.assertEqual(read(st.folder(cid)/'movement-warnings.json')['warnings'],[])
 def test_movement_defaults_preserve_custom_expression(self):
  from app.lab_ui import LabUI
  w=LabUI();d=definition();d['responses']['tap']['expression']='v**2';w.lab_edit=lambda fn:fn(d);w.lab_refresh=Mock();w.lab_movement_defaults();self.assertEqual(d['responses']['tap']['expression'],'v**2');self.assertEqual(d['vertical_scale'],.5);self.assertTrue(d['normalize_response']);self.assertEqual(d['speed_limit'],4)
 def test_normalized_curve_coordinate_conversion(self):
  from app.lab_ui import LabUI
  w=LabUI();w.lab_transform=lambda:(454,245,4,1);w.lab_curve_scale=10;event=Mock(x=242,y=115);x,y=w.lab_point_at(event);self.assertAlmostEqual(x,2);self.assertAlmostEqual(y,5)
if __name__=='__main__':unittest.main()
