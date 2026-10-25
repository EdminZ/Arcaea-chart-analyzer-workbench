import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from test_assignment import doc,tap,hold
from assign import make_units,solve
from reconstruct import build

class RevisionTests(unittest.TestCase):
    def test_zero_bridge_keeps_color_owner_and_sources(self):
        d=doc('timing(0,120,4);arc(0,1000,0,0,s,1,1,0,none,false);arc(1000,1000,0,1,s,1,1,0,none,false);arc(1000,2000,1,1,s,1,1,0,none,false);')
        u,m=make_units(d,build(d));self.assertEqual(len(u),1);self.assertEqual(len(u[0].sources),3)
        self.assertEqual(len(m['continuity_bridges']),1)
    def test_bridge_after_successor_in_source_order(self):
        d=doc('timing(0,120,4);arc(0,1000,0,0,s,1,1,0,none,false);arc(1000,2000,1,1,s,1,1,0,none,false);arc(1000,1000,0,1,s,1,1,0,none,false);')
        u,_=make_units(d,build(d));self.assertEqual(len(u),1)
    def test_bridge_does_not_release_for_a_hold(self):
        d=doc('timing(0,120,4);arc(0,1000,0,0,s,1,1,0,none,false);arc(1000,1000,0,1,s,1,1,0,none,false);arc(1000,2000,1,1,s,1,1,0,none,false);hold(1000,1500,1);')
        u,_=make_units(d,build(d));a,s=solve(u);self.assertNotEqual(a[0],a[1]);self.assertEqual(s['unresolved_units'],0)
    def test_bridge_colors_must_match(self):
        d=doc('timing(0,120,4);arc(0,1000,0,0,s,1,1,0,none,false);arc(1000,1000,0,1,s,1,1,1,none,false);arc(1000,2000,1,1,s,1,1,0,none,false);')
        u,_=make_units(d,build(d));self.assertEqual(len(u),2)
    def test_distinct_color_copies_are_not_merged(self):
        d=doc('timing(0,120,4);arc(0,1000,0,1,s,1,1,0,none,false);timinggroup(){timing(0,120,4);arc(1,1002,0,1,s,1,1,1,none,false);};')
        u,_=make_units(d,build(d));self.assertEqual(len(u),2)
    def test_rounded_duplicate_in_other_group_is_one_contact(self):
        d=doc('timing(0,120,4);arc(0,1000,0,1,s,1,1,0,none,false);timinggroup(){timing(0,120,4);arc(1,1002,0,1,s,1,1,0,none,false);};')
        u,m=make_units(d,build(d));self.assertEqual(len(u),1);self.assertEqual(len(u[0].sources),2);self.assertEqual(u[0].end,1002)
    def test_checkpoint_uncrosses(self):
        u=[tap(0,0,.75),tap(1,0,.25)];a,s=solve(u);self.assertEqual(a[0],'R');self.assertEqual(a[1],'L')
    def test_right_start_alternates(self):
        u=[tap(0,0,1),tap(1,83,.75),tap(2,166,.25),tap(3,250,.75)]
        a,s=solve(u);self.assertEqual([a[i] for i in range(4)],['R','L','R','L'])

if __name__=='__main__':unittest.main()
