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

addonHandler.initTranslation()

CONFIG_SECTION = "cliHelper"
config.conf.spec[CONFIG_SECTION] = {
	"interactivePrompts": "boolean(default=True)",
	"quietMode": "boolean(default=False)",
	"beepOnErrors": "boolean(default=False)",
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
	return menu.question.lstrip("?◆◇* ").strip()


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
