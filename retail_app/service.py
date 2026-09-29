#!/usr/bin/env python3
"""Optional macOS per-user local service. No administrator/root service is installed."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys

APP=Path(__file__).resolve().parent
LABEL='com.summitfield.retailagent'
PLIST=Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
DOMAIN=f'gui/{os.getuid()}'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['install','start','restart','stop','status','uninstall'])
    args=parser.parse_args()
    if sys.platform!='darwin':raise SystemExit('This optional service helper supports macOS. Use start.sh or Docker on other systems.')
    if args.action=='install':
        if PLIST.exists():raise SystemExit('A service registration already exists. Use start or inspect it before replacing it.')
        PLIST.parent.mkdir(parents=True,exist_ok=True);(APP/'state').mkdir(exist_ok=True)
        payload={'Label':LABEL,'ProgramArguments':[str(APP/'start.sh')],'WorkingDirectory':str(APP.parent),'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':10,'StandardOutPath':str(APP/'state/server.log'),'StandardErrorPath':str(APP/'state/server-error.log')}
        PLIST.write_bytes(plistlib.dumps(payload))
        subprocess.run(['launchctl','bootstrap',DOMAIN,str(PLIST)],check=True)
        print('Local service installed: http://127.0.0.1:8765')
    elif args.action=='start':subprocess.run(['launchctl','bootstrap',DOMAIN,str(PLIST)],check=True)
    elif args.action=='restart':subprocess.run(['launchctl','kickstart','-k',DOMAIN+'/'+LABEL],check=True)
    elif args.action=='stop':subprocess.run(['launchctl','bootout',DOMAIN+'/'+LABEL],check=True)
    elif args.action=='status':subprocess.run(['launchctl','print',DOMAIN+'/'+LABEL],check=True)
    elif args.action=='uninstall':
        subprocess.run(['launchctl','bootout',DOMAIN+'/'+LABEL],check=False)
        if PLIST.exists():PLIST.unlink()
        print('Removed service registration. Data, code and conversation history are preserved.')
if __name__=='__main__':main()
