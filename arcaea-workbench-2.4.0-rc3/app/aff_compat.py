"""Preview-only removal of unsupported legacy visual group attributes."""
import re
from pathlib import Path
from .common import atomic

def normalize(text):
 changes=[]
 def group(match):
  raw=match.group(1);kept=[];removed=[]
  # Legacy AFF joins properties with underscores; ArcCreate uses commas.
  # Avoid splitting quoted values or modern key=value syntax.
  parts=re.split(r',(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)',raw)
  for part in parts:
   tokens=part.split('_') if '=' not in part and '"' not in part else [part]
   for token in tokens:
    token=token.strip()
    if re.fullmatch(r'(?:tracecol[0-9a-fA-F]+|angle[xy][+-]?\d+(?:\.\d+)?)',token):removed.append(token)
    elif token:kept.append(token)
  result=','.join(kept)
  if result!=raw:changes.append({'original':raw,'exported':result,'removed_visual_attributes':removed})
  return 'timinggroup('+result+')'
 return re.sub(r'timinggroup\s*\(([^)]*)\)',group,text),changes

def normalize_file(path):
 p=Path(path);text=p.read_text(encoding='utf-8-sig');fixed,changes=normalize(text)
 if changes:atomic(p,fixed)
 return changes
