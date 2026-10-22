# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""CLI Helper: makes Command Prompt, PowerShell, Windows Terminal, WSL and other consoles
as comfortable to read as a document, and makes interactive prompts (selection lists,
checkboxes and yes/no toggles such as the ones in create-next-app) speak properly.

NVDA+Alt+C turns on CLI mode: until Escape, single keys read, select and copy terminal text
like a word processor, and run the add-on's commands. Keys are listed in MODE_GESTURES and HELP_TEXT.
"""

import addonHandler
import api
import core
import eventHandler
import globalCommands
import globalPluginHandler
import gui
import speech
import textInfos
import tones
import ui
import wx
from gui import settingsDialogs
from logHandler import log
from NVDAObjects.behaviors import Terminal
from scriptHandler import script

from . import compat
from . import history
from . import parsing
from . import problems
from . import reader
from . import terminal
from . import updater
from .common import (
	FOCUS_UNKNOWN_MESSAGE,
	SCRIPT_CATEGORY,
	conf,
	copyText,
	describeChoice,
	errorRe,
	isRoleTerminal,
	plainQuestion,
	problemsAsText,
	promptRe,
	summaryText,
	tone,
)
from .overlay import CLITerminal
from .settings import SettingsPanel

addonHandler.initTranslation()

#: Turns CLI mode on and off.
MODE_GESTURE = "kb:NVDA+alt+c"
#: How many lines a search for a paragraph, prompt, error or text will scan.
MAX_SCAN_LINES = 5000

# Keys of CLI mode. They act only while the mode is on; everything else keeps its normal meaning.
MODE_GESTURES = {
	# Reading, like the arrow keys in a word processor
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
	"kb:p": "nextPrompt",
	"kb:shift+p": "previousPrompt",
	"kb:space": "reviewCurrentLine",
	"kb:l": "reviewCurrentLine",
	"kb:a": "reviewSayAll",
	# Selecting, like Shift+arrows in a word processor
	"kb:shift+leftArrow": "selectPreviousCharacter",
	"kb:shift+rightArrow": "selectNextCharacter",
	"kb:control+shift+leftArrow": "selectPreviousWord",
	"kb:control+shift+rightArrow": "selectNextWord",
	"kb:shift+upArrow": "selectPreviousLine",
	"kb:shift+downArrow": "selectNextLine",
	"kb:control+shift+upArrow": "selectPreviousParagraph",
	"kb:control+shift+downArrow": "selectNextParagraph",
	"kb:shift+home": "selectToStartOfLine",
	"kb:shift+end": "selectToEndOfLine",
	"kb:control+shift+home": "selectToTop",
	"kb:control+shift+end": "selectToBottom",
	"kb:control+a": "selectAll",
	"kb:control+c": "copySelection",
	"kb:c": "copyLine",
	"kb:shift+c": "copyParagraph",
	"kb:w": "copyWord",
	# Output and commands
	"kb:o": "readLastOutput",
	"kb:shift+o": "copyLastOutput",
	"kb:t": "readCommand",
	"kb:shift+t": "copyCommand",
	"kb:m": "readMenu",
	"kb:r": "readErrorSummary",
	"kb:shift+r": "copyErrors",
	"kb:shift+h": "commandHistory",
	"kb:e": "nextError",
	"kb:shift+e": "previousError",
	"kb:v": "viewBuffer",
	"kb:shift+v": "viewLastOutput",
	"kb:f": "find",
	"kb:control+f": "find",
	"kb:n": "findNext",
	"kb:f3": "findNext",
	"kb:shift+n": "findPrevious",
	"kb:shift+f3": "findPrevious",
	"kb:q": "toggleQuietMode",
	"kb:s": "openSettings",
	"kb:u": "checkForUpdates",
	"kb:h": "help",
	"kb:f1": "help",
	"kb:/": "help",
	"kb:shift+/": "help",
	"kb:escape": "escape",
}
for _n in range(1, 10):
	MODE_GESTURES["kb:%d" % _n] = "readLine%d" % _n
	MODE_GESTURES["kb:shift+%d" % _n] = "copyLine%d" % _n
del _n


def isTerminal(obj):
	if obj is None:
		return False
	return isinstance(obj, (Terminal, CLITerminal)) or isRoleTerminal(obj)


#: Window classes of console hosts: Windows Console (conhost), Windows Terminal, and the pseudo console.
CONSOLE_WINDOW_CLASSES = ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "PseudoConsoleWindow")
CONSOLE_APPS = (
	"cmd",
	"powershell",
	"pwsh",
	"windowsterminal",
	"conhost",
	"openconsole",
	"wsl",
	"wslhost",
	"bash",
)


def isConsoleWindow(obj):
	"""Whether obj belongs to a console host, even if it is not the terminal text itself."""
	try:
		if obj.windowClassName in CONSOLE_WINDOW_CLASSES:
			return True
	except Exception:
		pass
	try:
		return obj.appModule.appName.lower() in CONSOLE_APPS
	except Exception:
		return False


def uiaFocusedTerminal():
	"""Ask UI Automation which control really has the keyboard focus, and return it if it is a terminal.

	When PowerShell or Command Prompt opens, NVDA sometimes receives focus for the console window
	before its text area exists, and then no focus event for the text area. NVDA would treat the
	window as an ordinary window until focus moved away and back. This finds the real terminal.
	"""
	try:
		import UIAHandler
		from NVDAObjects.UIA import UIA

		handler = UIAHandler.handler
		if handler is None:
			return None
		element = handler.clientObject.GetFocusedElement()
		element = element.buildUpdatedCache(handler.baseCacheRequest)
		obj = UIA(UIAElement=element)
	except Exception:
		log.debugWarning("CLI Helper: no UI Automation focus", exc_info=True)
		return None
	return obj if isTerminal(obj) else None


def _lineText(info):
	line = info.copy()
	line.expand(textInfos.UNIT_LINE)
	return line.text.rstrip("\r\n")


def _lineAbove(pos):
	above = pos.copy()
	if not above.move(textInfos.UNIT_LINE, -1):
		return ""
	return _lineText(above)


def _isParagraphStart(text, pos):
	return bool(text.strip()) and not _lineAbove(pos).strip()


def _ordered(a, b):
	return (a, b) if a.compareEndPoints(b, "startToStart") <= 0 else (b, a)


def _span(a, b):
	start, end = _ordered(a, b)
	span = start.copy()
	span.setEndPoint(end, "endToEnd")
	return span


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = SCRIPT_CATEGORY

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		self._modeActive = False
		#: Whether focus is in a terminal, to give the entry cue only when arriving.
		self._inTerminal = False
		#: CLI mode was paused for one of the add-on's dialogs and comes back with the terminal.
		self._modeSuspended = False
		self._lastSearch = ""
		self._clearSelection()
		settingsDialogs.NVDASettingsDialog.categoryClasses.append(SettingsPanel)
		try:
			updater.scheduleStartupCheck()
		except Exception:
			log.debugWarning("CLI Helper: could not schedule the update check", exc_info=True)

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
		if isTerminal(obj):
			if self._modeSuspended:
				self._modeSuspended = False
				self._bindMode()
				tone(880, 30)
			elif not self._inTerminal:
				self._announceTerminal()
			self._inTerminal = True
		else:
			self._inTerminal = False
			if self._modeActive:
				# Leaving the terminal (for example Alt+Tab) ends CLI mode.
				self._setMode(False, announce=False)
			if isConsoleWindow(obj):
				# The console may have focus without NVDA knowing its terminal yet; check once it has settled.
				for delay in (300, 1200):
					core.callLater(delay, self._recoverTerminalFocus)
		nextHandler()

	def _announceTerminal(self):
		"""Let the user know CLI Helper is working in this terminal, as set in settings."""
		entry = conf()["terminalEntry"]
		if entry == "tone":
			tones.beep(1100, 25)
			core.callLater(40, tones.beep, 1400, 25)
		elif entry == "speech":
			# Translators: Spoken when focus moves to a terminal, if set in settings.
			ui.message(_("CLI Helper active"))

	def _recoverTerminalFocus(self):
		focus = api.getFocusObject()
		if isTerminal(focus) or not isConsoleWindow(focus):
			# Already fine, or the user has moved on.
			return
		found = uiaFocusedTerminal()
		if found is not None:
			log.debug("CLI Helper: NVDA missed the focus of a terminal; sending it now")
			eventHandler.queueEvent("gainFocus", found)

	# CLI mode

	def getScript(self, gesture):
		found = super(GlobalPlugin, self).getScript(gesture)
		if not self._modeActive or found is not None or getattr(gesture, "isModifier", False):
			return found
		# NVDA's own commands, such as NVDA+T or the numpad review keys, keep working in CLI mode.
		try:
			if globalCommands.commands.getScript(gesture) is not None:
				return None
		except Exception:
			log.debugWarning("CLI Helper: could not look up NVDA command", exc_info=True)
		if conf()["unassignedKeysLeaveMode"]:
			self._setMode(False)
			return None
		return self.script_unassignedKey

	def _bindMode(self):
		self._modeActive = True
		self.bindGestures(MODE_GESTURES)

	def _unbindMode(self):
		self._modeActive = False
		for gestureId in MODE_GESTURES:
			try:
				self.removeGestureBinding(gestureId)
			except LookupError:
				pass

	def _setMode(self, on, announce=True):
		self._modeSuspended = False
		self._clearSelection()
		if on:
			obj = api.getFocusObject()
			try:
				info = obj.makeTextInfo(textInfos.POSITION_CARET)
			except Exception:
				info = obj.makeTextInfo(textInfos.POSITION_LAST)
			api.setReviewPosition(info)
			self._bindMode()
			tone(880, 40)
			if announce:
				# Translators: Reported when CLI mode is turned on.
				ui.message(_("CLI mode"))
		else:
			self._unbindMode()
			tone(440, 40)
			if announce:
				# Translators: Reported when CLI mode is turned off and keys go to the shell again.
				ui.message(_("Typing mode"))

	def _suspendForDialog(self):
		"""Pause CLI mode while one of the add-on's windows is open; it resumes back in the terminal."""
		if self._modeActive:
			self._unbindMode()
			self._modeSuspended = True

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_(
			"Turns CLI mode on or off. In CLI mode single keys read, select and copy terminal text; H lists them"
		),
		gesture=MODE_GESTURE,
	)
	def script_toggleMode(self, gesture):
		if self._modeActive:
			self._setMode(False)
		elif self._terminal():
			self._setMode(True)

	def script_unassignedKey(self, gesture):
		tones.beep(220, 60)

	def script_escape(self, gesture):
		if self._hasSelection():
			self._clearSelection()
			# Translators: Reported when Escape cancels the selection in CLI mode.
			ui.message(_("Selection cleared"))
		else:
			self._setMode(False)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Lists the keys of CLI mode"),
	)
	def script_help(self, gesture):
		self._suspendForDialog()
		ui.browseableMessage(HELP_TEXT, SCRIPT_CATEGORY, isHtml=True)

	# Helpers

	def _terminal(self):
		focus = api.getFocusObject()
		if isTerminal(focus):
			return focus
		if isConsoleWindow(focus):
			found = uiaFocusedTerminal()
			if found is not None:
				# Tell NVDA about the terminal it missed, then carry on with it.
				eventHandler.queueEvent("gainFocus", found)
				return found
		# Translators: Reported when a CLI Helper command is used outside a terminal.
		ui.message(_("Not in a terminal"))
		return None

	def _lastOutput(self, obj):
		return parsing.lastOutput(terminal.getBufferLines(obj), promptRe())

	def _reviewInTerminal(self):
		"""Return a copy of the review position, moving it into the focused terminal first if needed."""
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

	def _speakLine(self, pos):
		line = pos.copy()
		line.expand(textInfos.UNIT_LINE)
		speech.cancelSpeech()
		speech.speakTextInfo(line, unit=textInfos.UNIT_LINE, reason=compat.REASON_CARET)
		try:
			import braille

			braille.handler.handleReviewMove()
		except Exception:
			pass

	def _findLine(self, pos, direction, predicate):
		"""From pos, move line by line until predicate(lineText, position) is true. Returns the position or None."""
		pos = pos.copy()
		pos.expand(textInfos.UNIT_LINE)
		pos.collapse()
		for _i in range(MAX_SCAN_LINES):
			if not pos.move(textInfos.UNIT_LINE, direction):
				return None
			if predicate(_lineText(pos), pos):
				return pos
		return None

	def _moveReview(self, direction, predicate, notFound, copyFound=False):
		start = self._reviewInTerminal()
		if start is None:
			return
		self._clearSelection()
		pos = self._findLine(start, direction, predicate)
		if pos is None:
			tone(220, 60)
			ui.message(notFound)
			return
		api.setReviewPosition(pos)
		self._speakLine(pos)
		if copyFound and api.copyToClip(_lineText(pos).strip()):
			if conf()["tones"]:
				# A short high click tells that the line is on the clipboard.
				tone(1200, 20)
			else:
				# Translators: Said after an error line that was copied to the clipboard.
				ui.message(_("copied"))

	# Reading, using NVDA's own review commands so speech, braille and settings behave as usual

	def _nvdaReview(self, name, gesture):
		self._clearSelection()
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

	def script_reviewSayAll(self, gesture):
		self._nvdaReview("sayAll", gesture)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Moves to the next paragraph of terminal text"),
	)
	def script_nextParagraph(self, gesture):
		# Translators: Reported when there is no further paragraph.
		self._moveReview(1, _isParagraphStart, _("No next paragraph"))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Moves to the previous paragraph of terminal text"),
	)
	def script_previousParagraph(self, gesture):
		# Translators: Reported when there is no earlier paragraph.
		self._moveReview(-1, _isParagraphStart, _("No previous paragraph"))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Moves to the next shell prompt, that is the next command"),
	)
	def script_nextPrompt(self, gesture):
		pattern = promptRe()
		# Translators: Reported when there is no further prompt.
		self._moveReview(1, lambda text, pos: bool(pattern.match(text)), _("No next prompt"))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Moves to the previous shell prompt, that is the previous command"),
	)
	def script_previousPrompt(self, gesture):
		pattern = promptRe()
		# Translators: Reported when there is no earlier prompt.
		self._moveReview(-1, lambda text, pos: bool(pattern.match(text)), _("No previous prompt"))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Moves to the next line with an error or warning, and copies it if set in settings"),
	)
	def script_nextError(self, gesture):
		pattern = errorRe()
		self._moveReview(
			1,
			lambda text, pos: bool(pattern.search(text)),
			# Translators: Reported when there is no further error line.
			_("No next error"),
			copyFound=conf()["copyErrorLines"],
		)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_(
			"Moves to the previous line with an error or warning, and copies it if set in settings"
		),
	)
	def script_previousError(self, gesture):
		pattern = errorRe()
		self._moveReview(
			-1,
			lambda text, pos: bool(pattern.search(text)),
			# Translators: Reported when there is no earlier error line.
			_("No previous error"),
			copyFound=conf()["copyErrorLines"],
		)

	# Selecting and copying, like a word processor

	def _clearSelection(self):
		self._selAnchor = None
		self._selectAll = False

	def _hasSelection(self):
		return self._selAnchor is not None or self._selectAll

	def _select(self, findTarget):
		"""Extend the selection from the review position to findTarget(position), and speak the change."""
		pos = self._reviewInTerminal()
		if pos is None:
			return
		pos.collapse()
		self._selectAll = False
		if self._selAnchor is None or self._selAnchor.obj is not pos.obj:
			self._selAnchor = pos.copy()
		target = findTarget(pos.copy())
		if target is None or target.compareEndPoints(pos, "startToStart") == 0:
			tone(220, 40)
			return
		target.collapse()
		forward = target.compareEndPoints(pos, "startToStart") > 0
		fromAnchor = pos.compareEndPoints(self._selAnchor, "startToStart")
		selecting = fromAnchor == 0 or (fromAnchor > 0) == forward
		text = _span(pos, target).text
		api.setReviewPosition(target)
		speech.cancelSpeech()
		if len(text.strip()) <= 1:
			speech.speakSpelling(text if text.strip() else " ")
		else:
			speech.speakText(text.strip())
		# Translators: Spoken after text that was added to or removed from the selection.
		ui.message(_("selected") if selecting else _("unselected"))

	def _moved(self, unit, direction):
		def find(pos):
			return pos if pos.move(unit, direction) else None

		return find

	def _lineEdge(self, end):
		def find(pos):
			pos.expand(textInfos.UNIT_LINE)
			pos.collapse(end=end)
			if end:
				# Stay before the line break.
				text = pos.copy()
				text.move(textInfos.UNIT_CHARACTER, -1, endPoint="start")
				if text.text in ("\r", "\n", "\r\n"):
					pos.move(textInfos.UNIT_CHARACTER, -1)
			return pos

		return find

	def _documentEdge(self, end):
		def find(pos):
			info = pos.obj.makeTextInfo(textInfos.POSITION_ALL)
			info.collapse(end=end)
			return info

		return find

	def _paragraphEdge(self, direction):
		def find(pos):
			found = self._findLine(pos, direction, _isParagraphStart)
			if found is None:
				# No further paragraph: select to the top or bottom.
				return self._documentEdge(direction > 0)(pos)
			return found

		return find

	def script_selectPreviousCharacter(self, gesture):
		self._select(self._moved(textInfos.UNIT_CHARACTER, -1))

	def script_selectNextCharacter(self, gesture):
		self._select(self._moved(textInfos.UNIT_CHARACTER, 1))

	def script_selectPreviousWord(self, gesture):
		self._select(self._moved(textInfos.UNIT_WORD, -1))

	def script_selectNextWord(self, gesture):
		self._select(self._moved(textInfos.UNIT_WORD, 1))

	def script_selectPreviousLine(self, gesture):
		self._select(self._moved(textInfos.UNIT_LINE, -1))

	def script_selectNextLine(self, gesture):
		self._select(self._moved(textInfos.UNIT_LINE, 1))

	def script_selectPreviousParagraph(self, gesture):
		self._select(self._paragraphEdge(-1))

	def script_selectNextParagraph(self, gesture):
		self._select(self._paragraphEdge(1))

	def script_selectToStartOfLine(self, gesture):
		self._select(self._lineEdge(False))

	def script_selectToEndOfLine(self, gesture):
		self._select(self._lineEdge(True))

	def script_selectToTop(self, gesture):
		self._select(self._documentEdge(False))

	def script_selectToBottom(self, gesture):
		self._select(self._documentEdge(True))

	def script_selectAll(self, gesture):
		if not self._terminal():
			return
		self._selAnchor = None
		self._selectAll = True
		# Translators: Reported after Control+A in CLI mode.
		ui.message(_("All terminal text selected, Control+C to copy"))

	def script_copySelection(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		if self._selectAll:
			text = "\n".join(terminal.getBufferLines(obj))
		elif self._selAnchor is not None:
			pos = api.getReviewPosition().copy()
			pos.collapse()
			text = _span(self._selAnchor, pos).text
		else:
			# Nothing selected: copy the current line, as many editors do.
			self.script_copyLine(gesture)
			return
		count = len(text.splitlines()) or 1
		# Translators: Reported after copying the selection; {count} is a number of lines.
		copyText(text, _("Copied {count} lines").format(count=count) if count > 1 else _("Copied"))

	def script_copyLine(self, gesture):
		pos = self._reviewInTerminal()
		if pos is None:
			return
		line = _lineText(pos)
		# Translators: Reported after copying a line.
		copyText(line, _("Copied: {text}").format(text=line.strip()))

	def script_copyWord(self, gesture):
		pos = self._reviewInTerminal()
		if pos is None:
			return
		pos.expand(textInfos.UNIT_WORD)
		word = pos.text.strip()
		copyText(word, _("Copied: {text}").format(text=word))

	def script_copyParagraph(self, gesture):
		pos = self._reviewInTerminal()
		if pos is None:
			return
		pos.expand(textInfos.UNIT_LINE)
		pos.collapse()
		if not _lineText(pos).strip():
			copyText("", "")
			return
		start = pos.copy()
		while _lineAbove(start).strip():
			if not start.move(textInfos.UNIT_LINE, -1):
				break
		end = pos.copy()
		for _i in range(MAX_SCAN_LINES):
			below = end.copy()
			if not below.move(textInfos.UNIT_LINE, 1) or not _lineText(below).strip():
				break
			end = below
		end.expand(textInfos.UNIT_LINE)
		text = _span(start, end).text.rstrip("\r\n")
		count = len(text.splitlines())
		# Translators: Reported after copying a paragraph; {count} is a number of lines.
		copyText(text, _("Paragraph copied, {count} lines").format(count=count))

	# Output and commands

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
		# Translators: Reported after copying the output of the last command.
		copyText("\n".join(output), _("Output copied, {count} lines").format(count=len(output)))

	def _typedCommand(self, obj):
		"""Return (lineText, command): command is None when the caret is not on a prompt line."""
		try:
			info = obj.makeTextInfo(textInfos.POSITION_CARET)
			line = _lineText(info)
		except Exception:
			lines = terminal.getScreenLines(obj)
			line = lines[-1] if lines else ""
		return line, parsing.commandFromLine(line, promptRe())

	@compat.speakOnDemand
	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Reads the command typed at the prompt"),
	)
	def script_readCommand(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		line, command = self._typedCommand(obj)
		if command is None:
			# Translators: Reported for an empty line.
			ui.message(line.strip() or _("blank"))
		elif not command:
			# Translators: Reported when nothing is typed at the prompt.
			ui.message(_("No command typed"))
		else:
			ui.message(command)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Copies the command typed at the prompt"),
	)
	def script_copyCommand(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		line, command = self._typedCommand(obj)
		copyText(command or "", _("Copied: {text}").format(text=command))

	def _readNthLine(self, n, copy=False):
		obj = self._terminal()
		if not obj:
			return
		line = parsing.nthLastLine(terminal.getScreenLines(obj), n, promptRe())
		if line is None:
			ui.message(_("blank"))
		elif copy:
			copyText(line, _("Copied: {text}").format(text=line.strip()))
		else:
			speech.cancelSpeech()
			speech.speakText(line)

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
			parts.append(plainQuestion(menu))
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
		# Start at the last command, so its output is right below the cursor.
		prompts = parsing.promptIndexes(lines, promptRe())
		start = 0
		if len(prompts) >= 2:
			start = len("\n".join(lines[: prompts[-2]])) + (1 if prompts[-2] else 0)
		self._suspendForDialog()
		# Translators: Title of the reader window showing the whole terminal.
		wx.CallAfter(reader.show, _("Terminal text"), "\n".join(lines), start)

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
		self._suspendForDialog()
		wx.CallAfter(reader.show, title, "\n".join(output), 0)

	def _lastProblems(self, obj):
		command, output = self._lastOutput(obj)
		return problems.summarize(output, errorRe())

	@compat.speakOnDemand
	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Reads a summary of the errors and warnings of the last command"),
	)
	def script_readErrorSummary(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		speech.cancelSpeech()
		ui.message(summaryText(self._lastProblems(obj)))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Copies all errors and warnings of the last command, with their locations"),
	)
	def script_copyErrors(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		found = self._lastProblems(obj)
		# Translators: Reported after copying the errors of the last command.
		copyText(problemsAsText(found), _("{count} problems copied").format(count=len(found)))

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Opens the list of commands run in this terminal, with their output"),
	)
	def script_commandHistory(self, gesture):
		obj = self._terminal()
		if not obj:
			return
		pattern = errorRe()
		entries = []
		for command, output in parsing.commandBlocks(terminal.getBufferLines(obj), promptRe()):
			found = problems.summarize(output, pattern)
			errors = len([p for p in found if p.kind == problems.Problem.ERROR])
			entries.append((command, output, errors, len(found) - errors))
		if not entries:
			# Translators: Reported when no commands are found in the terminal.
			ui.message(_("No commands found"))
			return
		self._suspendForDialog()
		wx.CallAfter(history.show, entries)

	# Finding text

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Finds text in the terminal"),
	)
	def script_find(self, gesture):
		if not self._terminal():
			return
		self._suspendForDialog()

		def ask():
			gui.mainFrame.prePopup()
			# Translators: Prompt of the find dialog.
			text = wx.GetTextFromUser(_("Text to find in the terminal:"), _("Find"), self._lastSearch)
			gui.mainFrame.postPopup()
			if text:
				self._lastSearch = text
				# Search once the dialog has closed and the terminal has focus again.
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
		self._moveReview(direction, lambda text, pos: needle in text.lower(), _("Not found"))

	# Settings

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
		description=_("Checks GitHub for a new version of CLI Helper"),
	)
	def script_checkForUpdates(self, gesture):
		# Translators: Reported when a manual update check starts.
		ui.message(_("Checking for updates"))
		self._suspendForDialog()
		updater.checkInBackground(True)

	@script(
		# Translators: Description of a command in the Input Gestures dialog.
		description=_("Opens the CLI Helper settings"),
	)
	def script_openSettings(self, gesture):
		self._suspendForDialog()
		wx.CallAfter(compat.popupSettingsPanel, settingsDialogs.NVDASettingsDialog, SettingsPanel)


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

# Translators: Help listing the keys of CLI mode. Keep the HTML tags.
HELP_TEXT = _(
	"<h1>CLI Helper keys</h1>"
	"<p>Press NVDA+Alt+C to turn CLI mode on. Keys then read, select and copy the terminal instead of "
	"going to the shell. CLI mode stays on until you press Escape or NVDA+Alt+C again, "
	"or move to another window. NVDA's own commands keep working.</p>"
	"<h2>Reading</h2>"
	"<ul>"
	"<li>Left or Right Arrow: previous or next character</li>"
	"<li>Control+Left or Right Arrow: previous or next word</li>"
	"<li>Up or Down Arrow: previous or next line</li>"
	"<li>Control+Up or Down Arrow: previous or next paragraph</li>"
	"<li>Home or End: start or end of the line</li>"
	"<li>Control+Home or Control+End: top or bottom</li>"
	"<li>Page Up or Page Down (or Shift+P and P): previous or next command prompt</li>"
	"<li>Space or L: read the current line</li>"
	"<li>A: say all from here</li>"
	"<li>1 to 9: read that line counted from the bottom</li>"
	"</ul>"
	"<h2>Selecting and copying</h2>"
	"<ul>"
	"<li>Shift with any reading key above: select, for example Shift+Down Arrow selects a line "
	"and Control+Shift+Right Arrow selects a word</li>"
	"<li>Control+A: select all terminal text</li>"
	"<li>Control+C: copy the selection, or the current line if nothing is selected</li>"
	"<li>C: copy the current line</li>"
	"<li>W: copy the current word</li>"
	"<li>Shift+C: copy the current paragraph</li>"
	"<li>Shift+1 to Shift+9: copy that line counted from the bottom</li>"
	"<li>Escape: clear the selection; press again to leave CLI mode</li>"
	"</ul>"
	"<h2>Commands and output</h2>"
	"<ul>"
	"<li>O: read the output of the last command. Shift+O: copy it</li>"
	"<li>T: read the command typed at the prompt. Shift+T: copy it</li>"
	"<li>E or Shift+E: next or previous error or warning (also copied to the clipboard; "
	"this can be turned off in settings)</li>"
	"<li>M: read the interactive prompt on screen with all its choices</li>"
	"<li>R: read a summary of the last command's errors and warnings. Shift+R: copy them all</li>"
	"<li>Shift+H: command history, a list of every command with its output</li>"
	"<li>V: open all terminal text in a reader window. Shift+V: open only the last output</li>"
	"<li>F or Control+F: find. N or F3: next match. Shift+N or Shift+F3: previous match</li>"
	"</ul>"
	"<h2>Other</h2>"
	"<ul>"
	"<li>Q: quiet mode on or off (stop reading new output automatically)</li>"
	"<li>S: settings</li>"
	"<li>U: check for a new version of CLI Helper</li>"
	"<li>H, F1 or slash: this help</li>"
	"<li>Escape or NVDA+Alt+C: leave CLI mode</li>"
	"</ul>"
	"<h2>Without CLI mode</h2>"
	"<p>Interactive prompts (selection lists, checkboxes, yes/no toggles) are announced automatically: "
	"the arrow keys and Space speak only the choice that changed. When a long command finishes, "
	"two tones and a message tell you, or as soon as you come back to the terminal.</p>"
)
