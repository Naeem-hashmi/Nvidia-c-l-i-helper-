# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""Recognising progress bars and spinners, and deciding what to say about them.

Downloaders such as ollama, pip, npm, winget and docker redraw their progress many times a second.
NVDA reports every changed fragment ("46", "2.2 GB/4.7", "1m39s"...), which sounds like noise.
This module recognises such text so it can be replaced by an occasional "45 percent".

Nothing here imports NVDA, so it can be unit tested anywhere. Python 3.7 compatible.
"""

import re

#: Spinner characters (braille dots used by ollama, npm and many others, and the classic ones).
SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏⣾⣽⣻⢿⡿⣟⣯⣷⠁⠂⠄⡀⢀⠠⠐⠈◐◓◑◒◴◷◶◵"
#: Characters drawn as progress bars (block elements, pip's heavy lines, squares).
BAR_CHARS = "█▉▊▋▌▍▎▏▕▓▒░━╸╺■□⬛⬜"

_PERCENT_RE = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s?%")
_UNIT = r"(?:[kKMGT]i?B|B|bytes)"
_RATIO_RE = re.compile(
	r"(\d+(?:\.\d+)?)\s?(" + _UNIT + r")?\s?/\s?(\d+(?:\.\d+)?)\s?(" + _UNIT + r")(?!/s)",
)
_SPEED_RE = re.compile(r"\d+(?:\.\d+)?\s?" + _UNIT + r"/s\b")
_ETA_RE = re.compile(r"(?i)\beta\b")
#: A run of bar characters, or an ASCII bar in brackets such as docker's "[=====>    ]".
#: A plain "=====" or "-----" is a separator, not a bar.
_BAR_RUN_RE = re.compile(r"[" + BAR_CHARS + r"]{3,}|\[[=#>\-. ]*[=#>][=#>\-. ]*\]")
_DIGIT_RE = re.compile(r"\d")
#: Numbers with units, durations and percentages, removed before checking what is left of a fragment.
_MEASURE_RE = re.compile(
	r"(?i)\d+(?:\.\d+)?\s?(?:[kmgt]i?b(?:/s)?|b/s|bytes|ms|[hms](?=\d|\b)|%|it/s|s/it)",
)
_LEFTOVER_RE = re.compile(r"^[\s\d.,:;%/()\[\]<>|=#\-_+*~" + BAR_CHARS + SPINNER_CHARS + r"]*$")
_UNITS = {"b": 1, "bytes": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12, "kib": 1024.0, "mib": 1024.0**2}
_UNITS.update({"gib": 1024.0**3, "tib": 1024.0**4})
_HEXISH_RE = re.compile(r"^[0-9a-fA-F:.…]{8,}$")


def isSpinnerLine(line):
	"""A line whose first or last visible character is a spinner frame, such as "pulling manifest ⠋"."""
	text = line.strip()
	return bool(text) and (text[0] in SPINNER_CHARS or text[-1] in SPINNER_CHARS)


def isProgressLine(line):
	"""A whole line showing progress: a percentage, a bar, a transfer ratio or a speed."""
	text = line.strip()
	if not text:
		return False
	return bool(
		_PERCENT_RE.search(text)
		or _BAR_RUN_RE.search(text)
		or _RATIO_RE.search(text)
		or _SPEED_RE.search(text)
	)


def isStrongProgressLine(line):
	"""A line that can only be progress: a bar, a transfer ratio, a speed, or a spinner.

	A percentage alone is not enough ("Coverage: 85%" is a result, not a progress bar).
	"""
	text = line.strip()
	if not text:
		return False
	hasBar = bool(_BAR_RUN_RE.search(text)) and bool(_DIGIT_RE.search(text))
	return bool(isSpinnerLine(text) or hasBar or _RATIO_RE.search(text) or _SPEED_RE.search(text))


def isProgressFragment(text):
	"""A piece of a redrawn progress line: only numbers, units, durations, bar and spinner characters.

	Words are not progress, so "teams" or "done" never count, but "46", "2.2 GB/4.7" and "1m39s" do.
	"""
	stripped = text.strip()
	if not stripped:
		return False
	rest = _ETA_RE.sub(" ", _MEASURE_RE.sub("0", stripped))
	return bool(_LEFTOVER_RE.match(rest))


def isProgressText(line):
	return isSpinnerLine(line) or isProgressLine(line) or isProgressFragment(line)


def extractPercent(line):
	"""The progress of a line as a number from 0 to 100, or None if the line does not show it."""
	match = _PERCENT_RE.search(line)
	if match:
		value = float(match.group(1))
		return value if 0 <= value <= 100 else None
	match = _RATIO_RE.search(line)
	if match:
		done, doneUnit, total, totalUnit = match.groups()
		scaleTotal = _UNITS.get(totalUnit.lower(), 1)
		scaleDone = _UNITS.get(doneUnit.lower(), 1) if doneUnit else scaleTotal
		totalBytes = float(total) * scaleTotal
		if totalBytes <= 0:
			return None
		return max(0.0, min(100.0, float(done) * scaleDone * 100.0 / totalBytes))
	return None


def label(line):
	"""A short spoken name for a progress line: its first words, without hashes, numbers and bars.

	"pulling 6a0746a1ec1a...  45% ▕██  ▏ 2.1 GB/4.7 GB" gives "pulling".
	"""
	words = []
	for word in line.strip().split():
		if word[0].isdigit() or word[0] in BAR_CHARS + SPINNER_CHARS + "[(|":
			break
		word = word.strip(":.…")
		if not word or _HEXISH_RE.match(word):
			continue
		words.append(word)
		if len(words) == 3:
			break
	return " ".join(words)


class ProgressTracker(object):
	"""Decides when to speak or sound progress, so a download is heard as a few clear updates.

	feed() returns a list of actions: ("speak", label, percent) and ("tone", percent).
	"""

	def __init__(self, mode="speech", step=25, minInterval=3.0):
		#: "speech", "tones", "both" or "silent".
		self.mode = mode
		#: Speak each time progress passes a multiple of this many percent.
		self.step = max(1, step)
		#: Never speak progress more often than this many seconds, except at 100 percent.
		self.minInterval = minInterval
		self.reset()

	def reset(self):
		self.label = None
		self.lastBucket = None
		self.lastSpeech = -1e9
		self.lastTonePercent = None
		self.lastTone = -1e9
		self.labelAnnounced = False

	def feed(self, name, percent, now):
		actions = []
		if name != self.label:
			# A new download or step: start counting again.
			self.label = name
			self.lastBucket = None
			self.labelAnnounced = False
		if self.mode in ("tones", "both"):
			if self.lastTonePercent is None or (
				abs(percent - self.lastTonePercent) >= 1 and now - self.lastTone >= 0.25
			):
				actions.append(("tone", percent))
				self.lastTonePercent = percent
				self.lastTone = now
		if self.mode in ("speech", "both"):
			bucket = 100 if percent >= 100 else int(percent // self.step) * self.step
			first = self.lastBucket is None
			if first or bucket > self.lastBucket:
				if first or bucket >= 100 or now - self.lastSpeech >= self.minInterval:
					actions.append(("speak", "" if self.labelAnnounced else name, int(percent)))
					self.labelAnnounced = True
					self.lastBucket = bucket
					self.lastSpeech = now
		return actions


def toneFrequency(percent):
	"""The pitch NVDA itself uses for progress bar beeps: 110 Hz at 0 percent up to 1760 Hz at 100."""
	return int(110 * 2 ** (percent / 25.0))
