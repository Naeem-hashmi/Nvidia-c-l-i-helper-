# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""The add-on's panel in NVDA's settings dialog."""

import addonHandler
import wx
from gui import guiHelper, settingsDialogs

from .common import conf

addonHandler.initTranslation()

BOOLEAN_OPTIONS = (
	# Translators: A setting of the add-on.
	("interactivePrompts", _("Support &interactive prompts (selection lists, checkboxes, yes/no toggles)")),
	# Translators: A setting of the add-on.
	("quietMode", _("&Quiet mode: do not read new output automatically")),
	# Translators: A setting of the add-on.
	("beepOnErrors", _("&Beep when new output contains an error or warning")),
	# Translators: A setting of the add-on.
	("copyErrorLines", _("&Copy the error line to the clipboard when moving to an error")),
	# Translators: A setting of the add-on.
	("unassignedKeysLeaveMode", _("In CLI mode, keys without a command &leave the mode and are typed")),
)


class SettingsPanel(settingsDialogs.SettingsPanel):
	# Translators: Title of the add-on's settings panel.
	title = _("CLI Helper")

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self._checkBoxes = {}
		for key, label in BOOLEAN_OPTIONS:
			box = helper.addItem(wx.CheckBox(self, label=label))
			box.SetValue(conf()[key])
			self._checkBoxes[key] = box
		self.finishedAfter = helper.addLabeledControl(
			# Translators: A setting of the add-on.
			_("Announce when a command &finishes if it ran at least this many seconds (0 = never):"),
			wx.SpinCtrl,
			min=0,
			max=3600,
			initial=conf()["finishedAfterSeconds"],
		)
		self.promptPattern = helper.addLabeledControl(
			# Translators: A setting of the add-on.
			_("Shell &prompt pattern (regular expression, empty for the default):"),
			wx.TextCtrl,
		)
		self.promptPattern.SetValue(conf()["promptPattern"])
		self.errorPattern = helper.addLabeledControl(
			# Translators: A setting of the add-on.
			_("&Error pattern (regular expression, empty for the default):"),
			wx.TextCtrl,
		)
		self.errorPattern.SetValue(conf()["errorPattern"])

	def onSave(self):
		for key, box in self._checkBoxes.items():
			conf()[key] = box.GetValue()
		conf()["finishedAfterSeconds"] = self.finishedAfter.GetValue()
		conf()["promptPattern"] = self.promptPattern.GetValue()
		conf()["errorPattern"] = self.errorPattern.GetValue()
