import copy,csv,io,json,math,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.common import read,atomic,digest,digest_bytes
from app import sequence,difficulty,adapters
from app.store import Store
from app.locking import WorkspaceLock
AFF='AudioOffset:0\n-\ntiming(0,120,4);\n(0,1);\n(250,4);\nhold(500,750,1);\n(1000,4);\n'
def simple():
 units=[]
 for i,(t,x,h) in enumerate([(0,0,'L'),(100,1,'R'),(200,.5,'L'),(400,1,'R')]):
  u=sequence.new_unit(t);u.update(unit_id=str(i),hand=h,start_position=[x,0],end_position=[x,0]);units.append(u)
 return {'format':sequence.FORMAT,'sha256':'0'*64,'units':units,'arc_geometry':[],'exclusions':[],'flow_context':{'resets':[]},'multitouch':{'episodes':[]}}
class Definitions(unittest.TestCase):
 def test_piecewise(self):
  e=difficulty.Expression('x if x < 3 else sqrt(x-3)',{'x'});self.assertEqual(e({'x':2}),2);self.assertEqual(e({'x':7}),2)
 def test_reject_execution(self):
  for e in ["__import__('os')",'x.__class__','[x for x in [1]]','open(1)','(lambda:1)()']:
   with self.assertRaises((ValueError,SyntaxError)):difficulty.Expression(e,{'x'})
 def test_power_and_domain_bounds(self):
  with self.assertRaises(ValueError):difficulty.Expression('2**100',set())({})
  with self.assertRaises(ValueError):difficulty.Expression('sqrt(-1)',set())({})
 def test_invalid_definition_preserves_active(self):
  with tempfile.TemporaryDirectory() as t:
   s=Store(t);old=s.active_definition();d=copy.deepcopy(old);d['responses']['tap']['expression']='1/0'
   with self.assertRaises(ValueError):s.activate_definition(d)
   self.assertEqual(s.active_definition(),old)
 def test_versions_and_parameters(self):
  with tempfile.TemporaryDirectory() as t:
   s=Store(t);d=s.active_definition();a=digest(d);d['parameters']['speed_scale']=2;h=s.activate_definition(d)
   self.assertNotEqual(a,h);self.assertTrue((Path(t)/'definitions/versions'/(a+'.json')).exists())
 def test_feature_results_and_scaling(self):
  d=read(ROOT/'defaults/legacy-difficulty.json');s=simple();r=difficulty.calculate(s,{},d);self.assertAlmostEqual(r['summary']['total_distance'],.5)
  d['parameters']['speed_scale']=2;r2=difficulty.calculate(s,{},d);self.assertAlmostEqual(r2['metrics']['distance'],r['metrics']['distance']*2)
 def test_waypoints_not_presses(self):
  s=simple();s['units'][0].update(role='waypoint',fresh_press=False);r=difficulty.calculate(s,{},read(ROOT/'defaults/legacy-difficulty.json'));self.assertEqual(r['summary']['press_count'],3)
 def test_reset_transfer_not_scored(self):
  s=simple();s['flow_context']['resets']=[{'start_ms':0,'end_ms':200}];r=difficulty.calculate(s,{},read(ROOT/'defaults/legacy-difficulty.json'));self.assertEqual(r['summary']['total_distance'],0)
 def test_conflict_blocks_metrics(self):
  s=simple();s['units'][0]['end_ms']=300
  with self.assertRaises(ValueError):difficulty.calculate(s,{},read(ROOT/'defaults/legacy-difficulty.json'))
class Editing(unittest.TestCase):
 def test_split_merge(self):
  s=simple();s['units']=s['units'][:1];u=s['units'][0];u.update(end_ms=500,end_position=[1,0]);s=sequence.split(s,'0',250);self.assertEqual(len(s['units']),2);self.assertFalse(s['units'][1]['fresh_press']);s=sequence.merge(s,[u['unit_id'] for u in s['units']]);self.assertEqual(len(s['units']),1);self.assertEqual(s['units'][0]['end_ms'],500)
 def test_no_lossy_press_merge(self):
  s=simple();s['units'][1]['hand']='L'
  with self.assertRaises(ValueError):sequence.merge(s,['0','1'])
 def test_duplicate_ids_and_nonfinite(self):
  s=simple();s['units'].append(s['units'][0])
  with self.assertRaises(ValueError):sequence.validate(s)
  s=simple();s['units'][0]['start_ms']=float('nan')
  with self.assertRaises(ValueError):sequence.validate(s)
 def test_exclusion_conflict_is_explicit(self):
  s=simple();s['units'][0]['end_ms']=300;s['exclusions']=[{'start_ms':0,'end_ms':300,'status':'confirmed'}];self.assertFalse(any(d['level']=='error' for d in sequence.diagnostics(s)))
 def test_curve_not_replaced_by_chord(self):
  s=simple();u=s['units'][0];u.update(kind='arc',geometry_mode='source',source_event_ids=[7],end_ms=1000,end_position=[1,1]);s['arc_geometry']=[{'id':7,'start_ms':0,'end_ms':1000,'geometry':{'x0':0,'x1':1,'y0':0,'y1':1,'curve':'si'}}];self.assertGreater(sequence.at(u,s,500)[0],.5)
class Persistence(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.src=self.base/'songs';self.src.mkdir();(self.src/'extensionless').write_text(AFF);self.s=Store(self.base/'workspace');self.c=self.s.scan(self.src)['imported'][0]
 def seed(self):
  s=simple();s['sha256']=self.c;self.s.save_sequence(self.c,s);return self.s.load(self.c)
 def test_extensionless_dedup_binary(self):
  (self.src/'same.aff').write_text(AFF);(self.src/'audio').write_bytes(b'\xff\x00binary');r=self.s.scan(self.src);self.assertEqual(len(self.s.catalog()),1);self.assertGreater(r['skipped'],0)
 def test_external_conflict_and_adoption(self):
  s,h,token=self.seed();s['review_notes']='external';atomic(self.s.sequence_path(self.c),s)
  with self.assertRaises(ValueError):self.s.save_sequence(self.c,s,token)
  self.s.adopt_external(self.c,digest_bytes((self.s.sequence_path(self.c)).read_bytes()));self.assertEqual(self.s.load(self.c)[0]['review_notes'],'external')
 def test_metrics_stale_after_edit(self):
  s,h,token=self.seed();self.s.calculate(self.c);self.assertTrue(self.s.fresh(self.c,'difficulty'));s['review_notes']='changed';self.s.save_sequence(self.c,s,token);self.assertFalse(self.s.fresh(self.c,'difficulty'))
 def test_export_blank_stale_and_csv_escaping(self):
  s,h,token=self.seed();self.s.calculate(self.c);self.s.label(self.c,'=1+1','FTR');s['review_notes']='changed';self.s.save_sequence(self.c,s,token);dest=self.base/'export';self.s.export([self.c],dest);raw=(dest/'summary.csv').read_bytes();self.assertTrue(raw.startswith(b'\xef\xbb\xbf'));row=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))[0];self.assertEqual(row['status'],'stale');self.assertEqual(row['title'],"'=1+1");self.assertFalse(row.get('distance'))
 def test_generate_end_to_end_and_resume(self):
  before=self.s.source(self.c).read_bytes();self.s.generate(self.c);self.assertTrue((self.s.folder(self.c)/'baseline.json').exists());self.assertTrue(self.s.fresh(self.c,'preview'));head=self.s.load(self.c)[1];self.s.generate(self.c);self.assertEqual(self.s.load(self.c)[1],head);self.assertEqual(self.s.source(self.c).read_bytes(),before)
 def test_overlay_structural_input_is_noinput(self):
  self.s.generate(self.c);s,h,token=self.s.load(self.c);u=sequence.new_unit(1200);u['hand']='L';s['units'].append(u);self.s.save_sequence(self.c,s,token)
  with self.assertRaises(ValueError):self.s.make_preview(self.c)
  out=self.s.make_preview(self.c,True);self.assertIn('timinggroup(noinput)',Path(out).read_text());self.assertTrue(self.s.fresh(self.c,'preview'))
 def test_source_protection(self):
  self.seed();self.s.source(self.c).write_text('changed')
  with self.assertRaises(ValueError):self.s.calculate(self.c)
 def test_single_writer(self):
  with WorkspaceLock(self.base/'locked'):
   p=subprocess.run([sys.executable,'-c',"from app.locking import WorkspaceLock;WorkspaceLock(r'"+str(self.base/'locked')+"')"],cwd=ROOT,capture_output=True);self.assertNotEqual(p.returncode,0)
 def test_interrupted_stages_recover(self):
  self.s.stage(self.c,'allocation','running');s=Store(self.s.root);self.assertEqual(s.catalog()[0]['stages']['allocation']['status'],'interrupted')

class RecoveryAndWindows(unittest.TestCase):
 def test_recover_definition_without_factory_reset(self):
  with tempfile.TemporaryDirectory() as t:
   s=Store(t);d=s.active_definition();d['name']='My custom definition';s.activate_definition(d);atomic(Path(t)/'definitions/active.json','broken');s=Store(t);self.assertEqual(s.active_definition()['name'],'My custom definition')
 def test_temporal_integral_matches_channel(self):
  d=read(ROOT/'defaults/legacy-difficulty.json');d['temporal']={'area':{'input':'displacement','operator':'integral','window_ms':1000}};d['metrics']={'area':'area_max'};r=difficulty.calculate(simple(),{},d);self.assertAlmostEqual(r['metrics']['area'],.5)
 def test_unknown_temporal_input_rejected(self):
  d=read(ROOT/'defaults/legacy-difficulty.json');d['temporal']={'bad':{'input':'missing','operator':'max','window_ms':100}}
  with self.assertRaises(ValueError):difficulty.validate(d)

if __name__=='__main__':unittest.main()
