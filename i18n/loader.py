import json
import os

from dotenv import load_dotenv

load_dotenv()


class I18n:
    def __init__(self, locale_dir="locales", default_lang="en"):
        self.locale_dir = locale_dir
        self.translations = {}
        self.lang = default_lang

    def load(self, lang):
        abs_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), self.locale_dir
        )
        path = os.path.join(abs_path, f"{lang}.json")
        with open(path, "r", encoding="utf-8") as f:
            self.translations[lang] = json.load(f)

    def set_lang(self, lang):
        if lang not in self.translations:
            self.load(lang)
        self.lang = lang

    def t(self, key, **kwargs):
        keys = key.split(".")
        value = self.translations[self.lang]

        for k in keys:
            value = value.get(k, {})

        if isinstance(value, str):
            return value.format(**kwargs)

        return key


i18n = I18n()
i18n.set_lang(os.getenv("LANG"))
