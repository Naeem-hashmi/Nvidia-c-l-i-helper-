# CLI Helper for NVDA

CLI Helper is an NVDA add-on for Command Prompt, PowerShell, Windows Terminal, WSL, Git Bash, PuTTY, mintty and every other console NVDA treats as a terminal. Its goal is to make the command line read like a document, and to make interactive installers such as `npx create-next-app`, `npm create vite` and `npm init` usable by speech and braille.

* Version: 1.0.0
* NVDA compatibility: 2019.3 to 2026.3 (written to run on NVDA's 32-bit Python 3.7 and 3.11 releases and the 64-bit Python 3.13 releases). So far it has been verified only off Windows; see "Testing status" below.
* License: GPL v2

## What it adds

### Interactive prompts (selection lists, checkboxes and yes/no toggles)

Many command line tools ask questions with menus you move through with the arrow keys. Without help, NVDA either reads the whole list again on every key press or says nothing, because only the colour of the text changes. CLI Helper recognises these prompts on screen and speaks them properly:

* When a prompt appears you hear the question, how many choices there are, and the current choice. For example: "Which framework, list, 4 choices, React, 2 of 4".
* Up and Down arrow speak only the newly focused choice and its position.
* In checkbox lists, Space speaks whether the choice is now checked or not checked.
* For yes/no toggles (Left and Right arrow, as in create-next-app's "Would you like to use TypeScript? No / Yes"), the add-on tells you which answer is selected. It works this out from the text's underline or colour, so the terminal must report formatting. Windows Terminal and the Windows 11 console do; the old console does not. When the add-on cannot tell, it says so instead of guessing.
* NVDA+Alt+C then M reads the whole prompt: the question, every choice, its checked state and which one is current.

Recognised prompt styles: Inquirer and @inquirer/prompts, prompts (used by create-next-app), Enquirer selects, @clack/prompts (used by create-vite, Svelte's `sv` and others), Python's questionary and InquirerPy, and Go's survey. Both their Unicode symbols (❯ ◉ ◯ ● ○ ◼ ◻) and their plain ASCII fallbacks (> (*) ( ) [x] [ ] [+]) are recognised. When no prompt is on screen the arrow keys behave exactly as they do without the add-on, so command history and line editing are unchanged.

### Command layer: NVDA+Alt+C, then one key

| Key | Action |
| --- | --- |
| O | Read the output of the last command |
| Shift+O | Copy the output of the last command |
| V | Open the last output in the reader window |
| B | Open all terminal text, including output that scrolled off screen, in the reader window |
| 1 to 9 | Read that line counted from the bottom (1 is the newest output line) |
| Shift+1 to Shift+9 | Copy that line |
| C | Read the command typed at the prompt |
| M | Read the interactive prompt with all its choices |
| R | Turn review mode on or off |
| Q | Turn quiet mode on or off (stop or resume automatic reading of new output) |
| P / Shift+P | Move to the next / previous shell prompt (that is, the next or previous command) |
| E / Shift+E | Move to the next / previous line with an error or warning |
| F | Find text in the terminal |
| S | Open CLI Helper settings |
| H | Show this list of keys |
| Escape | Leave the layer without doing anything |

An unknown key gives a low beep and closes the layer. Every command can also be given its own shortcut in NVDA menu > Preferences > Input gestures > CLI Helper.

### Review mode: read the terminal like a word processor

Press NVDA+Alt+C then R. The keys below now read the terminal instead of being sent to the shell, until you press Escape:

| Key | Moves by |
| --- | --- |
| Left / Right arrow | Character |
| Control+Left / Right arrow | Word |
| Up / Down arrow | Line |
| Control+Up / Down arrow | Paragraph (a block of text between blank lines) |
| Home / End | Start / end of line |
| Control+Home / End | Top / bottom |
| Page Up / Page Down | Previous / next command prompt |
| E / Shift+E | Next / previous error or warning |
| F, N, Shift+N | Find, next match, previous match |
| L or Space | Read the current line |
| C | Copy the current line |

Character, word and line movement use NVDA's own review cursor commands, so speech, braille, "spell on double press" and your settings behave the same as with the numpad review keys. Review mode switches off by itself when focus leaves the terminal.

### Reader window

V (last output) and B (whole terminal) open the text in a read-only, multi-line edit field. Every normal editing key works there, exactly as in WordPad or Word: arrows, Control+arrows for words and paragraphs, Shift to select, Control+C to copy, NVDA+Down arrow for say all. Control+F finds text, F3 and Shift+F3 move to the next and previous match, and Escape closes the window. Use this for long output, such as build logs, that has scrolled out of the visible window.

### Other conveniences

* Quiet mode stops NVDA from reading new output automatically, which helps during very long installs. Turn it off to hear output again.
* Optional beep when new output contains an error or warning (off by default).

## Settings

NVDA menu > Preferences > Settings > CLI Helper:

* Support interactive prompts (on by default).
* Quiet mode.
* Beep when new output contains an error or warning.
* Shell prompt pattern: a regular expression for your prompt, if it is unusual. Leave it empty to use the default, which recognises PowerShell (`PS C:\>`), Command Prompt (`C:\>`), bash, zsh and WSL (`user@host:~$`), Git Bash (`$ `) and the Python REPL (`>>> `).
* Error pattern: a regular expression for lines that count as errors.

## Tips

* In Windows 11, Windows Terminal and the Windows Console both give NVDA formatting information, which the add-on needs to work out yes/no toggles. On Windows 10, install Windows Terminal (`winget install Microsoft.WindowsTerminal`) for the best results.
* Many tools can be asked not to prompt at all, which is often fastest. For example: `npx create-next-app@latest my-app --yes` (accept the recommended defaults) or `npx create-next-app@latest my-app --ts --eslint --tailwind --app --src-dir --use-npm --import-alias "@/*"`.
* Do not run CLI Helper together with another add-on that takes over the arrow keys in terminals (for example Console Toolkit or Terminal Access). Both would try to handle the same keys.

## Known limitations

* In the Windows Console (conhost), NVDA's review cursor stays inside the visible window, so review mode, P/E and Find search what is on screen. Use B to open everything, including output that scrolled away, in the reader window.
* Prompts drawn by full-screen programs (vim, htop, tmux menus, `less`) are not menus in this sense. Use review mode for those.
* Prompt and error detection uses patterns. If your shell prompt looks unusual, set the prompt pattern in settings.

## Testing status

The parsing logic and the add-on's event and key handling are covered by automated tests (`python -m unittest discover tests`). They use screen text in the format the prompt libraries print, and stand-ins for NVDA's modules. The build produces a valid `.nvda-addon` package. These tests do not replace trying the add-on with NVDA on Windows. The checklist in `docs/testing.md` lists what to try, and on which NVDA versions, before publishing to the add-on store.

## For developers

Build on Windows (Python 3.13 and Git required):

```powershell
py -3.13 -m pip install scons==4.10.1 Markdown==3.10
py -3.13 -m SCons
```

This produces `cliHelper-1.0.0.nvda-addon`. Run the tests with `python -m unittest discover tests`. The research behind the add-on, including sources, NVDA compatibility rules and a comparison with existing add-ons, is in `docs/research.md`.
