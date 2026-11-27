{ config, pkgs, ... }:

{
  languages.python = {
    enable = true;
    package = pkgs.python312;
    venv.enable = true;
    uv = {
      enable = true;
      sync = {
        enable = true;
        allExtras = true;
        arguments = [
          "--locked"
          "--all-packages"
        ];
      };
    };
  };

  languages.javascript = {
    enable = true;
    package = pkgs.nodejs_22;
    npm.enable = true;
  };

  packages = [
    pkgs.shellcheck
    pkgs.codex
    pkgs.claude-code
  ];

  env = {
    UV_PYTHON_DOWNLOADS = "never";
  };

  # .env is read by run-benchmark and `rhenium benchmark` at run time. devenv's dotenv
  # integration would copy the keys into the world-readable Nix store, so it stays off.
  dotenv.disableHint = true;

  scripts.benchmark.exec = ''
    exec "${config.devenv.root}/run-benchmark" "$@"
  '';

  # Build the Web UI on first use, then serve it on loopback only. Vite empties
  # web/dist, so the build steps restore the tracked web/dist/.keep afterwards.
  scripts.hub.exec = ''
    set -euo pipefail
    cd "${config.devenv.root}"
    if [ ! -f web/dist/index.html ]; then
      npm ci --prefix web
      npm run build --prefix web
      printf '\n' > web/dist/.keep
    fi
    exec rhenium web "$@"
  '';

  # The repository checks listed in AGENTS.md section 9.
  scripts.check.exec = ''
    set -euo pipefail
    cd "${config.devenv.root}"
    ruff check src plugins providers tests
    mypy src plugins providers tests
    pytest -q
    npm run lint --prefix web
    npm run test --prefix web
    npm run build --prefix web
    printf '\n' > web/dist/.keep
    shellcheck \
      run-benchmark scripts/prepare-exam scripts/score-exam \
      benchmarks/stardew-core/private/harbor/scripts/validate-task.sh \
      providers/steam/helper/build-helper.sh
    git diff --check
  '';

  enterShell = ''
    if [ "''${RHENIUM_QUIET_SHELL:-0}" != "1" ]; then
      echo "Rhenium"
      echo "  rhenium benchmark <game>[/<pack>[/<task>]] --provider api|codex|claude"
      echo "  benchmark <game/pack/task> [mini|codex|claude] [strict|practice]   (interactive)"
      echo "  hub      Web UI at http://127.0.0.1:4317"
      echo "  check    all repository checks"
    fi
  '';
}
