import argparse
import json
from pathlib import Path
import re

def score(text,nonce,entrypoint_exit):
 expected=json.loads(Path(__file__).with_name('cases.json').read_text())
 try:observed=json.loads(text)
 except (ValueError,TypeError):observed={}
 if not isinstance(observed,dict):observed={}
 rows=observed.get('cases',[])
 if not isinstance(rows,list) or not all(isinstance(r,dict) for r in rows):rows=[]
 valid=bool(nonce) and entrypoint_exit==0 and observed.get('nonce')==nonce and observed.get('fixture_build_exit')==0
 valid=valid and [r.get('id') for r in rows]==[r['id'] for r in expected]
 valid=valid and all(type(r.get('exit')) is int and r['exit']==0 and r.get('timeout') is False for r in rows)
 found={}
 for row in rows:
  stdout=row.get('stdout','');records=[s for s in stdout.splitlines() if s.startswith('ENUM_OBSERVATION ')] if isinstance(stdout,str) else []
  match=re.fullmatch(r'ENUM_OBSERVATION '+re.escape(nonce)+r'\|id='+re.escape(row.get('id',''))+r',loaded=(true|false),value=(.*),error=(.*)',records[0]) if len(records)==1 else None
  if match is None:valid=False
  else:found[row['id']]=match.groups()
 cases=[]
 for case in expected:
  required=('true' if case['loaded'] else 'false',case['value'],'none')
  cases.append({'id':case['id'],'group':case['group'],'passed':bool(valid and found.get(case['id'])==required)})
 passed=sum(r['passed'] for r in cases)
 return {'complete':bool(valid),'expected':len(expected),'passed':passed,'failed':len(expected)-passed,
         'reward':int(valid and passed==len(expected)),'entrypoint_exit':entrypoint_exit,'cases':cases}

if __name__=='__main__':
 parser=argparse.ArgumentParser()
 for name in ['observations','nonce-file','exit-file','output']:parser.add_argument('--'+name,type=Path,required=True)
 args=parser.parse_args();result=score(args.observations.read_text() if args.observations.exists() else '',args.nonce_file.read_text().strip(),int(args.exit_file.read_text()))
 args.output.mkdir(parents=True,exist_ok=True)
 (args.output/'result.json').write_text(json.dumps(result,indent=2));(args.output/'reward.txt').write_text(str(result['reward'])+'\n')
 (args.output/'summary.txt').write_text(f"Complete={result['complete']} Passed={result['passed']} Failed={result['failed']} Expected={result['expected']}\n")
