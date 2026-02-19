# Shared resources

## about.html

**About / credits / licenses** text shown in both the User and Admin launcher (About modal).

Edit `about.html` freely to change wording, add credits, or update the license section. The launcher replaces these placeholders at runtime:

| Placeholder      | Replaced with                          |
|------------------|----------------------------------------|
| `{{LAUNCHER_NAME}}` | e.g. "Matteino Launcher" or "Matteino Launcher Admin" |
| `{{VERSION}}`    | Version from `src/common/version.py`   |
| `{{REPO_ANCHOR}}` | Link to source code, or empty if no repo URL |

Do not remove the placeholders. The repo URL is set in `src/common/about.py` (`REPO_URL`).
