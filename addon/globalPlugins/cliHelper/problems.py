# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""Finding the important part of a command's errors.

Long error output is mostly noise: stack frames, repeated "npm ERR!" lines, code excerpts.
summarize() picks out each distinct problem, decides whether it is an error or a warning,
and finds the file and line it points to, so the add-on can say for example
"2 errors, 1 warning. Error 1: Type 'string' is not assignable to type 'number', page.tsx line 12".

Rules, in order:
1. Lines that report success ("0 errors", "found 0 vulnerabilities") are ignored.
2. A Python traceback counts as one error: the final "SomeError: message" line, located at the
   last 'File "...", line N' of the traceback (the place where it was raised).
3. Lines that start with the same tool prefix ("npm ERR!", "npm error", "yarn error") one after
   another are one problem; "code E404" style lines are skipped as the message.
4. Any other line matching the error pattern is a problem. It is a warning when it mentions
   "warn" or "deprecated" but no error word.
5. The location is taken from the problem line, or from the two lines before or after it
   ("./src/app/page.tsx:12:5", "--> src/main.rs:4:5", ESLint's "12:5  error" under a file name).

Nothing here imports NVDA. Python 3.7 compatible.
"""

import os
import re

NO_PROBLEM_RE = re.compile(
	r"(?i)\b(?:0|no|zero|without)\s+(?:errors?|warnings?|problems?|vulnerabilit(?:y|ies)|issues?|failures?)\b"
)
WARNING_RE = re.compile(r"(?i)\bwarn(?:ing)?s?\b|\bdeprecated\b")
ERROR_WORD_RE = re.compile(
	r"(?i)\berr!|\b(?:error|errors|fatal|failed|failure|exception|traceback|cannot|could not|"
	r"not recognized|not recognised|denied|panic)\b"
)
TOOL_PREFIX_RE = re.compile(r"^\s*(\S+\s+(?:ERR!|error|ERROR|ERR))(?:\s|$)")
CODE_ONLY_RE = re.compile(r"(?i)^(?:code|errno|syscall)\s+\S+$")
PY_FILE_RE = re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+)')
LOCATION_RE = re.compile(
	r"(?P<file>(?:[A-Za-z]:)?[\w.~@+\-/\\]*[\w\-]\.[A-Za-z][A-Za-z0-9]{0,5})"
	r"(?:[:(](?P<line>\d+)(?:[:,]\s?(?P<col>\d+))?)"
)
ESLINT_RE = re.compile(r"^\s*(?P<line>\d+):(?P<col>\d+)\s+(?:error|warning)\b")
STACK_FRAME_RE = re.compile(r"^\s+(?:at\s|File\s\")")
SUCCESS_RE = re.compile(
	r"(?i)\b(?:success(?:ful(?:ly)?)?|succeeded|passed|done|completed?|compiled|ready in|installed|added \d+ packages?)\b"
	r"|^\s*[\u2713\u2714\u221a]\s"
)


def classify(line, errorRe):
	""" "error", "warning", "success" or None, for choosing a sound for a line of new output."""
	if not line.strip() or NO_PROBLEM_RE.search(line):
		return "success" if NO_PROBLEM_RE.search(line) else None
	if errorRe.search(line):
		return _kind(line)
	if SUCCESS_RE.search(line):
		return "success"
	return None


class Problem(object):
	ERROR = "error"
	WARNING = "warning"

	def __init__(self, kind, message, lineIndex, file=None, line=None, column=None):
		self.kind = kind
		self.message = message
		self.lineIndex = lineIndex
		self.file = file
		self.line = line
		self.column = column

	def __repr__(self):
		return "Problem(%r, %r, file=%r, line=%r)" % (self.kind, self.message, self.file, self.line)


def _location(lines, index):
	"""Find (file, line, column) on the problem line, or near it."""
	order = [index, index - 1, index + 1, index - 2, index + 2]
	for i in order:
		if not 0 <= i < len(lines):
			continue
		text = lines[i]
		m = PY_FILE_RE.search(text)
		if m:
			return m.group("file"), int(m.group("line")), None
		m = LOCATION_RE.search(text)
		if m and m.group("line"):
			# Skip things that look like versions or URLs rather than files.
			if "://" not in text[max(0, m.start() - 3) : m.start() + 3]:
				col = m.group("col")
				return m.group("file"), int(m.group("line")), int(col) if col else None
	m = ESLINT_RE.match(lines[index])
	if m:
		# ESLint prints the file name on its own line above the list of problems.
		for i in range(index - 1, max(-1, index - 200), -1):
			text = lines[i].strip()
			if not text:
				break
			if not ESLINT_RE.match(lines[i]):
				return text, int(m.group("line")), int(m.group("col"))
		return None, int(m.group("line")), int(m.group("col"))
	return None, None, None


def _kind(text):
	if WARNING_RE.search(text) and not ERROR_WORD_RE.search(text):
		return Problem.WARNING
	return Problem.ERROR


def summarize(lines, errorRe):
	"""Return the list of Problems in lines, in order."""
	problems = []
	i = 0
	while i < len(lines):
		text = lines[i]
		stripped = text.strip()
		if not stripped or NO_PROBLEM_RE.search(stripped) or STACK_FRAME_RE.match(text):
			i += 1
			continue
		if stripped.startswith("Traceback (most recent call last)"):
			problem, i = _pythonTraceback(lines, i)
			if problem is not None:
				problems.append(problem)
			continue
		if not errorRe.search(text):
			i += 1
			continue
		prefixMatch = TOOL_PREFIX_RE.match(text)
		start = i
		if prefixMatch:
			prefix = prefixMatch.group(1)
			message = ""
			while i < len(lines) and lines[i].strip().startswith(prefix.strip()):
				rest = lines[i].strip()[len(prefix.strip()) :].strip()
				if rest and not message and not CODE_ONLY_RE.match(rest):
					message = rest
				i += 1
			message = message or stripped
		else:
			message = stripped
			i += 1
		file, line, column = _location(lines, start)
		problems.append(
			Problem(_kind(message if not prefixMatch else stripped), message, start, file, line, column)
		)
	return problems


def _pythonTraceback(lines, start):
	"""Return (Problem, nextIndex) for a Python traceback starting at lines[start]."""
	file = line = None
	i = start + 1
	while i < len(lines):
		text = lines[i]
		m = PY_FILE_RE.search(text)
		if m:
			file, line = m.group("file"), int(m.group("line"))
		if text.strip() and not text[:1].isspace():
			# The first line that is not indented ends the traceback: "ValueError: bad value".
			return Problem(Problem.ERROR, text.strip(), i, file, line), i + 1
		i += 1
	return None, i


def shorten(message, maxChars):
	"""Cut a message at a word boundary so it is at most about maxChars long."""
	message = " ".join(message.split())
	if maxChars <= 0 or len(message) <= maxChars:
		return message
	cut = message.rfind(" ", 0, maxChars)
	return message[: cut if cut > maxChars // 2 else maxChars].rstrip(" ,;:") + "…"


def fileLabel(path):
	return os.path.basename(path.replace("\\", "/").rstrip("/")) or path
