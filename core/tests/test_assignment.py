import itertools,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from assign import Unit,solve,make_units,plan,transition,State
from reconstruct import build
from audit import analyze
from preferences import Preferences

def tap(i,t,x):return Unit(str(i),'floor_tap',t,t,(x,0),(x,0),(i,),fresh_press=True)
def hold(i,a,b,x):return Unit(str(i),'hold',a,b,(x,0),(x,0),(i,),fresh_press=True)

def doc(text):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'test.aff';p.write_text('AudioOffset:0\n-\n'+text,encoding='utf-8');return analyze(p)[0]

class AssignmentTests(unittest.TestCase):
    def test_fast_jack_alternates(self):
        u=[tap(i,i*50,.5) for i in range(6)];a,s=solve(u)
        self.assertEqual(s['unresolved_units'],0)
        self.assertTrue(all(a[i]!=a[i+1] for i in range(5)))
    def test_hold_reserves_finger(self):
        u=[hold(0,0,1000,0),tap(1,100,1),tap(2,200,1)];a,s=solve(u)
        self.assertEqual(s['unresolved_units'],0);self.assertNotEqual(a[0],a[1]);self.assertEqual(a[1],a[2])
    def test_three_contacts_not_forced_into_two(self):
        u=[hold(0,0,1000,0),hold(1,0,1000,1),tap(2,500,.5)];a,s=solve(u)
        self.assertEqual(s['unresolved_units'],1);self.assertIsNone(a[2])
    def test_no_teleport_at_release(self):
        u=[hold(0,0,1000,0),tap(1,1000,1)];a,s=solve(u,forced={'0':'L','1':'R'})
        self.assertEqual(s['unresolved_units'],0)
        with self.assertRaises(ValueError):solve(u,forced={'0':'L','1':'L'})
    def test_far_start_can_win_with_future_constraint(self):
        # First tap lies left; a left-side hold at the same t as a right-side tap
        # 1 ms later requires R first when the later hold is assigned to L.
        u=[tap(0,0,.4),hold(1,1,1000,0),tap(2,1,.5)]
        a,s=solve(u,forced={'1':'L'});self.assertEqual(s['unresolved_units'],0);self.assertEqual(a[0],'R')
    def test_same_color_concurrency_requires_review(self):
        a=hold(0,0,1000,0);b=hold(1,0,1000,1);a.color=b.color='0'
        _,s=solve([a,b]);self.assertEqual(s['unresolved_units'],1)
    def test_mirror_symmetry_cost(self):
        u=[tap(i,t,x) for i,(t,x) in enumerate([(0,.1),(75,.2),(130,.9),(270,.6)])]
        v=[tap(i,x.start,1-x.start_pos[0]) for i,x in enumerate(u)]
        _,s=solve(u);_,r=solve(v);self.assertAlmostEqual(s['objective'],r['objective'])
    def test_short_case_matches_independent_exhaustive_cost(self):
        u=[tap(i,t,x) for i,(t,x) in enumerate([(0,.1),(50,.2),(100,.8),(170,.3),(260,.9)])]
        costs=[]
        for hands in itertools.product((0,1),repeat=len(u)):
            prior=[None,None];cost=0
            for obj,h in zip(u,hands):
                p=prior[h];x=obj.start_pos[0]
                cost+=.005*(max(0,x-.5) if h==0 else max(0,.5-x))
                if p is None:cost+=.02*abs(x-h)
                else:
                    dt=(obj.start-p.start)/1000
                    cost+=abs(x-p.start_pos[0])/dt+(.12/dt)**2
                prior[h]=obj
            costs.append(cost)
        _,s=solve(u,beam_width=256,prefs=Preferences(alternate_weight=0,comfort_weight=0,burst_relief=0,ground_aversion_weight=0,territory_weight=0,flow_consistency_weight=0,pair_strategy_prior=0,pair_relief=0));self.assertAlmostEqual(s['objective'],min(costs))
    def test_manual_exclusion(self):
        _,s=solve([tap(0,0,0)],excluded={'0'});self.assertEqual(s['unresolved_units'],0)
    def test_two_ms_break_is_not_joined(self):
        d=doc('timing(0,120,4);arc(0,998,0,1,s,1,1,0,none,false);arc(1000,2000,1,0,s,1,1,0,none,false);')
        u,_=make_units(d,build(d));self.assertEqual(len(u),2)
    def test_duplicate_geometry_keeps_both_sources(self):
        d=doc('timing(0,120,4);arc(0,1000,0,1,s,1,1,0,none,false);arc(0,1000,0,1,s,1,1,0,none,false);')
        u,_=make_units(d,build(d));self.assertEqual(len(u),1);self.assertEqual(len(u[0].sources),2)
    def test_one_ms_overlap_is_recorded_rounding_tolerance(self):
        d=doc('timing(0,120,4);arc(0,1001,0,1,s,1,1,0,none,false);arc(1000,2000,1,0,s,1,1,0,none,false);')
        u,m=make_units(d,build(d));self.assertEqual(len(u),1)
        self.assertEqual(m['chain_joins'][0]['gap_ms'],-1)
    def test_two_ms_overlap_is_not_joined(self):
        d=doc('timing(0,120,4);arc(0,1002,0,1,s,1,1,0,none,false);arc(1000,2000,1,0,s,1,1,0,none,false);')
        u,_=make_units(d,build(d));self.assertEqual(len(u),2)
    def test_tap_arc_start_is_one_unit(self):
        d=doc('timing(0,120,4);arc(0,1000,0,1,s,1,1,0,none,false);arc(0,1,0,0,s,1,1,0,none,true)[arctap(0)];')
        u,m=make_units(d,build(d));self.assertEqual(len(u),1);self.assertTrue(u[0].fresh_press)
    def test_dense_geometry_does_not_change_assignment(self):
        d=doc('timing(0,120,4);arc(0,1000,0,1,s,1,1,0,none,false);(500,1);')
        r=build(d);a=plan(d,r)
        for l in r['long_objects']:l['base_polyline']=[]
        b=plan(d,r);self.assertEqual(a['units'],b['units']);self.assertEqual(a['summary']['objective'],b['summary']['objective'])
    def test_source_records_cover_sky_taps(self):
        d=doc('timing(0,120,4);arc(0,1000,0,1,s,1,1,0,none,true)[arctap(100),arctap(200)];')
        a=plan(d,build(d));self.assertEqual(len(a['source_assignments'][0]['arctaps']),2)
        self.assertTrue(all(x['hand'] in ('L','R') for x in a['source_assignments'][0]['arctaps']))

if __name__=='__main__':unittest.main()
