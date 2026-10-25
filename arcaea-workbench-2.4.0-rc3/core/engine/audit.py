"""AFF syntax/provenance audit. No gameplay, fingering, or difficulty claims.
Usage: python audit.py INPUT_DIRECTORY OUTPUT_DIRECTORY
Python 3.10+, standard library only.
"""
import argparse, hashlib, json, re
from pathlib import Path
from collections import Counter

class ParseError(ValueError): pass

class Parser:
    def __init__(self, text):
        self.text = text
        sep = re.search(r'^-\s*$', text, re.M)
        if not sep: raise ParseError('Missing header separator')
        self.header = text[:sep.start()]
        self.i = sep.end()
        self.events, self.groups = [], [{'id': 0, 'parent': None, 'attributes': ''}]
    def ws(self):
        while self.i < len(self.text) and self.text[self.i].isspace(): self.i += 1
    def take(self, literal):
        self.ws()
        if not self.text.startswith(literal, self.i):
            raise ParseError(f'Expected {literal!r} at offset {self.i}')
        self.i += len(literal)
    def args(self):
        self.take('(')
        start = self.i
        end = self.text.find(')', start)
        if end < 0: raise ParseError('Unclosed argument list')
        raw = self.text[start:end]
        if '(' in raw: raise ParseError('Unexpected nested arguments')
        self.i = end + 1
        return [v.strip() for v in raw.split(',')] if raw.strip() else []
    def block(self, group=0):
        while True:
            self.ws()
            if self.i == len(self.text):
                if group: raise ParseError('Unclosed timing group')
                return
            if self.text[self.i] == '}':
                if not group: raise ParseError('Unexpected closing group')
                self.take('}'); self.take(';'); return
            start = self.i
            m = re.match(r'[A-Za-z_][A-Za-z_0-9]*', self.text[self.i:])
            kind = m.group() if m else 'tap'
            if m: self.i += len(kind)
            args = self.args()
            if kind == 'timinggroup':
                gid = len(self.groups)
                self.groups.append({'id': gid, 'parent': group, 'attributes': ','.join(args),
                                    'source_line': self.text.count('\n',0,start)+1})
                self.take('{'); self.block(gid); continue
            children = []
            self.ws()
            if self.i < len(self.text) and self.text[self.i] == '[':
                self.take('[')
                while True:
                    self.ws(); cs = self.i
                    cm = re.match(r'[A-Za-z_][A-Za-z_0-9]*',self.text[self.i:])
                    if not cm: raise ParseError('Expected child event')
                    ck = cm.group(); self.i += len(ck)
                    children.append({'kind': ck, 'args': self.args(), 'source_offset': cs})
                    self.ws()
                    if self.text[self.i:self.i+1] == ']': self.take(']'); break
                    self.take(',')
            self.take(';')
            self.events.append({'id': len(self.events), 'kind': kind, 'args': args,
                'group': group, 'children': children, 'source_line': self.text.count('\n',0,start)+1,
                'source_span': [start,self.i], 'source': self.text[start:self.i]})
    def parse(self):
        self.block()
        return {'header': self.header, 'groups': self.groups, 'events': self.events}

def analyze(path):
    raw=path.read_bytes(); text=raw.decode('utf-8-sig'); doc=Parser(text).parse()
    counts=Counter(e['kind'] for e in doc['events']); warnings=[]; styles=Counter()
    flags=Counter(); max_time=0; extended=0; noinput_objects=0; sky=0
    def noinput(g):
        while g is not None:
            x=doc['groups'][g]
            if 'noinput' in re.split('[_,]',x['attributes']): return True
            g=x['parent']
        return False
    expected={'tap':2,'hold':3,'arc':10,'timing':3}
    for e in doc['events']:
        k,a=e['kind'],e['args']
        e['noinput_group']=noinput(e['group'])
        if e['noinput_group'] and k in ('tap','hold','arc'): noinput_objects+=1
        if k in expected and (len(a)<expected[k] or (k!='arc' and len(a)!=expected[k])):
            warnings.append({'event':e['id'],'reason':'Unexpected argument count'}); continue
        if k not in ('tap','hold','arc','timing','scenecontrol','camera'):
            warnings.append({'event':e['id'],'reason':'Unknown event; preserved'})
        if k in ('tap','hold','arc'):
            e['start_ms']=int(a[0]); e['end_ms']=int(a[1]) if k in ('hold','arc') else int(a[0])
            max_time=max(max_time,e['end_ms'])
            if e['end_ms']<e['start_ms']: warnings.append({'event':e['id'],'reason':'End before start'})
        if k=='arc':
            styles[a[4]]+=1; flags[a[9]]+=1; extended+=len(a)>10
            e['geometry']={'x0':float(a[2]),'x1':float(a[3]),'y0':float(a[5]),'y1':float(a[6]),'curve':a[4]}
            e['color_raw']=a[7]; e['trace_raw']=a[9]; e['extensions_raw']=a[10:]
        for child in e['children']:
            if child['kind']=='arctap':
                sky+=1; child['time_ms']=int(child['args'][0])
                if not e.get('start_ms',0)<=child['time_ms']<=e.get('end_ms',0):
                    warnings.append({'event':e['id'],'reason':'Arctap outside parent interval'})
    doc.update(name=path.name,sha256=hashlib.sha256(raw).hexdigest(),warnings=warnings)
    summary={'name':path.name,'sha256':doc['sha256'],'events':len(doc['events']),
        'tap':counts['tap'],'hold':counts['hold'],'arc':counts['arc'],'arctap':sky,
        'groups':len(doc['groups'])-1,'extended_arcs':extended,'noinput_objects':noinput_objects,
        'last_object_end_ms':max_time,'curves':dict(styles),'trace_flags':dict(flags),'warnings':len(warnings)}
    return doc,summary

def main():
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('output');args=ap.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    summaries=[];seen={};duplicates=[]
    paths=sorted(Path(args.input).iterdir(),key=lambda p:(p.name=='3.aff',p.name))
    for p in paths:
        if not p.is_file():continue
        doc,row=analyze(p)
        if row['sha256'] in seen:
            duplicates.append({'name':p.name,'same_as':seen[row['sha256']]});continue
        seen[row['sha256']]=p.name;summaries.append(row)
        slug=re.sub(r'[^a-z0-9]+','-',p.name.lower()).strip('-')
        (out/(slug+'.json')).write_text(json.dumps(doc,ensure_ascii=False,indent=2))
    (out/'summary.json').write_text(json.dumps({'charts':summaries,'duplicates':duplicates},indent=2))
    lines=['# Arcaea corpus audit — parser checkpoint','',
        'Syntax and source provenance only. These counts include decorative content; they are not judgments or finger actions.', '',
        '| Chart | Floor taps | Holds | Arc statements | Arctaps | Groups | Extended arcs |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in summaries:lines.append('| '+' | '.join(str(r[k]) for k in ('name','tap','hold','arc','arctap','groups','extended_arcs'))+' |')
    lines+=['',f'Unique charts: {len(summaries)}. Parsed events: {sum(r["events"] for r in summaries)}.',
        f'Structural warnings: {sum(r["warnings"] for r in summaries)}.',
        'Duplicates: '+json.dumps(duplicates), '',
        'Not implemented: interpolation evaluation, judgment ticks, touch-state simulation, fingering, exclusion decisions, and difficulty metrics.',
        'The parser preserves unknown events and extension arguments. Successful parsing does not establish their gameplay semantics.']
    (out.parent/'AUDIT.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
if __name__=='__main__':main()
