#if defined __cvar_settings_included
	#endinput
#endif
#define __cvar_settings_included

#define CVS_MODULE_NAME			"CvarSettings"

#define CVARS_DEBUG				0
#define CVS_CVAR_MAXLEN			64

enum struct CVSEntry
{
	ConVar CVSE_cvar;
	char CVSE_oldval[256];
	char CVSE_enforced[256];
	bool CVSE_active;
	bool CVSE_writing;
	char CVSE_newval[CVS_CVAR_MAXLEN];
}

enum struct CVSPending
{
	char CVSP_name[CVS_CVAR_MAXLEN];
	char CVSP_newval[CVS_CVAR_MAXLEN];
}

static bool
	bTrackingStarted = false;

static ArrayList
	CvarSettingsArray = null,
	PendingCvarsArray = null;

void CVS_OnModuleStart()
{
	CVSEntry cvsetting;
	CVSPending cvspending;

	CvarSettingsArray = new ArrayList(sizeof(cvsetting));
	PendingCvarsArray = new ArrayList(sizeof(cvspending));

	RegConsoleCmd("confogl_cvarsettings", CVS_CvarSettings_Cmd, "List all ConVars being enforced by Confogl");
	RegConsoleCmd("confogl_cvardiff", CVS_CvarDiff_Cmd, "List any ConVars that have been changed from their initialized values");

	RegServerCmd("confogl_addcvar", CVS_AddCvar_Cmd, "Add a ConVar to be set by Confogl");
	RegServerCmd("confogl_setcvars", CVS_SetCvars_Cmd, "Starts enforcing ConVars that have been added.");
	RegServerCmd("confogl_resetcvars", CVS_ResetCvars_Cmd, "Resets enforced ConVars.  Cannot be used during a match!");
}

void CVS_OnModuleEnd()
{
	ClearAllSettings();
}

void CVS_OnConfigsExecuted()
{
	ResolvePendingCvars();

	if (bTrackingStarted) {
		SetEnforcedCvars();
	}
}

static Action CVS_SetCvars_Cmd(int args)
{
	if (!IsPluginEnabled()) {
		return Plugin_Handled;
	}

	if (bTrackingStarted) {
		PrintToServer("Tracking has already been started");
		return Plugin_Handled;
	}

#if CVARS_DEBUG
	LogMessage("[%s] No longer accepting new ConVars", CVS_MODULE_NAME);
#endif

	ResolvePendingCvars();
	SetEnforcedCvars();
	bTrackingStarted = true;

	return Plugin_Handled;
}

static Action CVS_AddCvar_Cmd(int args)
{
	if (args != 2) {
		PrintToServer("Usage: confogl_addcvar <cvar> <newValue>");

		if (IsDebugEnabled()) {
			char cmdbuf[MAX_NAME_LENGTH];
			GetCmdArgString(cmdbuf, sizeof(cmdbuf));
			Debug_LogError(CVS_MODULE_NAME, "Invalid Cvar Add: %s", cmdbuf);
		}

		return Plugin_Handled;
	}

	char cvar[CVS_CVAR_MAXLEN + 1], newval[CVS_CVAR_MAXLEN + 1];
	GetCmdArg(1, cvar, sizeof(cvar));
	GetCmdArg(2, newval, sizeof(newval));

	AddCvar(cvar, newval);

	return Plugin_Handled;
}

static Action CVS_ResetCvars_Cmd(int args)
{
	if (IsPluginEnabled()) {
		PrintToServer("Can't reset tracking in the middle of a match");
		return Plugin_Handled;
	}

	ClearAllSettings();
	PrintToServer("Server CVar Tracking Information Reset!");

	return Plugin_Handled;
}

static Action CVS_CvarSettings_Cmd(int client, int args)
{
	if (!IsPluginEnabled()) {
		return Plugin_Handled;
	}

	if (!bTrackingStarted) {
		ReplyToCommand(client, "[Confogl] CVar tracking has not been started!! THIS SHOULD NOT OCCUR DURING A MATCH!");
		return Plugin_Handled;
	}

	char buffer[CVS_CVAR_MAXLEN], name[CVS_CVAR_MAXLEN];
	int cvscount = CvarSettingsArray.Length;

	ReplyToCommand(client, "[Confogl] Enforced Server CVars (Total %d)", cvscount);

	GetCmdArg(1, buffer, sizeof(buffer));
	int offset = StringToInt(buffer);

	if (offset < 0 || offset > cvscount) {
		return Plugin_Handled;
	}

	int temp = cvscount;
	if ((offset + 20) < cvscount) {
		temp = offset + 20;
	}

	CVSEntry cvsetting;

	for (int i = offset; i < temp && i < cvscount; i++) {
		CvarSettingsArray.GetArray(i, cvsetting, sizeof(cvsetting));

		(cvsetting.CVSE_cvar).GetString(buffer, sizeof(buffer));
		(cvsetting.CVSE_cvar).GetName(name, sizeof(name));

		ReplyToCommand(client, "[Confogl] Server CVar: %s, Desired Value: %s, Current Value: %s", name, cvsetting.CVSE_newval, buffer);
	}

	if ((offset + 20) < cvscount) {
		ReplyToCommand(client, "[Confogl] To see more CVars, use confogl_cvarsettings %d", offset + 20);
	}

	return Plugin_Handled;
}

static Action CVS_CvarDiff_Cmd(int client, int args)
{
	if (!IsPluginEnabled()) {
		return Plugin_Handled;
	}

	if (!bTrackingStarted) {
		ReplyToCommand(client, "[Confogl] CVar tracking has not been started!! THIS SHOULD NOT OCCUR DURING A MATCH!");
		return Plugin_Handled;
	}

	char buffer[CVS_CVAR_MAXLEN], name[CVS_CVAR_MAXLEN];
	int cvscount = CvarSettingsArray.Length;

	GetCmdArg(1, buffer, sizeof(buffer));
	int offset = StringToInt(buffer);

	if (offset < 0 || offset > cvscount) {
		return Plugin_Handled;
	}

	int foundCvars = 0;

	CVSEntry cvsetting;

	while (offset < cvscount && foundCvars < 20) {
		CvarSettingsArray.GetArray(offset, cvsetting, sizeof(cvsetting));

		(cvsetting.CVSE_cvar).GetString(buffer, sizeof(buffer));
		(cvsetting.CVSE_cvar).GetName(name, sizeof(name));

		if (strcmp(cvsetting.CVSE_newval, buffer) != 0) {
			ReplyToCommand(client, "[Confogl] Server CVar: %s, Desired Value: %s, Current Value: %s", name, cvsetting.CVSE_newval, buffer);
			foundCvars++;
		}

		offset++;
	}

	if (offset < cvscount) {
		ReplyToCommand(client, "[Confogl] To see more CVars, use confogl_cvarsettings %d", offset);
	}

	return Plugin_Handled;
}

static void ClearAllSettings()
{
    bTrackingStarted = false;
    CVSEntry entry;
    for (int i=0; i<CvarSettingsArray.Length; i++) {
        CvarSettingsArray.GetArray(i, entry, sizeof(entry));
        if (entry.CVSE_active) entry.CVSE_cvar.RemoveChangeHook(CVS_ConVarChange);
    }
    for (int i=0; i<CvarSettingsArray.Length; i++) {
        CvarSettingsArray.GetArray(i, entry, sizeof(entry));
        if (entry.CVSE_active) entry.CVSE_cvar.SetString(entry.CVSE_oldval);
    }
    CvarSettingsArray.Clear();
    PendingCvarsArray.Clear();
}

static void SetEnforcedCvars()
{
    CVSEntry entry;
    // Capture the whole batch before invoking any engine write/change hook.
    for (int i=0; i<CvarSettingsArray.Length; i++) {
        CvarSettingsArray.GetArray(i, entry, sizeof(entry));
        if (!entry.CVSE_active) {
            entry.CVSE_cvar.GetString(entry.CVSE_oldval, sizeof(entry.CVSE_oldval));
            entry.CVSE_active = true;
            entry.CVSE_cvar.AddChangeHook(CVS_ConVarChange);
            CvarSettingsArray.SetArray(i, entry, sizeof(entry));
        }
    }
    bTrackingStarted = true;
    for (int i=0; i<CvarSettingsArray.Length; i++) CVS_ApplyEntry(i);
}

static void CVS_ApplyEntry(int index)
{
    CVSEntry entry;
    CvarSettingsArray.GetArray(index, entry, sizeof(entry));
    if (!entry.CVSE_active || entry.CVSE_writing) return;
    entry.CVSE_writing = true;
    CvarSettingsArray.SetArray(index, entry, sizeof(entry));
    do {
        entry.CVSE_cvar.SetString(entry.CVSE_newval);
    } while (!CVS_MatchesDesired(entry));
    entry.CVSE_cvar.GetString(entry.CVSE_enforced, sizeof(entry.CVSE_enforced));
    entry.CVSE_writing = false;
    CvarSettingsArray.SetArray(index, entry, sizeof(entry));
}

static bool CVS_MatchesDesired(CVSEntry entry)
{
    float low, high;
    bool hasLow = entry.CVSE_cvar.GetBounds(ConVarBound_Lower, low);
    bool hasHigh = entry.CVSE_cvar.GetBounds(ConVarBound_Upper, high);
    if (hasLow || hasHigh) {
        float desired = StringToFloat(entry.CVSE_newval);
        bool clamped = false;
        if (hasLow && desired < low) { desired = low; clamped = true; }
        if (hasHigh && desired > high) { desired = high; clamped = true; }
        if (clamped) return entry.CVSE_cvar.FloatValue == desired;
    }
    char current[256];entry.CVSE_cvar.GetString(current, sizeof(current));
    return StrEqual(current, entry.CVSE_newval);
}

static void AddCvar(const char[] cvar, const char[] newval)
{
	if (bTrackingStarted) {
		#if CVARS_DEBUG
			LogMessage("[%s] Attempt to track new cvar %s during a match!", CVS_MODULE_NAME, cvar);
		#endif
		return;
	}

	if (strlen(cvar) >= CVS_CVAR_MAXLEN) {
		Debug_LogError(CVS_MODULE_NAME, "CVar Specified (%s) is longer than max cvar/value length (%d)", cvar, CVS_CVAR_MAXLEN);
		return;
	}

	if (strlen(newval) >= CVS_CVAR_MAXLEN) {
		Debug_LogError(CVS_MODULE_NAME, "New Value Specified (%s) is longer than max cvar/value length (%d)", newval, CVS_CVAR_MAXLEN);
		return;
	}

	char cvarBuffer[CVS_CVAR_MAXLEN];
	int iSize = CvarSettingsArray.Length;

	CVSEntry existingEntry;

	for (int i = 0; i < iSize; i++) {
		CvarSettingsArray.GetArray(i, existingEntry, sizeof(existingEntry));

		(existingEntry.CVSE_cvar).GetName(cvarBuffer, CVS_CVAR_MAXLEN);

		if (strcmp(cvar, cvarBuffer, false) == 0) {
			strcopy(existingEntry.CVSE_newval, CVS_CVAR_MAXLEN, newval);
			CvarSettingsArray.SetArray(i, existingEntry, sizeof(existingEntry));
			return;
		}
	}

	int iPendingSize = PendingCvarsArray.Length;
	CVSPending pendingEntry;

	for (int i = 0; i < iPendingSize; i++) {
		PendingCvarsArray.GetArray(i, pendingEntry, sizeof(pendingEntry));

		if (strcmp(cvar, pendingEntry.CVSP_name, false) == 0) {
			strcopy(pendingEntry.CVSP_newval, CVS_CVAR_MAXLEN, newval);
			PendingCvarsArray.SetArray(i, pendingEntry, sizeof(pendingEntry));
			return;
		}
	}

	ConVar newCvar = FindConVar(cvar);

	if (newCvar == null) {
		// Owning plugin may not be loaded yet; retry from CVS_OnConfigsExecuted.
		strcopy(pendingEntry.CVSP_name, CVS_CVAR_MAXLEN, cvar);
		strcopy(pendingEntry.CVSP_newval, CVS_CVAR_MAXLEN, newval);
		PendingCvarsArray.PushArray(pendingEntry, sizeof(pendingEntry));

	#if CVARS_DEBUG
		LogMessage("[%s] Pending late-bind for cvar = %s, newval = %s", CVS_MODULE_NAME, cvar, newval);
	#endif
		return;
	}

	PushTrackedCvar(newCvar, newval);
}

static void PushTrackedCvar(ConVar cvar, const char[] newval)
{
	char cvarBuffer[256];
	cvar.GetString(cvarBuffer, sizeof(cvarBuffer));

	CVSEntry newEntry;
	newEntry.CVSE_cvar = cvar;
	newEntry.CVSE_active = false;
	newEntry.CVSE_writing = false;
	strcopy(newEntry.CVSE_newval, CVS_CVAR_MAXLEN, newval);

	// Hooks belong to activation, not registration.

#if CVARS_DEBUG
	char cvarName[CVS_CVAR_MAXLEN];
	cvar.GetName(cvarName, sizeof(cvarName));
	LogMessage("[%s] cvar = %s, newval = %s, oldval = %s", CVS_MODULE_NAME, cvarName, newval, cvarBuffer);
#endif

	CvarSettingsArray.PushArray(newEntry, sizeof(newEntry));
}

static void ResolvePendingCvars()
{
	int iSize = PendingCvarsArray.Length;
	if (iSize == 0) {
		return;
	}

	CVSPending pendingEntry;

	// Reverse iteration so Erase() doesn't shift entries we haven't visited.
	for (int i = iSize - 1; i >= 0; i--) {
		PendingCvarsArray.GetArray(i, pendingEntry, sizeof(pendingEntry));

		ConVar resolved = FindConVar(pendingEntry.CVSP_name);
		if (resolved == null) {
			continue;
		}

		PushTrackedCvar(resolved, pendingEntry.CVSP_newval);
		PendingCvarsArray.Erase(i);
	}
}

static void CVS_ConVarChange(ConVar hConVar, const char[] sOldValue, const char[] sNewValue)
{
    if (!bTrackingStarted) return;
    CVSEntry entry;
    for (int i=0; i<CvarSettingsArray.Length; i++) {
        CvarSettingsArray.GetArray(i, entry, sizeof(entry));
        if (entry.CVSE_cvar == hConVar) {
            char current[256];hConVar.GetString(current, sizeof(current));
            if (!StrEqual(current, entry.CVSE_enforced)) CVS_ApplyEntry(i);
            return;
        }
    }
}
