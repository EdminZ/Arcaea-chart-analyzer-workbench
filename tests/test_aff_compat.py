import unittest,tempfile
from pathlib import Path
from app.aff_compat import normalize
from app import adapters
from app.common import ROOT
import sys
sys.path.insert(0,str(ROOT/'core/engine'))
from audit import analyze
class Compatibility(unittest.TestCase):
 def test_screenshot_attributes_and_valid_flags(self):
  source='timinggroup(tracecoleeee00){\n};\ntiminggroup(angley3575){\n};\ntiminggroup(noinput_angley25){\n};\ntiminggroup(light){\n};\ntiminggroup(angley=25,name="a_b"){\n};'
  fixed,changes=normalize(source)
  self.assertNotIn('angley3575',fixed);self.assertNotIn('tracecol',fixed)
  self.assertIn('timinggroup(noinput)',fixed);self.assertIn('timinggroup(light)',fixed)
  self.assertIn('angley=25,name="a_b"',fixed);self.assertEqual(len(changes),3)
 def test_overlay_normalizes_copy_preserving_source_and_noinput(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);source=p/'source.aff';raw='AudioOffset:0\n-\ntiming(0,120,4);\ntiminggroup(noinput_angley3575){\narc(0,100,0,1,s,0,0,0,none,false);\n};\n';source.write_text(raw)
   out=p/'overlay.aff';report=adapters.overlay(source,{'units':[]},out)
   self.assertEqual(source.read_text(),raw);self.assertTrue(report['group_compatibility'])
   doc,_=analyze(out);self.assertTrue(next(e for e in doc['events'] if e['kind']=='arc')['noinput_group'])
if __name__=='__main__':unittest.main()
