#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(dirname "$SCRIPT_DIR")}"
VOIDSCAPE_SOURCE="$REPO_ROOT/skill"
LEGACY_SOURCE="$REPO_ROOT/compat/read-video"

CLAUDE_SKILLS_ROOT="${CLAUDE_SKILLS_ROOT:-$HOME/.claude/skills}"
AGENTS_SKILLS_ROOT="${AGENTS_SKILLS_ROOT:-$HOME/.agents/skills}"

install_to() {
  local label="$1" root="$2" name="$3" source="$4" dest="$root/$name"
  if [ ! -d "$source" ]; then
    echo "RESULT $label $name copy FAILED missing source"
    return 1
  fi
  if ! mkdir -p "$dest"; then
    echo "RESULT $label $name copy FAILED mkdir $dest"
    return 1
  fi
  if cp -r "$source"/. "$dest"/; then
    echo "RESULT $label $name copy OK"
    return 0
  fi
  echo "RESULT $label $name copy FAILED cp"
  return 1
}

verify_frontmatter() {
  local label="$1" name="$2" dest="$3" skill_md="$3/SKILL.md"
  if [ -f "$skill_md" ] && grep -q '^name:' "$skill_md" && grep -q '^description:' "$skill_md"; then
    echo "RESULT $label $name verify:frontmatter OK"
    return 0
  fi
  echo "RESULT $label $name verify:frontmatter FAILED"
  return 1
}

verify_cli() {
  local label="$1" name="$2" dest="$3"
  if command -v python >/dev/null 2>&1 && python "$dest/scripts/video.py" probe --help >/dev/null 2>&1; then
    echo "RESULT $label $name verify:cli OK"
    return 0
  fi
  echo "RESULT $label $name verify:cli FAILED"
  return 1
}

any_ok=0
for pair in "claude $CLAUDE_SKILLS_ROOT" "agents $AGENTS_SKILLS_ROOT"; do
  label="${pair%% *}"
  root="${pair#* }"
  for spec in "voidscape $VOIDSCAPE_SOURCE" "read-video $LEGACY_SOURCE"; do
    name="${spec%% *}"
    source="${spec#* }"
    dest="$root/$name"
    if install_to "$label" "$root" "$name" "$source"; then
      any_ok=1
      verify_frontmatter "$label" "$name" "$dest" || true
      verify_cli "$label" "$name" "$dest" || true
    fi
  done
done

if [ "$any_ok" -eq 0 ]; then
  echo "SUMMARY all targets FAILED"
  exit 1
fi
echo "SUMMARY install complete: Voidscape primary, read-video compatibility retained"
