# Exercises the add-on's NVDA-facing logic against minimal stand-ins for NVDA's modules.
# This catches Python errors and logic bugs off Windows; behaviour with real terminals
# still has to be checked in NVDA (see docs/testing.md).
import os
import sys
import types
import unittest

ADDON = os.path.join(os.path.dirname(__file__), "..", "addon", "globalPlugins")

spoken = []
beeps = []
clipboard = []


def _module(name, **attrs):
	mod = types.ModuleType(name)
	mod.__dict__.update(attrs)
	sys.modules[name] = mod
	return mod


class _Section(dict):
	pass


def installStubs():
	import builtins

	builtins._ = lambda s: s
	conf = {"cliHelper": _Section(), "documentFormatting": _Section(reportColor=False)}

	class _Conf(dict):
		spec = {}

	confObj = _Conf(conf)

	def addonInit():
		pass

	_module("addonHandler", initTranslation=addonInit)
	_module("config", conf=confObj)

	class Role:
		TERMINAL = "terminal"

	class OutputReason:
		CARET = "caret"

	_module("controlTypes", Role=Role, OutputReason=OutputReason)
	_module("api", copyToClip=lambda text: clipboard.append(text) or True, getFocusObject=lambda: None)

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
	_module("globalCommands", commands=None)

	class GlobalPluginBase(object):
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

	_module("globalPluginHandler", GlobalPlugin=GlobalPluginBase)

	class SettingsPanel(object):
		pass

	class NVDASettingsDialog(object):
		categoryClasses = []

	settingsDialogs = _module(
		"gui.settingsDialogs", SettingsPanel=SettingsPanel, NVDASettingsDialog=NVDASettingsDialog
	)
	guiHelper = _module("gui.guiHelper")
	_module("gui", settingsDialogs=settingsDialogs, guiHelper=guiHelper, mainFrame=None)
	_module(
		"speech",
		cancelSpeech=lambda: spoken.append("<cancel>"),
		speakText=lambda text: spoken.append(text),
		speakTextInfo=lambda *a, **k: None,
	)
	_module(
		"textInfos",
		POSITION_ALL="all",
		POSITION_CARET="caret",
		POSITION_LAST="last",
		UNIT_LINE="line",
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

	class Terminal(NVDAObject):
		def _reportNewText(self, line):
			spoken.append(line)

		def script_caret_moveByLine(self, gesture):
			spoken.append("<nvda caret line>")

	_module("NVDAObjects", NVDAObject=NVDAObject)
	_module("NVDAObjects.behaviors", Terminal=Terminal)

	def script(**kwargs):
		def wrap(fn):
			fn.gestures = [kwargs["gesture"]] if "gesture" in kwargs else []
			fn.__doc__ = kwargs.get("description")
			return fn

		return wrap

	_module("scriptHandler", script=script)
	return confObj


CONF = installStubs()
sys.path.insert(0, ADDON)
import cliHelper  # noqa: E402
from cliHelper import terminal as cliTerminal  # noqa: E402

SCREEN = {"text": ""}
cliTerminal.getScreenText = lambda obj: SCREEN["text"]
cliTerminal.getBufferText = lambda obj: SCREEN["text"]
cliTerminal.lineStyles = lambda obj, index: None

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


def makeTerminal():
	cls = type("T", (cliHelper.CLITerminal, Terminal), {})
	obj = cls()
	obj.initOverlayClass()
	return obj


class PluginTest(unittest.TestCase):
	def setUp(self):
		del spoken[:]
		del beeps[:]
		del clipboard[:]
		CONF["cliHelper"].clear()
		CONF["cliHelper"].update(
			interactivePrompts=True, quietMode=False, beepOnErrors=False, promptPattern="", errorPattern=""
		)

	def test_overlayIsAddedToTerminals(self):
		plugin = cliHelper.GlobalPlugin()
		clsList = [Terminal]
		plugin.chooseNVDAObjectOverlayClasses(None, clsList)
		self.assertIs(clsList[0], cliHelper.CLITerminal)
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
		core.runPending()
		self.assertEqual(gesture.sent, 1)
		self.assertNotIn("<nvda caret line>", spoken)
		self.assertEqual(spoken[-1], "Pages Router, 2 of 3")

	def test_newPromptIsIntroducedAndRawLinesSuppressed(self):
		SCREEN["text"] = "? Select features\n\u276f\u25c9 TypeScript\n \u25ef ESLint"
		obj = makeTerminal()
		for line in ("? Select features", "\u276f\u25c9 TypeScript", " \u25ef ESLint"):
			obj._reportNewText(line)
		core.runPending()
		self.assertEqual(spoken[-1], "Select features, list, 2 choices, TypeScript, checked, 1 of 2")
		self.assertNotIn("\u276f\u25c9 TypeScript", spoken)
		# Space toggles the focused checkbox; only the change is spoken.
		SCREEN["text"] = "? Select features\n\u276f\u25ef TypeScript\n \u25ef ESLint"
		obj._reportNewText("\u276f\u25ef TypeScript")
		core.runPending()
		self.assertEqual(spoken[-1], "TypeScript, not checked, 1 of 2")

	def test_newSelectListPlainChoicesAreSuppressed(self):
		SCREEN["text"] = "? Pick a router\n\u276f App Router\n  Pages Router\n  None"
		obj = makeTerminal()
		for line in ("? Pick a router", "\u276f App Router", "  Pages Router", "  None"):
			obj._reportNewText(line)
		core.runPending()
		self.assertEqual(spoken, ["<cancel>", "Pick a router, list, 3 choices, App Router, 1 of 3"])

	def test_plainOutputNeverReadsTheScreen(self):
		obj = makeTerminal()
		reads = []
		original = cliTerminal.getScreenText
		cliTerminal.getScreenText = lambda o: reads.append(1) or ""
		try:
			for n in range(50):
				obj._reportNewText("  added package %d" % n)
		finally:
			cliTerminal.getScreenText = original
		self.assertEqual(reads, [])
		self.assertEqual(len(spoken), 50)

	def test_ordinaryOutputIsStillRead(self):
		SCREEN["text"] = "PS C:\\> npm i\nadded 3 packages"
		obj = makeTerminal()
		obj._reportNewText("added 3 packages")
		self.assertEqual(spoken, ["added 3 packages"])

	def test_quietModeAndErrorBeep(self):
		obj = makeTerminal()
		SCREEN["text"] = ""
		CONF["cliHelper"]["quietMode"] = True
		obj._reportNewText("hello")
		self.assertEqual(spoken, [])
		CONF["cliHelper"]["quietMode"] = False
		CONF["cliHelper"]["beepOnErrors"] = True
		obj._reportNewText("npm ERR! missing script")
		self.assertEqual(beeps, [330])
		self.assertEqual(spoken, ["npm ERR! missing script"])

	def test_toggleWithoutColourInfoSaysSo(self):
		SCREEN["text"] = "? Would you like to use TypeScript? \u00bb No / Yes"
		obj = makeTerminal()
		obj.script_cliRightArrow(Gesture("kb:rightarrow"))
		core.runPending()
		self.assertIn(cliHelper.FOCUS_UNKNOWN_MESSAGE, spoken[-1])

	def test_commandLayer(self):
		plugin = cliHelper.GlobalPlugin()
		self.assertIsNone(plugin.getScript(Gesture("kb:o")))
		plugin._enterLayer()
		found = plugin.getScript(Gesture("kb:o"))
		self.assertEqual(found, plugin.script_readLastOutput)
		self.assertFalse(plugin._layerActive)
		self.assertIsNone(plugin.getScript(Gesture("kb:o")))
		plugin._enterLayer()
		self.assertEqual(plugin.getScript(Gesture("kb:z")), plugin.script_layerUnknown)
		plugin._enterLayer()
		self.assertEqual(plugin.getScript(Gesture("kb:1")), plugin.script_readLine1)
		self.assertTrue(plugin.script_readLine1.__doc__)

	def test_readLastOutputAndLines(self):
		import api

		SCREEN["text"] = "PS C:\\p> git status\nOn branch main\nnothing to commit\nPS C:\\p> "
		obj = makeTerminal()
		api.getFocusObject = lambda: obj
		plugin = cliHelper.GlobalPlugin()
		plugin.script_readLastOutput(None)
		self.assertEqual(spoken[-1], "On branch main\nnothing to commit")
		plugin.script_copyLastOutput(None)
		self.assertEqual(clipboard[-1], "On branch main\nnothing to commit")
		plugin.script_readLine1(None)
		self.assertEqual(spoken[-1], "nothing to commit")
		plugin.script_copyLine2(None)
		self.assertEqual(clipboard[-1], "On branch main")


if __name__ == "__main__":
	unittest.main()
