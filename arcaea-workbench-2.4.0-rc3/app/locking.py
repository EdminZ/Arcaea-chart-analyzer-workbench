"""OS-backed single-writer workspace lock, auto-released when process exits."""
import os
from pathlib import Path
class WorkspaceLock:
 def __init__(self,root):
  Path(root).mkdir(parents=True,exist_ok=True);self.file=(Path(root)/'.workbench.lock').open('a+b');self.file.seek(0);self.file.write(b'0');self.file.flush();self.file.seek(0)
  try:
   if os.name=='nt':
    import msvcrt;msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
   else:
    import fcntl;fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except OSError:self.file.close();raise RuntimeError('Workspace already open in another process. Close it or use a different workspace.')
 def close(self):self.file.close()
 def __enter__(self):return self
 def __exit__(self,*args):self.close()
