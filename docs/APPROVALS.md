# Approvals (D-032)

Gold and meaning approvals are the founder's own act (MASTERPLAN §9, D-024).
From D-032 on they are **commits made and signed by the founder, outside any
agent session**. Agents never write `Meaning-Approved-By`,
`Gold-Change-Approved-By` or `Ratifies` trailers.

## How it is enforced

`src/openverifiers/bench/gold_gate.py` (run in CI on every push, and over the
whole history by `reproduce.sh`):

- **Signed trailers only.** A trailer counts only if its commit is signed with an
  SSH key listed in `.approvers/allowed_signers` under the principal `founder`.
  The file is read from the parent commit, so a commit cannot approve itself
  by adding a key. Unsigned or wrongly signed approval commits fail. So does
  any unsigned commit that carries an approval trailer at all.
- **Setup.** The commit that creates `.approvers/allowed_signers` must be
  signed by a key it lists. After that, changing the file is a gold change.
- **Ratification.** History cannot be rewritten. So a signed approval commit
  may name earlier commits in a `Ratifies:` trailer. Their meaning violations
  are then cleared if it carries the meaning trailer, and their gold violations
  if it carries the gold trailer.
- **Signatures are SSH only** (`gpg.format ssh`), including hardware keys
  (`ed25519-sk`). GPG signatures are not checked against the file and do not
  count.

## The flow for every packet

1. The agent prepares an approval branch, `approval/<packet>`. The changes are
   staged in the working tree, not committed. It also prepares the note
   `approvals/<packet>.md`, which holds the summary, the held items and what is
   ratified. It runs the full test suite and the gate's dry run
   (`python -m openverifiers.bench.gold_gate --staged`) and reports both.
2. The founder reads the packet and the note. Then, in their own terminal:

   ```bash
   ./scripts/founder_approve.sh <packet>
   ```

   The script:
   - shows a one-screen summary and `git diff --cached --stat`;
   - asks y/N;
   - on y, makes **one signed commit** with the trailers;
   - checks the whole history with the gate;
   - pushes to `v1`.

   It refuses to run inside an agent session or a non-interactive shell.

   **That refusal is a speed bump, not security.** It looks for agent and CI
   environment variables and a terminal, and any process can fake both. The
   security is the key's passphrase (or a hardware key's touch): no commit is
   signed without you typing it. That holds only if the key never sits
   unlocked in an agent (see the warning under step 2 of the key setup).

## One-time key setup (copy and paste)

Do this once, in your own terminal, not in an agent session. The agent must
not create or hold this key.

1. **Make a passphrase-protected signing key.** Type a passphrase when asked.

   ```bash
   ssh-keygen -t ed25519 -C "openverifiers founder approvals" -f ~/.ssh/ov_founder_signing
   ```

   With a hardware key (YubiKey, etc.) use this instead:

   ```bash
   ssh-keygen -t ed25519-sk -C "openverifiers founder approvals" -f ~/.ssh/ov_founder_signing
   ```

2. **Tell git to sign with it in this repository.** `user.signingkey` is the
   **private** key's path (no `.pub`). Git then signs with `ssh-keygen` reading
   that file, so it asks for the passphrase on every approval:

   ```bash
   git config gpg.format ssh
   ```

   ```bash
   git config user.signingkey ~/.ssh/ov_founder_signing
   ```

   ```bash
   git config gpg.ssh.allowedSignersFile "$(git rev-parse --show-toplevel)/.approvers/allowed_signers"
   ```

3. **Register the public key as the founder's approval key.** Either let
   `./scripts/founder_approve.sh <packet>` do it: it offers to, shows you the
   key, and makes a separate signed setup commit. Or do it by hand:

   ```bash
   mkdir -p .approvers && printf 'founder namespaces="git" %s\n' "$(cat ~/.ssh/ov_founder_signing.pub)" > .approvers/allowed_signers
   ```

   ```bash
   git add .approvers/allowed_signers && git commit -S --only .approvers/allowed_signers -m "Approval key for the founder (D-032)"
   ```

   `--only` commits just this file, so any staged packet changes stay staged.

   > **Warning.** Never `ssh-add` this key, never store its passphrase in the
   > macOS Keychain (`ssh-add --apple-use-keychain`, `UseKeychain yes`), and use
   > it for nothing but signing approvals (not for SSH logins or pushes).
   > With a key loaded in ssh-agent, any process running as you, an agent
   > session included, could sign an approval without asking you. If you
   > configured it with the `.pub` path before, re-run the `user.signingkey`
   > command above and check that `ssh-add -l` does not list it.

4. **Check it** (it should print `G founder` for your setup commit):

   ```bash
   git log -1 --format='%G? %GS' -- .approvers/allowed_signers
   ```

5. **Recommended:** add the same public key to GitHub as a *signing* key
   (Settings → SSH and GPG keys → New SSH key → Key type: Signing key). Your
   approval commits then show as Verified, and CI gets an independent anchor
   for the key (below).

## The trust anchor in CI (read-only)

The CI gold-gate job runs `scripts/check_signing_anchor.py`. It reads the
public signing keys of the GitHub user from
`https://api.github.com/users/<owner>/ssh_signing_keys` and compares them with
`.approvers/allowed_signers`. The user is the repository owner unless the
repository variable `FOUNDER_GITHUB_USER` names another. It never writes to
GitHub.

- **Before you confirm:** a key in `allowed_signers` that is not one of your
  GitHub signing keys is a **warning**.
- **After you confirm:** a mismatch **fails** the job. To confirm, set the
  repository variable `FOUNDER_SIGNING_KEY_ON_GITHUB` to `true` (Settings →
  Secrets and variables → Actions → Variables) once the key is on GitHub.

This anchors `allowed_signers` to something an agent with only repository
access cannot change: the keys on your GitHub account.

**Who set the key.** Whoever first commits `.approvers/allowed_signers` sets
which key is trusted. So check its history once, and after any change to it:

```bash
git log --format='%h %an %G? %GS %s' -- .approvers/allowed_signers
```

Every line should be your own signed commit.

## If a key is lost or compromised

1. Make a new key (step 1).
2. Replace the line in `.approvers/allowed_signers`.
3. Commit it signed with the old key and the trailer
   `Gold-Change-Approved-By: founder (key rotation)`.

If the old key is gone, the gate needs a masterplan decision to re-anchor the
file. Report it; do not work around it.
