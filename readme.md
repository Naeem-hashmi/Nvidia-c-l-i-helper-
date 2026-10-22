# CLI Helper for NVDA

CLI Helper makes Command Prompt, PowerShell, Windows Terminal and other command line windows easier to use with the NVDA screen reader.

Without it, NVDA reads command line programs poorly:

* Menus where you choose with the arrow keys are read as a jumble of lines, or not at all.
* Download progress is read as a stream of changing numbers.
* Long output is hard to go back through, select and copy.
* While a slow command runs with no output, you cannot tell whether it is still working.

CLI Helper fixes these.

* Version: 1.4.0
* Works with NVDA 2019.3 to 2026.3, on Windows 10 and 11
* License: GNU General Public License version 2

## Download and install

1. [Download CLI Helper](https://github.com/Naeem-hashmi/Nvidia-c-l-i-helper-/releases/latest/download/cliHelper.nvda-addon).
2. Open the downloaded file. NVDA asks whether to install it. Choose Yes, then restart NVDA.

## What it does

* **Menus and questions.** When a program asks you to choose, for example `npx create-next-app`, you hear the question once, how to answer it, and the current choice. After that, each arrow key says only the new choice: "Pages Router, 2 of 3". This works for lists (Up and Down Arrow, then Enter), checkboxes (Space to check) and yes/no questions (Left and Right Arrow, or type y or n).
* **Progress.** Downloads and installs are read as "25 percent", "50 percent" and so on, instead of every changing number.
* **Status.** Press NVDA+Alt+I at any time to hear what is happening: "npm install running for 2 minutes, last output 40 seconds ago". When a command runs for a long time without output, CLI Helper tells you every 30 seconds that it is still running.
* **Finished commands.** When a command that took a while is done, you hear "Command finished after 42 seconds". If it failed, you also hear the first error, with its file and line.
* **CLI mode.** Press NVDA+Alt+C to read the terminal like a document. Move by character, word, line or paragraph, select with Shift, copy, find text, and jump between commands and errors. Press Escape to go back to typing.

## Keyboard shortcuts

### Anywhere in a terminal

| Key | Action |
| --- | --- |
| NVDA+Alt+C | Turn CLI mode on or off |
| NVDA+Alt+I | Status: what the terminal is doing |

### In CLI mode

Reading:

| Key | Action |
| --- | --- |
| Left and Right Arrow | Previous and next character |
| Control+Left and Right Arrow | Previous and next word |
| Up and Down Arrow | Previous and next line |
| Control+Up and Down Arrow | Previous and next paragraph |
| Home and End | Start and end of the line |
| Control+Home and Control+End | Top and bottom |
| Page Up and Page Down | Previous and next command |
| Space | Read the current line |
| A | Say all from here |
| 1 to 9 | Read a line counted from the bottom (1 is the newest) |

Selecting and copying:

| Key | Action |
| --- | --- |
| Shift with any reading key | Select |
| Control+A | Select everything |
| Control+C | Copy the selection, or the current line |
| C, W, Shift+C | Copy the current line, word or paragraph |
| Shift+1 to Shift+9 | Copy a line counted from the bottom |

Commands and output:

| Key | Action |
| --- | --- |
| O and Shift+O | Read and copy the output of the last command |
| T and Shift+T | Read and copy the command you typed |
| E and Shift+E | Next and previous error (the error line is also copied) |
| R and Shift+R | Read and copy a summary of the last command's errors |
| M | Read the menu or question on screen, with all its choices |
| I | Status |
| V and Shift+V | Open all text, or only the last output, in a window you can read like a document |
| Shift+H | List of the commands you ran, with their output |
| F, N and Shift+N | Find text, next match, previous match |

Other:

| Key | Action |
| --- | --- |
| Q | Quiet mode: stop or resume reading new output |
| S | Settings |
| U | Check for updates |
| H | Help: list of keys |
| Escape | Clear the selection; press again to leave CLI mode |

Any shortcut can be changed in NVDA menu > Preferences > Input gestures > CLI Helper.

## Settings

Open NVDA menu > Preferences > Settings > CLI Helper, or press S in CLI mode. You can, for example:

* turn the "how to answer" hints for menus on or off,
* change how often a silent command's status is announced, or turn it off,
* choose how progress is reported: percentages, beeps, or nothing,
* choose how much of an error summary is read,
* turn on sounds for errors, warnings and success (all off by default).

## Updates

CLI Helper checks for new versions when NVDA starts and offers to install them. Press U in CLI mode, or use the button in settings, to check right away.

## Help and contributing

Report problems or ideas on the [issues page](https://github.com/Naeem-hashmi/Nvidia-c-l-i-helper-/issues). To work on the code, see [CONTRIBUTING.md](CONTRIBUTING.md). Changes in each version are in [changelog.md](changelog.md).
