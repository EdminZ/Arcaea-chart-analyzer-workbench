import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app import model2,signals,sequence
from app.common import ROOT,read,atomic
from app.store import Store
from test_application import AFF

def definition():
 d=read(ROOT/'tests/fixtures/legacy-v2.2-definition.json');d['responses']={'tap':{'type':'expression','expression':'v'},'arc':{'type':'expression','expression':'v'}};return d

def unit(t,end=None,x=0,x2=None,kind='contact',hand='L',fresh=True):
 u=sequence.new_unit(t);u.update(end_ms=t if end is None else end,start_position=[x,0],end_position=[x if x2 is None else x2,0],kind=kind,hand=hand,fresh_press=fresh);return u

def seq(units):return {'format':sequence.FORMAT,'sha256':'0'*64,'units':units,'arc_geometry':[],'flow_context':{'resets':[]},'exclusions':[],'multitouch':{'episodes':[]}}
class Signals(unittest.TestCase):
 def test_frequency_simultaneous_and_silent_mode(self):
  f=signals.frequency([0,0,2000],500,0,2500);s=signals.active_stats(f);self.assertEqual(s['mean'],1.5);self.assertEqual(s['mode'],2);self.assertEqual(s['active_s'],1)
 def test_peak_rejects_short_overlap(self):
  p=signals.peak([[0,100,4],[100,110,5],[110,200,4]],20,.9);self.assertEqual(p['height'],4);self.assertEqual(p['raw_max'],5);self.assertEqual(p['near_peak_duration_s'],.2)
 def test_peak_never_bridges_excluded_gap(self):
  p=signals.peak([[0,10,10],[10,20,None],[20,30,10]],20);self.assertEqual(p['height'],0)
 def test_arc_path_length_not_endpoint(self):
  u=unit(0,1000,0,0,'arc');u['waypoints']=[[500,1,0]];u['geometry_mode']='polyline';f=signals.extract(seq([u]));self.assertEqual(f['arcs'][0]['length'],2)
 def test_signal_integral(self):
  s=signals.Signal([[0,100,2],[100,200,4]]);self.assertAlmostEqual(s.integral(200),.6);self.assertAlmostEqual(s.window(150,100),.3)
class Engine(unittest.TestCase):
 def test_distance_conserved_and_arc_stationary_zero(self):
  s=seq([unit(0,1000,0,1,'arc'),unit(1500,2000,1,1,'arc')]);r=model2.calculate(s,{},definition());self.assertAlmostEqual(r['metrics']['distance'],1);self.assertAlmostEqual(r['metrics']['Arc'],1)
 def test_separate_hands_before_nonlinearity(self):
  d=definition();d['responses']['tap']['expression']='v**2';s=seq([unit(0,x=0),unit(0,x=0,hand='R'),unit(1000,x=1),unit(1000,x=1,hand='R')]);r=model2.calculate(s,{},d);self.assertAlmostEqual(r['metrics']['distance'],2)
 def test_arc_steeper_than_transfer(self):
  d=definition();d['responses']['arc']['expression']='3*v';s=seq([unit(0),unit(1000,x=1),unit(2000,3000,1,2,'arc')]);r=model2.calculate(s,{},d);self.assertAlmostEqual(r['summary']['tap_weight'],1);self.assertAlmostEqual(r['metrics']['Arc'],3)
 def test_same_speed_subdivision_invariant(self):
  d=definition();d['responses']['arc']['expression']='v**2';s=seq([unit(0,1000,0,2,'arc')]);a=model2.calculate(s,{},d);s2=sequence.split(s,s['units'][0]['unit_id'],300);b=model2.calculate(s2,{},d);self.assertAlmostEqual(a['metrics']['Arc'],b['metrics']['Arc'])
 def test_silence_excluded_and_full_tail(self):
  s=seq([unit(0),unit(2000,hand='R')]);r=model2.calculate(s,{},definition());self.assertEqual(r['summary']['frequency_mean'],1);self.assertEqual(r['summary']['frequency_active_s'],1);self.assertEqual(r['summary']['duration_s'],2.5)
 def test_press_counts_not_ticks_waypoints_or_hold_duration(self):
  s=seq([unit(0,1000,kind='hold'),unit(1200,kind='waypoint',fresh=False)]);s['units'][1]['role']='waypoint';r=model2.calculate(s,{},definition());self.assertEqual(r['summary']['press_count'],1)
 def test_conflicts_block_unless_explicitly_excluded(self):
  s=seq([unit(0,1000),unit(500)])
  with self.assertRaises(ValueError):model2.calculate(s,{},definition())
  s['exclusions']=[{'start_ms':0,'end_ms':1000,'status':'confirmed'}];r=model2.calculate(s,{},definition());self.assertEqual(r['summary']['press_count'],0)
 def test_curve_validation_and_interpolation(self):
  d=definition();d['responses']['tap']={'type':'points','points':[[0,0],[2,4],[4,10]]};model2.validate(d);f=model2.response(d['responses']['tap'],{});self.assertEqual(f(3),7);self.assertEqual(f(100),10)
  d['responses']['tap']['points']=[[0,1],[2,4]]
  with self.assertRaises(ValueError):model2.validate(d)
 def test_invalid_mapping_and_axis_semantics(self):
  for exp in ('1','-v','1/0',"__import__('os')"):
   d=definition();d['responses']['tap']['expression']=exp
   with self.assertRaises((ValueError,SyntaxError)):model2.validate(d)
  d=definition();d['axes']['x']='movement'
  with self.assertRaises(ValueError):model2.validate(d)
 def test_smoothing_display_only_and_gap_preservation(self):
  r=model2.calculate(seq([unit(0),unit(250,hand='R')]),{},definition());before=copy.deepcopy(r);axes={**r['definition']['axes'],'smoothing_ms':10};p=model2.trajectory_points(r,axes);q=model2.trajectory_points(r,{**axes,'smoothing_ms':0});self.assertNotEqual(p,q);self.assertEqual(r,before)
  r['series'][2]['included']=False;self.assertIsNone(model2.trajectory_points(r,axes)[2][1])
 def test_single_input_supported(self):
  r=model2.calculate(seq([unit(0)]),{},definition());self.assertEqual(r['metrics']['note'],1)
class Volume(unittest.TestCase):
 def facts(self):return {'traits':[{'source_event_id':1,'kind':'hold','nominal_tick_counts':{'tight':12,'loose':13}},{'source_event_id':2,'kind':'arc','nominal_tick_counts':{'tight':8,'loose':10}}]}
 def test_hold_and_low_arc_removed_volume(self):
  u=unit(0,1000,0,.1,'arc');u['source_event_ids']=[2];f=signals.extract(seq([u]));r=signals.volume_report(f,self.facts());self.assertEqual(r['invalid_volume'],18);self.assertEqual(r['effective_count'],2)
 def test_split_shared_sources_not_double_counted(self):
  u=unit(0,1000,0,.1,'arc');u['source_event_ids']=[2];s=seq([u]);s2=sequence.split(s,u['unit_id'],500);r=signals.volume_report(signals.extract(s2),self.facts());self.assertEqual(r['invalid_volume'],18)
 def test_out_and_back_not_low_movement(self):
  u=unit(0,1000,0,0,'arc');u['source_event_ids']=[2];u['waypoints']=[[500,1,0]];r=signals.volume_report(signals.extract(seq([u])),self.facts());self.assertEqual(r['invalid_volume'],11)
 def test_zero_judgment_does_not_create_activation(self):
  facts=self.facts();facts['traits'][0]['nominal_tick_counts']['tight']=0;r=signals.volume_report(signals.extract(seq([unit(0)])),facts);self.assertEqual(r['effective_count'],0);self.assertEqual(r['invalid_volume'],0)
 def test_unknown_counts_remain_unknown(self):
  facts=self.facts();facts['traits'][0]['nominal_tick_counts']['tight']=None;r=signals.volume_report(signals.extract(seq([unit(0)])),facts);self.assertFalse(r['complete']);self.assertIsNone(r['records'][0]['effective_count'])
class Persistence2(unittest.TestCase):
 def test_cache_reused_for_formula_change_and_invalidated_for_edit(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);src=root/'songs';src.mkdir();(src/'a.aff').write_text(AFF);st=Store(root/'workspace');c=st.scan(src)['imported'][0];s=seq([unit(0),unit(1000,x=1)]);s['sha256']=c;st.save_sequence(c,s);st.calculate(c);key=read(st.folder(c)/'operation-features.json')['key'];d=st.active_definition();d['parameters']['tap_scale']=2;st.activate_definition(d)
   with patch('app.signals.extract',side_effect=AssertionError('cache not reused')):st.calculate(c)
   s,_,token=st.load(c);s['units'][1]['start_position'][0]=.5;s['units'][1]['end_position'][0]=.5;st.save_sequence(c,s,token);st.calculate(c);self.assertNotEqual(key,read(st.folder(c)/'operation-features.json')['key']);dest=root/'out';st.export([c],dest);self.assertTrue((dest/'a.invalid-volume.json').exists())
 def test_legacy_model_preserved_on_reopen(self):
  with tempfile.TemporaryDirectory() as t:
   st=Store(t);d=read(ROOT/'defaults/legacy-difficulty.json');st.activate_definition(d);self.assertEqual(Store(t).active_definition(),d)
if __name__=='__main__':unittest.main()
