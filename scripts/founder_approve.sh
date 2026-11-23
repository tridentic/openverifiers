#!/usr/bin/env bash
# The founder's approval command (D-032; docs/APPROVALS.md).
#
#   ./scripts/founder_approve.sh <packet>        e.g. ./scripts/founder_approve.sh packet2
#
# Run it yourself, in your own terminal, on the branch approval/<packet> that the
# agent prepared (changes staged, nothing committed). It shows a summary, asks
# y/N, then makes ONE commit signed with your SSH key, with the approval trailers,
# checks the whole history with the gold gate, and pushes to v1.
# It refuses to run inside an agent session or a non-interactive shell.
set -euo pipefail

die() { printf 'founder_approve: %s\n' "$*" >&2; exit 2; }

# ---------------------------------------------------------------- not an agent
for v in CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SSE_PORT CLAUDE_AGENT_SDK_VERSION \
         CODEX_SANDBOX CODEX_HOME CURSOR_AGENT AIDER_MODEL CI GITHUB_ACTIONS; do
  [ -n "${!v:-}" ] && die "refusing: \$$v is set (an agent session or CI). Run this in your own terminal."
done
[ -t 0 ] && [ -t 1 ] || die "refusing: not an interactive terminal. Run this in your own terminal."

packet="${1:-}"
[ -n "$packet" ] || die "usage: ./scripts/founder_approve.sh <packet>   (e.g. packet2)"
cd "$(git rev-parse --show-toplevel)"
py=python3; [ -x .venv/bin/python ] && py=.venv/bin/python

note="approvals/$packet.md"
[ -f "$note" ] || die "no $note: the agent prepares it on the branch approval/$packet"
[ "$(git branch --show-current)" = "approval/$packet" ] || die "check out approval/$packet first"
git diff --quiet || die "there are unstaged changes; only the staged change is approved. Stage or drop them first."
! git diff --cached --quiet || die "nothing is staged"

field() { sed -n "s/^$1: *//p" "$note" | head -1; }
hash=$(field packet-hash); title=$(field title); trailers=$(field trailers); ratifies=$(field ratifies)
[ -n "$hash" ] && [ -n "$title" ] || die "$note lacks 'packet-hash:' or 'title:'"

# ---------------------------------------------------------------- the signing key
[ "$(git config gpg.format || true)" = ssh ] || die "git is not set to sign with SSH; see docs/APPROVALS.md, steps 1-2"
key=$(git config user.signingkey || true)
[ -n "$key" ] || die "no signing key configured; see docs/APPROVALS.md, steps 1-2"
key="${key/#\~/$HOME}"
# Sign from the private key file (passphrase asked each time), never via ssh-agent:
# a .pub path or a key:: literal makes git sign with whatever the agent holds.
case "$key" in
  key::*|*.pub) die "user.signingkey must be the PRIVATE key's path (e.g. ~/.ssh/ov_founder_signing), not a public key; see docs/APPROVALS.md step 2";;
esac
[ -f "$key" ] && [ -f "$key.pub" ] || die "user.signingkey must be a private key file with its .pub next to it; see docs/APPROVALS.md step 2"
pub=$(cat "$key.pub")
case "$pub" in ssh-*|sk-ssh-*) ;; *) die "$key.pub is not an SSH public key";; esac
blob=$(awk '{print $2}' <<<"$pub")
if ssh-add -L 2>/dev/null | grep -qF "$blob"; then
  die "this signing key is loaded in ssh-agent; remove it (ssh-add -d $key.pub) and never add it again (docs/APPROVALS.md)"
fi
signers=.approvers/allowed_signers

if ! git show "HEAD:$signers" 2>/dev/null | grep -qF "$blob"; then
  git show "HEAD:$signers" >/dev/null 2>&1 && die "your key is not in $signers; a key change is a signed gold change (docs/APPROVALS.md)"
  echo "One-time setup: $signers does not exist yet. This key would become the founder's approval key:"
  echo "    $pub"
  read -r -p "Add it, in a separate commit signed with this key? [y/N] " a
  [ "$a" = y ] || [ "$a" = Y ] || die "stopped; nothing changed"
  mkdir -p .approvers
  printf 'founder namespaces="git" %s\n' "$pub" > "$signers"
  git add "$signers"
  git commit -q -S --only "$signers" -m "Approval key for the founder (D-032)"
  echo "setup commit: $(git log -1 --format='%h %G? %GS')"
fi

# ---------------------------------------------------------------- the summary
needs=$(PYTHONPATH=src "$py" -m openverifiers.bench.gold_gate --staged | sed -n 's/^gold gate (dry run): needs: //p')
case "$needs" in *BLOCKED*) die "the gate's dry run says: $needs";; esac
want="$needs $trailers"
clear 2>/dev/null || true
echo "================ APPROVE $packet (packet $hash) ================"
echo "$title"
echo
awk '/^## Summary/{on=1; next} /^## /{on=0} on' "$note" | sed '/^$/N;/^\n$/D' | head -40
echo
echo "---------------- staged change (git diff --cached --stat)"
git diff --cached --stat | tail -25
echo
echo "---------------- trailers on the signed commit"
echo "Meaning-Approved-By: founder (packet $hash)"
case " $want " in *" gold "*) echo "Gold-Change-Approved-By: founder (packet $hash)";; esac
[ -n "$ratifies" ] && echo "Ratifies: $ratifies"
echo
echo "Full note: $note    Packet: see the note's first lines"
read -r -p "Approve and sign this commit? [y/N] " a
[ "$a" = y ] || [ "$a" = Y ] || die "stopped; nothing committed"

# ---------------------------------------------------------------- one signed commit
msg=$(mktemp)
{
  printf 'Approve %s (packet %s): %s\n\n' "$packet" "$hash" "$title"
  printf 'Signed by the founder with scripts/founder_approve.sh (D-032). What is\n'
  printf 'approved, held and ratified: %s.\n\n' "$note"
  printf 'Meaning-Approved-By: founder (packet %s)\n' "$hash"
  case " $want " in *" gold "*) printf 'Gold-Change-Approved-By: founder (packet %s)\n' "$hash";; esac
  [ -n "$ratifies" ] && printf 'Ratifies: %s\n' "$ratifies"
} > "$msg"
git commit -q -S -F "$msg"
rm -f "$msg"

root=$(git rev-list --max-parents=0 HEAD | tail -1)
if ! PYTHONPATH=src "$py" -m openverifiers.bench.gold_gate "$root" HEAD; then
  echo
  echo "The gold gate does not pass over the whole history with this commit, so it is NOT pushed."
  echo "Undo it with:  git reset --soft HEAD~1   (the changes stay staged)"
  exit 1
fi

git push origin "HEAD:refs/heads/v1"
echo "Approved, signed and pushed: $(git log -1 --format='%h %G? %GS %s')"
if git checkout -q v1 2>/dev/null; then
  git merge -q --ff-only "approval/$packet"
else      # v1 is checked out in another worktree (the agent prepares approvals in one)
  echo "v1 is checked out in another folder: run 'git pull --ff-only' there."
fi
