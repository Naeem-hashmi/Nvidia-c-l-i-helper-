# Contributing to CLI Helper

Thank you for helping. Bug reports, ideas, translations and code are all welcome.

## Reporting a problem

Open an issue and include:

* your NVDA version (NVDA menu > Help > About) and CLI Helper version,
* your terminal: Windows Terminal, Command Prompt or PowerShell in the Windows Console, WSL, and so on,
* the command you ran and what you heard, compared with what you expected,
* if possible, the NVDA log (NVDA menu > Tools > View log). Remove anything private from it first.

## Changing the code

1. Fork the repository and create a branch.
2. Make your change. Keep the add-on's code compatible with Python 3.7, because NVDA 2019.3 to 2023.3 use it. `tests/test_parsing.py` checks the syntax of every file.
3. Run the checks:

   ```powershell
   py -3.13 -m pip install scons==4.10.1 Markdown==3.10 ruff==0.14.5
   ruff check .
   python -m unittest discover tests
   py -3.13 -m SCons
   ```

4. Try the built add-on in NVDA, in Windows Terminal and in the Windows Console, with the newest NVDA and if possible an older one.
5. Add a line to [changelog.md](changelog.md) and open a pull request.

### Where things are

| File | What it does |
| --- | --- |
| `addon/globalPlugins/cliHelper/__init__.py` | CLI mode, its keys, reading, selecting and copying |
| `overlay.py` | Added to every terminal: interactive prompts, automatic reading, progress, sounds, finished commands |
| `parsing.py` | Prompts, command output and interactive prompt recognition (no NVDA code, unit tested) |
| `progress.py` | Progress bar and spinner recognition (no NVDA code, unit tested) |
| `problems.py` | Error summaries (no NVDA code, unit tested) |
| `terminal.py` | Reading text and formatting from terminals |
| `settings.py`, `common.py` | Settings panel and configuration |
| `reader.py`, `history.py` | Reader and command history windows |
| `updater.py` | Update check against GitHub releases |
| `compat.py` | Differences between NVDA versions |

## Making a release (maintainers)

1. Set `addon_version` and `addon_changelog` in `buildVars.py`, and add a `## x.y.z` section to `changelog.md`.
2. Update `lastTestedNVDAVersion` in `buildVars.py` if you tested a newer NVDA.
3. Commit and push, then publish: on GitHub, open Actions > build addon > Run workflow, tick "publish", and run it. (Pushing a tag such as `v1.4.0` does the same.)
4. GitHub Actions builds the add-on and publishes a release with `cliHelper-1.3.0.nvda-addon` and `cliHelper.nvda-addon` attached. Users of the GitHub version are offered the update the next time NVDA starts.
5. Submit the new version to the NVDA Add-on Store with the [Add-on registration form](https://github.com/nvaccess/addon-datastore/issues/new?template=registerAddon.yml), using the versioned download link of the release (for example `https://github.com/Naeem-hashmi/Nvidia-c-l-i-helper-/releases/download/v1.3.0/cliHelper-1.3.0.nvda-addon`).
