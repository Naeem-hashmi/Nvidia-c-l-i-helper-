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

PROGRESS_MODES = (
	# Translators: A choice for how progress bars are reported.
	("speech", _("Speak the percentage at each step")),
	# Translators: A choice for how progress bars are reported.
	("tones", _("Beep, higher as it progresses")),
	# Translators: A choice for how progress bars are reported.
	("both", _("Speak and beep")),
	# Translators: A choice for how progress bars are reported.
	("silent", _("Silent")),
	# Translators: A choice for how progress bars are reported.
	("raw", _("Read every change, as NVDA does without the add-on")),
)
UPDATE_MODES = (
	# Translators: A choice for the update check.
	("auto", _("Automatic: check GitHub unless the Add-on Store updates add-ons by itself")),
	# Translators: A choice for the update check.
	("on", _("Always check GitHub once a day")),
	# Translators: A choice for the update check.
	("off", _("Never")),
)
ENTRY_MODES = (
	# Translators: A choice for what happens when focus moves to a terminal.
	("off", _("Nothing")),
	# Translators: A choice for what happens when focus moves to a terminal.
	("tone", _("Short rising tone")),
	# Translators: A choice for what happens when focus moves to a terminal.
	("speech", _('Say "CLI Helper active"')),
)


class SettingsPanel(settingsDialogs.SettingsPanel):
	# Translators: Title of the add-on's settings panel.
	title = _("CLI Helper")

	def _group(self, helper, label):
		box = wx.StaticBoxSizer(wx.VERTICAL, self, label=label)
		helper.addItem(box)
		return guiHelper.BoxSizerHelper(self, sizer=box)

	def _check(self, group, key, label):
		box = group.addItem(wx.CheckBox(self, label=label))
		box.SetValue(conf()[key])
		self._checks[key] = box

	def _spin(self, group, key, label, minimum, maximum):
		control = group.addLabeledControl(label, wx.SpinCtrl, min=minimum, max=maximum, initial=conf()[key])
		self._spins[key] = control

	def _choice(self, group, key, label, options):
		control = group.addLabeledControl(label, wx.Choice, choices=[text for value, text in options])
		values = [value for value, text in options]
		control.SetSelection(values.index(conf()[key]) if conf()[key] in values else 0)
		self._choices[key] = (control, values)

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self._checks = {}
		self._spins = {}
		self._choices = {}

		# Translators: A group of settings.
		group = self._group(helper, _("Reading"))
		# Translators: A setting of the add-on.
		self._check(group, "quietMode", _("&Quiet mode: do not read new output automatically"))
		self._check(
			group,
			"interactivePrompts",
			# Translators: A setting of the add-on.
			_("Support &interactive prompts (selection lists, checkboxes, yes/no toggles)"),
		)
		self._check(
			group,
			"promptHints",
			# Translators: A setting of the add-on.
			_("When a prompt appears, say which &keys answer it"),
		)
		self._spin(
			group,
			"statusEverySeconds",
			# Translators: A setting of the add-on.
			_("While a command runs without output, say its status every this many seconds (&0 = never):"),
			0,
			600,
		)
		self._choice(
			group,
			"terminalEntry",
			# Translators: A setting of the add-on.
			_("&When focus moves to a terminal:"),
			ENTRY_MODES,
		)

		# Translators: A group of settings.
		group = self._group(helper, _("Downloads and progress bars"))
		# Translators: A setting of the add-on.
		self._choice(group, "progressMode", _("&Progress bars and spinners:"), PROGRESS_MODES)
		# Translators: A setting of the add-on.
		self._spin(group, "progressStep", _("&Speak progress every this many percent:"), 5, 50)
		self._spin(
			group,
			"progressInterval",
			# Translators: A setting of the add-on.
			_("Speak progress at most every this many secon&ds:"),
			0,
			60,
		)

		# Translators: A group of settings.
		group = self._group(helper, _("Errors"))
		self._check(
			group,
			"summaryOnFinish",
			# Translators: A setting of the add-on.
			_("Read an error su&mmary when a long command finishes"),
		)
		# Translators: A setting of the add-on.
		self._spin(group, "summaryCount", _("&Number of errors read in detail:"), 1, 10)
		# Translators: A setting of the add-on.
		self._spin(group, "summaryMaxChars", _("&Longest error message read, in characters:"), 40, 1000)
		# Translators: A setting of the add-on.
		self._check(group, "summaryLocation", _("R&eport the file and line of each error"))
		self._check(
			group,
			"copyErrorLines",
			# Translators: A setting of the add-on.
			_("&Copy the error line to the clipboard when moving to an error"),
		)
		self._spin(
			group,
			"finishedAfterSeconds",
			# Translators: A setting of the add-on.
			_("&Announce when a command finishes if it ran at least this many seconds (0 = never):"),
			0,
			3600,
		)

		# Translators: A group of settings.
		group = self._group(helper, _("Sounds for new output"))
		# Translators: A setting of the add-on.
		self._check(group, "soundErrors", _("Low &buzz for errors"))
		# Translators: A setting of the add-on.
		self._check(group, "soundWarnings", _("Middle &tone for warnings"))
		# Translators: A setting of the add-on.
		self._check(group, "soundSuccess", _("Rising c&hirp for success (done, passed, compiled)"))
		self._check(
			group,
			"tones",
			# Translators: A setting of the add-on.
			_("Short tones for CLI mode on and off, copying, and &finished commands"),
		)

		# Translators: A group of settings.
		group = self._group(helper, _("Updates"))
		# Translators: A setting of the add-on.
		self._choice(
			group, "updateCheck", _("Check for new versions when NVDA starts, at most dail&y:"), UPDATE_MODES
		)
		# Translators: A button in the add-on's settings.
		checkButton = group.addItem(wx.Button(self, label=_("Check for &updates now")))
		checkButton.Bind(wx.EVT_BUTTON, self.onCheckNow)

		# Translators: A group of settings.
		group = self._group(helper, _("CLI mode and patterns"))
		self._check(
			group,
			"unassignedKeysLeaveMode",
			# Translators: A setting of the add-on.
			_("In CLI mode, keys without a command lea&ve the mode and are typed"),
		)
		self.promptPattern = group.addLabeledControl(
			# Translators: A setting of the add-on.
			_("Shell p&rompt pattern (regular expression, empty for the default):"),
			wx.TextCtrl,
		)
		self.promptPattern.SetValue(conf()["promptPattern"])
		self.errorPattern = group.addLabeledControl(
			# Translators: A setting of the add-on.
			_("Err&or pattern (regular expression, empty for the default):"),
			wx.TextCtrl,
		)
		self.errorPattern.SetValue(conf()["errorPattern"])

	def onCheckNow(self, evt):
		from . import updater

		updater.checkInBackground(True)

	def onSave(self):
		for key, box in self._checks.items():
			conf()[key] = box.GetValue()
		for key, control in self._spins.items():
			conf()[key] = control.GetValue()
		for key, (control, values) in self._choices.items():
			conf()[key] = values[max(0, control.GetSelection())]
		conf()["promptPattern"] = self.promptPattern.GetValue()
		conf()["errorPattern"] = self.errorPattern.GetValue()
