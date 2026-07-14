---
name: update-moxy
description: Automates building, versioning, releasing, and publishing the Moxy font. Use when asked to update or release Moxy.
---

# /update-moxy

Automate the full release loop for the **Moxy** font (ships the static instances
via homebrew; the variable font is the canonical/personal artifact).

## Trigger

User says something like:
- "update moxy"
- "build and release moxy font"
- "bump moxy font version"
- "/update-moxy"

## Workflow

### 1. Check repo state

- `cd /Users/kg/dev/oss/font-moxy`
- Check `git status`
- **If uncommitted changes exist:** warn the user but continue anyway
- **If working tree is clean:** warn the user that there are no changes to release and ask if they want to proceed anyway (they might want to bump version without config changes)

### 2. Auto-increment version

- Read `Version:` from `premade-configs/config.moxy.yaml`
- Increment by 1 (e.g., "39" → "40")
- Update the file

### 3. Commit changes

- `git add -A`
- `git commit -m "bump version to <new_version> for new release"`
- If nothing to commit (no changes at all), still proceed — the version bump itself is the change

### 4. Build fonts (static set — this is what ships)

- Delete old font files in `fonts/Moxy-Static/` first to avoid stale files
- Build: `venv/bin/python scripts/instantiate-code-fonts.py premade-configs/config.moxy.yaml font-data/Recursive_VF_1.085.ttf`
- Verify all 8 font files exist:
  - `Moxy-{Regular,Italic,Semibold,SemiboldItalic,Bold,BoldItalic,Black,BlackItalic}-<fontver>.ttf`
- (The variable font is built separately with `make build-vf` / `scripts/build-variable-font.py`; it is NOT part of the cask.)

### 5. Create release zip

- Bundle attribution: `cp OFL.txt font-data/Lilex-OFL.txt LICENSE fonts/Moxy-Static/`
- `cd fonts && zip -r -X /tmp/moxy-<version>.zip Moxy-Static && cd ..`
- Calculate SHA256: `shasum -a 256 /tmp/moxy-<version>.zip`

### 6. Create GitHub release

- `gh release create v<version> -R kaushikgopal/font-moxy --title "Moxy v<version>" --notes "Updated Moxy font build" /tmp/moxy-<version>.zip`
- **If release already exists:** warn user, then force-update by deleting the existing release first:
  - `gh release delete v<version> -R kaushikgopal/font-moxy --yes`
  - Then recreate it

### 7. Update homebrew-tools cask

- Edit `/Users/kg/dev/oss/homebrew-tools/Casks/font-moxy.rb`:
  - Update `version`
  - Update `sha256`
  - Update `url` to point to new release zip
  - Update the `font` paths to `Moxy-Static/Moxy-<Style>-<fontver>.ttf`
- Commit: `git add Casks/font-moxy.rb && git commit -m "update: moxy <version>"`
- Push: `git push origin master`

### 8. Update .brewfile

- Check if `cask "kaushikgopal/tools/font-moxy"` exists in both:
  - `/Users/kg/.Brewfile`
  - `/Users/kg/.brewfile`
- If missing, add it under the `######## Fonts` section
- If already present, no change needed

### 9. Push font-moxy

- `cd /Users/kg/dev/oss/font-moxy`
- `git push origin main`

### 10. Verify

- Confirm GitHub release URL is accessible
- Confirm homebrew-tools cask has correct version/sha
- Report success to user with install command:
  ```
  brew install --cask kaushikgopal/tools/font-moxy
  ```

## Error Handling

- **Build fails:** Stop and report error output
- **GitHub release fails (not "already exists"):** Stop and report
- **Homebrew push fails:** Stop and report
- **Missing font files after build:** Stop and report which files are missing

## Paths (hardcoded)

- Config repo: `/Users/kg/dev/oss/font-moxy` (formerly `recursive-code-config`)
- Homebrew tools: `/Users/kg/dev/oss/homebrew-tools`
- Brewfiles: `/Users/kg/.Brewfile`, `/Users/kg/.brewfile`
- GitHub repo: `kaushikgopal/font-moxy`
- Homebrew tap repo: `kaushikgopal/homebrew-tools`
- Python venv: `/Users/kg/dev/oss/font-moxy/venv/bin/python`

## Notes

- The skill assumes `gh` CLI is authenticated and has `workflow` scope
- The skill assumes the user has push access to both repos
- The cask ships the **static** Moxy instances (frozen per `config.moxy.yaml`); the
  variable font (with the `lilx`/`ss13` revert toggles) is built separately and is
  not part of the release
- The skill always bumps version even if no other config changes exist
- `make package` automates steps 4–9; this skill mirrors it for ad-hoc runs
