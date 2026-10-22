# Tests for progress bar recognition, error summaries and command history parsing.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "globalPlugins", "cliHelper"))
import parsing  # noqa: E402
import problems  # noqa: E402
import progress  # noqa: E402

ERROR_RE = parsing.compilePattern(None, parsing.DEFAULT_ERROR_REGEX)
PROMPT = parsing.compilePattern(None, parsing.DEFAULT_PROMPT_REGEX)

# Lines as drawn by real tools (ollama's format is from its progress/bar.go and spinner.go).
OLLAMA = "pulling 6a0746a1ec1a:  45% \u2595\u2588\u2588\u2588\u2588\u2588\u2588      \u258f 2.1 GB/4.7 GB   25 MB/s   1m40s"
OLLAMA_SPINNER = "pulling manifest \u280b "
PIP = "   \u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2578\u2501\u2501\u2501\u2501 4.2/10.0 MB 3.1 MB/s eta 0:00:02"
DOCKER = "a3ed95caeb02: Downloading [=====>      ]  12.3MB/45.6MB"
GIT = "Receiving objects:  45% (4500/10000), 2.10 MiB | 1.20 MiB/s"
WINGET = "  \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2592\u2592\u2592\u2592  12.0 MB / 30.0 MB"
TQDM = " 45%|\u2588\u2588\u2588\u2588\u258c     | 450/1000 [00:02<00:03, 150.00it/s]"


class TestProgressRecognition(unittest.TestCase):
	def test_strongProgressLines(self):
		for line in (OLLAMA, OLLAMA_SPINNER, PIP, DOCKER, GIT, WINGET, TQDM, "\u280b reify:react: timing"):
			self.assertTrue(progress.isStrongProgressLine(line), line)

	def test_ordinaryLinesAreNotProgress(self):
		for line in (
			"Coverage: 85%",
			"===================== 5 passed in 0.12s =====================",
			"---------------------------------",
			"added 120 packages in 3s",
			"\u2500\u2500\u2500\u2500\u2500 Summary \u2500\u2500\u2500\u2500\u2500",
			"success",
			"pulling manifest",
			"Done in 4.2s.",
		):
			self.assertFalse(progress.isStrongProgressLine(line), line)

	def test_fragments(self):
		# What NVDA reports when only part of a redrawn bar changes.
		for text in (
			"46",
			"2.2 GB/4.7",
			"1m39s",
			" 26 MB/s",
			"\u2588\u2588 ",
			"46% \u2595\u2588",
			"eta 0:00:01",
		):
			self.assertTrue(progress.isProgressFragment(text), text)
		for text in ("teams", "done", "Error 404", "verifying sha256 digest", "writing manifest"):
			self.assertFalse(progress.isProgressFragment(text), text)

	def test_extractPercent(self):
		self.assertEqual(progress.extractPercent(OLLAMA), 45)
		self.assertAlmostEqual(progress.extractPercent(PIP), 42.0)
		self.assertAlmostEqual(progress.extractPercent(DOCKER), 12.3 * 100 / 45.6)
		self.assertEqual(progress.extractPercent(GIT), 45)
		self.assertAlmostEqual(progress.extractPercent(WINGET), 40.0)
		self.assertAlmostEqual(progress.extractPercent("512 KB/1 MB"), 51.2)
		self.assertIsNone(progress.extractPercent("pulling manifest"))

	def test_label(self):
		self.assertEqual(progress.label(OLLAMA), "pulling")
		self.assertEqual(progress.label(GIT), "Receiving objects")
		self.assertEqual(progress.label(DOCKER), "Downloading")
		self.assertEqual(progress.label(PIP), "")


class TestProgressTracker(unittest.TestCase):
	def speak(self, actions):
		return [(a[1], a[2]) for a in actions if a[0] == "speak"]

	def test_speaksAtStepsOnly(self):
		tracker = progress.ProgressTracker("speech", 25, 0)
		spoken = []
		for n in range(0, 101):
			spoken += self.speak(tracker.feed("pulling", float(n), n))
		self.assertEqual(spoken, [("pulling", 0), ("", 25), ("", 50), ("", 75), ("", 100)])

	def test_minimumIntervalButAlwaysTheEnd(self):
		tracker = progress.ProgressTracker("speech", 10, 5)
		spoken = []
		for n in range(0, 101, 5):
			# The whole download takes two seconds: only the start and the end are spoken.
			spoken += self.speak(tracker.feed("x", float(n), n / 50.0))
		self.assertEqual(spoken, [("x", 0), ("", 100)])

	def test_newLabelStartsAgain(self):
		tracker = progress.ProgressTracker("speech", 50, 0)
		self.assertEqual(self.speak(tracker.feed("a", 60, 0)), [("a", 60)])
		self.assertEqual(self.speak(tracker.feed("b", 10, 1)), [("b", 10)])

	def test_tonesAndSilent(self):
		tracker = progress.ProgressTracker("tones", 25, 0)
		self.assertEqual(tracker.feed("x", 10, 0), [("tone", 10)])
		# Less than 1 percent of change, or less than a quarter second later: no beep.
		self.assertEqual(tracker.feed("x", 10.5, 1), [])
		self.assertEqual(tracker.feed("x", 12, 0.1), [])
		self.assertEqual(tracker.feed("x", 12, 1.1), [("tone", 12)])
		self.assertEqual(progress.ProgressTracker("silent").feed("x", 50, 0), [])
		self.assertEqual(progress.toneFrequency(0), 110)
		self.assertEqual(progress.toneFrequency(100), 1760)


class TestProblems(unittest.TestCase):
	def summarize(self, text):
		return problems.summarize(text.split("\n"), ERROR_RE)

	def test_nextTypeError(self):
		found = self.summarize(
			"Creating an optimized production build ...\n"
			"Failed to compile.\n"
			"\n"
			"./src/app/page.tsx:12:5\n"
			"Type error: Type 'string' is not assignable to type 'number'.\n"
			"\n"
			"  10 | export default function Home() {\n"
		)
		self.assertEqual([p.kind for p in found], ["error", "error"])
		last = found[1]
		self.assertEqual(last.message, "Type error: Type 'string' is not assignable to type 'number'.")
		self.assertEqual((last.file, last.line), ("./src/app/page.tsx", 12))

	def test_pythonTraceback(self):
		found = self.summarize(
			"Traceback (most recent call last):\n"
			'  File "C:\\app\\main.py", line 3, in <module>\n'
			"    run()\n"
			'  File "C:\\app\\lib.py", line 9, in run\n'
			"    raise ValueError('bad value')\n"
			"ValueError: bad value"
		)
		self.assertEqual(len(found), 1)
		self.assertEqual(found[0].message, "ValueError: bad value")
		self.assertEqual((found[0].file, found[0].line), ("C:\\app\\lib.py", 9))
		self.assertEqual(problems.fileLabel(found[0].file), "lib.py")

	def test_npmErrorBlockIsOneProblem(self):
		found = self.summarize(
			"npm ERR! code E404\n"
			"npm ERR! 404 Not Found - GET https://registry.npmjs.org/nope - Not found\n"
			"npm ERR! 404\n"
			"npm WARN deprecated inflight@1.0.6: This module is not supported\n"
		)
		self.assertEqual([p.kind for p in found], ["error", "warning"])
		self.assertEqual(found[0].message, "404 Not Found - GET https://registry.npmjs.org/nope - Not found")

	def test_eslintAndRustLocations(self):
		found = self.summarize(
			"C:\\proj\\src\\index.js\n  1:10  error  'x' is defined but never used  no-unused-vars\n"
			"  2:5   warning  Unexpected console statement  no-console\n"
		)
		self.assertEqual([p.kind for p in found], ["error", "warning"])
		self.assertEqual((found[0].file, found[0].line), ("C:\\proj\\src\\index.js", 1))
		self.assertEqual((found[1].file, found[1].line), ("C:\\proj\\src\\index.js", 2))
		found = self.summarize(
			"error[E0425]: cannot find value `x` in this scope\n --> src/main.rs:4:5\n  |\n"
		)
		self.assertEqual((found[0].file, found[0].line, found[0].column), ("src/main.rs", 4, 5))

	def test_successLinesAreNotProblems(self):
		self.assertEqual(self.summarize("found 0 vulnerabilities\nCompiled with 0 errors and 0 warnings"), [])

	def test_shorten(self):
		self.assertEqual(problems.shorten("a  b\n c", 100), "a b c")
		text = problems.shorten("word " * 100, 40)
		self.assertLessEqual(len(text), 41)
		self.assertTrue(text.endswith("\u2026"))

	def test_classifyForSounds(self):
		self.assertEqual(problems.classify("npm ERR! code E404", ERROR_RE), "error")
		self.assertEqual(problems.classify("npm WARN deprecated x", ERROR_RE), "warning")
		self.assertEqual(problems.classify("\u2713 Compiled successfully", ERROR_RE), "success")
		self.assertEqual(problems.classify("found 0 vulnerabilities", ERROR_RE), "success")
		self.assertIsNone(problems.classify("Creating a new Next.js app", ERROR_RE))


class TestCommandBlocks(unittest.TestCase):
	def test_blocks(self):
		lines = [
			"PS C:\\p> git status",
			"On branch main",
			"PS C:\\p> ",
			"PS C:\\p> dir",
			"",
			"a.txt",
			"",
			"PS C:\\p> ",
		]
		self.assertEqual(
			parsing.commandBlocks(lines, PROMPT),
			[("git status", ["On branch main"]), ("dir", ["a.txt"])],
		)


if __name__ == "__main__":
	unittest.main()
