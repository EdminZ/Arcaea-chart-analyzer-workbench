import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from assign import Unit,obstruction,plan
from preferences import Preferences,context
from audit import analyze
from reconstruct import build
from sequence_io import compact,validate
from export_colors import export

def tap(i,t,x):return Unit(str(i),'floor_tap',t,t,(x,0),(x,0),(i,),fresh_press=True)
class Snapshot12(unittest.TestCase):
 def test_reset_159_160_boundary(self):
  self.assertFalse(context([tap(0,0,0),tap(1,159,1)],Preferences())['resets'])
  self.assertEqual(context([tap(0,0,0),tap(1,160,1)],Preferences())['reset_times'],{160})
 def test_active_hold_prevents_global_reset(self):
  hold=Unit('h','hold',0,1000,(0,0),(0,0),(0,),fresh_press=True)
  self.assertFalse(context([hold,tap(1,400,1),tap(2,900,1)],Preferences())['resets'])
 def test_general_traversal_does_not_admit_pairs(self):
  c=context([tap(i,i*100,i*.1) for i in range(8)],Preferences())
  self.assertEqual(c['template_modes'][0],[0,1])
 def test_spatial_pairs_remain_available(self):
  c=context([tap(i,i*86,x) for i,x in enumerate([0,0,1,1,0,0,1,1])],Preferences())
  self.assertIn(2,c['template_modes'][0])
 def test_collinear_obstruction_and_mirror(self):
  self.assertGreater(obstruction((.8,0),(.2,0)),obstruction((.2,0),(.8,0)))
  self.assertAlmostEqual(obstruction((.7,.1),(.3,.4)),obstruction((.7,.4),(.3,.1)))
 def test_multitouch_warning_not_hidden_by_assignment(self):
  with tempfile.TemporaryDirectory() as td:
   src=Path(td)/'a.aff';out=Path(td)/'b.aff'
   src.write_text('AudioOffset:0\n-\ntiming(0,120,4);\nhold(0,1000,1);\nhold(0,1000,4);\n(500,2);\n')
   doc,_=analyze(src);r=plan(doc,build(doc),16);s=compact(r,src.name)
   self.assertTrue(s['multitouch']['episodes'])
   checks=export(src,s,validate(s,src),out)
   self.assertEqual(checks['counts']['multitouch_candidate_markers'],1)
if __name__=='__main__':unittest.main()
