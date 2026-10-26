import copy,csv,io,tempfile,unittest
from pathlib import Path
from app import metadata,signals,sequence,model2
from app.common import ROOT,read,atomic
from app.store import Store
from test_model2 import seq,unit,definition
from test_application import AFF

TABLE='Title,PST,PRS,FTR,BYD/INS,ETR\nCafé,2.5,6.5,9.2,,10.4\n'
def songlist():
 return {'songs':[{'id':'cafe','title_localized':{'en':'Café'},'difficulties':[{'ratingClass':c,'rating':c+5} for c in (0,1,2,4)]}]}
class Constants(unittest.TestCase):
 def test_legacy_encoding_etr_alias_and_decimal(self):
  e,r=metadata.apply_constants(metadata.index(songlist()),TABLE.encode('cp1252'))
  self.assertEqual(r['encoding'],'cp1252');self.assertEqual(e['cafe',3]['chart_constant'],10.4);self.assertEqual(e['cafe',3]['difficulty_name'],'ETR');self.assertEqual(e['cafe',4]['chart_constant'],10.4);self.assertEqual(e['cafe',2]['chart_constant'],9.2)
 def test_duplicate_titles_require_ids(self):
  data=songlist();b=copy.deepcopy(data['songs'][0]);b['id']='cafe2';data['songs'].append(b)
  e,r=metadata.apply_constants(metadata.index(data),TABLE.encode());self.assertEqual(len(r['ambiguous']),1);self.assertIsNone(e['cafe',2]['chart_constant'])
  table=TABLE.replace('Title,','song_id,Title,').replace('Café,','cafe2,Café,')
  e,r=metadata.apply_constants(metadata.index(data),table.encode());self.assertEqual(e['cafe2',2]['chart_constant'],9.2);self.assertIsNone(e['cafe',2]['chart_constant'])
 def test_duplicate_rows_do_not_overwrite(self):
  e,r=metadata.apply_constants(metadata.index(songlist()),(TABLE+TABLE.splitlines()[1]+'\n').encode());self.assertEqual(len(r['ambiguous']),2);self.assertIsNone(e['cafe',3]['chart_constant'])
 def test_reject_conflicting_columns_and_bad_values(self):
  for text in (TABLE.replace(',,10.4',',10.4,10.4'),TABLE.replace('9.2','nan'),TABLE.replace('9.2','bad'),TABLE.replace('9.2','-1')):
   with self.assertRaises(ValueError):metadata.read_constants(text.encode())
 def test_provided_table_accents_and_report(self):
  e,r=metadata.apply_constants(metadata.index(read(ROOT/'defaults/songlist.json')),(ROOT/'defaults/chart-constants.csv').read_bytes())
  self.assertEqual(r['rows'],1);self.assertEqual(e['workbench-demo',2]['chart_constant'],1.0);self.assertEqual(r['matched_rows'],1)
 def test_reload_preserves_sequence_and_failed_load_keeps_table(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);src=root/'cafe';src.mkdir();(src/'3.aff').write_text(AFF);st=Store(root/'workspace');atomic(root/'songlist.json',songlist());st.import_songlist(root/'songlist.json');cid=st.scan(src)['imported'][0]
   s=seq([unit(0)]);s['sha256']=cid;st.save_sequence(cid,s);st.calculate(cid);original=st.sequence_path(cid).read_bytes();active=st.active_definition()
   file=root/'table.csv';file.write_text(TABLE,encoding='utf-8');st.import_constants(file);self.assertEqual(st.metadata(cid)['chart_constant'],10.4);self.assertTrue(st.fresh(cid,'difficulty'))
   file.write_text(TABLE.replace('10.4','10.5'),encoding='utf-8');st.import_constants(file);self.assertEqual(st.metadata(cid)['chart_constant'],10.5)
   file.write_text('bad');before=(st.root/'chart-constants.csv').read_bytes()
   with self.assertRaises(ValueError):st.import_constants(file)
   self.assertEqual(before,(st.root/'chart-constants.csv').read_bytes());file.unlink();st=Store(st.root);self.assertEqual(st.metadata(cid)['chart_constant'],10.5);self.assertEqual(st.sequence_path(cid).read_bytes(),original);self.assertEqual(st.active_definition(),active)
   st.export([cid],root/'export');rows=list(csv.DictReader((root/'export/summary.csv').read_text(encoding='utf-8-sig').splitlines()));self.assertEqual(rows[0]['chart_constant'],'10.5');self.assertEqual(rows[0]['constant_source'],'unofficial wiki CSV')

class Filters(unittest.TestCase):
 def row(self,id,song,cls,value):return {'id':id,'title':song,'difficulty':'FTR','metadata':{'song_id':song,'rating_class':cls,'chart_constant':value}}
 def test_highest_then_inclusive_range_with_class_scope(self):
  rows=[self.row('a','song',2,9.2),self.row('b','song',3,10.4),self.row('c','other',2,9.2)]
  self.assertEqual([r['id'] for r in metadata.filter_rows(rows,{2,3},highest=True,lower=9.2,upper=9.2)],['c'])
  self.assertEqual([r['id'] for r in metadata.filter_rows(rows,{2},highest=True,lower=9.2,upper=9.2)],['a','c'])
 def test_unknown_group_and_tie(self):
  rows=[self.row('a','song',2,9),self.row('b','song',3,None)]
  self.assertEqual(metadata.filter_rows(rows,highest=True),[]);self.assertEqual(len(metadata.filter_rows(rows,lower=0)),1)
  rows[1]['metadata']['chart_constant']=9;self.assertEqual(metadata.filter_rows(rows,highest=True)[0]['id'],'b')
 def test_bad_range(self):
  for a,b in [(2,1),(float('nan'),2)]:
   with self.assertRaises(ValueError):metadata.filter_rows([],lower=a,upper=b)

class ArcOnsets(unittest.TestCase):
 def arc(self,t=0,end=1000,x=0,x2=1,hand='L',fresh=False):return unit(t,end,x,x2,'arc',hand,fresh)
 def count(self,units):return len(signals.extract(seq(units))['presses'])
 def test_independent_onsets_and_attached_tap(self):
  self.assertEqual(self.count([self.arc()]),1);self.assertEqual(self.count([self.arc(fresh=True)]),1);self.assertEqual(self.count([self.arc(),self.arc(2000,3000)]),2)
 def test_connected_continuations_split_and_two_hands(self):
  a=self.arc();b=self.arc(1000,2000,1,2);self.assertEqual(self.count([a,b]),1)
  self.assertEqual(self.count([a,self.arc(hand='R')]),2)
  s=seq([a]);s=sequence.split(s,a['unit_id'],500);self.assertEqual(len(signals.extract(s)['presses']),1)
 def test_explicit_tap_at_continuation_counts(self):
  self.assertEqual(self.count([self.arc(),self.arc(1000,2000,1,2,fresh=True)]),2)
 def test_override_does_not_erase_explicit_tap(self):
  a=self.arc();a['arc_activation']='skip';self.assertEqual(self.count([a]),0);a['fresh_press']=True;self.assertEqual(self.count([a]),1)
  b=self.arc(1000,2000,1,2);b['arc_activation']='count';self.assertEqual(self.count([a,b]),2)
 def test_no_duplicate_with_separate_attached_tap(self):
  self.assertEqual(self.count([self.arc(),unit(0)]),1)
 def test_changes_frequency_not_movement(self):
  a=self.arc();r=model2.calculate(seq([a]),{},definition());a['arc_activation']='skip';old=model2.calculate(seq([a]),{},definition())
  self.assertEqual(r['summary']['press_count'],1);self.assertEqual(old['summary']['press_count'],0);self.assertEqual(r['metrics']['Arc'],old['metrics']['Arc']);self.assertEqual(r['metrics']['distance'],old['metrics']['distance'])
 def test_merge_guards_onset_loss(self):
  a=self.arc();b=self.arc(2000,3000);s=seq([a,b])
  with self.assertRaises(ValueError):sequence.merge(s,[a['unit_id'],b['unit_id']])
 def test_old_engine_result_is_stale(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);src=root/'songs';src.mkdir();(src/'x.aff').write_text(AFF);st=Store(root/'workspace');cid=st.scan(src)['imported'][0];s=seq([self.arc()]);s['sha256']=cid;st.save_sequence(cid,s);st.calculate(cid)
   head=read(st.folder(cid)/'metrics-head.json');head['engine']='frequency-movement/2.1';atomic(st.folder(cid)/'metrics-head.json',head);self.assertFalse(st.fresh(cid,'difficulty'));st.calculate(cid);self.assertTrue(st.fresh(cid,'difficulty'))
if __name__=='__main__':unittest.main()
