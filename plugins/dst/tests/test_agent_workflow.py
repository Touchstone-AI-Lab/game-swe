from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parents[3]
RUN_BENCHMARK = ROOT / "run-benchmark"
PREPARE = ROOT / "scripts/prepare-exam"
SCORE = ROOT / "scripts/score-exam"
TASK_IDS = (
    "dst-fixed-bundle-regressions",
    "dst-fixed-module-regressions",
    "composting-together-regressions",
    "dsmmo-release-regressions",
    "glassic-api-regressions",
)
TASK_KEYS = tuple(f"dst/core/{task_id}" for task_id in TASK_IDS)


def _shell_test_path(fake_bin: Path) -> str:
    # Keep agents/launchers stubbed while resolving real shell utilities on NixOS,
    # where /bin/bash and /usr/bin/coreutils are not provided by the host.
    for name in ("bash", "env", "dirname", "basename", "mkdir"):
        executable = shutil.which(name)
        assert executable is not None, f"test requires {name}"
        (fake_bin / name).symlink_to(executable)
    return f"{fake_bin}:/usr/bin:/bin"


def _isolated_environment(tmp_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "RHENIUM_EVALUATION_SECURITY_MODE",
        "RHENIUM_EVALUATION_HOST_PROVIDER",
        "RHENIUM_EVALUATION_HOST_IMAGE",
    ):
        environment.pop(name, None)
    state = tmp_path / "state"
    environment["RHENIUM_STATE_DIR"] = str(state)
    environment["RHENIUM_CACHE_DIR"] = str(state / "cache")
    environment["RHENIUM_DATABASE_URL"] = f"sqlite:///{state / 'state.sqlite'}"
    environment["RHENIUM_BENCHMARK_PATH"] = str(ROOT / "benchmarks")
    environment["PATH"] = f"{Path(sys.executable).parent}:{environment.get('PATH', '')}"
    return environment


def test_run_benchmark_loads_agent_api_config_without_leaking_task_id(tmp_path: Path) -> None:
    launcher = tmp_path / "launcher"
    scripts = launcher / "scripts"
    scripts.mkdir(parents=True)
    run_benchmark = launcher / "run-benchmark"
    run_benchmark.write_bytes(RUN_BENCHMARK.read_bytes())
    run_benchmark.chmod(0o755)
    (launcher / "PROMPT.md").write_text("launcher prompt\n", encoding="utf-8")
    (launcher / ".env").write_text(
        "OPENAI_API_KEY='dotenv-key'\n"
        "OPENAI_BASE_URL='https://gateway.example/v1'\n"
        "CODEX_MODEL='gateway-model'\n"
        "ANTHROPIC_API_KEY='anthropic-key'\n"
        "ANTHROPIC_AUTH_TOKEN='anthropic-token'\n"
        "ANTHROPIC_BASE_URL='https://anthropic-gateway.example'\n"
        "ANTHROPIC_MODEL='claude-gateway-model'\n",
        encoding="utf-8",
    )
    prepare = scripts / "prepare-exam"
    prepare.write_text(
        '#!/bin/sh\nmkdir "$2"\nprintf \'task prompt\\n\' > "$2/PROMPT.md"\n',
        encoding="utf-8",
    )
    prepare.chmod(0o755)
    score = scripts / "score-exam"
    score.write_text("#!/bin/sh\n", encoding="utf-8")
    score.chmod(0o755)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    codex = fake_bin / "codex"
    codex.write_text(
        '#!/bin/sh\nprintf \'key=%s\\n\' "$OPENAI_API_KEY"\nprintf \'arg=%s\\n\' "$1" "$2" "$3" "$4"\n',
        encoding="utf-8",
    )
    codex.chmod(0o755)
    claude = fake_bin / "claude"
    claude.write_text(
        "#!/bin/sh\n"
        "printf 'api_key=%s\\n' \"$ANTHROPIC_API_KEY\"\n"
        "printf 'auth_token=%s\\n' \"$ANTHROPIC_AUTH_TOKEN\"\n"
        "printf 'base_url=%s\\n' \"$ANTHROPIC_BASE_URL\"\n"
        "printf 'model=%s\\n' \"$ANTHROPIC_MODEL\"\n",
        encoding="utf-8",
    )
    claude.chmod(0o755)
    rhenium = fake_bin / "rhenium"
    rhenium.write_text(
        "#!/bin/sh\n"
        "printf 'enabled=%s\n' \"$RHENIUM_MODEL_ENABLED\"\n"
        "printf 'name=%s\n' \"$RHENIUM_MODEL_NAME\"\n"
        "printf 'base_url=%s\n' \"$RHENIUM_MODEL_BASE_URL\"\n"
        "printf 'key=%s\n' \"$RHENIUM_MODEL_API_KEY\"\n"
        "printf 'command=%s\n' \"$1\"\n"
        "printf 'attempt=%s\n' \"$2\"\n",
        encoding="utf-8",
    )
    rhenium.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = _shell_test_path(fake_bin)
    attempt = tmp_path / "attempt"

    completed = subprocess.run(
        [str(run_benchmark), TASK_KEYS[0], "codex", "strict", str(attempt)],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert TASK_IDS[0] not in completed.stdout
    assert completed.stdout.splitlines()[-5:] == [
        "key=dotenv-key",
        "arg=--config",
        "arg=openai_base_url=https://gateway.example/v1",
        "arg=--model",
        "arg=gateway-model",
    ]

    claude_attempt = tmp_path / "claude-attempt"
    completed = subprocess.run(
        [str(run_benchmark), TASK_KEYS[0], "claude", "strict", str(claude_attempt)],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert TASK_IDS[0] not in completed.stdout
    assert completed.stdout.splitlines()[-4:] == [
        "api_key=anthropic-key",
        "auth_token=anthropic-token",
        "base_url=https://anthropic-gateway.example",
        "model=claude-gateway-model",
    ]

    mini_attempt = tmp_path / "mini-attempt"
    completed = subprocess.run(
        [str(run_benchmark), TASK_KEYS[0], "mini", "strict", str(mini_attempt)],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert TASK_IDS[0] not in completed.stdout
    assert completed.stdout.splitlines()[-6:] == [
        "enabled=true",
        "name=gateway-model",
        "base_url=https://gateway.example/v1",
        "key=dotenv-key",
        "command=solve-attempt",
        f"attempt={mini_attempt}",
    ]


def test_prepare_exam_creates_anonymous_public_bundle_with_api_usage(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt"
    completed = subprocess.run(
        [str(PREPARE), TASK_KEYS[1], str(attempt), "practice"],
        capture_output=True,
        text=True,
        check=False,
        env=_isolated_environment(tmp_path),
    )

    assert completed.returncode == 0, completed.stderr
    assert {path.name for path in attempt.iterdir()} == {
        "AGENTS.md",
        "CLAUDE.md",
        "EXAM.md",
        "PROMPT.md",
        "mod",
        "task.json",
    }
    assert (attempt / "mod" / "modinfo.lua").is_file() and (attempt / "mod" / "LICENSE").is_file()
    public = [path for path in attempt.rglob("*") if path.is_file()]
    bundle = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in public)
    assert all(task_id not in bundle for task_id in TASK_IDS)
    assert "dst/core" not in bundle
    assert "order:" not in bundle and "第 1 题" not in bundle
    exam = (attempt / "EXAM.md").read_text(encoding="utf-8")
    assert "/app/mod" not in exam and "`mod`" in exam
    assert "## Expected behaviour" in exam and "## Evaluation" in exam
    assert "汇报 Task ID" not in bundle
    assert "anonymous run ID" in bundle
    launcher_prompt = (ROOT / "PROMPT.md").read_text(encoding="utf-8")
    assert "汇报 Task ID" not in launcher_prompt
    assert "匿名 run ID" in launcher_prompt
    assert 'score-exam" "$PWD"' in bundle
    assert "Mode: `practice`" in bundle


def test_prepare_exam_refuses_nonempty_attempt(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    (attempt / "keep.txt").write_text("user data\n", encoding="utf-8")
    completed = subprocess.run(
        [str(PREPARE), TASK_KEYS[0], str(attempt)],
        capture_output=True,
        text=True,
        check=False,
        env=_isolated_environment(tmp_path),
    )
    assert completed.returncode == 2
    assert "not empty" in completed.stderr
    assert (attempt / "keep.txt").read_text(encoding="utf-8") == "user data\n"


def test_prepare_exam_refuses_parent_inside_repository() -> None:
    destination = ROOT / f".agent-workflow-{uuid.uuid4().hex}" / "attempt"
    completed = subprocess.run(
        [str(PREPARE), TASK_KEYS[0], str(destination)], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 2
    assert "parent directory does not exist" in completed.stderr
    assert not destination.parent.exists()


def test_prepare_exam_refuses_symlink_into_repository(tmp_path: Path) -> None:
    destination = tmp_path / "attempt"
    before = {path.name for path in ROOT.iterdir()}
    destination.symlink_to(ROOT, target_is_directory=True)
    try:
        completed = subprocess.run(
            [str(PREPARE), TASK_KEYS[0], str(destination)],
            capture_output=True,
            text=True,
            check=False,
            env=_isolated_environment(tmp_path),
        )
        assert completed.returncode == 2
        assert "symbolic link" in completed.stderr
        assert {path.name for path in ROOT.iterdir()} == before
    finally:
        destination.unlink(missing_ok=True)


def test_score_exam_refuses_benchmark_repository() -> None:
    completed = subprocess.run([str(SCORE), str(ROOT)], capture_output=True, text=True, check=False)
    assert completed.returncode == 2
    assert "outside the benchmark repository" in completed.stderr

    ancestor = subprocess.run([str(SCORE), str(ROOT.parent)], capture_output=True, text=True, check=False)
    assert ancestor.returncode == 2
    assert "must not contain" in ancestor.stderr


def test_score_exam_command_contains_no_task_id_and_supports_macos_bash_3(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_devenv = fake_bin / "devenv"
    fake_devenv.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    fake_devenv.chmod(0o755)
    environment = _isolated_environment(tmp_path)
    environment["PATH"] = _shell_test_path(fake_bin)

    completed = subprocess.run(
        ["/bin/bash" if Path("/bin/bash").is_file() else str(fake_bin / "bash"), str(SCORE), str(submission)],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines()[-4:] == ["--", "rhenium", "run-attempt", str(submission)]
    assert all(task_id not in completed.stdout for task_id in TASK_IDS)


def test_score_exam_forwards_explicit_untrusted_host_without_task_identity(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_devenv = fake_bin / "devenv"
    fake_devenv.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    fake_devenv.chmod(0o755)
    environment = _isolated_environment(tmp_path)
    environment["PATH"] = _shell_test_path(fake_bin)

    completed = subprocess.run(
        [
            "/bin/bash" if Path("/bin/bash").is_file() else str(fake_bin / "bash"),
            str(SCORE),
            str(submission),
            "--security-mode",
            "untrusted",
            "--host-provider",
            "fake-disposable",
            "--host-image",
            "sha256:trusted-image",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    arguments = completed.stdout.splitlines()
    assert arguments[-6:] == [
        "--security-mode",
        "untrusted",
        "--host-provider",
        "fake-disposable",
        "--host-image",
        "sha256:trusted-image",
    ]
    assert all(task_id not in completed.stdout for task_id in TASK_IDS)
