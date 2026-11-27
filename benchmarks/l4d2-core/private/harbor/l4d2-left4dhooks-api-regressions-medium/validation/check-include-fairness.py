"""Host-only verifier policy check. Compilation is mocked; not engine evidence."""
import ast
import re
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

verifier = Path(__file__).resolve().parents[1] / "tests/verify.py"
module = ast.parse(verifier.read_text(encoding="utf-8"))
functions = ast.Module(body=[node for node in module.body if isinstance(node, ast.FunctionDef)
    and node.name in {"sourcepawn_code_only", "evaluate_public_include"}], type_ignores=[])
with tempfile.TemporaryDirectory(prefix="l4d2-include-policy-") as directory:
    root = Path(directory)
    include = root / "sourcemod/scripting/include/left4dhooks.inc"
    include.parent.mkdir(parents=True)
    context = {"Path": Path, "re": re, "subprocess": subprocess,
               "COMPILER": root / "compiler", "SM_ROOT": root, "SUBMISSION": root}
    exec(compile(functions, str(verifier), "exec"), context)
    declaration = "native float L4D2Direct_GetSpawnTimer(int client);"
    docs = ("/** Returns the engine timestamp stored in m_flBecomeGhostAt (seconds), "
            "rather than the remaining duration; invalid client indices return -1.0.\n"
            + " * This accessor does not schedule a spawn or change player state.\n" * 24 + " */\n")
    assert "absolute" not in docs and len(docs) > 900
    for label, text, compile_exit, expected in [
        ("equivalent long prose", docs + declaration, 0, True),
        ("ABI unchanged without prose", declaration, 0, True),
        ("integer return rejected", docs + declaration.replace("native float", "native int"), 0, False),
        ("comment-only signature rejected", "/** " + declaration + " */", 0, False),
        ("compile failure rejected", docs + declaration, 1, False),
    ]:
        include.write_text(text, encoding="utf-8")
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], compile_exit)):
            result = context["evaluate_public_include"](root)
        assert len(result) == 1 and result[0][1] is expected, (label, result)
        print("PASS", label)
