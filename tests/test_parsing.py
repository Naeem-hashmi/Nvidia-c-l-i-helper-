# Tests for the NVDA-independent parsing module. Run with: python -m unittest discover tests
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "globalPlugins", "cliHelper"))
import parsing  # noqa: E402

PROMPT = parsing.compilePattern(None, parsing.DEFAULT_PROMPT_REGEX)


def menu(text):
	return parsing.parseMenu(text.split("\n"), PROMPT)


class TestPrompts(unittest.TestCase):
	def test_promptLines(self):
		for line in (
			"PS C:\\Users\\me> ",
			"PS C:\\Users\\me> npm install",
			"C:\\Users\\me>",
			"C:\\Users\\me>dir",
			"me@host:~/project$ ls",
			"root@box:/# ",
			"$ git status",
			">>> print(1)",
		):
			self.assertTrue(parsing.isPromptLine(line, PROMPT), line)
		for line in (
			"Mode                 LastWriteTime         Length Name",
			"> my-app@0.1.0 dev",
			"Send mail to me@example.com for help",
			"    Directory: C:\\Users\\me",
			"",
		):
			self.assertFalse(parsing.isPromptLine(line, PROMPT), line)

	def test_commandFromLine(self):
		self.assertEqual(parsing.commandFromLine("PS C:\\x> git status", PROMPT), "git status")
		self.assertEqual(parsing.commandFromLine("C:\\x>dir /b", PROMPT), "dir /b")
		self.assertEqual(parsing.commandFromLine("me@h:~$ ", PROMPT), "")
		self.assertIsNone(parsing.commandFromLine("hello", PROMPT))

	def test_invalidCustomPatternFallsBack(self):
		pattern = parsing.compilePattern("([", parsing.DEFAULT_PROMPT_REGEX)
		self.assertEqual(pattern.pattern, parsing.DEFAULT_PROMPT_REGEX)


class TestOutput(unittest.TestCase):
	LINES = [
		"PS C:\\p> echo one",
		"one",
		"PS C:\\p> dir",
		"",
		"    Directory: C:\\p",
		"",
		"a.txt",
		"",
		"PS C:\\p> ",
		"",
	]

	def test_lastOutputFinished(self):
		cmd, out = parsing.lastOutput(parsing.splitLines("\n".join(self.LINES)), PROMPT)
		self.assertEqual(cmd, "dir")
		self.assertEqual(out, ["    Directory: C:\\p", "", "a.txt"])

	def test_lastOutputRunning(self):
		lines = ["PS C:\\p> npm run dev", "> app dev", "ready on 3000"]
		cmd, out = parsing.lastOutput(lines, PROMPT)
		self.assertEqual(cmd, "npm run dev")
		self.assertEqual(out, ["> app dev", "ready on 3000"])

	def test_lastOutputNoPrompt(self):
		self.assertEqual(parsing.lastOutput(["a", "b"], PROMPT), (None, ["a", "b"]))

	def test_nthLastLineSkipsEmptyPrompt(self):
		lines = parsing.splitLines("\n".join(self.LINES))
		self.assertEqual(parsing.nthLastLine(lines, 1, PROMPT), "a.txt")
		self.assertEqual(parsing.nthLastLine(lines, 2, PROMPT), "    Directory: C:\\p")
		self.assertIsNone(parsing.nthLastLine(lines, 50, PROMPT))

	def test_paragraphs(self):
		lines = ["a", "b", "", "c", "d", "", "", "e"]
		self.assertEqual(parsing.findLine(lines, 0, 1, lambda i: parsing.isParagraphStart(lines, i)), 3)
		self.assertEqual(parsing.findLine(lines, 3, 1, lambda i: parsing.isParagraphStart(lines, i)), 7)
		self.assertEqual(parsing.findLine(lines, 7, -1, lambda i: parsing.isParagraphStart(lines, i)), 3)
		self.assertIsNone(parsing.findLine(lines, 0, -1, lambda i: parsing.isParagraphStart(lines, i)))
		self.assertEqual(parsing.paragraphAt(lines, 4), "c\nd")

	def test_errorPattern(self):
		err = parsing.compilePattern(None, parsing.DEFAULT_ERROR_REGEX)
		self.assertTrue(err.search("npm ERR! code ENOENT"))
		self.assertTrue(err.search("'foo' is not recognized as an internal or external command"))
		self.assertTrue(err.search("Traceback (most recent call last):"))
		self.assertFalse(err.search("added 12 packages in 3s"))


class TestMenus(unittest.TestCase):
	def test_promptsSelectWindows(self):
		# create-next-app uses the "prompts" library, which draws ">" on Windows.
		m = menu(
			"PS C:\\dev> npx create-next-app@latest\n"
			"? Would you like to use the recommended Next.js defaults? \u00bb - Use arrow-keys. Return to submit.\n"
			">   Yes, use recommended defaults\n"
			"    No, reuse previous settings\n"
			"    No, customize settings",
		)
		self.assertEqual(m.kind, parsing.Menu.SELECT)
		self.assertEqual(
			[i.label for i in m.items],
			[
				"Yes, use recommended defaults",
				"No, reuse previous settings",
				"No, customize settings",
			],
		)
		self.assertEqual(m.focusIndex, 0)
		self.assertIn("recommended Next.js defaults", m.question)

	def test_inquirerSelectUnicode(self):
		m = menu(
			"? Which framework? (Use arrow keys)\n  React\n\u276f Vue\n  Svelte\n",
		)
		self.assertEqual(m.focusIndex, 1)
		self.assertEqual(m.focused.label, "Vue")
		self.assertEqual(m.question, "? Which framework? (Use arrow keys)")

	def test_inquirerNewFooterIsIgnored(self):
		m = menu(
			"? Pick one\n\u276f Alpha\n  Beta\n\u2191\u2193 navigate \u2022 \u23ce select",
		)
		self.assertEqual([i.label for i in m.items], ["Alpha", "Beta"])

	def test_inquirerCheckbox(self):
		m = menu(
			"? Select features (Press <space> to select)\n"
			" \u25c9 TypeScript\n"
			"\u276f\u25ef ESLint\n"
			" \u25c9 Tailwind",
		)
		self.assertEqual(m.kind, parsing.Menu.CHECKBOX)
		self.assertEqual(m.focused.label, "ESLint")
		self.assertEqual([i.checked for i in m.items], [True, False, True])

	def test_promptsMultiselectWindows(self):
		# "prompts" multiselect shows focus only by colour and underline.
		m = menu(
			"? Pick colors \u00bb\n( )   Red\n(*)   Green\n( )   Blue",
		)
		self.assertEqual(m.kind, parsing.Menu.CHECKBOX)
		self.assertIsNone(m.focusIndex)
		self.assertEqual([i.label for i in m.items], ["Red", "Green", "Blue"])
		self.assertEqual([i.checked for i in m.items], [False, True, False])

	def test_promptsSelectScrollArrows(self):
		m = menu("? Pick\n    \u2191 Two\n>   Three\n    \u2193 Four")
		self.assertEqual([i.label for i in m.items], ["Two", "Three", "Four"])
		self.assertEqual(m.focusIndex, 1)

	def test_clackAsciiFallback(self):
		# Without Unicode (classic conhost) @clack/prompts draws ASCII symbols.
		m = menu("*  Select a framework:\n|  > React\n|    Vue\n\u2014")
		self.assertEqual([i.label for i in m.items], ["React", "Vue"])
		self.assertEqual(m.focusIndex, 0)
		m = menu("*  Add-ons\n|  [+] prettier\n|  [\u2022] eslint\n|  [ ] vitest\n\u2014")
		self.assertEqual(m.kind, parsing.Menu.CHECKBOX)
		self.assertEqual(m.focused.label, "eslint")
		self.assertEqual([i.checked for i in m.items], [True, False, False])

	def test_clackSelect(self):
		# @clack/prompts (create-vite, sv create) marks focus with a filled radio.
		m = menu(
			"\u25c6  Select a framework:\n"
			"\u2502  \u25cb Vanilla\n"
			"\u2502  \u25cf React\n"
			"\u2502  \u25cb Vue\n"
			"\u2514",
		)
		self.assertEqual(m.kind, parsing.Menu.SELECT)
		self.assertEqual(m.focused.label, "React")
		self.assertIsNone(m.focused.checked)
		self.assertEqual(m.question, "\u25c6  Select a framework:")

	def test_clackMultiselectColourOnlyFocus(self):
		m = menu(
			"\u25c6  Add-ons\n\u2502  \u25fc prettier\n\u2502  \u25fb eslint\n\u2502  \u25fb vitest\n\u2514",
		)
		self.assertEqual(m.kind, parsing.Menu.CHECKBOX)
		self.assertIsNone(m.focusIndex)
		self.assertEqual([i.checked for i in m.items], [True, False, False])

	def test_promptsToggle(self):
		m = menu("? Would you like to use TypeScript? \u00bb No / Yes")
		self.assertEqual(m.kind, parsing.Menu.TOGGLE)
		self.assertEqual([i.label for i in m.items], ["No", "Yes"])
		self.assertIsNone(m.focusIndex)
		self.assertEqual(m.question, "? Would you like to use TypeScript?")

	def test_clackConfirm(self):
		m = menu("\u25c6  Install dependencies?\n\u2502  \u25cf Yes / \u25cb No\n\u2514")
		self.assertEqual(m.kind, parsing.Menu.TOGGLE)
		self.assertEqual(m.focused.label, "Yes")
		self.assertEqual(m.question, "\u25c6  Install dependencies?")

	def test_questionaryAndSurveyAndInquirerPy(self):
		# questionary (Python): " » " pointer, ● / ○ indicators.
		m = menu("? Toppings\n \u00bb \u25cf Cheese\n   \u25cb Ham\n   \u25cf Olives")
		self.assertEqual(m.kind, parsing.Menu.CHECKBOX)
		self.assertEqual(m.focused.label, "Cheese")
		self.assertEqual([i.checked for i in m.items], [True, False, True])
		m = menu("? Size\n \u00bb Small\n   Large")
		self.assertEqual((m.kind, m.focused.label), (parsing.Menu.SELECT, "Small"))
		# survey (Go): ">" focus icon, [x] / [ ] options.
		m = menu("? Pick days:\n  [ ]  Monday\n> [x]  Tuesday\n  [ ]  Friday")
		self.assertEqual((m.focused.label, m.focused.checked), ("Tuesday", True))
		# InquirerPy (Python): ❯ pointer, ◉ / ○.
		m = menu("? Select\n\u276f \u25c9 one\n  \u25cb two")
		self.assertEqual((m.focused.label, m.focused.checked), ("one", True))

	def test_finishedPromptIsNotAMenu(self):
		self.assertIsNone(
			menu(
				"? Pick one\n\u276f Alpha\n  Beta\nPS C:\\dev> ",
			)
		)

	def test_npmOutputIsNotAMenu(self):
		self.assertIsNone(menu("\n> my-app@0.1.0 dev\n> next dev\n\n   Ready in 2s"))
		self.assertIsNone(menu("> my-app@0.1.0 build\nCreating an optimized production build\nCompiled"))
		self.assertIsNone(menu("PS C:\\dev> dir\n\n    Directory: C:\\dev\n\na.txt\nPS C:\\dev> "))

	def test_stateChangesWithFocusAndChecks(self):
		a = menu("? x\n\u276f\u25ef A\n \u25ef B")
		b = menu("? x\n \u25ef A\n\u276f\u25ef B")
		c = menu("? x\n \u25ef A\n\u276f\u25c9 B")
		self.assertEqual(a.signature(), b.signature())
		self.assertNotEqual(a.state(), b.state())
		self.assertNotEqual(b.state(), c.state())


class TestPython37Syntax(unittest.TestCase):
	def test_sourcesParseAsPython37(self):
		# NVDA 2019.3 - 2023.3 run Python 3.7, so the add-on must not use newer syntax.
		import ast

		root = os.path.join(os.path.dirname(__file__), "..", "addon")
		for dirpath, _dirs, files in os.walk(root):
			for name in files:
				if name.endswith(".py"):
					path = os.path.join(dirpath, name)
					with open(path, encoding="utf-8") as f:
						ast.parse(f.read(), path, feature_version=(3, 7))


if __name__ == "__main__":
	unittest.main()
