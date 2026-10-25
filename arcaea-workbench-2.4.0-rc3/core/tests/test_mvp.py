import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from audit import analyze
from reconstruct import build
from assign import make_units,solve,Unit
from preferences import context,Preferences

def tap(i,t,x):return Unit(str(i),'floor_tap',t,t,(x,0),(x,0),(i,),fresh_press=True)

class AlgorithmTests(unittest.TestCase):
 def test_pair_dominated_phrase(self):
  u=[tap(i,i*86,x) for i,x in enumerate((0,0,1,1,0,0))];c=context(u,Preferences());a,_=solve(u)
  self.assertEqual(len(c['pair_predecessors']),3)
  for b,p in c['pair_predecessors'].items():self.assertEqual(a[b],a[p])
 def test_sparse_pair_in_stream_not_discounted(self):
  u=[tap(i,i*86,x) for i,x in enumerate((1,.8,.8,.6,.4,.2,0))]
  self.assertFalse(context(u,Preferences())['pair_predecessors'])
 def test_stationary_stream_alternates(self):
  a,_=solve([tap(i,i*87,.5) for i in range(6)])
  self.assertTrue(all(a[i]!=a[i+1] for i in range(5)))
 def test_third_contact_is_flagged(self):
  a,s=solve([tap(0,0,0),tap(1,0,.5),tap(2,0,1)]);self.assertEqual(s['unresolved_units'],1)
 def test_bridge_preserves_owner_and_arc_reservation(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'a.aff';p.write_text('AudioOffset:0\n-\ntiming(0,180,4);arc(0,1000,0,0,s,1,1,0,none,false);arc(1000,1000,0,1,s,1,1,0,none,false);arc(1000,2000,1,1,s,1,1,0,none,false);')
   d,_=analyze(p);u,_=make_units(d,build(d));self.assertEqual(len(u),1);self.assertEqual(len(u[0].sources),3);self.assertEqual(u[0].end,2000)

class CLITests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dir=Path(self.tmp.name);self.chart=self.dir/'sample.aff';self.raw=b'AudioOffset:0\n-\ntiming(0,180,4);(0,1);(300,4);hold(600,1100,1);(900,4);\n';self.chart.write_bytes(self.raw);self.seq=self.dir/'sequence.json'
 def command(self,program,*args,ok=True):
  r=subprocess.run([sys.executable,str(ROOT/program),*map(str,args)],cwd=self.dir,capture_output=True,text=True)
  if ok:self.assertEqual(r.returncode,0,r.stderr)
  else:self.assertNotEqual(r.returncode,0)
  return r
 def analyze(self):self.command('analyze_aff.py',self.chart,'-o',self.seq)
 def test_full_pipeline_and_backup(self):
  self.analyze();s=json.loads(self.seq.read_text());self.assertEqual(s['format'],'arcaea-input-sequence/1');self.assertEqual(len(s['units']),4)
  r=self.command('color_aff.py',self.chart,self.seq,'-o',self.dir/'colored.aff');info=json.loads(r.stdout)
  self.assertEqual(Path(info['backup']).read_bytes(),self.raw);self.assertEqual(self.chart.read_bytes(),self.raw);self.assertTrue(info['validation']['input_center_time_multiset_preserved'])
 def test_mismatched_source_rejected_without_output(self):
  self.analyze();self.chart.write_bytes(self.raw+b'\n');out=self.dir/'colored.aff';self.command('color_aff.py',self.chart,self.seq,'-o',out,ok=False);self.assertFalse(out.exists())
 def test_structure_edit_rejected(self):
  self.analyze();s=json.loads(self.seq.read_text());s['units'][0]['start_ms']=50;self.seq.write_text(json.dumps(s));self.command('color_aff.py',self.chart,self.seq,'-o',self.dir/'out.aff',ok=False)
 def test_in_place_requires_backup_and_hash_matches(self):
  self.analyze();r=self.command('color_aff.py',self.chart,self.seq,'--in-place');info=json.loads(r.stdout);self.assertEqual(Path(info['backup']).read_bytes(),self.raw);self.assertNotEqual(self.chart.read_bytes(),self.raw)
 def test_existing_output_not_overwritten(self):
  self.analyze();out=self.dir/'colored.aff';out.write_text('KEEP');self.command('color_aff.py',self.chart,self.seq,'-o',out,ok=False);self.assertEqual(out.read_text(),'KEEP')
 def test_sequence_not_overwritten(self):
  self.analyze();before=self.seq.read_bytes();self.command('analyze_aff.py',self.chart,'-o',self.seq,ok=False);self.assertEqual(self.seq.read_bytes(),before)

if __name__=='__main__':unittest.main()
