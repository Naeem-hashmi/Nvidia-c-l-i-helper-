# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""The command history window: every command in the terminal with its output."""

import addonHandler
import api
import gui
import ui
import wx

from . import reader

addonHandler.initTranslation()

_instance = None


class HistoryDialog(wx.Dialog):
	def __init__(self, parent, entries):
		"""entries: list of (command, outputLines, errorCount, warningCount), oldest first."""
		# Translators: Title of the command history window.
		super(HistoryDialog, self).__init__(
			parent, title=_("Command history"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
		)
		self.entries = entries
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of the list of commands in the command history window.
		mainSizer.Add(
			wx.StaticText(self, label=_("&Commands (newest last):")), flag=wx.LEFT | wx.TOP, border=8
		)
		self.list = wx.ListBox(self, choices=[self._label(e) for e in entries], size=(700, 200))
		mainSizer.Add(self.list, proportion=1, flag=wx.EXPAND | wx.ALL, border=8)
		# Translators: Label of the output field in the command history window.
		mainSizer.Add(wx.StaticText(self, label=_("&Output:")), flag=wx.LEFT, border=8)
		self.output = wx.TextCtrl(
			self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.TE_DONTWRAP, size=(700, 250)
		)
		mainSizer.Add(self.output, proportion=2, flag=wx.EXPAND | wx.ALL, border=8)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		for label, handler in (
			# Translators: A button in the command history window.
			(_("Copy co&mmand"), self.onCopyCommand),
			# Translators: A button in the command history window.
			(_("Copy o&utput"), self.onCopyOutput),
			# Translators: A button in the command history window.
			(_("Open in &reader"), self.onOpenReader),
		):
			button = wx.Button(self, label=label)
			button.Bind(wx.EVT_BUTTON, handler)
			buttons.Add(button, flag=wx.RIGHT, border=8)
		# Translators: A button in the command history window.
		closeButton = wx.Button(self, id=wx.ID_CLOSE, label=_("&Close"))
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
		buttons.Add(closeButton)
		mainSizer.Add(buttons, flag=wx.ALIGN_RIGHT | wx.ALL, border=8)
		self.SetSizerAndFit(mainSizer)
		self.SetEscapeId(wx.ID_CLOSE)
		self.list.Bind(wx.EVT_LISTBOX, self.onSelect)
		self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.onOpenReader)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		if entries:
			self.list.SetSelection(len(entries) - 1)
			self.onSelect(None)
		self.list.SetFocus()

	@staticmethod
	def _label(entry):
		command, output, errors, warnings = entry
		# Translators: Number of output lines of a command in the history list.
		parts = [command, _("{count} lines").format(count=len(output))]
		if errors:
			# Translators: Number of errors of a command in the history list.
			parts.append(_("{count} errors").format(count=errors))
		if warnings:
			# Translators: Number of warnings of a command in the history list.
			parts.append(_("{count} warnings").format(count=warnings))
		return ", ".join(parts)

	def _current(self):
		index = self.list.GetSelection()
		if index == wx.NOT_FOUND:
			return None
		return self.entries[index]

	def onSelect(self, evt):
		entry = self._current()
		self.output.SetValue("\n".join(entry[1]) if entry else "")

	def _copy(self, text):
		if text.strip() and api.copyToClip(text):
			# Translators: Reported after copying.
			ui.message(_("Copied"))

	def onCopyCommand(self, evt):
		entry = self._current()
		if entry:
			self._copy(entry[0])

	def onCopyOutput(self, evt):
		entry = self._current()
		if entry:
			self._copy("\n".join(entry[1]))

	def onOpenReader(self, evt):
		entry = self._current()
		if not entry:
			return
		self.Close()
		# Translators: Title of the reader window; {command} is the command that produced the output.
		reader.show(_("Output of {command}").format(command=entry[0]), "\n".join(entry[1]), 0)

	def onClose(self, evt):
		global _instance
		_instance = None
		self.Destroy()


def show(entries):
	"""Open the history window. Must be called on the main thread."""
	global _instance
	if _instance is not None:
		try:
			_instance.Destroy()
		except Exception:
			pass
	gui.mainFrame.prePopup()
	_instance = HistoryDialog(gui.mainFrame, entries)
	_instance.Show()
	_instance.Raise()
	gui.mainFrame.postPopup()
