"""Compile immutable mods; exercise each through a fresh real public SDK loader."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

parser=argparse.ArgumentParser()
for name in ['jar','runtime','nonce-file','output']:parser.add_argument('--'+name,type=Path,required=True)
args=parser.parse_args();tests=Path(__file__).resolve().parent
cases=json.loads((tests/'cases.json').read_text());runtime=args.runtime;runtime.mkdir()
baseline=Path('/opt/sts/lib/ModTheSpire.jar');game=Path('/opt/sts/lib/desktop-1.0.jar')
shutil.copyfile(args.jar,runtime/'ModTheSpire.jar')
compiled=runtime/'runner';compiled.mkdir()
report={'nonce':args.nonce_file.read_text().strip(),'fixture_build_exit':255,'cases':[]}
compile_log=[]
def command(values,**kwargs):
 result=subprocess.run(values,capture_output=True,text=True,**kwargs)
 compile_log.append(result.stdout+result.stderr)
 if result.returncode:
  report['fixture_build_exit']=result.returncode;args.output.write_text(json.dumps(report,indent=2))
  (args.output.parent/'probe-build.log').write_text('\n'.join(compile_log))
  raise RuntimeError('Immutable fixture compilation failed')
 return result
command(['javac','-g','-encoding','UTF-8','-source','8','-target','8','-cp',str(baseline)+':'+str(game),'-d',str(compiled),str(tests/'Runner.java')])
for case in cases:
 folder=runtime/case['id'];folder.mkdir();classes=folder/'classes';classes.mkdir()
 command(['javac','-g','-encoding','UTF-8','-source','8','-target','8','-cp',str(baseline)+':'+str(game),'-d',str(classes),str(tests/case['id']/'Fixture.java')])
 shutil.copyfile(tests/case['id']/'ModTheSpire.json',classes/'ModTheSpire.json')
 command(['jar','cf',str(folder/'fixture.jar'),'-C',str(classes),'.'])
report['fixture_build_exit']=0
(args.output.parent/'probe-build.log').write_text('\n'.join(compile_log))
runtime.chmod(0o755)
for path in runtime.rglob('*'):path.chmod(0o755 if path.is_dir() else 0o644)
for case in cases:
 folder=runtime/case['id'];home=folder/'home';home.mkdir();shutil.chown(home,'nobody','nogroup')
 row={'id':case['id'],'timeout':False}
 values=['runuser','-u','nobody','--','java','-Xmx1000m','-Djava.awt.headless=true','-Duser.home='+str(home),
         '-cp',str(compiled)+':'+str(runtime/'ModTheSpire.jar'),'enumobserver.Runner',str(folder/'fixture.jar'),case['id'],str(game),str(home/'private-loader-export.jar')]
 try:
  result=subprocess.run(values,cwd=home,env=dict(os.environ,STS_VERIFY_NONCE=report['nonce']),capture_output=True,text=True,timeout=100)
  row.update(exit=result.returncode,stdout=result.stdout,stderr=result.stderr)
 except subprocess.TimeoutExpired:
  row.update(exit=124,timeout=True,stdout='',stderr='Public loader exceeded bounded observation time')
 report['cases'].append(row);args.output.write_text(json.dumps(report,indent=2))
 # The exported patched bytecode is an ephemeral execution dependency. Never copy it into logs or artifacts.
print(json.dumps({'observed':len(report['cases']),'timed_out':any(r['timeout'] for r in report['cases'])}))
