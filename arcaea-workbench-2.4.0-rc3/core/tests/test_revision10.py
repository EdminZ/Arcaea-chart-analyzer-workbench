import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from test_assignment import tap,hold
from assign import solve,State,transition
from preferences import Preferences,context

class Revision10(unittest.TestCase):
 def test_spatial_pairs_keep_one_hand_per_pair(self):
  u=[tap(i,i*86,x) for i,x in enumerate((0,0,1,1,0,0))]
  c=context(u,Preferences());self.assertEqual(c['pair_predecessors'],{1:0,3:2,5:4})
  a,_=solve(u)
  for b,f in c['pair_predecessors'].items():self.assertEqual(a[b],a[f])
 def test_stationary_stream_does_not_start_with_fake_pair(self):
  u=[tap(i,i*87,.5) for i in range(6)];c=context(u,Preferences());self.assertEqual(c['pair_predecessors'],{})
  a,_=solve(u);self.assertTrue(all(a[i]!=a[i+1] for i in range(5)))
 def test_hold_contact_is_not_idle_reset_time(self):
  u=[hold(0,0,87,0),tap(1,174,1),tap(2,261,0)]
  c=context(u,Preferences());self.assertEqual(c['run_predecessors'].get(1),0)
 def test_ground_cross_reach_cost_exceeds_sky(self):
  u=[tap(0,0,1)];ground=transition(State(),0,0,u).cost-transition(State(),0,1,u).cost
  u[0].start_pos=(1,.65);u[0].end_pos=(1,.65)
  sky=transition(State(),0,0,u).cost-transition(State(),0,1,u).cost
  self.assertGreater(ground,sky)
 def test_same_side_floor_sky_is_independent_of_packet_order(self):
  f=tap(0,0,1.25);s=tap(1,0,1);s.kind='sky_tap';s.start_pos=s.end_pos=(1,.65)
  a,x=solve([f,s]);b,y=solve([s,f]);self.assertEqual([a[0],a[1]],['R','L']);self.assertEqual([b[1],b[0]],['R','L']);self.assertAlmostEqual(x['objective'],y['objective'])

if __name__=='__main__':unittest.main()
