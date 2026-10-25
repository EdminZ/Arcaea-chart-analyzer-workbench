import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from test_assignment import doc,tap,hold
from assign import make_units,solve
from reconstruct import build
from input_policy import contact_candidates
from preferences import context,Preferences

class Revision08(unittest.TestCase):
 def units(self,text,**kw):
  d=doc(text);return make_units(d,build(d),**kw)
 def test_rounding_bridge_retains_owner(self):
  u,m=self.units('timing(0,120,4);arc(0,1000,1,.87,s,1,1,1,none,false);arc(1001,1001,.88,.13,s,1,1,1,none,false);arc(1001,2000,.13,0,s,1,1,1,none,false);')
  self.assertEqual(len(u),1);self.assertEqual(len(u[0].sources),3)
 def test_disconnected_bridges_do_not_join(self):
  u,m=self.units('timing(0,180,4);arc(0,333,1.25,1.5,s,1.61,1.61,1,none,false);arc(333,333,1.5,.75,s,1.61,.8,1,none,false);arc(333,333,.5,-.25,s,.8,1.61,1,none,false);arc(333,666,-.25,-.5,s,1.61,1.61,1,none,false);')
  self.assertEqual(len(u),2);self.assertFalse(set(u[0].sources)&set(u[1].sources))
 def test_hidden_policy_reversible(self):
  text='timing(0,120,4);timinggroup(){timing(0,120,4);scenecontrol(0,hidegroup,0,1);arc(0,1000,0,1,s,1,1,0,none,false);};'
  u,m=self.units(text);self.assertEqual(len(u),0);self.assertEqual(len(m['hidden_source_event_ids']),1)
  u,m=self.units(text,include_hidden=True);self.assertEqual(len(u),1)
 def test_single_tick_and_dense_holds_both_reserve_full_duration(self):
  u,m=self.units('timing(0,180,4);hold(0,167,1);timinggroup(){timing(0,1440,4);hold(1000,1167,4);};')
  self.assertEqual(u[0].end,167);self.assertEqual(u[1].end,1167);self.assertEqual(m['single_tick_releases'],[])
 def test_tight_checkpoint_keeps_prepared_hands(self):
  u=[tap(0,0,1),tap(1,1,0),hold(2,20,500,0),hold(3,20,500,1)]
  a,_=solve(u,forced={'0':'L','1':'R'});self.assertEqual(a[2],'R');self.assertEqual(a[3],'L')
 def test_demand_detection_independent_of_search(self):
  x=contact_candidates([hold(0,0,1000,0),hold(1,0,1000,1),tap(2,500,.5)])
  self.assertEqual(x['windows'][0]['peak_contacts'],3)
 def test_accelerating_phrase_starts_new_run(self):
  u=[tap(0,0,0),tap(1,167,1),tap(2,250,1),tap(3,333,.5)]
  c=context(u,Preferences());self.assertNotIn(1,c['run_predecessors']);self.assertIn(1,c['natural_starts'])

if __name__=='__main__':unittest.main()
