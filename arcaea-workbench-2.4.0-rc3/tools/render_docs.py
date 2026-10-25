"""Small offline renderer for the subset of Markdown used by these guides."""
from pathlib import Path
import html,re
ROOT=Path(__file__).resolve().parents[1]
def inline(s):
 s=html.escape(s)
 s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
 s=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',s)
 return re.sub(r'\[([^]]+)\]\(([^)]+)\)',lambda m:'<a href="'+m[2].removesuffix('.md')+('.html' if m[2].endswith('.md') else '')+'">'+m[1]+'</a>',s)
def render(text):
 out=[];lines=text.splitlines();i=0
 while i<len(lines):
  line=lines[i];i+=1
  if not line.strip():continue
  if line.startswith('```'):
   code=[]
   while i<len(lines) and not lines[i].startswith('```'):code.append(lines[i]);i+=1
   i+=1;out.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>');continue
  if line.startswith('|'):
   rows=[line]
   while i<len(lines) and lines[i].startswith('|'):rows.append(lines[i]);i+=1
   out.append('<div class="table"><table>')
   for j,row in enumerate(rows):
    if re.fullmatch(r'[\s|:\-]+',row):continue
    tag='th' if j==0 else 'td';out.append('<tr>'+''.join('<'+tag+'>'+inline(c.strip())+'</'+tag+'>' for c in row.strip('|').split('|'))+'</tr>')
   out.append('</table></div>');continue
  h=re.match(r'^(#{1,6}) (.+)',line)
  if h:out.append(f'<h{len(h[1])}>'+inline(h[2])+f'</h{len(h[1])}>');continue
  item=re.match(r'^(?:\d+\. |[-*] )(.+)',line)
  if item:
   ordered=bool(re.match(r'\d',line));tag='ol' if ordered else 'ul';out.append('<'+tag+'><li>'+inline(item[1])+'</li>')
   while i<len(lines) and (m:=re.match(r'^(?:\d+\. |[-*] )(.+)',lines[i])):out.append('<li>'+inline(m[1])+'</li>');i+=1
   out.append('</'+tag+'>');continue
  paragraph=[line]
  while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||```|\d+\. |[-*] )',lines[i]):paragraph.append(lines[i]);i+=1
  out.append('<p>'+inline(' '.join(paragraph))+'</p>')
 return '\n'.join(out)
def main():
 for p in (ROOT/'docs').glob('*.md'):
  title=p.read_text().splitlines()[0].lstrip('# ')
  shell='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>body{margin:0;background:#eef2f6;color:#203047;font:17px/1.65 system-ui,sans-serif}main{max-width:980px;margin:24px auto;padding:32px;background:white;border-radius:12px}h1{line-height:1.25}h2{margin-top:2em;border-top:1px solid #ccd5df;padding-top:1em}a{color:#175ca0}code,pre{background:#eef2f6}code{padding:2px 4px}pre{padding:15px;overflow:auto}.table{overflow:auto}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd5df;text-align:left;padding:9px}li{margin:8px 0}nav{font-size:14px} @media(max-width:600px){main{margin:0;padding:18px}}</style><main><nav><a href="USER_MANUAL.html">User guide</a> · <a href="FUNCTIONS_TUTORIAL.html">Functions</a> · <a href="MAINTAINER_GUIDE.html">Maintainer guide</a></nav>'
  p.with_suffix('.html').write_text(shell+render(p.read_text())+'</main></html>',encoding='utf-8')
if __name__=='__main__':main()
