# Changelog

## 1.2.0

* New: downloads and progress bars. Tools such as ollama, pip, npm, winget, docker and git redraw their progress many times a second, and NVDA used to read every changing number. Progress is now read as a percentage every 25 percent (configurable), as rising beeps, both, or not at all. Spinners are read once by their text. The final 100 percent is always spoken.
* New: error summary. R in CLI mode reads how many errors and warnings the last command had, and the first error with its file and line; Shift+R copies all of them. The summary is also read when a long command finishes. How many errors, how long a message and whether to include locations are settings.
* New: sounds for new output: a low buzz for errors, a middle tone for warnings, a rising chirp for success. Each can be turned off.
* New: command history (Shift+H in CLI mode): every command in the terminal with its output, which can be copied or opened in the reader.
* Fixed: a newly opened PowerShell or Command Prompt window was not recognised as a terminal until focus left and came back. CLI Helper now asks Windows which control really has focus. A short tone (or speech, or nothing, as set) confirms that CLI Helper is active when focus arrives in a terminal.
* The settings panel is now organised in groups: Reading, Downloads and progress bars, Errors, Sounds, CLI mode and patterns.
* The "beep on errors" setting is replaced by the new sound settings.

## 1.1.0

* CLI mode replaces the one-key command layer and the separate review mode. NVDA+Alt+C turns it on, and it stays on until Escape, so reading, copying and finding work without pressing NVDA+Alt+C before every key.
* New: word-processor style selection. Shift with any reading key selects by character, word, line or paragraph; Control+A selects all; Control+C copies. C, W and Shift+C copy the current line, word and paragraph.
* New: moving to an error (E / Shift+E) also copies the error line. This can be turned off in settings.
* New: when a long command finishes, two tones and a message tell you, also when you come back from another window.
* New: H, F1 or slash opens help. V opens all terminal text, Shift+V the last output. T and Shift+T read and copy the typed command. A says all from the current position.
* Fixed: when a selection list appeared, all of its choices were read before the current one. NVDA can report only fragments of changed lines; these are now recognised as part of the prompt.
* Fixed: for yes/no toggles on a screen with more than 40 lines, the wrong line was checked for underline and colour.
* Fixed: the keyboard shortcut tables in the add-on help page were shown as plain text.

## 1.0.0

* First release.
