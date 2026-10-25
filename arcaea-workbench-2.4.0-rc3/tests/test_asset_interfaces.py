import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from app import arc_paths,recognition,adapters
from app.common import ROOT,read,atomic,digest
from test_model2 import seq,unit
class PathAssets(unittest.TestCase):
 def setUp(self):
  u=unit(0,1000,0,1,'arc',fresh=False);u['start_position'][1]=1/8.5;u['end_position'][1]=5.5/8.5;self.s=seq([u]);self.uid=u['unit_id'];self.data=arc_paths.from_sequence(self.s)
 def test_aff_coordinate_roundtrip(self):
  p=self.data['paths'][0];self.assertAlmostEqual(p['points'][0][2],0);self.assertAlmostEqual(p['points'][-1][2],1);p['review_status']='manually_reviewed';out=arc_paths.apply(self.s,self.data,self.uid);self.assertEqual(out['units'][0]['geometry_mode'],'polyline');self.assertAlmostEqual(out['units'][0]['end_position'][1],5.5/8.5)
 def test_wrong_chart_stale_sequence_unreviewed(self):
  with self.assertRaises(ValueError):arc_paths.validate(self.data,'1'*64)
  with self.assertRaises(ValueError):arc_paths.apply(self.s,self.data,self.uid)
  self.data['paths'][0]['review_status']='manually_reviewed';s=copy.deepcopy(self.s);s['review_notes']='new'
  with self.assertRaises(ValueError):arc_paths.apply(s,self.data,self.uid)
 def test_timing_and_finite_validation(self):
  for value in (float('nan'),float('inf')):
   d=copy.deepcopy(self.data);d['paths'][0]['points'][0][1]=value
   with self.assertRaises(ValueError):arc_paths.validate(d)
  d=copy.deepcopy(self.data);d['paths'][0]['points'][-1][0]=1001
  with self.assertRaises(ValueError):arc_paths.validate(d)
 def test_reviewed_zero_time_jump_rejected(self):
  d=copy.deepcopy(self.data);p=d['paths'][0];p['points'].insert(1,[0,1,0]);arc_paths.validate(d);p['review_status']='manually_reviewed'
  with self.assertRaises(ValueError):arc_paths.validate(d)
 def test_explicit_attached_input_start_protected(self):
  s=copy.deepcopy(self.s);s['units'][0]['fresh_press']=True;d=arc_paths.from_sequence(s);p=d['paths'][0];p['review_status']='manually_reviewed';p['points'][0][1]=.1
  with self.assertRaises(ValueError):arc_paths.apply(s,d,self.uid)
 def test_sparse_path_preserves_sources_and_hand(self):
  p=self.data['paths'][0];p['points']=[[0,0,0],[500,.2,.5],[1000,1,1]];p['review_status']='manually_reviewed';out=arc_paths.apply(self.s,self.data,self.uid);self.assertEqual(out['units'][0]['hand'],'L');self.assertEqual(out['units'][0]['source_event_ids'],[]);self.assertEqual(len(out['units'][0]['waypoints']),1)
class RecognitionProfile(unittest.TestCase):
 def test_reference_tolerances_and_unknown_fields(self):
  d=recognition.validate(read(ROOT/'defaults/recognition.json'));self.assertEqual(d['tolerance_x'],.1);self.assertEqual(d['tolerance_y'],.25);self.assertIsNone(d['judgment_time_tolerance_ms'])
  d['allocator_preferences']={'does_not_exist':1}
  with self.assertRaises(ValueError):recognition.validate(d)
 def test_bad_spatial_and_timing_values(self):
  for key,value in [('coordinate_system','plane'),('tolerance_x',-1),('tolerance_y',float('nan')),('judgment_time_tolerance_ms',0)]:
   d=read(ROOT/'defaults/recognition.json');d[key]=value
   with self.assertRaises(ValueError):recognition.validate(d)
 def test_preferences_forwarded_and_profile_snapshotted(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);d=read(ROOT/'defaults/recognition.json');d['allocator_preferences']={'alternate_weight':15};atomic(root/'profile.json',d);settings={'allocation_script':'core/analyze_aff.py','beam_width':128,'recognition_profile':str(root/'profile.json')}
   with patch('app.adapters.invoke',return_value='ok') as call:adapters.allocate(root/'source.aff',root/'run/output.json',settings)
   args=call.call_args.args[0];self.assertIn('--preferences',args);self.assertEqual(read(root/'run/allocator-preferences.json'),{'alternate_weight':15});self.assertEqual(read(root/'run/recognition-profile.json'),d)
 def test_default_profile_does_not_pass_unimplemented_solver_flags(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);settings={'allocation_script':'core/analyze_aff.py','recognition_profile':str(ROOT/'defaults/recognition.json')}
   with patch('app.adapters.invoke',return_value='ok') as call:adapters.allocate(root/'source.aff',root/'out.json',settings)
   self.assertNotIn('--preferences',call.call_args.args[0]);self.assertNotIn('--tolerance-x',call.call_args.args[0])
if __name__=='__main__':unittest.main()
