# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""The overlay class added in front of NVDA's own terminal classes."""

import time

import addonHandler
import core
import speech
import textInfos
import tones
import ui
from logHandler import log
from NVDAObjects import NVDAObject
from scriptHandler import script

from . import parsing
from . import problems
from . import progress
from . import terminal
from .common import FOCUS_UNKNOWN_MESSAGE, conf, describeChoice, errorRe, plainQuestion, promptRe, summaryText

addonHandler.initTranslation()

#: How often (ms) and how many times to check the screen after a key press in an interactive prompt.
POLL_INTERVAL = 40
POLL_ATTEMPTS = 12
#: While a command runs, how often (seconds) at most to look at the screen for the returning shell prompt.
FINISH_CHECK_INTERVAL = 1.0
#: After seeing a progress bar or spinner, numbers and fragments count as progress for this many seconds.
PROGRESS_LINGER = 3.0
#: While progress is redrawn in fragments, how often (seconds) at most to read the screen for the percentage.
PROGRESS_SCAN_INTERVAL = 0.5
#: The same kind of sound is played at most this often (seconds).
SOUND_INTERVAL = 0.4


def playSound(kind):
	"""Short sounds for new output: a low buzz for errors, a middle tone for warnings, a rising chirp for success."""
	if kind == "error":
		tones.beep(200, 100)
	elif kind == "warning":
		tones.beep(400, 60)
	elif kind == "success":
		tones.beep(1000, 40)
		core.callLater(50, tones.beep, 1300, 40)


def _hasPromptMarker(line):
	"""Whether a line carries a symbol used by interactive prompts (pointer, checkbox or question mark)."""
	stripped = line.strip()
	if not stripped:
		return False
	parsed = parsing.parseChoiceLine(line)
	return bool(
		(parsed is not None and (parsed[2] or parsed[1] is not None))
		or stripped.startswith(parsing.QUESTION_STARTS)
		or parsing.TOGGLE_RE.match(stripped) is not None
	)


class CLITerminal(NVDAObject):
	"""Added to every terminal NVDA knows about.

	It sits in front of NVDA's terminal classes, so it can filter the automatic reading of new text,
	take over the arrow keys while an interactive prompt is on screen, and notice when commands finish.
	"""

	_cliMenuSignature = None
	_cliMenuState = None
	_cliMenuActive = False
	_cliSuppressUntil = 0.0
	_cliPendingAnnounce = None
	_cliPollToken = 0
	_cliInBatch = False
	_cliCommandStart = None
	_cliCommandSawError = False
	_cliLastFinishCheck = 0.0
	_cliProgressUntil = 0.0
	_cliLastProgressScan = 0.0
	_cliProgressTracker = None
	_cliProgressKey = None
	_cliSpinnerLabel = None
	#: Progress was reported only in fragments since the screen was last read for it.
	_cliProgressUnread = False
	_cliSpinnerSpoken = 0.0
	_cliLastSounds = None

	def initOverlayClass(self):
		self._cliScreenCache = (0.0, None)

	# Interactive prompts

	def cliDetectMenu(self, maxAge=0.0):
		"""Return (menu, screenLines) for the interactive prompt on screen, or (None, lines).

		A result read less than maxAge seconds ago is reused.
		"""
		stamp, cached = getattr(self, "_cliScreenCache", (0.0, None))
		if cached is not None and time.time() - stamp <= maxAge:
			return cached
		lines = terminal.getScreenLines(self)
		menu = parsing.parseMenu(lines, promptRe())
		if menu is not None and menu.focusIndex is None:
			menu.focusIndex = terminal.emphasisedIndex(self, menu)
		result = (menu, lines)
		self._cliScreenCache = (time.time(), result)
		return result

	def cliAnnounceMenu(self, menu, afterKey=False):
		"""Speak the prompt: the question and focused choice when it first appears, then only what changed."""
		signature = menu.signature()
		state = menu.state()
		previousSignature = self._cliMenuSignature
		previousState = self._cliMenuState
		self._cliMenuSignature = signature
		self._cliMenuState = state
		if signature == previousSignature and state == previousState:
			return
		parts = []
		isNew = signature != previousSignature
		if isNew:
			if menu.question:
				parts.append(plainQuestion(menu))
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
		if item is None and menu.kind == parsing.Menu.CHECKBOX and previousState and not isNew:
			# Focus is shown only by colour and could not be read; report the choice that was toggled.
			changed = [i for i, (old, new) in enumerate(zip(previousState[1], state[1])) if old != new]
			if len(changed) == 1:
				item = menu.items[changed[0]]
		if item is not None:
			parts.append(item.label if menu.kind == parsing.Menu.TOGGLE else describeChoice(menu, item))
		elif afterKey or (isNew and menu.kind == parsing.Menu.TOGGLE):
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
			self._cliCallOriginal(fallbackScript, gesture)
			return
		self._cliMenuActive = True
		if self._cliMenuSignature != menu.signature():
			# The prompt appeared without being announced (e.g. quiet mode); remember it silently.
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

	def _cliCallOriginal(self, scriptNames, gesture):
		"""Run the first of the named scripts that NVDA's own classes provide, or just send the key."""
		if isinstance(scriptNames, str):
			scriptNames = (scriptNames,)
		for name in scriptNames:
			original = getattr(super(CLITerminal, self), name, None)
			if original is not None:
				original(gesture)
				return
		gesture.send()

	def _cliPollMenu(self, token, before, attemptsLeft, kind):
		if token != self._cliPollToken:
			return
		menu, _lines = self.cliDetectMenu()
		if menu is None:
			return
		if (menu.state() != before and kind != parsing.Menu.TOGGLE) or attemptsLeft <= 1:
			# Always speak after a key press, even when focus did not move (for example at the end of a list).
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
				# A key press is being handled; its poll will speak.
				return
			menu, _lines = self.cliDetectMenu(maxAge=0.1)
			if menu is not None:
				self.cliAnnounceMenu(menu)

		self._cliPendingAnnounce = core.callLater(POLL_INTERVAL, announce)

	def _cliFilterMenuText(self, lines):
		"""Remove text that belongs to an interactive prompt on screen; the prompt is announced instead.

		NVDA reports changed text, which may be whole lines or only fragments of lines (for example
		just the words that differ when one question replaces another). So once a prompt is on screen,
		every batch is compared with the prompt's area of the screen, from its question to the bottom.
		"""
		if not conf()["interactivePrompts"]:
			return lines
		if not self._cliMenuActive and not any(_hasPromptMarker(line) for line in lines):
			# Ordinary output: never read the screen for it, so long builds and installs cost nothing.
			return lines
		# A screen read from a moment ago is reused when it explains all the new text;
		# otherwise the screen has changed since, so read it again.
		for maxAge in (0.05, 0.0):
			try:
				menu, screen = self.cliDetectMenu(maxAge=maxAge)
			except Exception:
				log.debugWarning("CLI Helper: menu detection failed", exc_info=True)
				return lines
			if menu is None:
				continue
			region = [line.strip() for line in screen[menu.startIndex :] if line.strip()]
			kept = [line for line in lines if line.strip() and not any(line.strip() in r for r in region)]
			if not kept:
				break
		if menu is None:
			self._cliMenuActive = False
			return lines
		self._cliMenuActive = True
		if len(kept) != len(lines):
			self._cliScheduleMenuAnnounce()
		return kept

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

	# Command start and finish

	@script(gestures=["kb:enter", "kb:numpadEnter"])
	def script_cliEnter(self, gesture):
		"""Note when a command is started, so its end can be announced."""
		try:
			info = self.makeTextInfo(textInfos.POSITION_CARET)
			info.expand(textInfos.UNIT_LINE)
			command = parsing.commandFromLine(info.text.rstrip("\r\n"), promptRe())
		except Exception:
			command = None
		if command:
			self._cliCommandStart = time.time()
			self._cliCommandSawError = False
		# NVDA's terminal classes use Enter to flush typed characters; keep that behaviour.
		self._cliCallOriginal(("script_flush_queuedChars", "script_caret_newLine"), gesture)

	def _cliCheckFinished(self, lines):
		"""Announce the end of a long command, when the shell prompt comes back."""
		start = self._cliCommandStart
		if start is None:
			return
		pattern = promptRe()
		if any(errorRe().search(line) for line in lines):
			self._cliCommandSawError = True
		promptSeen = any(pattern.match(line) for line in lines)
		now = time.time()
		if not promptSeen:
			# NVDA may report only part of the new prompt line; look at the screen now and then.
			if now - self._cliLastFinishCheck < FINISH_CHECK_INTERVAL:
				return
			self._cliLastFinishCheck = now
			if not self.cliPromptAtBottom():
				return
		self._cliCommandStart = None
		self.cliAnnounceFinished(now - start)

	def cliPromptAtBottom(self):
		try:
			lines = terminal.getScreenLines(self)
		except Exception:
			return False
		content = [line for line in lines if line.strip()]
		return bool(content) and parsing.commandFromLine(content[-1], promptRe()) == ""

	def cliLastProblems(self):
		"""The errors and warnings in the output of the last command."""
		command, output = parsing.lastOutput(terminal.getBufferLines(self), promptRe())
		return problems.summarize(output, errorRe())

	def cliAnnounceFinished(self, seconds):
		threshold = conf()["finishedAfterSeconds"]
		if not threshold or seconds < threshold:
			return
		try:
			found = self.cliLastProblems()
		except Exception:
			log.debugWarning("CLI Helper: could not analyse output", exc_info=True)
			found = []
		hasErrors = any(p.kind == problems.Problem.ERROR for p in found)
		if hasErrors:
			tones.beep(440, 80)
			core.callLater(100, tones.beep, 330, 120)
			# Translators: Announced when a long command finishes and its output contained errors.
			message = _("Command finished with errors after {seconds} seconds")
		else:
			tones.beep(660, 80)
			core.callLater(100, tones.beep, 880, 120)
			# Translators: Announced when a long command finishes.
			message = _("Command finished after {seconds} seconds")
		message = message.format(seconds=int(round(seconds)))
		if found and conf()["summaryOnFinish"]:
			message += ". " + summaryText(found)
		ui.message(message)

	def event_gainFocus(self):
		super(CLITerminal, self).event_gainFocus()
		# A long command may have finished while you were in another window.
		if self._cliCommandStart is not None and self.cliPromptAtBottom():
			start = self._cliCommandStart
			self._cliCommandStart = None
			core.callLater(300, self.cliAnnounceFinished, time.time() - start)

	# Automatic reading of new output

	def _cliProcessLines(self, lines):
		"""Everything the add-on does with a batch of new text; returns the lines NVDA should still speak."""
		self._cliCheckFinished(lines)
		if conf()["quietMode"]:
			return []
		lines = self._cliFilterMenuText(lines)
		lines = self._cliFilterProgress(lines)
		if lines:
			self._cliPlaySounds(lines)
		return lines

	# Progress bars and spinners

	def _cliTracker(self, mode):
		key = (mode, conf()["progressStep"], conf()["progressInterval"])
		if self._cliProgressTracker is None or self._cliProgressKey != key:
			self._cliProgressTracker = progress.ProgressTracker(mode, key[1], key[2])
			self._cliProgressKey = key
		return self._cliProgressTracker

	def _cliRunProgressActions(self, actions):
		for action in actions:
			if action[0] == "tone":
				tones.beep(progress.toneFrequency(action[1]), 40)
			elif action[0] == "speak":
				name, percent = action[1], action[2]
				# Translators: Spoken progress of a download or install, e.g. "45 percent".
				text = _("{percent} percent").format(percent=percent)
				speech.speakText(name + ", " + text if name else text)

	def _cliFilterProgress(self, lines):
		"""Replace redrawn progress bars and spinners with occasional percentages or tones.

		A line counts as progress when it has a bar, a transfer ratio, a speed or a spinner. For a few seconds
		after such a line, plain numbers and fragments such as "46" or "1m39s" count as progress too,
		because NVDA reports only the changed parts of a redrawn bar.
		"""
		mode = conf()["progressMode"]
		if mode == "raw":
			return lines
		now = time.time()
		tracker = self._cliTracker(mode)
		kept = []
		fed = False
		fragmentSeen = False
		for line in lines:
			strong = progress.isStrongProgressLine(line)
			active = now < self._cliProgressUntil
			if not strong and not (
				active and (progress.isProgressLine(line) or progress.isProgressFragment(line))
			):
				kept.append(line)
				continue
			self._cliProgressUntil = now + PROGRESS_LINGER
			percent = progress.extractPercent(line) if (strong or progress.isProgressLine(line)) else None
			if percent is not None:
				self._cliRunProgressActions(tracker.feed(progress.label(line), percent, now))
				fed = True
			elif progress.isSpinnerLine(line):
				self._cliSpinner(line, mode, now)
			else:
				fragmentSeen = True
		if fed:
			self._cliProgressUnread = False
		elif fragmentSeen:
			self._cliProgressUnread = True
		# Read the whole bar from the screen when only parts of it were reported: now and then while it
		# runs, and always once when ordinary output follows, so the final "100 percent" is never missed.
		finished = bool(kept) and self._cliProgressUnread
		if self._cliProgressUnread and (
			finished or now - self._cliLastProgressScan >= PROGRESS_SCAN_INTERVAL
		):
			self._cliLastProgressScan = now
			self._cliProgressUnread = False
			try:
				screen = terminal.getScreenLines(self)
			except Exception:
				screen = []
			for line in reversed(screen[-15:]):
				percent = progress.extractPercent(line) if progress.isProgressLine(line) else None
				if percent is not None:
					self._cliRunProgressActions(tracker.feed(progress.label(line), percent, now))
					break
		return kept

	def _cliSpinner(self, line, mode, now):
		"""Say what a spinner is waiting for ("pulling manifest") when it changes, not every frame."""
		if mode not in ("speech", "both"):
			return
		name = line.strip().strip(progress.SPINNER_CHARS).strip()
		if not name or name == self._cliSpinnerLabel:
			return
		if now - self._cliSpinnerSpoken < conf()["progressInterval"]:
			return
		self._cliSpinnerLabel = name
		self._cliSpinnerSpoken = now
		speech.speakText(name)

	# Sounds

	def _cliPlaySounds(self, lines):
		enabled = {
			"error": conf()["soundErrors"],
			"warning": conf()["soundWarnings"],
			"success": conf()["soundSuccess"],
		}
		if not any(enabled.values()):
			return
		pattern = errorRe()
		kinds = set(problems.classify(line, pattern) for line in lines)
		now = time.time()
		if self._cliLastSounds is None:
			self._cliLastSounds = {}
		for kind in ("error", "warning", "success"):
			if kind in kinds and enabled[kind]:
				if now - self._cliLastSounds.get(kind, 0.0) >= SOUND_INTERVAL:
					self._cliLastSounds[kind] = now
					playSound(kind)
				# One sound per batch: the most important kind.
				return

	def _reportNewLines(self, lines):
		# NVDA 2020.4 and later report each batch of new text here.
		lines = self._cliProcessLines(lines)
		if not lines:
			return
		self._cliInBatch = True
		try:
			original = getattr(super(CLITerminal, self), "_reportNewLines", None)
			if original is not None:
				original(lines)
			else:
				for line in lines:
					self._reportNewText(line)
		finally:
			self._cliInBatch = False

	def _reportNewText(self, line):
		# Older NVDA versions report new text one line at a time, without _reportNewLines.
		if not self._cliInBatch and not self._cliProcessLines([line]):
			return
		original = getattr(super(CLITerminal, self), "_reportNewText", None)
		if original is not None:
			original(line)
		else:
			speech.speakText(line)

	def event_UIA_notification(self, *args, **kwargs):
		# Windows Terminal can be set to read new output from UI Automation notifications.
		original = getattr(super(CLITerminal, self), "event_UIA_notification", None)
		displayString = kwargs.get("displayString") or ""
		lines = [line for line in displayString.splitlines() if line.strip()]
		if lines:
			kept = self._cliProcessLines(lines)
			if len(kept) != len(lines):
				if kept:
					for line in kept:
						speech.speakText(line)
				return
		if original is not None:
			original(*args, **kwargs)
