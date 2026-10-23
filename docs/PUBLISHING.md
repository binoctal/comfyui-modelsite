# Publishing checklist

Nothing here has been done yet: the repository has **not** been pushed and the pack has **not** been published.
Both steps need you, personally, to be logged in. The browser automation used during development has no saved login for GitHub or for registry.comfy.org.

## Suggested defaults (change any of them)

| Item | Suggested value |
|---|---|
| GitHub repository | `binoctal/comfyui-modelsite` (public) |
| Registry PublisherId | `modelsite` (globally unique and **cannot be changed later**; if it is taken, use `binoctal`) |
| License | MIT (`LICENSE` is in the repo; `pyproject.toml` says MIT) |
| Commit author | `binoctal <binoctal@gmail.com>`, as approved; no other identity appears anywhere |
| Icon | `https://modelsite.ai/favicon-96x96.png` (placeholder in `pyproject.toml`; the Registry accepts SVG/PNG/JPG/GIF up to 800x400, so a wider logo is better if you have one) |

## What you need to do yourself

1. **GitHub**: create the empty public repository, then from this folder push **`main` only**:
   ```bash
   git remote add origin git@github.com:binoctal/comfyui-modelsite.git
   git push -u origin main
   ```
   A local branch `dev-history` holds the development history; do not push it (`git push` without `--all` and without naming it keeps it local). GitHub Actions is not needed.
2. **registry.comfy.org**: sign in, create the publisher (the `PublisherId` above), open `registry.comfy.org/nodes`, choose the publisher and create a **publishing API key**. Save it; if lost, create a new one. The key is for publishing only.
3. **Publish with comfy-cli** (the flow was checked against docs.comfy.org on 2026-10-23; re-check if a command is rejected):
   ```bash
   pip install comfy-cli
   comfy node publish        # asks for the publishing API key; input is hidden
   ```
   `pyproject.toml` already has `[project]` (name, description, semantic version, license, repository URL) and `[tool.comfy]` (`PublisherId`, `DisplayName`, `Icon`). `.comfyignore` keeps `tests/`, `docs/` and test config out of the archive.
4. Bump `version` in `pyproject.toml` for every later release (semantic versioning).

## Before every publish: audit

Generic checks (run from the repository root; each should print nothing):

```bash
git grep -nIE "/home/|/Users/|C:\\\\Users"                       # local paths
git grep -nIEo "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"   # e-mail addresses
git grep -nIE "sk-ms-[A-Za-z0-9_-]{12,}"                          # key-shaped strings
grep -l -i "api_key\|apikey\|sk-ms" examples/*.json               # workflows carrying a key
git log --all --format='%an <%ae>' | sort | uniq -c               # only the approved author
```

The author line `binoctal <binoctal@gmail.com>` is **known and approved**; it is not a failure.

A second, stricter audit (upstream names, personal identifiers, and a scan of the **whole commit history**, not just the latest tree) is kept in a private script outside this repository, because the list it checks must not be published. Run it before every push and publish; it must print `AUDIT PASSED`.

## Known limits to mention in the release notes

- Reference **video and audio** inputs are not supported (they need an upload endpoint).
- The model dropdown is filled when the page loads; a model listed after that needs a page reload or the `custom_model` field.
- Result links returned by the API are time-limited; the pack downloads immediately.
