#!/usr/bin/env bash
set -euo pipefail

root="/workspace/spirit-mod"
oracle="$(cd "$(dirname "$0")" && pwd)/after"

cp "$oracle/Mechanics/QuestSystem/Quest.cs" "$root/Mechanics/QuestSystem/Quest.cs"
cp "$oracle/Mechanics/QuestSystem/QuestMultiplayer.cs" "$root/Mechanics/QuestSystem/QuestMultiplayer.cs"
cp "$oracle/Mechanics/QuestSystem/Tasks/QuestTask.cs" "$root/Mechanics/QuestSystem/Tasks/QuestTask.cs"
cp "$oracle/Mechanics/QuestSystem/Tasks/BranchingTask.cs" "$root/Mechanics/QuestSystem/Tasks/BranchingTask.cs"
