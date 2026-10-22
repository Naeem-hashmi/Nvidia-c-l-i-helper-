# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""CLI Helper: makes Command Prompt, PowerShell, Windows Terminal, WSL and other consoles
as comfortable to read as a document, and makes interactive prompts (selection lists,
checkboxes and yes/no toggles such as the ones in create-next-app) speak properly.
"""

import time

import addonHandler
import api
import config
import core
import globalCommands
import globalPluginHandler
import gui
import speech
import textInfos
import tones
import ui
import wx
from gui import guiHelper, settingsDialogs
from logHandler import log
from NVDAObjects import NVDAObject
from NVDAObjects.behaviors import Terminal
from scriptHandler import script

from . import compat
from . import parsing
from . import reader
from . import terminal

addonHandler.initTranslation()

CONFIG_SECTION = "cliHelper"
config.conf.spec[CONFIG_SECTION] = {
	"interactivePrompts": "boolean(default=True)",
	"quietMode": "boolean(default=False)",
	"beepOnErrors": "boolean(default=False)",
	"promptPattern": "string(default='')",
	"errorPattern": "string(default='')",
}

# Translators: The category of this add-on's commands in the Input Gestures dialog.
SCRIPT_CATEGORY = _("CLI Helper")
#: Prefix gesture of the command layer.
LAYER_GESTURE = "kb:NVDA+alt+c"
#: How often (ms) and how many times to check the screen after a key press in an interactive prompt.
POLL_INTERVAL = 40
POLL_ATTEMPTS = 12
#: How many lines review navigation will scan when looking for a paragraph, prompt or error.
MAX_SCAN_LINES = 5000


def conf():
	return config.conf[CONFIG_SECTION]


def promptRe():
	return parsing.compilePattern(conf()["promptPattern"], parsing.DEFAULT_PROMPT_REGEX)


def errorRe():
	return parsing.compilePattern(conf()["errorPattern"], parsing.DEFAULT_ERROR_REGEX)


def isTerminal(obj):
	if obj is None:
		return False
	if isinstance(obj, (Terminal, CLITerminal)):
		return True
	try:
		return obj.role == compat.ROLE_TERMINAL
	except Exception:
		return False


# Translators: Reported when an interactive prompt shows its current choice only with colour
# and this terminal does not tell NVDA about colours (for example the legacy Windows Console).
FOCUS_UNKNOWN_MESSAGE = _("current choice shown only by colour, not detectable in this terminal")


def describeChoice(menu, item):
	parts = [item.label]
	if item.checked is not None:
		# Translators: State of a checkbox in an interactive prompt.
		parts.append(_("checked") if item.checked else _("not checked"))
	# Translators: Position of a choice in an interactive prompt, e.g. "2 of 5".
	parts.append(_("{index} of {count}").format(index=menu.items.index(item) + 1, count=len(menu.items)))
	return ", ".join(parts)


class CLITerminal(NVDAObject):
	"""Overlay class added to every terminal NVDA knows about.

	It sits in front of NVDA's own terminal classes, so it can filter the automatic reading of new text
	and take over the arrow keys while an interactive prompt is on screen.
	"""

	_cliMenuSignature = None
	_cliMenuState = None
	_cliSuppressUntil = 0.0
	_cliPendingAnnounce = None
	_cliPollToken = 0

	def initOverlayClass(self):
		self._cliScreenCache = (0.0, None)

	# Interactive prompts

	def cliDetectMenu(self, maxAge=0.0, cachedOnly=False):
		"""Return (menu, screenLines) for the interactive prompt on screen, or (None, lines).

		A result read less than maxAge seconds ago is reused. With cachedOnly, the screen is never read.
		"""
		stamp, cached = getattr(self, "_cliScreenCache", (0.0, None))
		if cached is not None and time.time() - stamp <= maxAge:
			return cached
		if cachedOnly:
			return (None, [])
		lines = terminal.getScreenLines(self)
		menu = parsing.parseMenu(lines, promptRe())
		if menu is not None and menu.focusIndex is None:
			menu.focusIndex = terminal.emphasisedIndex(self, menu)
		result = (menu, lines)
		self._cliScreenCache = (time.time(), result)
		return result

	def cliAnnounceMenu(self, menu, force=False, afterKey=False):
		"""Speak the prompt: the question and focused choice when it first appears, then only what changed."""
		signature = menu.signature()
		state = menu.state()
		previousSignature = self._cliMenuSignature
		previousState = self._cliMenuState
		self._cliMenuSignature = signature
		self._cliMenuState = state
		if not force and signature == previousSignature and state == previousState:
			return
		parts = []
		if force or signature != previousSignature:
			if menu.question:
				parts.append(menu.question.lstrip("?◆◇* ").strip())
			if menu.kind == parsing.Menu.TOGGLE:
				# Translators: Announced for a yes/no style prompt, followed by its two choices.
				parts.append(
					_("toggle, {first} or {second}").format(
						first=menu.items[0].label,
						second=menu.items[1].label,
					)
				)
			else:
				# Translators: Announced when a list of choices appears, e.g. "list, 4 choices".
				parts.append(_("list, {count} choices").format(count=len(menu.items)))
		item = menu.focused
		if (
			item is None
			and menu.kind == parsing.Menu.CHECKBOX
			and previousState
			and signature == previousSignature
		):
			# Focus is shown only by colour and could not be read; report the choice that was toggled.
			changed = [i for i, (old, new) in enumerate(zip(previousState[1], state[1])) if old != new]
			if len(changed) == 1:
				item = menu.items[changed[0]]
		if item is not None:
			if menu.kind == parsing.Menu.TOGGLE:
				parts.append(item.label)
			else:
				parts.append(describeChoice(menu, item))
		elif afterKey or (menu.kind == parsing.Menu.TOGGLE and signature != previousSignature):
			parts.append(FOCUS_UNKNOWN_MESSAGE)
		if parts:
			speech.cancelSpeech()
			ui.message(", ".join(parts))

	def cliMenuKey(self, gesture, fallbackScript):
		"""Handle an arrow key: inside an interactive prompt announce the new choice, otherwise act as NVDA would."""
		menu = None
		if conf()["interactivePrompts"]:
			try:
				menu, _lines = self.cliDetectMenu()
			except Exception:
				log.debugWarning("CLI Helper: menu detection failed", exc_info=True)
		if menu is None:
			original = getattr(super(CLITerminal, self), fallbackScript, None)
			if original is not None:
				original(gesture)
			else:
				gesture.send()
			return
		if self._cliMenuSignature != menu.signature():
			# The prompt appeared without being announced (e.g. automatic reading is off); remember it silently.
			self._cliMenuSignature = menu.signature()
			self._cliMenuState = menu.state()
		before = menu.state()
		gesture.send()
		self._cliSuppressUntil = time.time() + 1.0
		self._cliPollToken += 1
		token = self._cliPollToken
		# Toggles change only colour, so the text never changes; wait briefly then read the formatting.
		attempts = 3 if menu.kind == parsing.Menu.TOGGLE else POLL_ATTEMPTS
		core.callLater(POLL_INTERVAL, self._cliPollMenu, token, before, attempts, menu.kind)

	def _cliPollMenu(self, token, before, attemptsLeft, kind):
		if token != self._cliPollToken:
			return
		menu, _lines = self.cliDetectMenu()
		if menu is None:
			return
		if (menu.state() != before and kind != parsing.Menu.TOGGLE) or attemptsLeft <= 1:
			# Make sure a choice is always spoken after a key press, even when focus did not move
			# (for example at the end of a list that does not wrap).
			self._cliMenuState = None
			self.cliAnnounceMenu(menu, afterKey=True)
			return
		core.callLater(POLL_INTERVAL, self._cliPollMenu, token, before, attemptsLeft - 1, kind)

	def _cliScheduleMenuAnnounce(self):
		if self._cliPendingAnnounce is not None:
			try:
				self._cliPendingAnnounce.Stop()
			except Exception:
				pass

		def announce():
			self._cliPendingAnnounce = None
			if time.time() < self._cliSuppressUntil:
				# A key press is being handled; the poll will speak.
				return
			menu, _lines = self.cliDetectMenu()
			if menu is not None:
				self.cliAnnounceMenu(menu)

		self._cliPendingAnnounce = core.callLater(POLL_INTERVAL, announce)

	def _cliIsMenuText(self, text):
		"""Whether newly reported text belongs to an interactive prompt that is on screen."""
		if not conf()["interactivePrompts"]:
			return False
		stripped = text.strip()
		if not stripped:
			return False
		parsed = parsing.parseChoiceLine(text)
		hasMarker = (
			(parsed is not None and (parsed[2] or parsed[1] is not None))
			or stripped.startswith(parsing.QUESTION_STARTS)
			or parsing.TOGGLE_RE.match(stripped) is not None
		)
		if hasMarker:
			# Several lines usually arrive together, so reuse a very recent screen read,
			# but read again if the text is not on it (the screen changed since).
			maxAges = (0.15, 0.0)
		elif parsed is not None:
			# A plain line can only be an unfocused choice of a prompt detected moments ago
			# (its question or focused choice arrives first). Never read the screen for it,
			# so heavy output such as an npm install costs nothing.
			maxAges = (0.5,)
		else:
			return False
		for maxAge in maxAges:
			try:
				menu, lines = self.cliDetectMenu(maxAge=maxAge, cachedOnly=not hasMarker)
			except Exception:
				log.debugWarning("CLI Helper: menu detection failed", exc_info=True)
				return False
			if menu is None:
				continue
			menuLines = set(lines[item.lineIndex].strip() for item in menu.items)
			if menu.question:
				menuLines.add(menu.question.strip())
			# NVDA may report only the changed part of a line.
			if any(stripped in line for line in menuLines):
				return True
		return False

	@script(gesture="kb:upArrow")
	def script_cliUpArrow(self, gesture):
		self.cliMenuKey(gesture, "script_caret_moveByLine")

	@script(gesture="kb:downArrow")
	def script_cliDownArrow(self, gesture):
		self.cliMenuKey(gesture, "script_caret_moveByLine")

	@script(gesture="kb:leftArrow")
	def script_cliLeftArrow(self, gesture):
		self.cliMenuKey(gesture, "script_caret_moveByCharacter")

	@script(gesture="kb:rightArrow")
	def script_cliRightArrow(self, gesture):
		self.cliMenuKey(gesture, "script_caret_moveByCharacter")

	# Automatic reading of new output

	def _reportNewText(self, line):
		if conf()["quietMode"]:
			return
		if self._cliIsMenuText(line):
			self._cliScheduleMenuAnnounce()
			return
		if conf()["beepOnErrors"] and errorRe().search(line):
			tones.beep(330, 60)
		original = getattr(super(CLITerminal, self), "_reportNewText", None)
		if original is not None:
			original(line)
		else:
			speech.speakText(line)

	def event_UIA_notification(self, *args, **kwargs):
		# Windows Terminal can be set to read new output from UI Automation notifications.
		original = getattr(super(CLITerminal, self), "event_UIA_notification", None)
		if conf()["quietMode"]:
			return
		displayString = kwargs.get("displayString") or ""
		if displayString and any(self._cliIsMenuText(line) for line in displayString.splitlines()):
			self._cliScheduleMenuAnnounce()
			return
		if conf()["beepOnErrors"] and errorRe().search(displayString):
			tones.beep(330, 60)
		if original is not None:
			original(*args, **kwargs)


class SettingsPanel(settingsDialogs.SettingsPanel):
	# Translators: Title of the add-on's settings panel.
	title = _("CLI Helper")

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.interactivePrompts = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: A setting of the add-on.
				label=_("Support &interactive prompts (selection lists, checkboxes, yes/no toggles)"),
			)
		)
		self.interactivePrompts.SetValue(conf()["interactivePrompts"])
		self.quietMode = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: A setting of the add-on.
				label=_("&Quiet mode: do not read new output automatically"),
			)
		)
		self.quietMode.SetValue(conf()["quietMode"])
		self.beepOnErrors = helper.addItem(
			wx.CheckBox(
				self,
				# Translators: A setting of the add-on.
				label=_("&Beep when new output contains an error or warning"),
			)
		)
		self.beepOnErrors.SetValue(conf()["beepOnErrors"])
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
		conf()["interactivePrompts"] = self.interactivePrompts.GetValue()
		conf()["quietMode"] = self.quietMode.GetValue()
		conf()["beepOnErrors"] = self.beepOnErrors.GetValue()
		conf()["promptPattern"] = self.promptPattern.GetValue()
		conf()["errorPattern"] = self.errorPattern.GetValue()


# Single key commands available after pressing the layer gesture.
LAYER_GESTURES = {
	"kb:o": "readLastOutput",
	"kb:shift+o": "copyLastOutput",
	"kb:v": "viewLastOutput",
	"kb:b": "viewBuffer",
	"kb:c": "readCommand",
	"kb:m": "readMenu",
	"kb:r": "toggleReviewMode",
	"kb:q": "toggleQuietMode",
	"kb:e": "nextError",
	"kb:shift+e": "previousError",
	"kb:p": "nextPrompt",
	"kb:shift+p": "previousPrompt",
	"kb:f": "find",
	"kb:s": "openSettings",
	"kb:h": "layerHelp",
	"kb:escape": "exitLayer",
}
for _n in range(1, 10):
	LAYER_GESTURES["kb:%d" % _n] = "readLine%d" % _n
	LAYER_GESTURES["kb:shift+%d" % _n] = "copyLine%d" % _n
del _n

# Keys of review mode, which stays on until Escape is pressed.
REVIEW_GESTURES = {
	"kb:leftArrow": "reviewPreviousCharacter",
	"kb:rightArrow": "reviewNextCharacter",
	"kb:control+leftArrow": "reviewPreviousWord",
	"kb:control+rightArrow": "reviewNextWord",
	"kb:upArrow": "reviewPreviousLine",
	"kb:downArrow": "reviewNextLine",
	"kb:control+upArrow": "previousParagraph",
	"kb:control+downArrow": "nextParagraph",
	"kb:home": "reviewStartOfLine",
	"kb:end": "reviewEndOfLine",
	"kb:control+home": "reviewTop",
	"kb:control+end": "reviewBottom",
	"kb:pageUp": "previousPrompt",
	"kb:pageDown": "nextPrompt",
	"kb:e": "nextError",
	"kb:shift+e": "previousError",
	"kb:l": "reviewCurrentLine",
	"kb:space": "reviewCurrentLine",
	"kb:c": "copyReviewLine",
	"kb:f": "find",
	"kb:n": "findNext",
	"kb:shift+n": "findPrevious",
	"kb:escape": "toggleReviewMode",
}


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = SCRIPT_CATEGORY

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		self._layerActive = False
		self._reviewMode = False
		self._lastSearch = ""
		settingsDialogs.NVDASettingsDialog.categoryClasses.append(SettingsPanel)

	def terminate(self):
		try:
			settingsDialogs.NVDASettingsDialog.categoryClasses.remove(SettingsPanel)
		except ValueError:
			pass
		super(GlobalPlugin, self).terminate()

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		for cls in clsList:
			if not isinstance(cls, type):
				continue
			if issubclass(cls, Terminal) or cls.__dict__.get("role") == compat.ROLE_TERMINAL:
				clsList.insert(0, CLITerminal)
				return

	def event_gainFocus(self, obj, nextHandler):
		if self._reviewMode and not isTerminal(obj):
			self._setReviewMode(False, announce=False)
		nextHandler()

	# Command layer

	def getScript(self, gesture):
		found = super(GlobalPlugin, self).getScript(gesture)
		if not self._layerActive or getattr(gesture, "isModifier", False):
			return found
		self._exitLayer()
		if found is None:
			return self.script_layerUnknown
		if found == self.script_commandLayer:
			# Pressing the layer key again cancels the layer.
			return self.script_exitLayer
		return found

	def _enterLayer(self):
		self._layerActive = True
		self.bindGestures(LAYER_GESTURES)
		tones.beep(880, 40)

	def _exitLayer(self):
		if not self._layerActive:
			return
		self._layerActive = False
		for gestureId in LAYER_GESTURES:
			try:
				self.removeGestureBinding(gestureId)
			except LookupError:
				pass
		# Layer keys shadow review mode keys while the layer is open; restore them.
		if self._reviewMode:
			self.bindGestures(REVIEW_GESTURES)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("CLI Helper command layer: press this, then a single key (H lists the keys)"),
		gesture=LAYER_GESTURE,
	)
	def script_commandLayer(self, gesture):
		if self._layerActive:
			self._exitLayer()
			return
		self._enterLayer()

	def script_layerUnknown(self, gesture):
		tones.beep(220, 80)

	def script_exitLayer(self, gesture):
		tones.beep(440, 40)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Lists the keys of the CLI Helper command layer and review mode"),
	)
	def script_layerHelp(self, gesture):
		ui.browseableMessage(HELP_TEXT, SCRIPT_CATEGORY)

	# Helpers

	def _terminal(self):
		focus = api.getFocusObject()
		if isTerminal(focus):
			return focus
		# Translators: Reported when a CLI Helper command is used outside a terminal.
		ui.message(_("Not in a terminal"))
		return None

	def _lastOutput(self, obj):
		return parsing.lastOutput(terminal.getBufferLines(obj), promptRe())

	# Reading output

	@compat.speakOnDemand
	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Reads the output of the last command"),
	)
	def script_readLastOutput(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		command, output = self._lastOutput(obj)
		text = "\n".join(output).strip()
		if not text:
			# Translators: Reported when the last command printed nothing.
			ui.message(_("No output"))
			return
		speech.cancelSpeech()
		speech.speakText(text)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Copies the output of the last command to the clipboard"),
	)
	def script_copyLastOutput(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		command, output = self._lastOutput(obj)
		text = "\n".join(output)
		if text.strip() and api.copyToClip(text):
			# Translators: Reported after copying the output of the last command.
			ui.message(_("Output copied, {count} lines").format(count=len(output)))
		else:
			ui.message(_("No output"))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Opens the output of the last command in a window you can read like a document"),
	)
	def script_viewLastOutput(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		command, output = self._lastOutput(obj)
		if not "\n".join(output).strip():
			ui.message(_("No output"))
			return
		# Translators: Title of the reader window; {command} is the command that produced the output.
		title = _("Output of {command}").format(command=command) if command else _("Terminal output")
		wx.CallAfter(reader.show, title, "\n".join(output), 0)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_(
			"Opens all terminal text, including scrolled-off output, in a window you can read like a document"
		),
	)
	def script_viewBuffer(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		lines = terminal.getBufferLines(obj)
		text = "\n".join(lines)
		# Start at the beginning of the last command so the newest output is right below the cursor.
		prompts = parsing.promptIndexes(lines, promptRe())
		start = 0
		if len(prompts) >= 2:
			start = len("\n".join(lines[: prompts[-2]])) + (1 if prompts[-2] else 0)
		# Translators: Title of the reader window showing the whole terminal.
		wx.CallAfter(reader.show, _("Terminal text"), text, start)

	@compat.speakOnDemand
	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Reads the command typed at the prompt"),
	)
	def script_readCommand(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		try:
			info = obj.makeTextInfo(textInfos.POSITION_CARET)
			info.expand(textInfos.UNIT_LINE)
			line = info.text.rstrip("\r\n")
		except Exception:
			lines = terminal.getScreenLines(obj)
			line = lines[-1] if lines else ""
		command = parsing.commandFromLine(line, promptRe())
		if command is None:
			ui.message(line.strip() or _("blank"))
		elif not command:
			# Translators: Reported when nothing is typed at the prompt.
			ui.message(_("No command typed"))
		else:
			ui.message(command)

	def _readNthLine(self, n, copy=False):
		obj = self._terminal()
		if not obj:
			return
		line = parsing.nthLastLine(terminal.getScreenLines(obj), n, promptRe())
		if line is None:
			ui.message(_("blank"))
		elif copy:
			if api.copyToClip(line):
				# Translators: Reported after copying a line.
				ui.message(_("Copied: {line}").format(line=line))
		else:
			speech.cancelSpeech()
			speech.speakText(line)

	# Interactive prompts

	@compat.speakOnDemand
	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Reads the interactive prompt on screen: question, choices and their states"),
	)
	def script_readMenu(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		if not isinstance(obj, CLITerminal):
			ui.message(_("Not in a terminal"))
			return
		menu, _lines = obj.cliDetectMenu()
		if menu is None:
			# Translators: Reported when no interactive prompt is detected.
			ui.message(_("No interactive prompt detected"))
			return
		parts = []
		if menu.question:
			parts.append(menu.question.lstrip("?◆◇* ").strip())
		for item in menu.items:
			text = describeChoice(menu, item)
			if item is menu.focused:
				# Translators: Marks the focused choice when reading a whole prompt.
				text += ", " + _("current")
			parts.append(text)
		if menu.focused is None:
			parts.append(FOCUS_UNKNOWN_MESSAGE)
		speech.cancelSpeech()
		ui.message(". ".join(parts))

	# Modes

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Turns quiet mode on or off (automatic reading of new output)"),
	)
	def script_toggleQuietMode(self, gesture):
		conf()["quietMode"] = not conf()["quietMode"]
		if conf()["quietMode"]:
			# Translators: Reported when quiet mode is turned on.
			ui.message(_("Quiet mode on, new output is not read"))
		else:
			# Translators: Reported when quiet mode is turned off.
			ui.message(_("Quiet mode off"))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_(
			"Turns review mode on or off: arrow keys read the terminal like a document until Escape"
		),
	)
	def script_toggleReviewMode(self, gesture):
		if not self._reviewMode and not self._terminal():
			return
		self._setReviewMode(not self._reviewMode)

	def _setReviewMode(self, on, announce=True):
		self._reviewMode = on
		if on:
			obj = api.getFocusObject()
			try:
				info = obj.makeTextInfo(textInfos.POSITION_CARET)
			except Exception:
				info = obj.makeTextInfo(textInfos.POSITION_LAST)
			api.setReviewPosition(info)
			self.bindGestures(REVIEW_GESTURES)
			if announce:
				tones.beep(660, 50)
				# Translators: Reported when review mode is turned on.
				ui.message(_("Review mode, arrows read output, Escape to type"))
		else:
			for gestureId in REVIEW_GESTURES:
				try:
					self.removeGestureBinding(gestureId)
				except LookupError:
					pass
			if announce:
				tones.beep(330, 50)
				# Translators: Reported when review mode is turned off.
				ui.message(_("Typing mode"))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Opens the CLI Helper settings"),
	)
	def script_openSettings(self, gesture):
		wx.CallAfter(compat.popupSettingsPanel, settingsDialogs.NVDASettingsDialog, SettingsPanel)

	# Review navigation. Character, word and line movement reuse NVDA's own review commands,
	# so speech, braille and settings behave exactly as with the review cursor.

	def _nvdaReview(self, name, gesture):
		getattr(globalCommands.commands, "script_review_" + name)(gesture)

	def script_reviewPreviousCharacter(self, gesture):
		self._nvdaReview("previousCharacter", gesture)

	def script_reviewNextCharacter(self, gesture):
		self._nvdaReview("nextCharacter", gesture)

	def script_reviewPreviousWord(self, gesture):
		self._nvdaReview("previousWord", gesture)

	def script_reviewNextWord(self, gesture):
		self._nvdaReview("nextWord", gesture)

	def script_reviewPreviousLine(self, gesture):
		self._nvdaReview("previousLine", gesture)

	def script_reviewNextLine(self, gesture):
		self._nvdaReview("nextLine", gesture)

	def script_reviewCurrentLine(self, gesture):
		self._nvdaReview("currentLine", gesture)

	def script_reviewStartOfLine(self, gesture):
		self._nvdaReview("startOfLine", gesture)

	def script_reviewEndOfLine(self, gesture):
		self._nvdaReview("endOfLine", gesture)

	def script_reviewTop(self, gesture):
		self._nvdaReview("top", gesture)

	def script_reviewBottom(self, gesture):
		self._nvdaReview("bottom", gesture)

	def script_copyReviewLine(self, gesture):
		info = api.getReviewPosition().copy()
		info.expand(textInfos.UNIT_LINE)
		text = info.text.rstrip("\r\n")
		if text.strip() and api.copyToClip(text):
			ui.message(_("Copied: {line}").format(line=text))

	def _reviewInTerminal(self):
		"""Return the review position, moving it into the focused terminal first if needed."""
		obj = self._terminal()
		if not obj:
			return None
		pos = api.getReviewPosition()
		if getattr(pos, "obj", None) is not obj:
			try:
				pos = obj.makeTextInfo(textInfos.POSITION_CARET)
			except Exception:
				pos = obj.makeTextInfo(textInfos.POSITION_LAST)
			api.setReviewPosition(pos)
		return pos.copy()

	def _moveReview(self, direction, predicate, notFound):
		"""Move the review cursor line by line until predicate(lineText, lineAboveText) is true."""
		pos = self._reviewInTerminal()
		if pos is None:
			return
		pos.expand(textInfos.UNIT_LINE)
		pos.collapse()
		for _i in range(MAX_SCAN_LINES):
			if not pos.move(textInfos.UNIT_LINE, direction):
				break
			line = pos.copy()
			line.expand(textInfos.UNIT_LINE)
			text = line.text.rstrip("\r\n")
			if not predicate(text, lambda: _lineAbove(pos)):
				continue
			api.setReviewPosition(pos)
			speech.cancelSpeech()
			speech.speakTextInfo(line, unit=textInfos.UNIT_LINE, reason=compat.REASON_CARET)
			try:
				import braille

				braille.handler.handleReviewMove()
			except Exception:
				pass
			return
		tones.beep(220, 60)
		ui.message(notFound)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Moves the review cursor to the next paragraph of terminal text"),
	)
	def script_nextParagraph(self, gesture):
		# Translators: Reported when there is no further paragraph.
		self._moveReview(
			1, lambda text, above: bool(text.strip()) and not above().strip(), _("No next paragraph")
		)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Moves the review cursor to the previous paragraph of terminal text"),
	)
	def script_previousParagraph(self, gesture):
		self._moveReview(
			-1,
			lambda text, above: bool(text.strip()) and not above().strip(),
			# Translators: Reported when there is no earlier paragraph.
			_("No previous paragraph"),
		)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Moves the review cursor to the next shell prompt (the next command)"),
	)
	def script_nextPrompt(self, gesture):
		pattern = promptRe()
		# Translators: Reported when there is no further prompt.
		self._moveReview(1, lambda text, above: bool(pattern.match(text)), _("No next prompt"))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Moves the review cursor to the previous shell prompt (the previous command)"),
	)
	def script_previousPrompt(self, gesture):
		pattern = promptRe()
		# Translators: Reported when there is no earlier prompt.
		self._moveReview(-1, lambda text, above: bool(pattern.match(text)), _("No previous prompt"))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Moves the review cursor to the next line containing an error or warning"),
	)
	def script_nextError(self, gesture):
		pattern = errorRe()
		# Translators: Reported when there is no further error line.
		self._moveReview(1, lambda text, above: bool(pattern.search(text)), _("No next error"))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Moves the review cursor to the previous line containing an error or warning"),
	)
	def script_previousError(self, gesture):
		pattern = errorRe()
		# Translators: Reported when there is no earlier error line.
		self._moveReview(-1, lambda text, above: bool(pattern.search(text)), _("No previous error"))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Finds text in the terminal and moves the review cursor to it"),
	)
	def script_find(self, gesture):
		if not self._terminal():
			return

		def ask():
			gui.mainFrame.prePopup()
			# Translators: Prompt of the find dialog.
			text = wx.GetTextFromUser(_("Text to find in the terminal:"), _("Find"), self._lastSearch)
			gui.mainFrame.postPopup()
			if text:
				self._lastSearch = text
				# Searching starts after the dialog closes and focus has returned to the terminal.
				core.callLater(300, self._findFrom, -1)

		wx.CallAfter(ask)

	def script_findNext(self, gesture):
		self._findFrom(1)

	def script_findPrevious(self, gesture):
		self._findFrom(-1)

	def _findFrom(self, direction):
		if not self._lastSearch:
			self.script_find(None)
			return
		needle = self._lastSearch.lower()
		# Translators: Reported when the searched text is not found.
		self._moveReview(direction, lambda text, above: needle in text.lower(), _("Not found"))


def _lineAbove(pos):
	above = pos.copy()
	if not above.move(textInfos.UNIT_LINE, -1):
		return ""
	above.expand(textInfos.UNIT_LINE)
	return above.text.rstrip("\r\n")


def _makeLineScripts():
	for n in range(1, 10):

		def read(self, gesture, n=n):
			self._readNthLine(n)

		def copy(self, gesture, n=n):
			self._readNthLine(n, copy=True)

		# Translators: Description of a command in the Input Gestures dialog.
		read.__doc__ = _("Reads line {n} counted from the bottom of the terminal").format(n=n)
		read.category = SCRIPT_CATEGORY
		read.speakOnDemand = True
		# Translators: Description of a command in the Input Gestures dialog.
		copy.__doc__ = _("Copies line {n} counted from the bottom of the terminal").format(n=n)
		copy.category = SCRIPT_CATEGORY
		setattr(GlobalPlugin, "script_readLine%d" % n, read)
		setattr(GlobalPlugin, "script_copyLine%d" % n, copy)


_makeLineScripts()

# Translators: Help shown by the "h" key of the command layer. Keep the HTML tags.
HELP_TEXT = _(
	"<h1>CLI Helper keys</h1>"
	"<p>Press NVDA+Alt+C, then one key:</p>"
	"<ul>"
	"<li>O: read the output of the last command. Shift+O: copy it.</li>"
	"<li>V: open the last output in a reader window (navigate like a document, Control+F to find).</li>"
	"<li>B: open all terminal text, including scrolled-off output, in the reader window.</li>"
	"<li>1 to 9: read that line counted from the bottom. Shift+1 to 9: copy it.</li>"
	"<li>C: read the command typed at the prompt.</li>"
	"<li>M: read the interactive prompt on screen with all choices.</li>"
	"<li>R: review mode on or off.</li>"
	"<li>Q: quiet mode on or off.</li>"
	"<li>P / Shift+P: next / previous prompt. E / Shift+E: next / previous error.</li>"
	"<li>F: find text. S: settings. H: this help. Escape: cancel.</li>"
	"</ul>"
	"<h2>Review mode</h2>"
	"<p>Keys read the terminal instead of going to the shell, until Escape:</p>"
	"<ul>"
	"<li>Left / Right: character. Control+Left / Right: word.</li>"
	"<li>Up / Down: line. Control+Up / Down: paragraph.</li>"
	"<li>Home / End: start / end of line. Control+Home / End: top / bottom.</li>"
	"<li>Page Up / Page Down: previous / next command prompt.</li>"
	"<li>E / Shift+E: next / previous error. F: find, N / Shift+N: next / previous match.</li>"
	"<li>L or Space: read current line. C: copy current line.</li>"
	"</ul>"
)
