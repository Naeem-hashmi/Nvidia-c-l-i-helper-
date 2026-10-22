# CLI Helper for NVDA

CLI Helper is a free, open source add-on for the [NVDA screen reader](https://www.nvaccess.org/). It makes Command Prompt, PowerShell, Windows Terminal, WSL, Git Bash, PuTTY and other consoles as comfortable to read as a document. It also makes interactive installers such as `npx create-next-app`, `npm create vite` and `npm init` usable with speech and braille.

* Latest version: 1.3.0
* Works with: NVDA 2019.3 to 2026.3, on Windows 10 and 11
* License: GNU General Public License version 2

## Download

* **[Download the latest version of CLI Helper (.nvda-addon file)](https://github.com/Naeem-hashmi/Nvidia-c-l-i-helper-/releases/latest/download/cliHelper.nvda-addon)**
* [All versions and their release notes](https://github.com/Naeem-hashmi/Nvidia-c-l-i-helper-/releases)
* NVDA Add-on Store: CLI Helper has not been submitted yet. Once it is listed, you will be able to install and update it from NVDA menu > Tools > Add-on Store.

## Install

1. Download the `.nvda-addon` file with the link above.
2. Open the downloaded file, for example by pressing Enter on it in File Explorer or in your browser's downloads list.
3. NVDA asks whether you want to install CLI Helper. Choose Yes.
4. Restart NVDA when asked.

To remove it later, use NVDA menu > Tools > Add-on Store > Installed add-ons.

## Quick start

1. Open PowerShell, Command Prompt or Windows Terminal, and run any command. New output is read as usual.
2. Press **NVDA+Alt+C** to turn on CLI mode. Now the arrow keys read the output by character, word, line or paragraph, as in a word processor. Shift with the arrow keys selects, and Control+C copies.
3. Press **H** in CLI mode to hear every key. Press **Escape** to go back to typing.
4. Try an interactive installer such as `npx create-next-app@latest`: the arrow keys now say only the choice you move to.

## What it adds

### Interactive prompts (selection lists, checkboxes and yes/no toggles)

Many command line tools ask questions with menus you move through with the arrow keys. Without help, NVDA either reads the whole list again on every key press or says nothing, because only the colour of the text changes. CLI Helper recognises these prompts on screen and speaks them properly:

* When a prompt appears you hear the question, how many choices there are, and the current choice, once. For example: "Which framework, list, 4 choices, React, 2 of 4". The choices themselves are not read out one after another.
* Up and Down arrow speak only the newly focused choice and its position.
* In checkbox lists, Space speaks whether the choice is now checked or not checked.
* For yes/no toggles (Left and Right arrow, as in create-next-app's "Would you like to use TypeScript? No / Yes"), the add-on tells you which answer is selected. It works this out from the text's underline or colour, so the terminal must report formatting. Windows Terminal and the Windows 11 console do; the old console does not. When the add-on cannot tell, it says so instead of guessing.
* In CLI mode, M reads the whole prompt: the question, every choice, its checked state and which one is current.

Recognised prompt styles: Inquirer and @inquirer/prompts, prompts (used by create-next-app), Enquirer selects, @clack/prompts (used by create-vite, Svelte's `sv` and others), Python's questionary and InquirerPy, and Go's survey. Both their Unicode symbols (❯ ◉ ◯ ● ○ ◼ ◻) and their plain ASCII fallbacks (> (*) ( ) [x] [ ] [+]) are recognised. When no prompt is on screen the arrow keys behave exactly as they do without the add-on, so command history and line editing are unchanged.

### CLI mode: NVDA+Alt+C

Press **NVDA+Alt+C** once; NVDA says "CLI mode". Until you press **Escape** (or NVDA+Alt+C again), single keys read, select and copy the terminal like a word processor instead of going to the shell. CLI mode stays on between keys, so you can read, then copy, then find, without pressing NVDA+Alt+C again. It switches off by itself when you move to another window, and it comes back after you close one of the add-on's own windows (help, settings, find, reader). NVDA's own commands, such as NVDA+T or the numpad review keys, keep working. A key with no command gives a low beep. If you would rather have such keys leave CLI mode and be typed, turn that on in settings.

#### Reading

| Key | Action |
| --- | --- |
| Left / Right Arrow | Previous / next character |
| Control+Left / Right Arrow | Previous / next word |
| Up / Down Arrow | Previous / next line |
| Control+Up / Down Arrow | Previous / next paragraph (a block of text between blank lines) |
| Home / End | Start / end of the line |
| Control+Home / Control+End | Top / bottom |
| Page Up / Page Down (or Shift+P / P) | Previous / next command prompt, that is the previous or next command |
| Space or L | Read the current line |
| A | Say all from here |
| 1 to 9 | Read that line counted from the bottom (1 is the newest output line) |

#### Selecting and copying

| Key | Action |
| --- | --- |
| Shift with any reading key | Select. For example Shift+Down Arrow selects a line, Control+Shift+Right Arrow a word, Shift+End to the end of the line, Control+Shift+Down Arrow a paragraph |
| Control+A | Select all terminal text, including output that scrolled off screen |
| Control+C | Copy the selection, or the current line if nothing is selected |
| C | Copy the current line |
| W | Copy the current word |
| Shift+C | Copy the current paragraph |
| Shift+1 to Shift+9 | Copy that line counted from the bottom |
| Escape | Clear the selection. Press Escape again to leave CLI mode |

While you select, NVDA says the text followed by "selected", or "unselected" when you move back towards where you started.

#### Commands and output

| Key | Action |
| --- | --- |
| O / Shift+O | Read / copy the output of the last command |
| T / Shift+T | Read / copy the command typed at the prompt |
| E / Shift+E | Next / previous line with an error or warning. The line is also copied to the clipboard, and NVDA says "copied" (copying can be turned off in settings) |
| M | Read the interactive prompt on screen, with all its choices |
| R / Shift+R | Read a summary of the last command's errors and warnings / copy them all, with file and line |
| Shift+H | Command history: every command in this terminal with its output |
| V | Open all terminal text in the reader window, at the last command |
| Shift+V | Open only the last command's output in the reader window |
| F or Control+F | Find text |
| N or F3 / Shift+N or Shift+F3 | Next / previous match |
| Q | Quiet mode on or off (stop or resume automatic reading of new output) |
| S | Settings |
| H, F1 or slash (/) | Help: the list of keys |
| Escape or NVDA+Alt+C | Leave CLI mode |

Every command can also be given its own shortcut in NVDA menu > Preferences > Input gestures > CLI Helper.

Character, word and line movement use NVDA's own review cursor commands, so speech, braille, "spell on double press" and your settings behave the same as with the numpad review keys.

### Command finished notice

When a command that ran for at least 5 seconds finishes (the shell prompt comes back), you hear "Command finished after 42 seconds". If its output contained errors, you hear "Command finished with errors", and then a short error summary (see below). With tones turned on in settings, two rising tones (or falling tones, for errors) come first. If you were in another window, for example your browser during a long `npm install`, you hear it as soon as you come back to the terminal. Change the number of seconds in settings, or set it to 0 to turn this off.

### Downloads and progress bars

Tools such as `ollama pull`, `pip install`, `npm install`, `winget`, `docker pull` and `git clone` redraw their progress bar many times a second. NVDA on its own reads every changed piece ("46", "2.2 GB/4.7", "1m39s", ...), which is hard to follow. CLI Helper recognises progress bars, transfer amounts, speeds and spinners, keeps them out of the automatic reading, and says something useful instead. For example, `ollama pull llama3` sounds like:

"pulling manifest. pulling, 0 percent. 26 percent. 51 percent. 75 percent. 100 percent. verifying sha256 digest. writing manifest. success."

Settings (Downloads and progress bars):

* **Progress bars and spinners**: speak the percentage at each step (default), beep with a pitch that rises as it progresses (like NVDA's own progress bar beeps), both, silent, or read every change as NVDA does without the add-on.
* **Speak progress every this many percent**: 25 by default (5 to 50).
* **Speak progress at most every this many seconds**: 3 by default. The final 100 percent is always spoken.

A spinner ("pulling manifest ⠋") is spoken once by its text, not every frame. A line is treated as progress only when it shows a bar, a transfer amount ("2.1 GB/4.7 GB"), a speed ("25 MB/s") or a spinner. A result such as "Coverage: 85%" or a line of numbers printed by your command is still read normally.

### Error summary: how it decides what to read

Error output is often long and repetitive. The summary picks out what matters:

1. **Problems are found** by the error pattern (error, failed, exception, ERR!, cannot, not recognized, denied, panic, warning...). Lines that report success, such as "0 errors" or "found 0 vulnerabilities", are ignored.
2. **Repeated lines become one problem.** A block of "npm ERR!" lines is one error, and the line that explains it ("404 Not Found - GET ...") is used rather than "code E404". A Python traceback is one error: its last line ("ValueError: bad value"), at the place it was raised.
3. **Errors are separated from warnings.** A line that only mentions warn, warning or deprecated is a warning.
4. **The location is found** on the problem line or the two lines around it, in the forms used by TypeScript, Next.js, ESLint, Rust, Go, Python and others ("./src/app/page.tsx:12:5", "--> src/main.rs:4:5"). Only the file name is spoken, not the whole path.
5. **Errors come first**, because the first error usually causes the others.

You hear for example: "2 errors, 1 warnings. Error 1: Type 'string' is not assignable to type 'number', page.tsx line 12".

Settings (Errors): read the summary when a long command finishes (on), how many errors to read in detail (1), the longest message read in characters (150; longer ones are cut at a word), and whether to say the file and line (on). R reads the summary at any time, and Shift+R copies every problem with its full path and line, ready to paste into an issue or a chat.

### Sounds for new output

Sounds are off by default, because speech already says everything. If you like, turn them on in settings: a low buzz for an error line, a middle tone for a warning, and a rising chirp for success ("done", "passed", "compiled successfully", "found 0 vulnerabilities"). Only one sound plays per burst of output, the most important one. Another setting adds short tones when CLI mode turns on and off, when an error line is copied, and when a long command finishes.

### Command history

In CLI mode, Shift+H opens a list of every command in this terminal, newest last, with the number of output lines and of errors and warnings, for example "npm run build, 42 lines, 2 errors". The output of the selected command appears below the list. Buttons copy the command or its output, or open the output in the reader window (Enter on the list does the same).

### Terminal detection

When a new PowerShell or Command Prompt window opens, NVDA sometimes gets focus for the window before its text area is ready, and then treats it as an ordinary window until you switch away and back. CLI Helper notices this and asks Windows which control really has the keyboard focus, so the terminal works at once. If you want confirmation that CLI Helper is active when focus arrives in a terminal, choose a short rising tone or the words "CLI Helper active" in settings (off by default).

### Reader window

V (whole terminal) and Shift+V (last output) open the text in a read-only, multi-line edit field. Every normal editing key works there, exactly as in WordPad or Word: arrows, Control+arrows for words and paragraphs, Shift to select, Control+C to copy, NVDA+Down Arrow for say all. Control+F finds text, F3 and Shift+F3 move to the next and previous match, and Escape closes the window. Use this for long output, such as build logs, that has scrolled out of the visible window.

### Other conveniences

* Quiet mode stops NVDA from reading new output automatically, which helps during very long installs. Turn it off to hear output again.

## Settings

NVDA menu > Preferences > Settings > CLI Helper. The settings are in groups:

* **Reading**: quiet mode; support interactive prompts; what happens when focus moves to a terminal (nothing by default, a tone, or speech).
* **Downloads and progress bars**: how progress is reported; every how many percent; at most every how many seconds.
* **Errors**: read an error summary when a long command finishes; number of errors read in detail; longest message; file and line; copy the error line when moving to an error; announce when a command finishes after this many seconds.
* **Sounds for new output**: errors, warnings, success, and short tones for CLI mode, copying and finished commands. All off by default.
* **Updates**: check GitHub for new versions automatically, always, or never; and a button to check now.
* **CLI mode and patterns**: whether keys without a command leave CLI mode; the shell prompt pattern, a regular expression for your prompt if it is unusual (the default recognises PowerShell `PS C:\>`, Command Prompt `C:\>`, bash, zsh and WSL `user@host:~$`, Git Bash `$ ` and the Python REPL `>>> `); the error pattern.

## Tips

* In Windows 11, Windows Terminal and the Windows Console both give NVDA formatting information, which the add-on needs to work out yes/no toggles. On Windows 10, install Windows Terminal (`winget install Microsoft.WindowsTerminal`) for the best results.
* Many tools can be asked not to prompt at all, which is often fastest. For example: `npx create-next-app@latest my-app --yes` (accept the recommended defaults) or `npx create-next-app@latest my-app --ts --eslint --tailwind --app --src-dir --use-npm --import-alias "@/*"`.
* Do not run CLI Helper together with another add-on that takes over the arrow keys in terminals (for example Console Toolkit or Terminal Access). Both would try to handle the same keys.

## Known limitations

* In the Windows Console (conhost), NVDA's review cursor stays inside the visible window, so in CLI mode the arrow keys, P, E and Find work on what is on screen. Use V to open everything, including output that scrolled away, in the reader window.
* Prompts drawn by full-screen programs (vim, htop, tmux menus, `less`) are not menus in this sense. Use CLI mode to read them.
* Prompt and error detection uses patterns. If your shell prompt looks unusual, set the prompt pattern in settings.

## Updating

* **From the NVDA Add-on Store** (once CLI Helper is listed there): NVDA 2024.3 and later tell you about add-on updates when NVDA starts.
* **From GitHub**: CLI Helper checks this project's releases once a day, about 20 seconds after NVDA starts. When there is a new version, a dialog shows what is new and offers **Download and install**, **Remind me later** or **Skip this version**. Installing goes through NVDA's usual add-on installation dialog. You can check right away with U in CLI mode, or with the "Check for updates now" button in settings. In settings you can also turn the check off. The default ("Automatic") leaves updates to the Add-on Store if the store is set to install updates by itself.

## Reporting problems and contributing

* Report a problem or suggest an idea on the [issues page](https://github.com/Naeem-hashmi/Nvidia-c-l-i-helper-/issues). Include your NVDA version, your terminal (for example Windows Terminal or Command Prompt), the command you ran, and if possible the NVDA log (NVDA menu > Tools > View log).
* Code contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
* What has changed in each version: [changelog.md](changelog.md).

## Building from source

On Windows, with [Python 3.13](https://www.python.org/) and [Git](https://git-scm.com/):

```powershell
git clone https://github.com/Naeem-hashmi/Nvidia-c-l-i-helper-.git
cd Nvidia-c-l-i-helper-
py -3.13 -m pip install scons==4.10.1 Markdown==3.10
py -3.13 -m SCons
```

This produces `cliHelper-1.3.0.nvda-addon`. Run the tests with `python -m unittest discover tests`. They need neither Windows nor NVDA.

## License and credits

CLI Helper is free software under the [GNU General Public License version 2](COPYING.txt), the same license as NVDA.

* Built with NV Access's [NVDA add-on template](https://github.com/nvaccess/AddonTemplate).
* Inspired by [Console Toolkit](https://github.com/mltony/nvda-console-toolkit), [Terminal Access for NVDA](https://github.com/PratikP1/Terminal-Access-for-NVDA), [TDSR](https://github.com/tspivey/tdsr) and [Speakup](https://github.com/linux-speakup/speakup).
