#!/usr/bin/env python3
import argparse,os,sys
from pathlib import Path
from app.store import Store

def main():
 p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parent/'workspace');a=p.parse_args();a.workspace.mkdir(parents=True,exist_ok=True)
 from app.locking import WorkspaceLock
 lock=WorkspaceLock(a.workspace)
 import tkinter as tk
 from app.gui import Window
 root=tk.Tk();Window(root,Store(a.workspace));root.mainloop();lock.close()
if __name__=='__main__':main()
