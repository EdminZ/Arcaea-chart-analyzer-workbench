import tempfile,unittest
from pathlib import Path
import numpy as np
from app import adapters,sequence
from app.arc_solver import endpoint_fits,optimize,recognize
from app.common import ROOT,read
class ArcSolverTests(unittest.TestCase):
 def test_endpoint_interval_containment(self):
  self.assertTrue(endpoint_fits([.5,.5],[[.4,.25],[.6,.75]],[.1,.25]))
  self.assertFalse(endpoint_fits([.5,.5],[[.4,.25],[.61,.75]],[.1,.25]))
 def test_optimizer_preserves_required_point_and_bounds(self):
  centers=np.array([[0.,0.],[.4,.7],[1.,0.]])
  p,ok,_,error=optimize(np.array([0,100,200]),centers,[0,2],np.array([.1,.25]))
  self.assertTrue(ok);np.testing.assert_equal(p[[0,2]],centers[[0,2]])
  self.assertLessEqual(error,1e-7);self.assertTrue(np.all(np.abs(p-centers)<=[.100001,.250001]))
 def test_unknown_timing_is_not_silently_used(self):
  d=read(ROOT/'defaults/recognition.json');d['max_contact_speed_aff_per_s']=4
  with self.assertRaisesRegex(ValueError,'requires null'):recognize(Path('missing'),{},d)
 def test_endpoint_pass_and_required_start(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);source=p/'test.aff';source.write_text('AudioOffset:0\n-\ntiming(0,120,4);\narc(0,1000,0.50,0.55,s,0.5,0.5,0,none,false);\n')
   out=p/'base.json';adapters.allocate(source,out,{})
   s=sequence.convert(read(out));u=next(u for u in s['units'] if u['kind']=='arc');u['fresh_press']=False
   d=read(ROOT/'defaults/recognition.json');candidate,asset=recognize(source,s,d)
   self.assertTrue(any(r['relaxed'] for r in asset['recognition_report'][0]['endpoint_relaxation']))
   self.assertEqual(candidate['units'][0]['start_ms'],u['start_ms'])
   u['fresh_press']=True;candidate,asset=recognize(source,s,d)
   self.assertEqual(candidate['units'][0]['start_position'],u['start_position'])
   self.assertFalse(asset['recognition_report'][0]['endpoint_relaxation'][0]['relaxed'])
   d['endpoint_relaxation']=False;candidate,asset=recognize(source,s,d)
   self.assertEqual(candidate['units'][0]['end_position'],u['end_position'])
 def test_store_generates_and_exports_core_asset(self):
  from app.store import Store
  from app.common import digest
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);songs=p/'songs';songs.mkdir();(songs/'sample_2.aff').write_text('AudioOffset:0\n-\ntiming(0,120,4);\narc(0,1000,0.50,0.55,s,0.5,0.5,0,none,false);\n')
   store=Store(p/'workspace');c=store.scan(songs)['imported'][0];result=store.generate(c)
   self.assertFalse(any(str(v).startswith('Failed') for v in result.values()),result)
   asset=read(read(store.folder(c)/'arc-paths-location.json')['path']);self.assertEqual(asset['sequence_hash'],digest(store.load(c)[0]))
   store.export([c],p/'export');self.assertTrue((p/'export/sample_2.arc-paths.json').exists())
   self.assertIn('timinggroup(noinput)',(songs/'sample_2.preview.aff').read_text())
if __name__=='__main__':unittest.main()

