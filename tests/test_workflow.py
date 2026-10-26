import copy,csv,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from test_application import AFF,simple
from app import metadata
from app.common import atomic,read,digest_bytes
from app.store import Store
DATA={'songs':[{'id':'demo','title_localized':{'en':'Demo Song'},'difficulties':[{'ratingClass':2,'rating':9,'ratingPlus':True},{'ratingClass':3,'rating':10}]}]}
class Workflow(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.song=self.root/'songs/dl_demo';self.song.mkdir(parents=True);self.aff=self.song/'demo_2.aff';self.aff.write_text(AFF);self.store=Store(self.root/'workspace');atomic(self.root/'songlist',DATA);self.store.import_songlist(self.root/'songlist');self.c=self.store.scan(self.root/'songs')['imported'][0]
 def seed(self):
  s=simple();s['sha256']=self.c;self.store.save_sequence(self.c,s);return self.store.load(self.c)
 def test_ratings_constants_and_filters(self):
  r=self.store.catalog()[0];self.assertEqual(r['title'],'Demo Song');self.assertEqual(r['metadata']['display_rating'],'9+');self.assertIsNone(r['metadata']['chart_constant']);self.assertTrue(metadata.visible(r,{2,3}));self.assertFalse(metadata.visible(r,{3}));self.assertEqual(metadata.identify(self.song/'3.aff'),('demo',3))
 def test_named_working_file_and_skip_generated(self):
  self.seed();p=self.store.sequence_path(self.c);self.assertEqual(p,self.song/'_analysis/demo_2.sequence.json');(p.parent/'preview.aff').write_text(AFF.replace('(0,1)','(0,2)'));report=self.store.scan(self.root/'songs');self.assertEqual(len(self.store.catalog()),1);self.assertEqual(report['imported'],[])
 def test_legacy_migration_keeps_bytes_and_revision(self):
  s=simple();s['sha256']=self.c;p=self.store.folder(self.c);atomic(p/'working.sequence.json',s);atomic(p/'head.json',{'revision':'old','sequence_hash':'old'});loaded,head,_=self.store.load(self.c);self.assertEqual(head['revision'],'old');self.assertEqual(self.store.sequence_path(self.c).read_bytes(),(p/'working.sequence.json').read_bytes());self.assertEqual(loaded,s)
 def test_destination_collision_preserves_existing(self):
  p=self.song/'_analysis/demo_2.sequence.json';atomic(p,{'sha256':'other'});before=p.read_bytes()
  with self.assertRaises(ValueError):self.seed()
  self.assertEqual(p.read_bytes(),before)
 def test_metadata_reload_preserves_sequence_and_manual_label(self):
  self.seed();before=self.store.load(self.c);self.store.label(self.c,'My title','Custom');self.store.import_songlist(self.root/'songlist');self.assertEqual(self.store.load(self.c),before);self.assertEqual(self.store.catalog()[0]['title'],'My title')
 def test_reject_invalid_metadata_before_replacement(self):
  prior=(self.store.root/'songlist.json').read_bytes();atomic(self.root/'bad',{'songs':[DATA['songs'][0],DATA['songs'][0]]})
  with self.assertRaises(ValueError):self.store.import_songlist(self.root/'bad')
  self.assertEqual((self.store.root/'songlist.json').read_bytes(),prior)
 def test_export_named_sequence_and_rating_columns(self):
  self.seed();dest=self.root/'export';self.store.export([self.c],dest);self.assertTrue((dest/'demo_2.sequence.json').exists());r=list(csv.DictReader((dest/'summary.csv').read_text(encoding='utf-8-sig').splitlines()))[0];self.assertEqual(r['display_rating'],'9+');self.assertEqual(r['rating_class'],'2');self.assertEqual(r['chart_constant'],'')
 def test_external_edit_named_file_retains_conflict_guard(self):
  s,h,token=self.seed();s['review_notes']='external';atomic(self.store.sequence_path(self.c),s)
  with self.assertRaises(ValueError):self.store.save_sequence(self.c,s,token)
  self.store.adopt_external(self.c,digest_bytes(self.store.sequence_path(self.c).read_bytes()));self.assertEqual(self.store.load(self.c)[0]['review_notes'],'external')
class BundledExample(unittest.TestCase):
 def test_synthetic_demo_hand_edit_roundtrip(self):
  from app.common import ROOT
  with tempfile.TemporaryDirectory() as t:
   store=Store(t);c=store.scan(ROOT/'examples')['imported'][0];store.import_sequence(c,ROOT/'examples/workbench-demo_2.sequence.json');s,_,token=store.load(c);old=s['units'][0]['hand'];s['units'][0]['hand']='R' if old=='L' else 'L';store.save_sequence(c,s,token);self.assertEqual(store.load(c)[0]['units'][0]['hand'],s['units'][0]['hand'])
class Controls(unittest.TestCase):
 def window(self):
  from app.gui import Window
  w=Window.__new__(Window);w.seq=simple();w.property_uid='0';w.require_idle=Mock();w.pick_unit=Mock();w.props={'hand':Mock()};w.props['hand'].get.return_value='R';w.change=Mock(side_effect=lambda s:setattr(w,'seq',s));return w
 def test_dropdown_commits_once_without_apply(self):
  w=self.window();w.commit_property('hand');self.assertEqual(w.seq['units'][0]['hand'],'R');w.commit_property('hand');self.assertEqual(w.change.call_count,1)
 def test_role_waypoint_clears_press(self):
  w=self.window();w.props['role']=Mock();w.props['role'].get.return_value='waypoint';w.commit_property('role');self.assertFalse(w.seq['units'][0]['fresh_press'])
 def test_geometry_edit_retains_aff_reference(self):
  w=self.window();w.seq['units'][0]['geometry_mode']='source';w.props['start_x']=Mock();w.props['start_x'].get.return_value='0.2';w.commit_property('start_x');self.assertEqual(w.seq['units'][0]['geometry_mode'],'polyline');self.assertEqual(w.seq['units'][0]['start_position'][0],.2)
if __name__=='__main__':unittest.main()
