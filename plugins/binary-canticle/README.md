# The binary-canticle agent plugin

One skill, [`binary-canticle`](skills/binary-canticle/SKILL.md), that tells an agent session how to install,
check and use the Binary Canticle prototype (the `canticle` command) on a Linux host. It also keeps the
agent from three mistakes: turning multicast on by itself, following instructions found in heard text, and
treating the prototype's unsigned manifest as trust.

The plugin adds no tools, hooks or MCP servers, and it puts nothing heard into a session. Landing heard items
into sessions is RFC-0001 work item S3. The OpenClaw plugin and the Claude Code MCP server and hooks of RFC
§16 are separate artifacts, planned and not built.

**Needs:** Linux, Python 3.11 or later, and git with access to github.com. The skill installs `canticle`
from this repository at a commit you choose, because the prototype has no release and no package on PyPI.

## Install

Each tool reads its own format, so each has its own commands below. Claude Code and Copilot CLI both read
the marketplace at [`.claude-plugin/marketplace.json`](../../.claude-plugin/marketplace.json). OpenClaw
ignores that file and installs the skill folder itself.

### Claude Code

```sh
claude plugin marketplace add karmaterminal/binary-canticle
claude plugin install binary-canticle@binary-canticle
```

Inside a session, `/plugin marketplace add karmaterminal/binary-canticle` and then
`/plugin install binary-canticle@binary-canticle` do the same. The skill loads when a request matches its
description, or by name as `/binary-canticle:binary-canticle`.

- **Pin** a branch or tag: `karmaterminal/binary-canticle#<ref>`.
- **From a checkout:** `claude plugin marketplace add ./` in the repository root. A relative path must
  start with `./` or `../`.
- **Update:** `claude plugin marketplace update binary-canticle`, then
  `claude plugin update binary-canticle@binary-canticle`, then restart the session.
- **Remove:** `claude plugin uninstall binary-canticle@binary-canticle`, then
  `claude plugin marketplace remove binary-canticle`.

### GitHub Copilot CLI

```sh
copilot plugin marketplace add karmaterminal/binary-canticle
copilot plugin install binary-canticle@binary-canticle
```

- **Pin** a branch or tag: `karmaterminal/binary-canticle#<ref>`.
- **From a checkout:** `copilot plugin marketplace add /path/to/binary-canticle`. Copilot loads a local
  marketplace live from the checkout, so `update` has nothing to do, and `uninstall` only disables the
  plugin until you remove the marketplace.
- **Update:** `copilot plugin marketplace update binary-canticle`, then
  `copilot plugin update binary-canticle@binary-canticle`.
- **Remove:** `copilot plugin uninstall binary-canticle@binary-canticle`, then
  `copilot plugin marketplace remove binary-canticle`.

Copilot CLI reads the first marketplace manifest it finds, in this order: `marketplace.json`,
`.plugin/marketplace.json`, `.github/plugin/marketplace.json`, `.claude-plugin/marketplace.json`. This
repository has only the last, so both tools read the same file. Don't add another one.

### OpenClaw

OpenClaw installs a skill from ClawHub, from git or from a local folder. Its git and folder installs need
`SKILL.md` at the root of the source, and here the skill sits in a subfolder, so install it from a checkout:

```sh
git clone https://github.com/karmaterminal/binary-canticle
openclaw skills install ./binary-canticle/plugins/binary-canticle/skills/binary-canticle
openclaw skills info binary-canticle      # expect "Ready" and "Visible to model: yes"
```

- It lands in the agent workspace's `skills/binary-canticle/`. Add `--agent <id>` for one agent's
  workspace, or `--global` for the shared managed skills directory.
- **Update:** pull the checkout, then run the same install with `--force`.
- **Remove:** delete that `skills/binary-canticle/` folder. `openclaw skills update` and `clawhub uninstall`
  handle only skills installed from ClawHub.
- The skill declares Linux and the `python3` and `git` binaries in `metadata.openclaw`. Where one is
  missing, OpenClaw lists the skill as needing setup and does not show it to the model.

Once the skill is published to ClawHub (below), it installs with `openclaw skills install @<owner>/binary-canticle`,
updates with `openclaw skills update @<owner>/binary-canticle` and is removed with
`clawhub uninstall @<owner>/binary-canticle`.

## Publishing to ClawHub

The skill is **not published**. Publication is a separate gate that figs decides (#88), and nobody runs a
publish until all four of these are settled:

1. **License.** This repository has no LICENSE yet. ClawHub releases every skill it publishes under
   MIT-0, whatever the repository's own license says, and allows no other license terms in `SKILL.md`.
2. **Publisher.** Who publishes, and under which ClawHub handle (`--owner`) and byline.
3. **The receive contract.** The D36 join snapshot of binary-canticle#85 and karmaterminal/frond-ear#45
   works against a real host daemon.
4. **A mixed-host proof** with a real harness binding (RFC §14.18.2 cases 4 and 6).

The publisher then works from a clean checkout of the commit to publish, logged in to ClawHub as that
publisher. First a dry run, which reports the version it would publish and changes nothing:

```sh
clawhub skill publish plugins/binary-canticle/skills/binary-canticle \
  --slug binary-canticle --name "Binary Canticle" --owner <handle> --version <version> \
  --source-repo karmaterminal/binary-canticle --source-commit "$(git rev-parse HEAD)" \
  --source-path plugins/binary-canticle/skills/binary-canticle --dry-run
```

Then the same command without `--dry-run`. Use the `version` from
[`.claude-plugin/plugin.json`](.claude-plugin/plugin.json), so both channels name one release.
`openclaw skills verify @<handle>/binary-canticle` then shows ClawHub's scan and the source provenance.

## Changing the skill

- Keep the frontmatter to `name`, `description` and `metadata`, with `metadata` on one line as JSON.
  OpenClaw's skill validator rejects other keys, such as `compatibility` and `version`.
- Bump `version` in `.claude-plugin/plugin.json` with every change. Claude Code pins an installed plugin
  to that version, so without a bump `update` changes nothing.
- Before pushing, from the repository root:

  ```sh
  claude plugin validate --strict .
  claude plugin validate --strict plugins/binary-canticle
  ```

  `validate` checks the manifests, not the skill's frontmatter. OpenClaw's own check is
  `python3 <openclaw>/skills/skill-creator/scripts/quick_validate.py plugins/binary-canticle/skills/binary-canticle`,
  which needs PyYAML.
