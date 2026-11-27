#define GCB_PREFIX "@@GCB_SM@@__GCB_NONCE__"

int g_GcbPassed;
int g_GcbTotal;

void GCB_Case(const char[] name, bool passed, const char[] format, any ...)
{
    char detail[256];
    VFormat(detail, sizeof(detail), format, 4);
    g_GcbTotal++;
    if (passed)
    {
        g_GcbPassed++;
    }
    LogMessage("%s:CASE:%s:%s:%s", GCB_PREFIX, name, passed ? "PASS" : "FAIL", detail);
}

void GCB_Final(int expected)
{
    LogMessage("%s:FINAL:%d:%d", GCB_PREFIX, g_GcbPassed, expected);
}
