# CLI Helper add-on for NVDA
# Copyright (C) 2026 CLI Helper contributors
# This file is covered by the GNU General Public License, version 2 or later.
# See the file COPYING.txt for more details.

"""Update check against the add-on's GitHub releases.

NVDA's Add-on Store (NVDA 2024.3 and later) already tells you about updates of add-ons it lists.
This check covers everyone else: older NVDA versions, and copies installed from GitHub.
Once a day at most, a little after NVDA starts, it asks GitHub for the latest release. If it is newer,
a dialog offers to download it; NVDA's normal add-on installation dialog then asks for confirmation.
"""

import json
import os
import re
import tempfile
import threading
import time
import zipfile

import addonHandler
import gui
import ui
import wx
from logHandler import log

from .common import conf

addonHandler.initTranslation()

REPOSITORY = "Naeem-hashmi/Nvidia-c-l-i-helper-"
LATEST_RELEASE_API = "https://api.github.com/repos/%s/releases/latest" % REPOSITORY
RELEASES_PAGE = "https://github.com/%s/releases/latest" % REPOSITORY
ADDON_NAME = "cliHelper"
#: Seconds between automatic checks.
CHECK_INTERVAL = 24 * 60 * 60
#: Wait this long after NVDA starts, so the check never slows down startup.
STARTUP_DELAY_MS = 20000


def parseVersion(text):
	"""(1, 2, 0) from "1.2", "v1.2.0" or "1.2.0-beta"; () if there is no number."""
	return tuple(int(n) for n in re.findall(r"\d+", text or "")[:3])


def isNewer(latest, current):
	a, b = list(parseVersion(latest)), list(parseVersion(current))
	length = max(len(a), len(b))
	return a + [0] * (length - len(a)) > b + [0] * (length - len(b))


def currentVersion():
	try:
		return addonHandler.getCodeAddon().version
	except Exception:
		return "0"


class Release(object):
	def __init__(self, version, notes, downloadUrl, pageUrl):
		self.version = version
		self.notes = notes
		self.downloadUrl = downloadUrl
		self.pageUrl = pageUrl


def releaseFromJson(data):
	"""Pick the version, notes and .nvda-addon download from a GitHub "latest release" answer."""
	downloadUrl = None
	for asset in data.get("assets") or ():
		url = asset.get("browser_download_url") or ""
		if url.endswith(".nvda-addon"):
			downloadUrl = url
			break
	version = (data.get("tag_name") or "").lstrip("vV")
	return Release(version, data.get("body") or "", downloadUrl, data.get("html_url") or RELEASES_PAGE)


def fetchLatestRelease():
	import urllib.request

	request = urllib.request.Request(
		LATEST_RELEASE_API,
		headers={"Accept": "application/vnd.github+json", "User-Agent": "CLI-Helper-NVDA-add-on"},
	)
	with urllib.request.urlopen(request, timeout=20) as response:
		return releaseFromJson(json.loads(response.read().decode("utf-8")))


def isEnabled():
	mode = conf()["updateCheck"]
	if mode == "off":
		return False
	if mode == "auto":
		# When NVDA's Add-on Store updates add-ons by itself, leave it to the store.
		try:
			import config

			if config.conf["addonStore"]["automaticUpdates"] == "update":
				return False
		except Exception:
			pass
	return True


def scheduleStartupCheck():
	"""Called when the add-on loads: check once a day, a little after NVDA has started."""
	if not isEnabled():
		return
	if time.time() - conf()["updateLastCheck"] < CHECK_INTERVAL:
		return
	import core

	core.callLater(STARTUP_DELAY_MS, checkInBackground, False)


def checkInBackground(manual):
	"""Ask GitHub on a background thread; manual checks also report "up to date" and errors."""

	def run():
		try:
			release = fetchLatestRelease()
			error = None
		except Exception as e:
			log.debugWarning("CLI Helper: update check failed", exc_info=True)
			release, error = None, e
		wx.CallAfter(_onChecked, release, error, manual)

	thread = threading.Thread(target=run, name="cliHelperUpdateCheck")
	thread.daemon = True
	thread.start()


def _onChecked(release, error, manual):
	conf()["updateLastCheck"] = int(time.time())
	if release is None:
		if manual:
			# Translators: Reported when checking for updates failed, for example without internet.
			ui.message(_("Could not check for updates. Check your internet connection and try again."))
		return
	current = currentVersion()
	if not isNewer(release.version, current):
		if manual:
			# Translators: Reported when the add-on is up to date; {version} is its version.
			ui.message(_("CLI Helper {version} is the latest version.").format(version=current))
		return
	if not manual and release.version == conf()["updateSkipVersion"]:
		return
	_offer(release, current)


def _offer(release, current):
	notes = release.notes.strip()
	if len(notes) > 1500:
		notes = notes[:1500].rsplit("\n", 1)[0] + "\n..."
	# Translators: Message of the update dialog.
	message = _("CLI Helper {new} is available. You have version {old}.").format(
		new=release.version, old=current
	)
	if notes:
		# Translators: Introduces the release notes in the update dialog.
		message += "\n\n" + _("What's new:") + "\n" + notes
	# Translators: Title of the update dialog.
	dialog = wx.MessageDialog(
		gui.mainFrame, message, _("CLI Helper update"), wx.YES_NO | wx.CANCEL | wx.ICON_INFORMATION
	)
	dialog.SetYesNoCancelLabels(
		# Translators: Button of the update dialog.
		_("&Download and install"),
		# Translators: Button of the update dialog.
		_("Remind me &later"),
		# Translators: Button of the update dialog.
		_("&Skip this version"),
	)
	gui.mainFrame.prePopup()
	try:
		answer = dialog.ShowModal()
	finally:
		dialog.Destroy()
		gui.mainFrame.postPopup()
	if answer == wx.ID_YES:
		if release.downloadUrl:
			_downloadAndInstall(release)
		else:
			import webbrowser

			webbrowser.open(release.pageUrl)
	elif answer == wx.ID_CANCEL:
		conf()["updateSkipVersion"] = release.version


def _downloadAndInstall(release):
	# Translators: Reported while an update downloads.
	ui.message(_("Downloading CLI Helper {version}...").format(version=release.version))

	def run():
		import urllib.request

		path = os.path.join(tempfile.gettempdir(), "%s-%s.nvda-addon" % (ADDON_NAME, release.version))
		try:
			request = urllib.request.Request(
				release.downloadUrl, headers={"User-Agent": "CLI-Helper-NVDA-add-on"}
			)
			with urllib.request.urlopen(request, timeout=60) as response, open(path, "wb") as out:
				out.write(response.read())
			if not isOwnPackage(path):
				raise ValueError("downloaded file is not a CLI Helper add-on package")
		except Exception:
			log.warning("CLI Helper: update download failed", exc_info=True)
			wx.CallAfter(_downloadFailed, release)
			return
		wx.CallAfter(_install, path)

	thread = threading.Thread(target=run, name="cliHelperUpdateDownload")
	thread.daemon = True
	thread.start()


def isOwnPackage(path):
	"""Check that a downloaded file is a CLI Helper add-on before handing it to NVDA."""
	try:
		with zipfile.ZipFile(path) as package:
			manifest = package.read("manifest.ini").decode("utf-8", "replace")
	except Exception:
		return False
	return bool(re.search(r"^name\s*=\s*%s\s*$" % ADDON_NAME, manifest, re.MULTILINE))


def _install(path):
	"""Hand the package to NVDA, which shows its usual install dialog and asks to restart."""
	try:
		from gui import addonGui

		addonGui.handleRemoteAddonInstall(path)
	except Exception:
		log.debugWarning("CLI Helper: NVDA's installer not available, opening the file", exc_info=True)
		os.startfile(path)


def _downloadFailed(release):
	import webbrowser

	# Translators: Reported when an update could not be downloaded; the download page opens instead.
	ui.message(_("The download failed. Opening the download page."))
	webbrowser.open(release.pageUrl)
