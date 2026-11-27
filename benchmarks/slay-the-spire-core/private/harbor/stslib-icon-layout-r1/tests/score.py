import argparse
import json
import math
from pathlib import Path
CASES = [{'id': 'engine', 'group': 'control', 'mode': 'engine', 'expected': True}, {'id': 'width-one', 'group': 'width', 'mode': 'width', 'expected': 24}, {'id': 'width-wide', 'group': 'width', 'mode': 'width', 'expected': 72}, {'id': 'width-narrow', 'group': 'width', 'mode': 'width', 'expected': 24}, {'id': 'width-after-newline', 'group': 'width', 'mode': 'width', 'expected': 24}, {'id': 'width-lowercase', 'group': 'width', 'mode': 'width', 'expected': 24}, {'id': 'width-short-code', 'group': 'width', 'mode': 'width', 'expected': 24}, {'id': 'width-cn', 'group': 'width', 'mode': 'width', 'expected': 24}, {'id': 'en-height-three', 'group': 'en-height', 'mode': 'height', 'expected': -60}, {'id': 'en-height-five', 'group': 'en-height', 'mode': 'height', 'expected': -60}, {'id': 'en-height-spacing', 'group': 'en-height', 'mode': 'height', 'expected': -88}, {'id': 'en-height-newline', 'group': 'en-height', 'mode': 'height', 'expected': -90}, {'id': 'cn-height-three', 'group': 'cn-height', 'mode': 'height', 'expected': -60}, {'id': 'cn-height-five', 'group': 'cn-height', 'mode': 'height', 'expected': -60}, {'id': 'cn-height-lowercase', 'group': 'cn-height', 'mode': 'height', 'expected': -88}, {'id': 'cn-height-mixed', 'group': 'cn-height', 'mode': 'height', 'expected': -30}, {'id': 'cn-height-orb', 'group': 'cn-height', 'mode': 'height', 'expected': -30}, {'id': 'cn-height-colored', 'group': 'cn-height', 'mode': 'height', 'expected': -30}, {'id': 'cn-wrap-three', 'group': 'cn-wrap', 'mode': 'render', 'expected': [[0, 0], [0, -30], [0, -60]]}, {'id': 'cn-wrap-five', 'group': 'cn-wrap', 'mode': 'render', 'expected': [[0, 0], [24, 0], [0, -30], [24, -30], [0, -60]]}, {'id': 'cn-wrap-lowercase', 'group': 'cn-wrap', 'mode': 'render', 'expected': [[0, 0], [0, -44], [0, -88]]}, {'id': 'cn-wrap-newline', 'group': 'cn-wrap', 'mode': 'render', 'expected': [[0, 0], [0, -30], [0, -60]]}, {'id': 'header-one', 'group': 'header', 'mode': 'header', 'expected': True}, {'id': 'header-multiple', 'group': 'header', 'mode': 'header', 'expected': True}, {'id': 'header-lowercase', 'group': 'header', 'mode': 'header', 'expected': True}, {'id': 'tint-0', 'group': 'control', 'mode': 'tint', 'expected': True}, {'id': 'tint-1', 'group': 'control', 'mode': 'tint', 'expected': True}, {'id': 'tint-2', 'group': 'control', 'mode': 'tint', 'expected': True}, {'id': 'card-en-1', 'group': 'control', 'mode': 'card', 'expected': True}, {'id': 'card-en-6', 'group': 'control', 'mode': 'card', 'expected': True}, {'id': 'card-en-14', 'group': 'control', 'mode': 'card', 'expected': True}, {'id': 'newline-en', 'group': 'control', 'mode': 'render', 'expected': [[0, 0], [0, -30]]}, {'id': 'wide-en', 'group': 'control', 'mode': 'render', 'expected': [[0, 0], [30, 0], [60, 0]]}, {'id': 'ordinary-height-en', 'group': 'control', 'mode': 'height', 'expected': -30}, {'id': 'unknown-render-en', 'group': 'control', 'mode': 'render', 'expected': []}, {'id': 'card-cn-1', 'group': 'control', 'mode': 'card', 'expected': True}, {'id': 'card-cn-6', 'group': 'control', 'mode': 'card', 'expected': True}, {'id': 'card-cn-14', 'group': 'control', 'mode': 'card', 'expected': True}, {'id': 'newline-cn', 'group': 'control', 'mode': 'render', 'expected': [[0, 0], [0, -30]]}, {'id': 'wide-cn', 'group': 'control', 'mode': 'render', 'expected': [[0, 0], [24, 0], [48, 0]]}, {'id': 'ordinary-height-cn', 'group': 'control', 'mode': 'height', 'expected': -30}, {'id': 'unknown-render-cn', 'group': 'control', 'mode': 'render', 'expected': []}, {'id': 'ordinary-header', 'group': 'control', 'mode': 'header', 'expected': True}]
def score(raw, nonce, entrypoint_exit):
    rows=[];complete_count=0;valid=True
    for line in raw.splitlines():
        if not line.startswith(nonce+'|'):valid=False;continue
        payload=line[len(nonce)+1:]
        if payload=='completed=true':complete_count+=1;continue
        if not payload.startswith('case,'):valid=False;continue
        parts=payload[5:].split(',');row={}
        for part in parts:
            if '=' not in part:valid=False;continue
            key,value=part.split('=',1)
            if key in row:valid=False
            row[key]=value
        rows.append(row)
    complete=valid and entrypoint_exit==0 and complete_count==1 and [row.get('id') for row in rows]==[case['id'] for case in CASES]
    results=[]
    for i,case in enumerate(CASES):
        row=rows[i] if i<len(rows) and rows[i].get('id')==case['id'] else {}
        passed=False;value=row.get('value');expected=case['expected']
        if complete and row.get('error')=='none':
            try:
                if isinstance(expected,bool):passed=value==str(expected).lower()
                elif isinstance(expected,(int,float)):passed=math.isfinite(float(value)) and abs(float(value)-expected)<0.02
                else:
                    points=[[float(part) for part in item.split(':')] for item in value.rstrip(';').split(';')] if value else []
                    passed=len(points)==len(expected) and all(len(actual)==2 and all(math.isfinite(a) and abs(a-b)<0.02 for a,b in zip(actual,wanted)) for actual,wanted in zip(points,expected))
            except (ValueError,TypeError,AttributeError):passed=False
        results.append({'id':case['id'],'group':case['group'],'passed':passed,'actual':row,'expected_value':expected})
    passed=sum(row['passed'] for row in results)
    return {'complete':complete,'expected':len(CASES),'passed':passed,'failed':len(CASES)-passed,'reward':int(complete and passed==len(CASES)),'entrypoint_exit':entrypoint_exit,'cases':results}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--observations',type=Path,required=True);p.add_argument('--nonce-file',type=Path,required=True);p.add_argument('--exit-file',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=score(a.observations.read_text() if a.observations.exists() else '',a.nonce_file.read_text().strip(),int(a.exit_file.read_text()))
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'result.json').write_text(json.dumps(result,indent=2));(a.output/'reward.txt').write_text(str(result['reward'])+'\n');(a.output/'summary.txt').write_text('passed='+str(result['passed'])+' failed='+str(result['failed'])+' complete='+str(result['complete'])+'\n')
