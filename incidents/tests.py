from django.test import TestCase
from django.urls import reverse
import ast
import importlib.util
from pathlib import Path
import tempfile


class LoginTemplateLocaleTestCase(TestCase):
    def test_login_template_uses_rtl_for_hebrew(self):
        response = self.client.get(reverse("login"), HTTP_ACCEPT_LANGUAGE="he")
        self.assertContains(response, 'lang="he"')
        self.assertContains(response, 'dir="rtl"')

    def test_login_template_does_not_use_rtl_for_english(self):
        response = self.client.get(reverse("login"), HTTP_ACCEPT_LANGUAGE="en-us")
        self.assertRegex(response.content.decode(), r'lang="en(?:-us)?"')
        self.assertNotContains(response, 'dir="rtl"')

    def test_hebrew_login_po_catalog_has_translated_auth_strings(self):
        catalogs = [
            (
                Path(__file__).resolve().parent / "locale" / "he" / "LC_MESSAGES" / "django.po",
                {
                    "Sign in &middot; FIR": "התחברות &middot; FIR",
                    "Sign in to FIR": "התחברות ל-FIR",
                    "Username": "שם משתמש",
                    "Remember me": "זכור אותי",
                    "Sign in": "התחבר",
                },
            ),
            (
                Path(importlib.util.find_spec("fir_auth_2fa").submodule_search_locations[0])
                / "locale"
                / "he"
                / "LC_MESSAGES"
                / "django.po",
                {
                    "Sign in to FIR": "התחברות ל-FIR",
                    "Submit": "שלח",
                    "Back": "חזרה",
                    "Next": "הבא",
                },
            ),
        ]

        for catalog_path, required_translations in catalogs:
            self.assertTrue(
                catalog_path.exists(),
                f"Missing translation catalog file: {catalog_path}",
            )
            entries = self._parse_po_entries(catalog_path)
            for msgid, msgstr in required_translations.items():
                self.assertIn(msgid, entries)
                self.assertEqual(entries[msgid], msgstr)

            for msgid, msgstr in entries.items():
                if msgid:
                    self.assertTrue(msgstr.strip(), f"Missing Hebrew translation for: {msgid}")

    def test_parse_po_entries_supports_context_and_plural(self):
        po_content = """
msgctxt "button"
msgid "Back"
msgstr "חזרה"

msgid "item"
msgid_plural "items"
msgstr[0] "פריט"
msgstr[1] "פריטים"
"""
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=".po") as po_file:
            po_file.write(po_content)
            po_file.flush()
            entries = self._parse_po_entries(Path(po_file.name))

        self.assertEqual(entries["Back"], "חזרה")
        self.assertEqual(entries["item"], "פריט")
        self.assertEqual(entries["items"], "פריטים")

    @staticmethod
    def _parse_po_entries(path):
        entries = {}
        msgctxt = None
        msgid = None
        msgid_plural = None
        msgstr = {}
        mode = None

        def _decode_po_line(line):
            line = line.strip()
            if not (line.startswith('"') and line.endswith('"')):
                return ""
            return ast.literal_eval(line)

        def _store_entry():
            if not msgid:
                return
            if msgstr:
                if 0 in msgstr:
                    entries[msgid] = msgstr[0]
                    if msgid_plural and 1 in msgstr:
                        entries[msgid_plural] = msgstr[1]
                elif "single" in msgstr:
                    entries[msgid] = msgstr["single"]

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("#"):
                continue
            if line.startswith("msgctxt "):
                msgctxt = _decode_po_line(line[7:].strip())
                mode = "msgctxt"
                continue
            if line.startswith("msgid "):
                if msgid is not None:
                    _store_entry()
                msgid = _decode_po_line(line[5:].strip())
                msgid_plural = None
                msgstr = {}
                mode = "msgid"
                continue
            if line.startswith("msgid_plural "):
                msgid_plural = _decode_po_line(line[12:].strip())
                mode = "msgid_plural"
                continue
            if line.startswith("msgstr["):
                index_end = line.find("]")
                if index_end == -1:
                    continue
                index = int(line[7:index_end])
                msgstr[index] = _decode_po_line(line[index_end + 1 :].strip())
                mode = f"msgstr[{index}]"
                continue
            if line.startswith("msgstr "):
                msgstr["single"] = _decode_po_line(line[6:].strip())
                mode = "msgstr"
                continue
            if line.startswith('"') and line.endswith('"'):
                if mode == "msgctxt" and msgctxt is not None:
                    msgctxt += _decode_po_line(line)
                elif mode == "msgid" and msgid is not None:
                    msgid += _decode_po_line(line)
                elif mode == "msgid_plural" and msgid_plural is not None:
                    msgid_plural += _decode_po_line(line)
                elif mode == "msgstr":
                    msgstr["single"] = msgstr.get("single", "") + _decode_po_line(line)
                elif mode and mode.startswith("msgstr["):
                    index = int(mode[7:-1])
                    msgstr[index] = msgstr.get(index, "") + _decode_po_line(line)
                continue
            if line == "" and msgid is not None:
                _store_entry()
                msgctxt = None
                msgid = None
                msgid_plural = None
                msgstr = {}
                mode = None

        if msgid is not None:
            _store_entry()

        return entries
