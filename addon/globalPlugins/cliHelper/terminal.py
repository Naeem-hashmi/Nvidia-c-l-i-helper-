# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""Reading text and formatting out of terminal NVDA objects."""

import textInfos
from logHandler import log

from . import compat
from . import parsing

#: How many screen lines are analysed when looking for an interactive prompt.
SCREEN_LINES = 60


def _uiaPattern(obj):
	return getattr(obj, "UIATextPattern", None)


def _rangeText(rangeObj):
	return rangeObj.GetText(-1) or ""


def getScreenText(obj):
	"""Return the text currently visible in the terminal window."""
	pattern = _uiaPattern(obj)
	if pattern is not None:
		try:
			ranges = pattern.GetVisibleRanges()
			return "\n".join(_rangeText(ranges.GetElement(i)) for i in range(ranges.Length))
		except Exception:
			log.debugWarning("CLI Helper: visible ranges unavailable", exc_info=True)
	try:
		return obj.makeTextInfo(textInfos.POSITION_ALL).text or ""
	except Exception:
		log.debugWarning("CLI Helper: could not read terminal text", exc_info=True)
		return ""


def getBufferText(obj):
	"""Return all text in the terminal, including output that has scrolled off the screen."""
	pattern = _uiaPattern(obj)
	if pattern is not None:
		try:
			# Windows Console and Windows Terminal expose the whole scroll-back buffer here.
			return _rangeText(pattern.DocumentRange)
		except Exception:
			log.debugWarning("CLI Helper: document range unavailable", exc_info=True)
	return getScreenText(obj)


def getScreenLines(obj):
	return parsing.splitLines(getScreenText(obj))


def getBufferLines(obj):
	return parsing.splitLines(getBufferText(obj))


def _screenLineInfo(obj, index):
	"""Return a TextInfo for the given line (0 based) of the visible screen, or None."""
	pattern = _uiaPattern(obj)
	if pattern is None:
		return None
	try:
		rangeObj = pattern.GetVisibleRanges().GetElement(0).Clone()
		rangeObj.MoveEndpointByRange(compat.UIA_ENDPOINT_END, rangeObj, compat.UIA_ENDPOINT_START)
		if index and rangeObj.Move(compat.UIA_TEXT_UNIT_LINE, index) != index:
			return None
		rangeObj.ExpandToEnclosingUnit(compat.UIA_TEXT_UNIT_LINE)
		return obj.TextInfo(obj, None, _rangeObj=rangeObj)
	except Exception:
		log.debugWarning("CLI Helper: could not get line %d" % index, exc_info=True)
		return None


def lineStyles(obj, index):
	"""Return a list of (text, style) chunks for a screen line, where style is (underline, colour, bold).

	Returns None when the terminal does not expose formatting (for example the legacy Windows Console).
	"""
	info = _screenLineInfo(obj, index)
	if info is None:
		return None
	try:
		fields = info.getTextWithFields(compat.FormatConfig())
	except Exception:
		log.debugWarning("CLI Helper: could not get formatting", exc_info=True)
		return None
	chunks = []
	style = (None, None, None)
	for field in fields:
		if isinstance(field, textInfos.FieldCommand):
			if field.command == "formatChange" and field.field is not None:
				f = field.field
				style = (f.get("underline"), str(f.get("color")), f.get("bold"))
		elif isinstance(field, str) and field:
			chunks.append((field, style))
	return chunks


def emphasisedIndex(obj, menu):
	"""Find the focused choice of a prompt that shows focus only with colour or underline.

	Returns an index into menu.items, or None if it cannot be determined.
	"""
	if menu.kind == parsing.Menu.TOGGLE:
		lineIndex = menu.items[0].lineIndex
		chunks = lineStyles(obj, lineIndex)
		if not chunks:
			return None
		# Search from the end, as the question may contain the same words as the choices.
		joined = "".join(c for c, s in chunks)
		styles = []
		for item in menu.items:
			pos = joined.rfind(item.label)
			styles.append(_styleAt(chunks, pos) if pos != -1 else None)
		return _pickDistinct(styles)
	styles = []
	for item in menu.items:
		chunks = lineStyles(obj, item.lineIndex)
		if not chunks:
			return None
		styles.append(_styleAt(chunks, "".join(c for c, s in chunks).find(item.label)))
	return _pickDistinct(styles)


def _styleAt(chunks, pos):
	if pos < 0:
		return None
	offset = 0
	for chunk, style in chunks:
		if offset <= pos < offset + len(chunk):
			return style
		offset += len(chunk)
	return None


def _pickDistinct(styles):
	"""Index of the one style that differs from all the others, preferring underline."""
	if None in styles or len(styles) < 2:
		return None
	underlined = [i for i, s in enumerate(styles) if s[0]]
	if len(underlined) == 1:
		return underlined[0]
	if len(styles) < 3:
		# With two choices there is no majority to compare against.
		return None
	for i, style in enumerate(styles):
		others = styles[:i] + styles[i + 1 :]
		if all(o == others[0] for o in others) and style != others[0]:
			return i
	return None
