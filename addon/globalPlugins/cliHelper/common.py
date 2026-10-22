# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""Configuration and small helpers shared by the add-on's modules."""

import addonHandler
import config
import ui

from . import compat
from . import parsing
from . import problems as problemsModule

addonHandler.initTranslation()

CONFIG_SECTION = "cliHelper"
config.conf.spec[CONFIG_SECTION] = {
	"interactivePrompts": "boolean(default=True)",
	# When a prompt appears, also say which keys answer it.
	"promptHints": "boolean(default=True)",
	# While a command runs without output, say its status every this many seconds (0 = never).
	"statusEverySeconds": "integer(min=0, max=600, default=30)",
	"quietMode": "boolean(default=False)",
	# Progress bars and spinners: speech, tones, both, silent, or raw (read every change, as NVDA does).
	"progressMode": 'option("speech", "tones", "both", "silent", "raw", default="speech")',
	"progressStep": "integer(min=5, max=50, default=25)",
	"progressInterval": "integer(min=0, max=60, default=3)",
	# Error summary
	"summaryOnFinish": "boolean(default=True)",
	"summaryCount": "integer(min=1, max=10, default=1)",
	"summaryMaxChars": "integer(min=40, max=1000, default=150)",
	"summaryLocation": "boolean(default=True)",
	# Sounds. All off by default: speech says everything, sounds are an opt-in extra.
	"soundErrors": "boolean(default=False)",
	"soundWarnings": "boolean(default=False)",
	"soundSuccess": "boolean(default=False)",
	# Short tones for CLI mode on and off, copying, and finished commands.
	"tones": "boolean(default=False)",
	# What happens when focus lands in a terminal: off, tone or speech.
	"terminalEntry": 'option("off", "tone", "speech", default="off")',
	# Update check against GitHub releases: auto (unless the Add-on Store updates add-ons itself), on, off.
	"updateCheck": 'option("auto", "on", "off", default="auto")',
	"updateLastCheck": "integer(default=0)",
	"updateSkipVersion": "string(default='')",
	"copyErrorLines": "boolean(default=True)",
	"finishedAfterSeconds": "integer(min=0, max=3600, default=5)",
	"unassignedKeysLeaveMode": "boolean(default=False)",
	"promptPattern": "string(default='')",
	"errorPattern": "string(default='')",
}

# Translators: The category of this add-on's commands in the Input Gestures dialog.
SCRIPT_CATEGORY = _("CLI Helper")

# Translators: Reported when an interactive prompt shows its current choice only with colour
# and this terminal does not tell NVDA about colours (for example the legacy Windows Console).
FOCUS_UNKNOWN_MESSAGE = _("current choice shown only by colour, not detectable in this terminal")


def conf():
	return config.conf[CONFIG_SECTION]


def tone(hz, ms):
	"""A feedback tone, played only if tones are turned on in settings."""
	if conf()["tones"]:
		import tones

		tones.beep(hz, ms)


def promptRe():
	return parsing.compilePattern(conf()["promptPattern"], parsing.DEFAULT_PROMPT_REGEX)


def errorRe():
	return parsing.compilePattern(conf()["errorPattern"], parsing.DEFAULT_ERROR_REGEX)


def describeChoice(menu, item):
	parts = [item.label]
	if item.checked is not None:
		# Translators: State of a checkbox in an interactive prompt.
		parts.append(_("checked") if item.checked else _("not checked"))
	# Translators: Position of a choice in an interactive prompt, e.g. "2 of 5".
	parts.append(_("{index} of {count}").format(index=menu.items.index(item) + 1, count=len(menu.items)))
	return ", ".join(parts)


def plainQuestion(menu):
	"""The question without its symbols and key hints: "Pick a router", not "? Pick a router » - Use arrow-keys"."""
	return parsing.cleanQuestion(menu.question)


def copyText(text, message):
	"""Copy text to the clipboard and report message, or report that there was nothing to copy."""
	import api

	if text and text.strip() and api.copyToClip(text):
		ui.message(message)
		return True
	# Translators: Reported when there is nothing to copy.
	ui.message(_("Nothing to copy"))
	return False


def isRoleTerminal(obj):
	try:
		return obj.role == compat.ROLE_TERMINAL
	except Exception:
		return False


def summaryText(problems, count=None, maxChars=None, location=None):
	"""What to say about the problems of a command, following the user's settings.

	For example: "2 errors, 1 warning. Error 1: Cannot find module 'react', page.tsx line 3".
	"""
	if count is None:
		count = conf()["summaryCount"]
	if maxChars is None:
		maxChars = conf()["summaryMaxChars"]
	if location is None:
		location = conf()["summaryLocation"]
	errors = [p for p in problems if p.kind == problemsModule.Problem.ERROR]
	warnings = [p for p in problems if p.kind == problemsModule.Problem.WARNING]
	if not errors and not warnings:
		# Translators: Reported when the last command's output has no errors or warnings.
		return _("No errors or warnings")
	# Translators: Number of errors and warnings, e.g. "2 errors, 1 warnings".
	parts = [_("{errors} errors, {warnings} warnings").format(errors=len(errors), warnings=len(warnings))]
	# Errors first: the first error is usually the cause of the others.
	for n, problem in enumerate((errors or warnings)[:count]):
		if problem.kind == problemsModule.Problem.ERROR:
			# Translators: Introduces one error of a summary, e.g. "Error 1: ...".
			text = _("Error {n}: {message}")
		else:
			# Translators: Introduces one warning of a summary, e.g. "Warning 1: ...".
			text = _("Warning {n}: {message}")
		text = text.format(n=n + 1, message=problemsModule.shorten(problem.message, maxChars))
		if location and problem.file:
			if problem.line:
				# Translators: Where an error is, e.g. "page.tsx line 12".
				text += ", " + _("{file} line {line}").format(
					file=problemsModule.fileLabel(problem.file), line=problem.line
				)
			else:
				text += ", " + problemsModule.fileLabel(problem.file)
		parts.append(text)
	return ". ".join(parts)


def problemsAsText(problems):
	"""All problems, one per line with their location, for the clipboard."""
	out = []
	for problem in problems:
		where = ""
		if problem.file:
			where = problem.file + (":%d" % problem.line if problem.line else "") + ": "
		out.append(where + problem.message)
	return "\n".join(out)


def duration(seconds):
	"""Spoken duration: "45 seconds", "2 minutes 5 seconds", "1 hour 3 minutes"."""
	seconds = int(round(seconds))
	if seconds < 60:
		# Translators: A duration in seconds.
		return _("{seconds} seconds").format(seconds=seconds)
	minutes, seconds = divmod(seconds, 60)
	if minutes < 60:
		# Translators: A duration in minutes and seconds.
		return _("{minutes} minutes {seconds} seconds").format(minutes=minutes, seconds=seconds)
	hours, minutes = divmod(minutes, 60)
	# Translators: A duration in hours and minutes.
	return _("{hours} hours {minutes} minutes").format(hours=hours, minutes=minutes)


def answerHint(menu):
	"""Which keys answer an interactive prompt."""
	if menu.kind == parsing.Menu.TOGGLE:
		# Translators: How to answer a yes/no prompt.
		return _("Left and Right arrows to choose, or type y or n, then Enter")
	if menu.kind == parsing.Menu.CHECKBOX:
		# Translators: How to answer a list where several choices can be checked.
		return _("Up and Down arrows to move, Space to check or uncheck, Enter when done")
	# Translators: How to answer a list where one choice is picked.
	return _("Up and Down arrows to move, Enter to choose")
