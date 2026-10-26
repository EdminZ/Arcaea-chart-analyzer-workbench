import sys,tempfile,json,unittest,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'engine'))
from assign import Unit,State,transition,solve,make_units
from preferences import Preferences,context
from audit import analyze
from reconstruct import build
from sequence_io import compact,validate
from export_colors import export

def tap(i,t,x):return Unit(str(i),'floor_tap',t,t,(x,0),(x,0),(i,),fresh_press=True)
class Snapshot11(unittest.TestCase):
 def test_hold_is_not_a_posture_checkpoint(self):
  a=Unit('a','hold',100,500,(0,0),(0,0),(0,),fresh_press=True);b=Unit('b','hold',100,500,(1,0),(1,0),(1,),fresh_press=True)
  self.assertFalse(context([a,b],Preferences())['checkpoints'])
 def test_hold_blocks_later_tap_until_end(self):
  a=Unit('a','hold',0,167,(0,0),(0,0),(0,),fresh_press=True);u=[a,tap(1,100,0)]
  choices,_=solve(u,forced={'a':'L'});self.assertEqual(choices[1],'R')
 def test_no_hold_duration_exertion(self):
  p=Preferences();u=[Unit('a','hold',0,100,(0,0),(0,0),(0,),fresh_press=True)]
  a=transition(State(),0,0,u,p,context(u,p));u[0].end=10000;b=transition(State(),0,0,u,p,context(u,p));self.assertEqual(a.cost,b.cost)
 def test_pair_relief_is_smooth_across_old_cutoff(self):
  def cost(x):
   u=[tap(0,0,0),tap(1,86,x),tap(2,172,1),tap(3,258,1)];p=Preferences();c=context(u,p);s=State(pattern=(0,2));s=transition(s,0,0,u,p,c);return transition(s,1,0,u,p,c).cost-s.cost
  self.assertLess(abs(cost(.08001)-cost(.07999)),.01)
 def test_long_stationary_run_remains_alternating(self):
  a,_=solve([tap(i,i*86,.5) for i in range(16)]);self.assertTrue(all(a[i]!=a[i+1] for i in range(15)))
 def test_repeated_spatial_pairs_keep_pattern(self):
  a,_=solve([tap(i,i*86,x) for i,x in enumerate([0,0,1,1]*4)]);self.assertTrue(all(a[i]==a[i+1] for i in range(0,16,2)))
 def test_reset_does_not_force_home_detour(self):
  p=Preferences();u=[tap(0,0,1),tap(1,2000,1)];c=context(u,p)
  s=transition(State(),0,0,u,p,c);a=transition(s,1,0,u,p,c)
  c['resets']=[];b=transition(s,1,0,u,p,c);self.assertEqual(a.cost,b.cost)
 def test_arc_marker_only_on_nondefault_assignment(self):
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/'in.aff';f.write_text('AudioOffset:0\n-\ntiming(0,180,4);arc(0,1000,0,0,s,1,1,0,none,false);')
   from assign import plan
   d,_=analyze(f)
   for h,count in [('L',0),('R',1)]:
    r=plan(d,build(d),overrides={'force_hands':{'A1':h}});s=compact(r,'test');result=export(f,s,validate(s,f),Path(td)/(h+'.aff'));self.assertEqual(result['counts'].get('arc_hand_markers',0),count)
 def test_cli_hand_override_and_source_guard(self):
  with tempfile.TemporaryDirectory() as td:
   td=Path(td);src=td/'in.aff';src.write_text('AudioOffset:0\n-\ntiming(0,180,4);(100,1);')
   def run(*args):return subprocess.run([sys.executable,str(ROOT/'analyze_aff.py'),str(src),*map(str,args)],capture_output=True,text=True)
   base=td/'base.json';r=run('-o',base);self.assertEqual(r.returncode,0,r.stderr);data=json.loads(base.read_text());u=data['units'][0];h='R' if u['hand']=='L' else 'L'
   override=td/'override.json';override.write_text(json.dumps({'source_sha256':data['sha256'],'force_hands':{u['unit_id']:h}}))
   new=td/'new.json';r=run('-o',new,'--hand-overrides',override);self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(new.read_text())['units'][0]['hand'],h)
   override.write_text(json.dumps({'source_sha256':'0'*64,'force_hands':{u['unit_id']:h}}));bad=td/'bad.json';r=run('-o',bad,'--hand-overrides',override);self.assertNotEqual(r.returncode,0);self.assertFalse(bad.exists())
if __name__=='__main__':unittest.main()
