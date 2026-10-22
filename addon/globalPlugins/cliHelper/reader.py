# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""A read-only document window for terminal output.

The text sits in a standard multi-line edit control, so all of NVDA's usual reading keys work
exactly as in a word processor: arrows, Control+arrows for words and paragraphs, Home/End,
Control+Home/End, Shift to select, Control+C to copy, and say all.
"""

import addonHandler
import api
import gui
import ui
import wx

addonHandler.initTranslation()

_instance = None


class OutputReader(wx.Dialog):
	def __init__(self, parent, title, text, startOffset):
		super(OutputReader, self).__init__(
			parent,
			title=title,
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
		)
		self._lastSearch = ""
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		self.text = wx.TextCtrl(
			self,
			value=text,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.TE_DONTWRAP,
			size=(800, 500),
		)
		mainSizer.Add(self.text, proportion=1, flag=wx.EXPAND | wx.ALL, border=8)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: A button in the terminal output reader.
		findButton = wx.Button(self, label=_("&Find... (Control+F)"))
		findButton.Bind(wx.EVT_BUTTON, lambda evt: self.find())
		buttons.Add(findButton)
		# Translators: A button in the terminal output reader.
		copyButton = wx.Button(self, label=_("Copy &all"))
		copyButton.Bind(wx.EVT_BUTTON, self.onCopyAll)
		buttons.Add(copyButton, flag=wx.LEFT, border=8)
		# Translators: A button in the terminal output reader.
		closeButton = wx.Button(self, id=wx.ID_CLOSE, label=_("&Close"))
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
		buttons.Add(closeButton, flag=wx.LEFT, border=8)
		mainSizer.Add(buttons, flag=wx.ALIGN_RIGHT | wx.ALL, border=8)
		self.SetSizerAndFit(mainSizer)
		self.SetEscapeId(wx.ID_CLOSE)
		self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.text.SetFocus()
		self.text.SetInsertionPoint(startOffset)
		self.text.ShowPosition(startOffset)

	def onCharHook(self, evt):
		key = evt.GetKeyCode()
		if key == ord("F") and evt.ControlDown():
			self.find()
		elif key == wx.WXK_F3:
			self.findNext(backwards=evt.ShiftDown())
		elif key == wx.WXK_ESCAPE:
			self.Close()
		else:
			evt.Skip()

	def find(self):
		# Translators: Prompt of the find dialog in the terminal output reader.
		text = wx.GetTextFromUser(_("Text to find:"), _("Find"), self._lastSearch, self)
		if text:
			self._lastSearch = text
			self.findNext()

	def findNext(self, backwards=False):
		if not self._lastSearch:
			self.find()
			return
		haystack = self.text.GetValue().lower()
		needle = self._lastSearch.lower()
		pos = self.text.GetInsertionPoint()
		if backwards:
			found = haystack.rfind(needle, 0, max(0, pos))
		else:
			found = haystack.find(needle, pos + 1)
		if found == -1:
			# Translators: Reported when the searched text is not found.
			ui.message(_("Not found"))
			return
		self.text.SetFocus()
		self.text.SetInsertionPoint(found)
		self.text.SetSelection(found, found + len(needle))
		# Report the line containing the match.
		start = haystack.rfind("\n", 0, found) + 1
		end = haystack.find("\n", found)
		ui.message(self.text.GetValue()[start : end if end != -1 else None])

	def onCopyAll(self, evt):
		if api.copyToClip(self.text.GetValue()):
			# Translators: Reported after copying.
			ui.message(_("Copied"))

	def onClose(self, evt):
		global _instance
		_instance = None
		self.Destroy()


def show(title, text, startOffset=0):
	"""Open (or replace) the reader window. Must be called on the main thread."""
	global _instance
	if _instance is not None:
		try:
			_instance.Destroy()
		except Exception:
			pass
	gui.mainFrame.prePopup()
	_instance = OutputReader(gui.mainFrame, title, text, startOffset)
	_instance.Show()
	_instance.Raise()
	gui.mainFrame.postPopup()
