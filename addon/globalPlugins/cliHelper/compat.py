# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""Small shims so the add-on runs on every NVDA release from 2019.3 to the current one.

NVDA renamed or moved a few APIs over the years. Everything version dependent lives here.
"""

import controlTypes

try:
	# NVDA 2021.2 and later.
	ROLE_TERMINAL = controlTypes.Role.TERMINAL
except AttributeError:
	ROLE_TERMINAL = controlTypes.ROLE_TERMINAL

try:
	# NVDA 2021.1 and later.
	REASON_CARET = controlTypes.OutputReason.CARET
except AttributeError:
	REASON_CARET = controlTypes.REASON_CARET

# UI Automation enumeration values, defined by Windows and stable across NVDA versions.
UIA_TEXT_UNIT_LINE = 3
UIA_ENDPOINT_START = 0
UIA_ENDPOINT_END = 1


def popupSettingsPanel(dialogClass, panelClass):
	"""Open NVDA's settings dialog on the given panel."""
	import gui

	frame = gui.mainFrame
	# popupSettingsDialog was added in NVDA 2024.x; older releases only have the private name.
	popup = getattr(frame, "popupSettingsDialog", None) or getattr(frame, "_popupSettingsDialog")
	popup(dialogClass, panelClass)


def speakOnDemand(func):
	"""Mark a script as allowed in "on-demand" speech mode (NVDA 2024.1+); harmless before that."""
	func.speakOnDemand = True
	return func


class FormatConfig(dict):
	"""documentFormatting configuration with the options needed to read colour and underline forced on.

	Keys that are not overridden are read from the user's configuration, so this works with
	both the old (reportFontAttributes) and new (fontAttributeReporting) option names.
	"""

	def __init__(self):
		super(FormatConfig, self).__init__(
			reportColor=True,
			reportFontAttributes=True,
			fontAttributeReporting=1,
		)

	def __missing__(self, key):
		import config

		return config.conf["documentFormatting"][key]

	def get(self, key, default=None):
		try:
			return self[key]
		except KeyError:
			return default
