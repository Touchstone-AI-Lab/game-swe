{
  description = "Extensible game engineering benchmark runner";

  inputs = {
    nixpkgs.url = "github:moeleak/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{
      self,
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];
      forAllSystems = lib.genAttrs systems;
      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };
      editableOverlay = workspace.mkEditablePyprojectOverlay { root = "$REPO_ROOT"; };

      outputsFor =
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.allowUnfreePredicate = package: lib.getName package == "claude-code";
          };
          pythonSet =
            (pkgs.callPackage pyproject-nix.build.packages { python = pkgs.python312; }).overrideScope
              (
                lib.composeManyExtensions [
                  pyproject-build-systems.overlays.wheel
                  overlay
                ]
              );
          pythonEnv = pythonSet.mkVirtualEnv "rhenium-python" workspace.deps.default;
          devPythonSet = pythonSet.overrideScope (
            lib.composeManyExtensions [
              editableOverlay
              (final: prev: {
                rhenium = prev.rhenium.overrideAttrs (old: {
                  nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ final.resolveBuildSystem { editables = [ ]; };
                });
              })
            ]
          );
          devPythonEnv = devPythonSet.mkVirtualEnv "rhenium-python-dev" workspace.deps.all;
          rhenium = pkgs.writeShellApplication {
            name = "rhenium";
            runtimeInputs = [ pythonEnv ];
            text = ''
              export RHENIUM_ROOT="''${RHENIUM_ROOT:-$PWD}"
              export RHENIUM_BENCHMARK_PATH="''${RHENIUM_BENCHMARK_PATH:-$RHENIUM_ROOT/benchmarks}"
              export RHENIUM_STATE_DIR="''${RHENIUM_STATE_DIR:-$RHENIUM_ROOT/.rhenium/hub}"
              exec ${pythonEnv}/bin/rhenium "$@"
            '';
          };
          pythonChecks =
            pkgs.runCommand "rhenium-python-checks"
              {
                nativeBuildInputs = [ devPythonEnv ];
              }
              ''
                cp -r ${self} source
                chmod -R u+w source
                cd source
                export PYTHONPATH="$PWD/src"
                export HOME="$TMPDIR/home"
                mkdir -p "$HOME"
                ruff check src plugins tests
                mypy src plugins tests
                pytest -q tests plugins/dst/tests plugins/contract/tests
                touch "$out"
              '';
          shellChecks =
            pkgs.runCommand "rhenium-shell-checks"
              {
                nativeBuildInputs = [
                  pkgs.bash
                  pkgs.shellcheck
                ];
              }
              ''
                cd ${self}
                bash -n run-benchmark scripts/prepare-exam scripts/score-exam
                shellcheck run-benchmark scripts/prepare-exam scripts/score-exam
                touch "$out"
              '';
        in
        {
          packages.default = rhenium;
          apps.default = {
            type = "app";
            program = "${rhenium}/bin/rhenium";
          };
          devShells.default = pkgs.mkShell {
            packages = [
              devPythonEnv
              pkgs.uv
              pkgs.shellcheck
              pkgs.codex
              pkgs.claude-code
            ];
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = devPythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
            };
            shellHook = ''
              unset PYTHONPATH
              export REPO_ROOT="$PWD"
            '';
          };
          checks = {
            package = rhenium;
            python = pythonChecks;
            shell = shellChecks;
          };
        };
    in
    {
      packages = forAllSystems (system: (outputsFor system).packages);
      apps = forAllSystems (system: (outputsFor system).apps);
      devShells = forAllSystems (system: (outputsFor system).devShells);
      checks = forAllSystems (system: (outputsFor system).checks);
    };
}
