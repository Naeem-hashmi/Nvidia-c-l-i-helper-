# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""Pure text analysis for terminal screens.

Nothing in this module imports NVDA, so it can be unit tested on any platform.
It must stay compatible with Python 3.7 (NVDA 2019.3 - 2023.3).
"""

import re

#: Default regular expression recognising shell prompts at the start of a line.
#: Covers PowerShell, Command Prompt, bash/zsh (user@host), Git Bash / MSYS ($ on its own line),
#: root shells (#), and the Python REPL.
DEFAULT_PROMPT_REGEX = (
	r"^(?:"
	r"PS [^>\r\n]*>"  # PowerShell: PS C:\Users\me>
	r"|[A-Za-z]:\\[^>\r\n]*>"  # Command Prompt: C:\Users\me>
	r"|[\w.\-]+@[\w.\-]+[: ][^\r\n]*?[$#%>](?=\s|$)"  # bash / zsh / WSL: me@host:~/dir$
	r"|[$#%] "  # bare $ / # / % prompts (Git Bash second line, minimal shells)
	r"|>>> "  # Python REPL
	r")"
)

#: Default regular expression recognising lines that report a problem.
DEFAULT_ERROR_REGEX = (
	r"(?i)(?:\berr!|\b(?:error|errors|fatal|failed|failure|exception|traceback|"
	r"cannot|could not|not recognized|not recognised|denied|panic|warning|warn)\b)"
)

#: Characters used by prompt libraries to point at the focused choice.
POINTERS = ("\u276f", "\u203a", "\u00bb", "\u2192", "\u25b8", "\u25b6", "\u279c", ">")
#: Checkbox / radio markers meaning "selected".
CHECKED_MARKERS = (
	"[x]",
	"[X]",
	"[*]",
	"[+]",
	"(*)",
	"(x)",
	"[\u2713]",
	"[\u2714]",
	"\u25c9",
	"\u25cf",
	"\u25fc",
	"\u25a0",
	"\u2611",
	"\u2612",
	"\u2705",
)
#: Checkbox / radio markers meaning "not selected".
UNCHECKED_MARKERS = ("[ ]", "( )", "\u25ef", "\u25cb", "\u25fb", "\u25a1", "\u2610")
#: Checkbox markers meaning "focused and not selected" (@clack/prompts without Unicode).
FOCUSED_UNCHECKED_MARKERS = ("[\u2022]",)
#: Characters drawn as the frame of a prompt (for example by @clack/prompts).
FRAME_CHARS = "\u2502\u2503|\u2551\u250a\u2506 \t"
#: Symbols that start the question line of a prompt.
QUESTION_STARTS = ("?", "* ", "\u25c6", "\u25c7", "\u2714", "\u2716", "\u221a", "\u00d7", "\u2717", "\u2753")
#: Lines that are hints rather than choices.
HINT_RE = re.compile(
	r"(?i)(use arrow|arrow keys|\u2191\u2193|\u2191/\u2193|navigate|press <?space>?|"
	r"to select|to toggle|return to submit|enter to (confirm|submit)|\(move up and down)",
)
SEPARATOR_RE = re.compile(r"^[\s\u2500\u2501\-=_\u2550\u2574\u2576]+$")
TOGGLE_RE = re.compile(
	r"^(?P<question>.*?)\s+(?:\u203a|\u00bb|>|\u2026|\.\.\.)\s+(?P<a>[^/]+?)\s+/\s+(?P<b>[^/]+?)\s*$"
)


def compilePattern(pattern, fallback):
	"""Compile a user supplied pattern, falling back to the default if it is invalid."""
	try:
		return re.compile(pattern or fallback, re.MULTILINE)
	except re.error:
		return re.compile(fallback, re.MULTILINE)


def splitLines(text):
	"""Split terminal text into lines, dropping trailing blank lines."""
	lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
	while lines and not lines[-1].strip():
		lines.pop()
	return lines


def isPromptLine(line, promptRe):
	return bool(promptRe.match(line))


def commandFromLine(line, promptRe):
	"""Return the command typed after the prompt on this line, or None if it is not a prompt line."""
	m = promptRe.match(line)
	if not m:
		return None
	return line[m.end() :].strip()


def promptIndexes(lines, promptRe):
	return [i for i, line in enumerate(lines) if promptRe.match(line)]


def lastOutput(lines, promptRe):
	"""Return (command, outputLines) for the most recent command.

	If the last non-blank line is a prompt (the shell is waiting for input),
	the output is everything between the previous prompt and that one.
	Otherwise a command is still running, and its output so far is returned.
	"""
	prompts = promptIndexes(lines, promptRe)
	if not prompts:
		return None, [line for line in lines]
	last = prompts[-1]
	trailing = [line for line in lines[last + 1 :] if line.strip()]
	if trailing:
		start, end = last, len(lines)
	elif len(prompts) >= 2:
		start, end = prompts[-2], last
	else:
		return commandFromLine(lines[last], promptRe), []
	output = lines[start + 1 : end]
	while output and not output[0].strip():
		output.pop(0)
	while output and not output[-1].strip():
		output.pop()
	return commandFromLine(lines[start], promptRe), output


def nthLastLine(lines, n, promptRe):
	"""Return the nth (1 based) non-blank line counted from the bottom.

	The prompt the user is currently sitting on is skipped, so 1 is the newest output line.
	"""
	content = [line for line in lines if line.strip()]
	if content and promptRe.match(content[-1]) and not commandFromLine(content[-1], promptRe):
		content = content[:-1]
	if n < 1 or n > len(content):
		return None
	return content[-n]


def findLine(lines, start, direction, predicate):
	"""Return the index of the next line after start (in direction +1 or -1) matching predicate."""
	i = start + direction
	while 0 <= i < len(lines):
		if predicate(i):
			return i
		i += direction
	return None


def isParagraphStart(lines, i):
	"""A paragraph starts at a non-blank line that follows a blank line (or the top of the buffer)."""
	if not lines[i].strip():
		return False
	return i == 0 or not lines[i - 1].strip()


def paragraphAt(lines, i):
	"""Return the text of the paragraph containing line i."""
	if not 0 <= i < len(lines) or not lines[i].strip():
		return ""
	start = i
	while start > 0 and lines[start - 1].strip():
		start -= 1
	end = i
	while end + 1 < len(lines) and lines[end + 1].strip():
		end += 1
	return "\n".join(lines[start : end + 1])


# Interactive prompt (menu) detection


class MenuItem(object):
	def __init__(self, label, checked, focused, lineIndex):
		#: Visible text of the choice, without markers.
		self.label = label
		#: True / False for checkboxes and radio buttons, None when the choice has no state.
		self.checked = checked
		#: Whether a pointer marks this choice as focused.
		self.focused = focused
		#: Index of the line on the analysed screen.
		self.lineIndex = lineIndex

	def __repr__(self):
		return "MenuItem(%r, checked=%r, focused=%r)" % (self.label, self.checked, self.focused)


class Menu(object):
	SELECT = "select"
	CHECKBOX = "checkbox"
	TOGGLE = "toggle"

	def __init__(self, kind, question, items, focusIndex):
		self.kind = kind
		self.question = question
		self.items = items
		#: Index into items of the focused choice, or None if focus is only shown by colour.
		self.focusIndex = focusIndex
		#: Index of the first screen line belonging to the prompt (its question, or its first choice).
		#: Everything from here to the bottom of the screen is part of the prompt, including hint lines.
		self.startIndex = items[0].lineIndex if items else 0

	@property
	def focused(self):
		if self.focusIndex is None:
			return None
		return self.items[self.focusIndex]

	def signature(self):
		"""Identifies a prompt independently of where focus is."""
		return (self.kind, self.question, tuple(item.label for item in self.items))

	def state(self):
		"""Changes whenever focus moves or a choice is checked."""
		return (self.focusIndex, tuple(item.checked for item in self.items))

	def __repr__(self):
		return "Menu(%r, %r, %r, focus=%r)" % (self.kind, self.question, self.items, self.focusIndex)


def _stripFrame(line):
	return line.lstrip(FRAME_CHARS)


def _takeMarker(text, markers):
	for marker in markers:
		if text.startswith(marker):
			return marker, text[len(marker) :]
	return None, text


def parseChoiceLine(line):
	"""Analyse one line that may be a choice.

	Returns (label, checked, hasPointer) or None if the line cannot be a choice.
	"""
	text = _stripFrame(line)
	if not text.strip():
		return None
	pointer, rest = _takeMarker(text, POINTERS)
	if pointer is not None:
		# A pointer must be followed by a space or a checkbox marker, otherwise it is ordinary text
		# such as ">>" or "->foo".
		after = rest.lstrip(" ")
		if not rest or not (rest[0] == " " or _takeMarker(after, CHECKED_MARKERS + UNCHECKED_MARKERS)[0]):
			return None
		text = after
	checked = None
	marker, rest = _takeMarker(text, FOCUSED_UNCHECKED_MARKERS)
	if marker is not None:
		pointer = marker
		checked = False
		text = rest
	marker, rest = _takeMarker(text, CHECKED_MARKERS)
	if checked is not None:
		pass
	elif marker is not None and (not rest or rest[0] == " "):
		checked = True
		text = rest
	else:
		marker, rest = _takeMarker(text, UNCHECKED_MARKERS)
		if marker is not None and (not rest or rest[0] == " "):
			checked = False
			text = rest
	# The "prompts" library draws scroll arrows in front of the first and last visible choice.
	label = text.strip().lstrip("\u2191\u2193").strip()
	if not label:
		return None
	return label, checked, pointer is not None


def _isQuestionLine(line):
	text = _stripFrame(line).strip()
	return bool(text) and text.startswith(QUESTION_STARTS)


def _isBoundary(line, promptRe):
	text = _stripFrame(line).strip()
	if not text:
		return True
	if promptRe is not None and promptRe.match(line):
		return True
	return _isQuestionLine(line) or text.startswith(("\u2514", "\u250c", "\u2570", "\u256d", "\u2014"))


def _questionAbove(lines, index):
	"""Return (questionText, lineIndex) of the question at or above index, or ("", None)."""
	i = index
	while i >= 0:
		text = _stripFrame(lines[i]).strip()
		if text and _isQuestionLine(lines[i]):
			return text, i
		if not text and not lines[i].strip():
			return "", None
		i -= 1
	return "", None


def _parseToggle(lines, promptRe):
	"""Detect yes/no style toggles such as the ones in create-next-app."""
	for i in range(len(lines) - 1, max(-1, len(lines) - 6), -1):
		line = lines[i]
		text = _stripFrame(line).strip()
		if not text or text in ("\u2514", "\u2570", "\u2514\u2500", "\u2570\u2500", "\u2014"):
			continue
		# @clack/prompts confirm: "● Yes / ○ No"
		parts = [p.strip() for p in text.split(" / ")]
		if len(parts) == 2:
			states = []
			labels = []
			for part in parts:
				marker, rest = _takeMarker(part, CHECKED_MARKERS)
				if marker:
					states.append(True)
				else:
					marker, rest = _takeMarker(part, UNCHECKED_MARKERS)
					states.append(False if marker else None)
				labels.append(rest.strip())
			if None not in states and states.count(True) == 1:
				items = [MenuItem(labels[j], None, states[j], i) for j in range(2)]
				question, questionIndex = _questionAbove(lines, i - 1)
				menu = Menu(Menu.TOGGLE, question, items, states.index(True))
				menu.startIndex = i if questionIndex is None else questionIndex
				return menu
		# prompts toggle: "? Would you like to use TypeScript? › No / Yes"
		if _isQuestionLine(line):
			m = TOGGLE_RE.match(text)
			if m:
				items = [
					MenuItem(m.group("a").strip(), None, False, i),
					MenuItem(m.group("b").strip(), None, False, i),
				]
				menu = Menu(Menu.TOGGLE, m.group("question").strip(), items, None)
				menu.startIndex = i
				return menu
		break
	return None


def parseMenu(lines, promptRe=None, maxLines=40):
	"""Find an interactive choice prompt at the bottom of the screen.

	Recognises the rendering of the common JavaScript, Python and Go prompt libraries
	(inquirer, @inquirer/prompts, prompts, enquirer, @clack/prompts, questionary, survey, bubbletea lists).
	Returns a Menu or None.
	"""
	lines = list(lines)
	while lines and not lines[-1].strip():
		lines.pop()
	offset = max(0, len(lines) - maxLines)
	screen = lines[offset:]
	# Find the last line carrying a pointer, or failing that the last checkbox line.
	anchor = None
	for i in range(len(screen) - 1, -1, -1):
		if promptRe is not None and promptRe.match(screen[i]):
			# A shell prompt below the choices means the prompt is finished.
			if anchor is None:
				break
		parsed = parseChoiceLine(screen[i])
		if parsed and parsed[2]:
			anchor = i
			break
	if anchor is None:
		for i in range(len(screen) - 1, -1, -1):
			if promptRe is not None and promptRe.match(screen[i]):
				break
			parsed = parseChoiceLine(screen[i])
			if parsed and parsed[1] is not None:
				anchor = i
				break
	if anchor is None:
		return _withOffset(_parseToggle(screen, promptRe), offset)
	# Grow the block of choice lines around the anchor.
	start = anchor
	while start - 1 >= 0 and not _isBoundary(screen[start - 1], promptRe):
		start -= 1
	end = anchor
	while end + 1 < len(screen) and not _isBoundary(screen[end + 1], promptRe):
		end += 1
	items = []
	for i in range(start, end + 1):
		line = screen[i]
		if HINT_RE.search(line) or SEPARATOR_RE.match(_stripFrame(line) or "-"):
			continue
		parsed = parseChoiceLine(line)
		if not parsed:
			continue
		label, checked, hasPointer = parsed
		if not hasPointer and checked is None and line[:1] not in FRAME_CHARS:
			# Choices that are not focused are indented to line up with the focused one.
			# A flush-left line is ordinary output, such as npm's "> next dev".
			continue
		items.append(MenuItem(label, checked, hasPointer, i + offset))
	if len(items) < 2:
		return _withOffset(_parseToggle(screen, promptRe), offset)
	focusIndexes = [j for j, item in enumerate(items) if item.focused]
	states = [item.checked for item in items if item.checked is not None]
	# @clack/prompts select draws the focused choice as a filled radio and the rest as empty ones.
	if (
		not focusIndexes
		and len(states) == len(items)
		and states.count(True) == 1
		and _allRadio(screen, items, offset)
	):
		focusIndexes = [j for j, item in enumerate(items) if item.checked]
		for item in items:
			item.focused = item.checked
			item.checked = None
		states = []
	if len(focusIndexes) > 1:
		return None
	if not focusIndexes and not states:
		return None
	kind = Menu.CHECKBOX if len(states) >= max(2, len(items) - 1) else Menu.SELECT
	if kind == Menu.SELECT:
		for item in items:
			item.checked = None
	question, questionIndex = _questionAbove(screen, start - 1)
	menu = Menu(kind, question, items, focusIndexes[0] if focusIndexes else None)
	menu.startIndex = (start if questionIndex is None else questionIndex) + offset
	return menu


def _withOffset(menu, offset):
	"""Convert line indexes of a menu found in the last part of the screen to whole-screen indexes."""
	if menu is not None and offset:
		for item in menu.items:
			item.lineIndex += offset
		menu.startIndex += offset
	return menu


def _allRadio(screen, items, offset):
	for item in items:
		text = _stripFrame(screen[item.lineIndex - offset])
		if not text.startswith(("\u25cf", "\u25cb")):
			return False
	return True
