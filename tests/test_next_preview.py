import tempfile,unittest,json
from pathlib import Path
from app.store import Store
from app.common import read,atomic,ROOT
from test_application import AFF
class PreviewLocation(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.songs=self.root/'song';self.songs.mkdir();self.file=self.songs/'song_2.aff';self.file.write_text(AFF);self.store=Store(self.root/'workspace');self.cid=self.store.scan(self.songs)['imported'][0]
 def test_readable_adjacent_preview_rescan_export_and_source_preserved(self):
  before=self.file.read_bytes();self.store.generate(self.cid);out=self.songs/'song_2.preview.aff';self.assertTrue(out.exists());self.assertEqual(Path(read(self.store.folder(self.cid)/'preview.json')['file']),out);self.assertTrue(self.store.fresh(self.cid,'preview'));self.assertEqual(self.file.read_bytes(),before)
  self.store.scan(self.songs);self.assertEqual(len(self.store.catalog()),1);self.store.export([self.cid],self.root/'export');self.assertEqual((self.root/'export/song_2.preview.aff').read_bytes(),out.read_bytes())
  self.assertEqual(self.store.make_preview(self.cid),str(out));self.assertTrue(self.store.fresh(self.cid,'preview'))
 def test_overlay_has_distinct_name(self):
  self.store.generate(self.cid);out=Path(self.store.make_preview(self.cid,True));self.assertEqual(out,self.songs/'song_2.overlay.aff');self.assertTrue((self.songs/'song_2.preview.aff').exists());self.store.scan(self.songs);self.assertEqual(len(self.store.catalog()),1)
 def test_external_edit_and_unowned_file_not_overwritten(self):
  self.store.generate(self.cid);out=self.songs/'song_2.preview.aff';out.write_text('manual changes');self.assertFalse(self.store.fresh(self.cid,'preview'))
  with self.assertRaises(ValueError):self.store.make_preview(self.cid)
  self.assertEqual(out.read_text(),'manual changes');out.with_name(out.name+'.workbench.json').unlink()
  with self.assertRaises(ValueError):self.store.make_preview(self.cid)
  self.assertEqual(out.read_text(),'manual changes')
 def test_other_chart_receipt_blocks_overwrite(self):
  self.store.generate(self.cid);out=self.songs/'song_2.preview.aff';receipt=out.with_name(out.name+'.workbench.json');r=read(receipt);r['source_hash']='0'*64;atomic(receipt,r)
  with self.assertRaises(ValueError):self.store.make_preview(self.cid)
 def test_missing_source_falls_back_and_legacy_pointer_still_resolves(self):
  self.store.generate(self.cid);p=self.store.folder(self.cid);info=read(p/'preview.json');info['file']=info['archive_file'];info.pop('output_hash');atomic(p/'preview.json',info);self.assertTrue(self.store.fresh(self.cid,'preview'));self.file.unlink();out=Path(self.store.make_preview(self.cid));self.assertEqual(out,self.store.root/'results/song_2/song_2.preview.aff')
if __name__=='__main__':unittest.main()
