# Publishing to FloxHub

This guide explains how to publish the SBOM2CVE environment to FloxHub, making it available for users to pull with a simple `flox pull` command.

## Prerequisites

1. **FloxHub Account**: Create account at https://hub.flox.dev
2. **Flox CLI**: Version with `flox push` support
3. **Clean Environment**: Tested and working locally

---

## Current Status

✅ **Environment is FloxHub-ready**:
- All dependencies in `.flox/env/manifest.toml`
- No external dependencies (Docker, pip, etc.)
- Auto-setup via `on-activate` hook
- Clean .gitignore (excludes data/logs)

⏳ **Not yet published**: Users currently use `git clone`

---

## Publishing Steps

### 1. Test Locally First

Ensure everything works from a clean state:

```bash
# Exit current environment
exit

# Re-enter to test hook
flox activate

# Verify packages installed
flox list | grep -E "python312|kafka|flask|packageurl"

# Test demo
./scripts/demo_start.sh

# Verify dashboard
open http://localhost:5001

# Clean stop
./scripts/demo_stop.sh
```

### 2. Clean Up Environment

Remove any local data/state:

```bash
# Clean everything
./scripts/demo_clean.sh

# Exit Flox environment
exit

# Verify gitignore is working
git status  # Should not show data/kafka or logs/*.log
```

### 3. Check Manifest

Verify `.flox/env/manifest.toml` is complete:

```bash
flox list

# Should show:
# - python312
# - apacheKafka
# - openjdk
# - python312Packages.kafka-python
# - python312Packages.packaging
# - python312Packages.flask
# - python312Packages.packageurl-python
```

### 4. Publish to FloxHub

```bash
# Login to FloxHub (if needed)
flox auth login

# Push environment
flox push <your-org>/sbom2cve

# Example:
# flox push flox-examples/sbom2cve
# or
# flox push yourusername/sbom2cve
```

### 5. Test the Pull Workflow

On a different machine or directory:

```bash
# Pull from FloxHub
flox pull <your-org>/sbom2cve

# Enter directory
cd sbom2cve

# Activate (should auto-install all packages)
flox activate

# Should see welcome message with Quick Start commands

# Test demo
./scripts/demo_start.sh
```

---

## What Gets Published

When you `flox push`, FloxHub stores:

✅ **Included**:
- `.flox/env/manifest.toml` - All package declarations
- Source code (`src/`, `scripts/`, `config/`)
- Documentation (`*.md` files)
- Configuration files

❌ **Excluded** (via .gitignore):
- `data/kafka/` - Local Kafka data
- `logs/*.log` - Log files
- `venv/` - Old virtual environment (legacy)
- `.flox/cache/`, `.flox/log/` - Flox runtime

---

## After Publishing

### Update Documentation

Once published, update these files to use the new FloxHub URL:

#### README.md
```markdown
## Quick Start

```bash
# Pull from FloxHub
flox pull <your-org>/sbom2cve
cd sbom2cve

# Activate and start
flox activate
./scripts/demo_start.sh
```
```

#### FLOX_QUICKSTART.md
```markdown
## 🎯 Get Started in 2 Commands

```bash
flox pull <your-org>/sbom2cve && cd sbom2cve
flox activate && ./scripts/demo_start.sh
```
```

### Share the Environment

Share the FloxHub URL:
- `https://hub.flox.dev/<your-org>/sbom2cve`
- Users can browse, star, and pull the environment
- Add description, tags, and README on FloxHub

---

## Updating After Publishing

When you make changes:

```bash
# Make changes to code or manifest
# ...

# Test locally
flox activate
./scripts/demo_start.sh

# Commit to git
git add -A
git commit -m "Update: description"
git push

# Push updated environment to FloxHub
flox push <your-org>/sbom2cve

# Users can update with:
# flox pull <your-org>/sbom2cve --update
```

---

## Versioning

FloxHub supports versioning:

```bash
# Tag a release
git tag -a v1.0.0 -m "Release v1.0.0: Native Kafka, full Floxification"
git push origin v1.0.0

# Push specific version to FloxHub
flox push <your-org>/sbom2cve:v1.0.0

# Users can pull specific version:
# flox pull <your-org>/sbom2cve:v1.0.0
```

---

## Recommended FloxHub Metadata

When publishing, provide:

**Name**: `sbom2cve`

**Short Description**:
"Real-time vulnerability detection for Nix/Flox packages - 100% Flox-managed, no Docker"

**Long Description**:
```
High-confidence SBOM-to-CVE vulnerability matcher optimized for the Nix/Flox ecosystem.

Features:
- Scans Flox environments automatically
- Native Kafka (no containers)
- Zero false positives via PURL type filtering
- 95% confidence semantic version matching
- SPDX 2.3 SBOM generation
- Real-time web dashboard

Setup: 2 commands
  flox pull <org>/sbom2cve && cd sbom2cve
  flox activate && ./scripts/demo_start.sh
```

**Tags**:
- security
- vulnerability
- sbom
- cve
- nix
- flox
- kafka
- vulnerability-scanning
- supply-chain

**Category**: Security & DevOps

**License**: (Specify your license)

---

## Troubleshooting

### "flox push" not available

Update Flox CLI to latest version:
```bash
flox upgrade
flox --version
```

### Environment too large

Check what's being included:
```bash
# See what would be published
git ls-files | head -50

# Ensure .gitignore is working
git status --ignored
```

### Dependencies not installing on pull

Verify manifest.toml is complete:
```bash
flox list
```

All Python packages should be listed.

---

## Benefits of FloxHub Publishing

1. **Easier Distribution**:
   - `flox pull` instead of `git clone`
   - Automatic updates
   - Version management

2. **Discoverability**:
   - Listed on FloxHub marketplace
   - Searchable by tags
   - Community visibility

3. **Trust**:
   - Official Flox environment format
   - Verified dependencies
   - No manual setup required

4. **Analytics** (if available):
   - Pull counts
   - Usage statistics
   - Community feedback

---

## Example: Complete Publishing Workflow

```bash
# 1. Clean and test locally
./scripts/demo_clean.sh
exit

# 2. Fresh activation test
flox activate
./scripts/demo_start.sh
# Verify works correctly
./scripts/demo_stop.sh
exit

# 3. Publish
flox auth login
flox push flox-examples/sbom2cve

# 4. Test from different directory
cd /tmp
flox pull flox-examples/sbom2cve
cd sbom2cve
flox activate
./scripts/demo_start.sh
# Verify works!

# 5. Update documentation
cd ~/sbom2cve
# Update README.md with FloxHub URL
git commit -am "Update docs with FloxHub URL"
git push

# 6. Announce!
# Share on social media, Flox community, etc.
```

---

## Questions?

- **Flox Docs**: https://flox.dev/docs
- **FloxHub**: https://hub.flox.dev
- **Flox Community**: https://discourse.flox.dev

---

## Next Steps

After publishing:

1. ✅ Update README.md with FloxHub URL
2. ✅ Update FLOX_QUICKSTART.md
3. ✅ Add FloxHub badge to README
4. ✅ Share in Flox community
5. ✅ Create blog post/demo video
6. ✅ Add to Flox examples showcase

---

**Ready to publish?** Follow the steps above and make SBOM2CVE available to the Flox community! 🚀
