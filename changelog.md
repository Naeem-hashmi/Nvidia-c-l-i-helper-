# Changelog

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
