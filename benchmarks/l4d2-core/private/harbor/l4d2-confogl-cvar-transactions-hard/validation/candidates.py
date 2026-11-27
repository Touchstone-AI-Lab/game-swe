from pathlib import Path
import shutil
def materialize(task: Path,candidate: str,destination: Path)->None:
    if candidate not in {'nop','gold','alternative','minus-finite-return','minus-bounded-string',*{f'minus-report-{i}' for i in range(1,8)}}:raise ValueError(candidate)
    shutil.copytree(task/'environment/l4d2-competitive',destination)
    if candidate=='nop':return
    if candidate!='nop':shutil.copytree(task/'solution/after',destination,dirs_exist_ok=True)
    p=destination/'addons/sourcemod/scripting/confoglcompmod/CvarSettings.sp'
    s=p.read_text(encoding='utf-8')
    def edit(a,b):
        nonlocal s
        if a not in s:raise ValueError(a)
        s=s.replace(a,b)
    if candidate=='alternative':
        edit('for (int i=0; i<CvarSettingsArray.Length; i++) CVS_ApplyEntry(i);','for (int i=CvarSettingsArray.Length-1; i>=0; i--) CVS_ApplyEntry(i);')
        edit('if (!StrEqual(current, entry.CVSE_enforced))','if (strcmp(current, entry.CVSE_enforced) != 0)')
    elif candidate=='minus-report-1':
        edit('strcopy(existingEntry.CVSE_newval, CVS_CVAR_MAXLEN, newval);','// first assignment incorrectly wins')
        edit('strcopy(pendingEntry.CVSP_newval, CVS_CVAR_MAXLEN, newval);\n\t\t\tPendingCvarsArray.SetArray','// pending first assignment incorrectly wins\n\t\t\tPendingCvarsArray.SetArray')
    elif candidate=='minus-report-2':
        edit('newEntry.CVSE_active = false;','strcopy(newEntry.CVSE_oldval, sizeof(newEntry.CVSE_oldval), cvarBuffer);\n\tnewEntry.CVSE_active = false;')
        edit('entry.CVSE_cvar.GetString(entry.CVSE_oldval, sizeof(entry.CVSE_oldval));','// incorrectly retain registration-time baseline')
    elif candidate=='minus-report-3':
        edit('if (!StrEqual(current, entry.CVSE_enforced)) CVS_ApplyEntry(i);','// drift is logged/ignored but not corrected')
    elif candidate=='minus-report-4':
        edit('void CVS_OnConfigsExecuted()\n{\n\tResolvePendingCvars();','void CVS_OnConfigsExecuted()\n{\n\t// no late binding')
    elif candidate=='minus-report-5':
        edit('if (entry.CVSE_active) entry.CVSE_cvar.SetString(entry.CVSE_oldval);','entry.CVSE_cvar.SetString(entry.CVSE_oldval);')
    elif candidate=='minus-report-6':
        edit('char cvar[CVS_CVAR_MAXLEN + 1], newval[CVS_CVAR_MAXLEN + 1];','char cvar[CVS_CVAR_MAXLEN], newval[CVS_CVAR_MAXLEN];')
    elif candidate=='minus-report-7':
        edit('if (offset < 0 || offset > cvscount)', 'if (offset > cvscount)')
    elif candidate=='minus-finite-return':
        edit('} while (!CVS_MatchesDesired(entry));','} while (false);')
    elif candidate=='minus-bounded-string':
        edit('if (clamped) return entry.CVSE_cvar.FloatValue == desired;','return entry.CVSE_cvar.FloatValue == desired;')
    p.write_text(s,encoding='utf-8',newline='\n')
