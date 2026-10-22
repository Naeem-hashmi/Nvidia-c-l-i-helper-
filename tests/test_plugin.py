# Exercises the add-on's NVDA-facing logic against minimal stand-ins for NVDA's modules.
# This catches Python errors and logic bugs off Windows; behaviour with real terminals
# still has to be checked in NVDA (see docs/testing.md).
import os
import re
import sys
import types
import unittest

ADDON = os.path.join(os.path.dirname(__file__), "..", "addon", "globalPlugins")

spoken = []
beeps = []
clipboard = []
review = {"pos": None}


def _module(name, **attrs):
	mod = types.ModuleType(name)
	mod.__dict__.update(attrs)
	sys.modules[name] = mod
	return mod


class FakeTextInfo(object):
	"""A text range over a plain string, supporting what the add-on uses of NVDA's TextInfo."""

	def __init__(self, obj, start, end=None):
		self.obj = obj
		self.start = start
		self.end = start if end is None else end

	@property
	def _text(self):
		return self.obj.text

	@property
	def text(self):
		return self._text[self.start : self.end]

	def copy(self):
		return FakeTextInfo(self.obj, self.start, self.end)

	def collapse(self, end=False):
		if end:
			self.start = self.end
		else:
			self.end = self.start

	def _bounds(self, unit, offset):
		t = self._text
		if unit == "character":
			return offset, min(offset + 1, len(t))
		if unit == "line":
			s = t.rfind("\n", 0, offset) + 1
			e = t.find("\n", offset)
			return s, (e + 1 if e != -1 else len(t))
		if unit == "word":
			for m in re.finditer(r"\S+\s*|\s+", t):
				if m.start() <= offset < m.end():
					return m.start(), m.end()
			return offset, offset
		raise ValueError(unit)

	def expand(self, unit):
		self.start, self.end = self._bounds(unit, self.start)

	def move(self, unit, direction, endPoint=None):
		t = self._text
		pos = self.start if endPoint != "end" else self.end
		s, e = self._bounds(unit, pos)
		if direction > 0:
			new = e
			if new >= len(t):
				return 0
		else:
			if s == 0:
				return 0
			new = self._bounds(unit, s - 1)[0] if unit != "character" else pos - 1
		if endPoint == "start":
			self.start = new
		elif endPoint == "end":
			self.end = new
		else:
			self.start = self.end = new
		return direction

	def compareEndPoints(self, other, which):
		mine = self.start if which.startswith("start") else self.end
		theirs = other.start if which.endswith("Start") else other.end
		return (mine > theirs) - (mine < theirs)

	def setEndPoint(self, other, which):
		value = other.start if which.endswith("Start") else other.end
		if which.startswith("start"):
			self.start = value
		else:
			self.end = value


def installStubs():
	import builtins

	builtins._ = lambda s: s
	conf = {"cliHelper": {}, "documentFormatting": {"reportColor": False}}

	class _Conf(dict):
		spec = {}

	confObj = _Conf(conf)
	_module("addonHandler", initTranslation=lambda: None)
	_module("config", conf=confObj)

	class Role:
		TERMINAL = "terminal"

	class OutputReason:
		CARET = "caret"

	_module("controlTypes", Role=Role, OutputReason=OutputReason)

	def setReviewPosition(info, *args, **kwargs):
		review["pos"] = info.copy()

	_module(
		"api",
		copyToClip=lambda text: clipboard.append(text) or True,
		getFocusObject=lambda: None,
		getReviewPosition=lambda: review["pos"],
		setReviewPosition=setReviewPosition,
	)
	pending = []

	class _Later(object):
		def __init__(self, fn, args):
			self.fn, self.args, self.stopped = fn, args, False

		def Stop(self):
			self.stopped = True

	def callLater(ms, fn, *args):
		later = _Later(fn, args)
		pending.append(later)
		return later

	def runPending():
		while pending:
			later = pending.pop(0)
			if not later.stopped:
				later.fn(*later.args)

	_module("core", callLater=callLater, runPending=runPending)

	class NVDACommands(object):
		def getScript(self, gesture):
			return (lambda g: None) if gesture.id == "kb:nvda+t" else None

	_module("globalCommands", commands=NVDACommands())

	class ScriptableBase(object):
		def __init__(self):
			self._gestureMap = {}

		def bindGesture(self, gesture, name):
			self._gestureMap[gesture.lower()] = getattr(self, "script_" + name)

		def bindGestures(self, gestures):
			for g, n in gestures.items():
				self.bindGesture(g, n)

		def removeGestureBinding(self, gesture):
			del self._gestureMap[gesture.lower()]

		def getScript(self, gesture):
			return self._gestureMap.get(gesture.id)

		def terminate(self):
			pass

	_module("globalPluginHandler", GlobalPlugin=ScriptableBase)

	class SettingsPanel(object):
		pass

	class NVDASettingsDialog(object):
		categoryClasses = []

	settingsDialogs = _module(
		"gui.settingsDialogs", SettingsPanel=SettingsPanel, NVDASettingsDialog=NVDASettingsDialog
	)
	guiHelper = _module("gui.guiHelper")
	mainFrame = types.SimpleNamespace(popupSettingsDialog=lambda *a: None)
	_module("gui", settingsDialogs=settingsDialogs, guiHelper=guiHelper, mainFrame=mainFrame)
	_module(
		"speech",
		cancelSpeech=lambda: spoken.append("<cancel>"),
		speakText=lambda text: spoken.append(text),
		speakSpelling=lambda text: spoken.append("spell:" + text),
		speakTextInfo=lambda info, **k: spoken.append(info.text.rstrip("\n")),
	)
	_module(
		"textInfos",
		POSITION_ALL="all",
		POSITION_CARET="caret",
		POSITION_LAST="last",
		UNIT_LINE="line",
		UNIT_WORD="word",
		UNIT_CHARACTER="character",
		FieldCommand=type("FieldCommand", (), {}),
	)
	_module("tones", beep=lambda hz, ms: beeps.append(hz))
	_module("ui", message=lambda text: spoken.append(text), browseableMessage=lambda *a, **k: None)
	_module("wx", CallAfter=lambda fn, *a: fn(*a), Dialog=object)

	class _Log(object):
		def debugWarning(self, *a, **k):
			pass

		warning = error = exception = debugWarning

	_module("logHandler", log=_Log())

	class NVDAObject(object):
		def initOverlayClass(self):
			pass

		def event_gainFocus(self):
			pass

	class Terminal(NVDAObject):
		text = ""
		caret = 0

		def _reportNewLines(self, lines):
			for line in lines:
				self._reportNewText(line)

		def _reportNewText(self, line):
			spoken.append(line)

		def script_caret_moveByLine(self, gesture):
			spoken.append("<nvda caret line>")

		def script_flush_queuedChars(self, gesture):
			gesture.send()

		def makeTextInfo(self, position):
			if position == "caret":
				return FakeTextInfo(self, self.caret)
			if position == "all":
				return FakeTextInfo(self, 0, len(self.text))
			return FakeTextInfo(self, len(self.text))

	_module("NVDAObjects", NVDAObject=NVDAObject)
	_module("NVDAObjects.behaviors", Terminal=Terminal)

	def script(**kwargs):
		def wrap(fn):
			fn.__doc__ = kwargs.get("description")
			return fn

		return wrap

	_module("scriptHandler", script=script)
	return confObj


CONF = installStubs()
sys.path.insert(0, ADDON)
import cliHelper  # noqa: E402
from cliHelper import overlay  # noqa: E402
from cliHelper import terminal as cliTerminal  # noqa: E402

SCREEN = {"text": ""}
cliTerminal.getScreenText = lambda obj: SCREEN["text"]
cliTerminal.getBufferText = lambda obj: SCREEN["text"]
cliTerminal.lineStyles = lambda obj, index: None

import api  # noqa: E402
import core  # noqa: E402
from NVDAObjects.behaviors import Terminal  # noqa: E402


class Gesture(object):
	isModifier = False

	def __init__(self, gid, onSend=None):
		self.id = gid
		self.onSend = onSend
		self.sent = 0

	def send(self):
		self.sent += 1
		if self.onSend:
			self.onSend()


def makeTerminal(text=""):
	cls = type("T", (overlay.CLITerminal, Terminal), {})
	obj = cls()
	obj.initOverlayClass()
	obj.text = text
	return obj


class Base(unittest.TestCase):
	def setUp(self):
		del spoken[:]
		del beeps[:]
		del clipboard[:]
		CONF["cliHelper"].clear()
		CONF["cliHelper"].update(
			interactivePrompts=True,
			quietMode=False,
			beepOnErrors=False,
			copyErrorLines=True,
			finishedAfterSeconds=5,
			unassignedKeysLeaveMode=False,
			promptPattern="",
			errorPattern="",
		)
		SCREEN["text"] = ""


class OverlayTest(Base):
	def test_overlayIsAddedToTerminals(self):
		plugin = cliHelper.GlobalPlugin()
		clsList = [Terminal]
		plugin.chooseNVDAObjectOverlayClasses(None, clsList)
		self.assertIs(clsList[0], overlay.CLITerminal)
		clsList = [object]
		plugin.chooseNVDAObjectOverlayClasses(None, clsList)
		self.assertEqual(clsList, [object])

	def test_arrowFallsBackToNvdaOutsidePrompts(self):
		SCREEN["text"] = "PS C:\\> dir\na.txt\nPS C:\\> "
		obj = makeTerminal()
		gesture = Gesture("kb:uparrow")
		obj.script_cliUpArrow(gesture)
		self.assertEqual(spoken, ["<nvda caret line>"])
		self.assertEqual(gesture.sent, 0)

	def test_arrowInSelectPromptAnnouncesChoice(self):
		before = "? Pick a router\n\u276f App Router\n  Pages Router\n  None"
		after = "? Pick a router\n  App Router\n\u276f Pages Router\n  None"
		SCREEN["text"] = before
		obj = makeTerminal()
		gesture = Gesture("kb:downarrow", onSend=lambda: SCREEN.update(text=after))
		obj.script_cliDownArrow(gesture)
		# NVDA's diff reports the two changed lines; they must not be read.
		obj._reportNewLines(["  App Router", "\u276f Pages Router"])
		core.runPending()
		self.assertEqual(gesture.sent, 1)
		self.assertEqual(spoken[-1], "Pages Router, 2 of 3")
		self.assertNotIn("\u276f Pages Router", spoken)
		self.assertNotIn("  App Router", spoken)

	def test_newPromptIsIntroducedOnceWithoutReadingAllChoices(self):
		# The bug reported in 1.0.0: when a list appeared, every choice was read.
		SCREEN["text"] = (
			"PS C:\\dev> npx create-next-app@latest\n"
			"? Pick a router\n\u276f App Router\n  Pages Router\n  None\n\u2191\u2193 navigate \u2022 \u23ce select"
		)
		obj = makeTerminal()
		obj._reportNewLines(
			[
				"? Pick a router",
				"\u276f App Router",
				"  Pages Router",
				"  None",
				"\u2191\u2193 navigate \u2022 \u23ce select",
			]
		)
		core.runPending()
		self.assertEqual(spoken, ["<cancel>", "Pick a router, list, 3 choices, App Router, 1 of 3"])

	def test_fragmentsOfANewQuestionAreNotRead(self):
		# NVDA's character diff may report only the words that changed between two questions.
		SCREEN["text"] = "? Would you like to use ESLint? \u00bb No / Yes"
		obj = makeTerminal()
		obj._reportNewLines(["? Would you like to use ESLint? \u00bb No / Yes"])
		core.runPending()
		del spoken[:]
		SCREEN["text"] = (
			"\u221a Would you like to use ESLint? ... Yes\n? Would you like to use Tailwind CSS? \u00bb No / Yes"
		)
		obj._reportNewLines(["Tailwind CSS"])
		core.runPending()
		self.assertNotIn("Tailwind CSS", spoken)
		self.assertIn("Would you like to use Tailwind CSS?", spoken[-1])

	def test_checkboxToggleSpeaksOnlyTheChange(self):
		SCREEN["text"] = "? Select features\n\u276f\u25c9 TypeScript\n \u25ef ESLint"
		obj = makeTerminal()
		obj._reportNewLines(["? Select features", "\u276f\u25c9 TypeScript", " \u25ef ESLint"])
		core.runPending()
		SCREEN["text"] = "? Select features\n\u276f\u25ef TypeScript\n \u25ef ESLint"
		obj._reportNewLines(["\u276f\u25ef TypeScript"])
		core.runPending()
		self.assertEqual(spoken[-1], "TypeScript, not checked, 1 of 2")

	def test_ordinaryOutputIsReadWithoutScreenReads(self):
		obj = makeTerminal()
		reads = []
		cliTerminal.getScreenText = lambda o: reads.append(1) or ""
		try:
			for n in range(50):
				obj._reportNewLines(["  added package %d" % n])
		finally:
			cliTerminal.getScreenText = lambda obj: SCREEN["text"]
		self.assertEqual(reads, [])
		self.assertEqual(len(spoken), 50)

	def test_outputAfterAPromptIsReadAgain(self):
		SCREEN["text"] = "? Pick\n\u276f A\n  B"
		obj = makeTerminal()
		obj._reportNewLines(["? Pick", "\u276f A", "  B"])
		core.runPending()
		SCREEN["text"] = "\u221a Pick \u00bb A\nCreating a new app"
		obj._reportNewLines(["Creating a new app"])
		self.assertEqual(spoken[-1], "Creating a new app")

	def test_quietModeAndErrorBeep(self):
		obj = makeTerminal()
		CONF["cliHelper"]["quietMode"] = True
		obj._reportNewLines(["hello"])
		self.assertEqual(spoken, [])
		CONF["cliHelper"]["quietMode"] = False
		CONF["cliHelper"]["beepOnErrors"] = True
		obj._reportNewLines(["npm ERR! missing script"])
		self.assertEqual(beeps, [330])
		self.assertEqual(spoken, ["npm ERR! missing script"])

	def test_toggleWithoutColourInfoSaysSo(self):
		SCREEN["text"] = "? Would you like to use TypeScript? \u00bb No / Yes"
		obj = makeTerminal()
		obj.script_cliRightArrow(Gesture("kb:rightarrow"))
		core.runPending()
		self.assertIn(cliHelper.FOCUS_UNKNOWN_MESSAGE, spoken[-1])

	def test_longCommandFinishedIsAnnounced(self):
		obj = makeTerminal("PS C:\\p> npm install")
		obj.caret = len(obj.text)
		enter = Gesture("kb:enter")
		obj.script_cliEnter(enter)
		self.assertEqual(enter.sent, 1)
		obj._cliCommandStart -= 30
		obj._reportNewLines(["npm ERR! network"])
		self.assertEqual(spoken, ["npm ERR! network"])
		SCREEN["text"] = "PS C:\\p> npm install\nnpm ERR! network\nPS C:\\p> "
		obj._reportNewLines(["PS C:\\p> "])
		core.runPending()
		self.assertIn("Command finished with errors after 30 seconds", spoken)

	def test_shortCommandIsNotAnnounced(self):
		obj = makeTerminal("PS C:\\p> dir")
		obj.caret = len(obj.text)
		obj.script_cliEnter(Gesture("kb:enter"))
		obj._reportNewLines(["a.txt", "PS C:\\p> "])
		self.assertEqual(spoken, ["a.txt", "PS C:\\p> "])
		self.assertIsNone(obj._cliCommandStart)

	def test_finishedWhileAwayIsAnnouncedOnReturn(self):
		obj = makeTerminal("PS C:\\p> npm run build")
		obj.caret = len(obj.text)
		obj.script_cliEnter(Gesture("kb:enter"))
		obj._cliCommandStart -= 60
		SCREEN["text"] = "PS C:\\p> npm run build\ndone\nPS C:\\p> "
		obj.event_gainFocus()
		core.runPending()
		self.assertIn("Command finished after 60 seconds", spoken)


class ModeTest(Base):
	TEXT = "PS C:\\p> npm test\nfirst line\nsecond word here\n\nError: boom\nlast\nPS C:\\p> "

	def setUp(self):
		super(ModeTest, self).setUp()
		self.obj = makeTerminal(self.TEXT)
		self.obj.caret = len(self.TEXT)
		SCREEN["text"] = self.TEXT
		api.getFocusObject = lambda: self.obj
		self.plugin = cliHelper.GlobalPlugin()
		self.plugin.script_toggleMode(None)
		del spoken[:]

	def run_key(self, gid):
		found = self.plugin.getScript(Gesture(gid))
		self.assertIsNotNone(found, gid)
		found(Gesture(gid))

	def test_modeIsStickyUntilEscape(self):
		self.assertTrue(self.plugin._modeActive)
		self.run_key("kb:o")
		self.run_key("kb:o")
		self.assertTrue(self.plugin._modeActive)
		self.run_key("kb:escape")
		self.assertFalse(self.plugin._modeActive)
		self.assertIsNone(self.plugin.getScript(Gesture("kb:o")))

	def test_unassignedKeysBeepButNvdaCommandsPassThrough(self):
		self.assertEqual(self.plugin.getScript(Gesture("kb:z")), self.plugin.script_unassignedKey)
		self.assertIsNone(self.plugin.getScript(Gesture("kb:nvda+t")))
		CONF["cliHelper"]["unassignedKeysLeaveMode"] = True
		self.assertIsNone(self.plugin.getScript(Gesture("kb:z")))
		self.assertFalse(self.plugin._modeActive)

	def test_helpKeys(self):
		for gid in ("kb:h", "kb:/", "kb:f1"):
			self.assertEqual(self.plugin.getScript(Gesture(gid)), self.plugin.script_help)

	def test_leavingTheTerminalEndsModeButDialogsDoNot(self):
		self.run_key("kb:s")
		self.assertTrue(self.plugin._modeSuspended)
		self.plugin.event_gainFocus(object(), lambda: None)
		self.plugin.event_gainFocus(self.obj, lambda: None)
		self.assertTrue(self.plugin._modeActive)
		self.plugin.event_gainFocus(object(), lambda: None)
		self.assertFalse(self.plugin._modeActive)

	def test_errorJumpCopiesTheLine(self):
		self.run_key("kb:shift+e")
		self.assertEqual(spoken[-1], "Error: boom")
		self.assertEqual(clipboard[-1], "Error: boom")
		CONF["cliHelper"]["copyErrorLines"] = False
		del clipboard[:]
		self.run_key("kb:shift+e")
		self.assertEqual(clipboard, [])

	def test_selectLinesAndCopy(self):
		review["pos"] = FakeTextInfo(self.obj, self.TEXT.index("first"))
		self.run_key("kb:shift+downarrow")
		self.assertEqual(spoken[-2:], ["first line", "selected"])
		self.run_key("kb:shift+downarrow")
		self.run_key("kb:control+c")
		self.assertEqual(clipboard[-1], "first line\nsecond word here\n")
		self.assertEqual(spoken[-1], "Copied 2 lines")
		self.run_key("kb:shift+uparrow")
		self.assertEqual(spoken[-1], "unselected")
		self.run_key("kb:escape")
		self.assertEqual(spoken[-1], "Selection cleared")
		self.assertTrue(self.plugin._modeActive)

	def test_selectWordsAndCharacters(self):
		review["pos"] = FakeTextInfo(self.obj, self.TEXT.index("second"))
		self.run_key("kb:control+shift+rightarrow")
		self.assertEqual(spoken[-2:], ["second", "selected"])
		self.run_key("kb:shift+rightarrow")
		self.assertEqual(spoken[-2:], ["spell:w", "selected"])
		self.run_key("kb:control+c")
		self.assertEqual(clipboard[-1], "second w")

	def test_copyLineWordParagraph(self):
		review["pos"] = FakeTextInfo(self.obj, self.TEXT.index("word"))
		self.run_key("kb:c")
		self.assertEqual(clipboard[-1], "second word here")
		self.run_key("kb:w")
		self.assertEqual(clipboard[-1], "word")
		self.run_key("kb:shift+c")
		self.assertEqual(clipboard[-1], "PS C:\\p> npm test\nfirst line\nsecond word here")
		self.run_key("kb:control+a")
		self.run_key("kb:control+c")
		self.assertEqual(clipboard[-1], self.TEXT)

	def test_paragraphNavigation(self):
		review["pos"] = FakeTextInfo(self.obj, 0)
		self.run_key("kb:control+downarrow")
		self.assertEqual(spoken[-1], "Error: boom")
		self.run_key("kb:control+uparrow")
		self.assertEqual(spoken[-1], "PS C:\\p> npm test")

	def test_outputAndLines(self):
		self.run_key("kb:o")
		self.assertEqual(spoken[-1], "first line\nsecond word here\n\nError: boom\nlast")
		self.run_key("kb:shift+o")
		self.assertTrue(clipboard[-1].startswith("first line"))
		self.run_key("kb:1")
		self.assertEqual(spoken[-1], "last")
		self.run_key("kb:shift+2")
		self.assertEqual(clipboard[-1], "Error: boom")
		self.run_key("kb:t")
		self.assertEqual(spoken[-1], "No command typed")


if __name__ == "__main__":
	unittest.main()
