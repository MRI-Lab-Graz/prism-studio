from urllib import parse

from app.src.library_autotranslate import (
    DeepLTranslationProvider,
    translate_survey_template,
)


class _FakeHTTPResponse:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeTranslationProvider:
    def __init__(self):
        self.calls: list[list[str]] = []

    def translate_texts(self, texts, *, source_lang: str, target_lang: str):
        self.calls.append(list(texts))
        return [f"DE::{text}" for text in texts]


def test_translate_survey_template_adds_de_to_localized_fields() -> None:
    provider = FakeTranslationProvider()
    payload = {
        "Study": {
            "OriginalName": {"en": "Humor Styles Questionnaire"},
            "Instructions": {"en": "Please answer honestly."},
        },
        "HSQ01": {
            "Description": {"en": "I use humor to cope."},
            "Levels": {
                "0": {"en": "totally disagree"},
                "1": {"en": "totally agree"},
            },
        },
    }

    stats = translate_survey_template(payload, provider, batch_size=10)

    assert stats.localized_entries_added == 5
    assert payload["Study"]["OriginalName"]["de"] == "DE::Humor Styles Questionnaire"
    assert payload["Study"]["Instructions"]["de"] == "DE::Please answer honestly."
    assert payload["HSQ01"]["Description"]["de"] == "DE::I use humor to cope."
    assert payload["HSQ01"]["Levels"]["0"]["de"] == "DE::totally disagree"
    assert payload["HSQ01"]["Levels"]["1"]["de"] == "DE::totally agree"


def test_translate_survey_template_wraps_plain_description_and_levels() -> None:
    provider = FakeTranslationProvider()
    payload = {
        "HSQ01": {
            "Description": "I use humor to cope.",
            "Levels": {
                "0": "never",
                "1": "always",
            },
        }
    }

    stats = translate_survey_template(payload, provider, batch_size=10)

    assert stats.localized_entries_added == 3
    assert payload["HSQ01"]["Description"] == {
        "en": "I use humor to cope.",
        "de": "DE::I use humor to cope.",
    }
    assert payload["HSQ01"]["Levels"]["0"] == {
        "en": "never",
        "de": "DE::never",
    }
    assert payload["HSQ01"]["Levels"]["1"] == {
        "en": "always",
        "de": "DE::always",
    }


def test_translate_survey_template_preserves_existing_de_unless_overwrite_requested() -> (
    None
):
    provider = FakeTranslationProvider()
    payload = {
        "HSQ01": {
            "Description": {
                "en": "I use humor to cope.",
                "de": "Bestehende Uebersetzung",
            },
            "Levels": {
                "0": {"en": "never", "de": "nie"},
            },
        }
    }

    stats = translate_survey_template(payload, provider, batch_size=10)

    assert stats.localized_entries_added == 0
    assert payload["HSQ01"]["Description"]["de"] == "Bestehende Uebersetzung"
    assert payload["HSQ01"]["Levels"]["0"]["de"] == "nie"

    overwrite_stats = translate_survey_template(
        payload,
        provider,
        overwrite_existing=True,
        batch_size=10,
    )

    assert overwrite_stats.localized_entries_added == 2
    assert payload["HSQ01"]["Description"]["de"] == "DE::I use humor to cope."
    assert payload["HSQ01"]["Levels"]["0"]["de"] == "DE::never"


def test_deepl_provider_uses_authorization_header_not_auth_key_body(
    monkeypatch,
) -> None:
    captured = {}

    def fake_urlopen(req, timeout: int = 60):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["authorization"] = req.get_header("Authorization")
        captured["content_type"] = req.get_header("Content-type")
        captured["body"] = req.data.decode("utf-8")
        return _FakeHTTPResponse(
            '{"translations": [{"text": "Hallo"}, {"text": "Welt"}]}'
        )

    monkeypatch.setattr("app.src.library_autotranslate.request.urlopen", fake_urlopen)

    provider = DeepLTranslationProvider(
        "test-key", api_url="https://api-free.deepl.com/v2/translate"
    )
    result = provider.translate_texts(
        ["Hello", "World"], source_lang="en", target_lang="de"
    )

    assert result == ["Hallo", "Welt"]
    assert captured["authorization"] == "DeepL-Auth-Key test-key"
    assert captured["content_type"] == "application/x-www-form-urlencoded"
    parsed_body = parse.parse_qs(captured["body"])
    assert "auth_key" not in parsed_body
    assert parsed_body["source_lang"] == ["EN"]
    assert parsed_body["target_lang"] == ["DE"]
    assert parsed_body["text"] == ["Hello", "World"]
