from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib import error, parse, request

from src.utils.io import read_json, write_json

_LANG_KEY_RE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")
_TRANSLATABLE_STRING_FIELDS = {
    "Description",
    "OriginalName",
    "Instructions",
    "License",
    "Version",
}


class TranslationProvider(Protocol):
    def translate_texts(
        self, texts: list[str], *, source_lang: str, target_lang: str
    ) -> list[str]: ...


class TranslationError(RuntimeError):
    pass


@dataclass
class TranslationRef:
    mapping: dict[str, Any]
    target_lang: str
    source_text: str


@dataclass
class TranslationStats:
    files_processed: int = 0
    files_changed: int = 0
    localized_entries_added: int = 0
    unique_source_texts: int = 0


def _is_language_map(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value
        and all(
            isinstance(key, str) and _LANG_KEY_RE.match(key) for key in value.keys()
        )
    )


def _chunked(values: list[str], chunk_size: int) -> list[list[str]]:
    if chunk_size <= 0:
        return [values]
    return [values[idx : idx + chunk_size] for idx in range(0, len(values), chunk_size)]


class DeepLTranslationProvider:
    def __init__(self, api_key: str, api_url: str | None = None):
        self.api_key = api_key.strip()
        self.api_url = (
            api_url.strip()
            if api_url
            else os.environ.get(
                "DEEPL_API_URL", "https://api-free.deepl.com/v2/translate"
            ).strip()
        )
        if not self.api_key:
            raise TranslationError("DeepL API key is required")

    def translate_texts(
        self, texts: list[str], *, source_lang: str, target_lang: str
    ) -> list[str]:
        if not texts:
            return []

        form_data: list[tuple[str, str]] = [
            ("source_lang", source_lang.upper()),
            ("target_lang", target_lang.upper()),
        ]
        form_data.extend(("text", text) for text in texts)
        payload = parse.urlencode(form_data).encode("utf-8")
        req = request.Request(
            self.api_url,
            data=payload,
            headers={
                "Authorization": f"DeepL-Auth-Key {self.api_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=60) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TranslationError(
                f"DeepL request failed: {exc.code} {detail}"
            ) from exc
        except error.URLError as exc:
            raise TranslationError(f"DeepL request failed: {exc}") from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise TranslationError("DeepL returned invalid JSON") from exc

        translations = data.get("translations")
        if not isinstance(translations, list) or len(translations) != len(texts):
            raise TranslationError("DeepL returned an unexpected translation payload")

        translated_texts: list[str] = []
        for entry in translations:
            if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
                raise TranslationError("DeepL returned an invalid translation entry")
            translated_texts.append(entry["text"])
        return translated_texts


class LibreTranslateProvider:
    def __init__(self, api_url: str, api_key: str | None = None):
        self.api_url = api_url.strip()
        self.api_key = (api_key or os.environ.get("LIBRETRANSLATE_API_KEY", "")).strip()
        if not self.api_url:
            raise TranslationError("LibreTranslate API URL is required")

    def translate_texts(
        self, texts: list[str], *, source_lang: str, target_lang: str
    ) -> list[str]:
        if not texts:
            return []

        payload_dict: dict[str, Any] = {
            "q": texts,
            "source": source_lang,
            "target": target_lang,
            "format": "text",
        }
        if self.api_key:
            payload_dict["api_key"] = self.api_key

        payload = json.dumps(payload_dict).encode("utf-8")
        req = request.Request(
            self.api_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=60) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TranslationError(
                f"LibreTranslate request failed: {exc.code} {detail}"
            ) from exc
        except error.URLError as exc:
            raise TranslationError(f"LibreTranslate request failed: {exc}") from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise TranslationError("LibreTranslate returned invalid JSON") from exc

        translated = data.get("translatedText")
        if isinstance(translated, list) and len(translated) == len(texts):
            if not all(isinstance(entry, str) for entry in translated):
                raise TranslationError(
                    "LibreTranslate returned invalid translation entries"
                )
            return translated
        if isinstance(translated, str) and len(texts) == 1:
            return [translated]
        raise TranslationError(
            "LibreTranslate returned an unexpected translation payload"
        )


def build_translation_provider(
    provider_name: str,
    *,
    api_key: str | None = None,
    api_url: str | None = None,
) -> TranslationProvider:
    normalized = provider_name.strip().lower()
    if normalized == "deepl":
        resolved_key = (api_key or os.environ.get("DEEPL_API_KEY", "")).strip()
        return DeepLTranslationProvider(api_key=resolved_key, api_url=api_url)
    if normalized == "libretranslate":
        resolved_url = (api_url or os.environ.get("LIBRETRANSLATE_URL", "")).strip()
        return LibreTranslateProvider(api_url=resolved_url, api_key=api_key)
    raise TranslationError(f"Unsupported translation provider: {provider_name}")


def _collect_translation_refs(
    node: Any,
    refs: list[TranslationRef],
    *,
    source_lang: str,
    target_lang: str,
    overwrite_existing: bool,
    in_levels: bool = False,
) -> None:
    if isinstance(node, list):
        for entry in node:
            _collect_translation_refs(
                entry,
                refs,
                source_lang=source_lang,
                target_lang=target_lang,
                overwrite_existing=overwrite_existing,
                in_levels=in_levels,
            )
        return

    if not isinstance(node, dict):
        return

    if _is_language_map(node):
        source_text = str(node.get(source_lang, "") or "").strip()
        target_text = str(node.get(target_lang, "") or "").strip()
        if source_text and (overwrite_existing or not target_text):
            refs.append(
                TranslationRef(
                    mapping=node,
                    target_lang=target_lang,
                    source_text=source_text,
                )
            )
        return

    for key, value in list(node.items()):
        if isinstance(value, str) and (in_levels or key in _TRANSLATABLE_STRING_FIELDS):
            source_text = value.strip()
            if not source_text:
                continue
            localized = {source_lang: value}
            node[key] = localized
            refs.append(
                TranslationRef(
                    mapping=localized,
                    target_lang=target_lang,
                    source_text=source_text,
                )
            )
            continue

        _collect_translation_refs(
            value,
            refs,
            source_lang=source_lang,
            target_lang=target_lang,
            overwrite_existing=overwrite_existing,
            in_levels=(key == "Levels"),
        )


def translate_survey_template(
    data: dict[str, Any],
    provider: TranslationProvider,
    *,
    source_lang: str = "en",
    target_lang: str = "de",
    overwrite_existing: bool = False,
    batch_size: int = 50,
) -> TranslationStats:
    refs: list[TranslationRef] = []
    _collect_translation_refs(
        data,
        refs,
        source_lang=source_lang,
        target_lang=target_lang,
        overwrite_existing=overwrite_existing,
    )

    unique_source_texts = list(dict.fromkeys(ref.source_text for ref in refs))
    translations: dict[str, str] = {}
    for chunk in _chunked(unique_source_texts, batch_size):
        translated_chunk = provider.translate_texts(
            chunk,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        for source_text, translated_text in zip(chunk, translated_chunk):
            translations[source_text] = translated_text

    localized_entries_added = 0
    for ref in refs:
        translated_text = translations.get(ref.source_text, "")
        if translated_text and ref.mapping.get(ref.target_lang) != translated_text:
            ref.mapping[ref.target_lang] = translated_text
            localized_entries_added += 1

    return TranslationStats(
        localized_entries_added=localized_entries_added,
        unique_source_texts=len(unique_source_texts),
    )


def autotranslate_survey_library(
    src_dir: Path,
    dst_dir: Path,
    provider: TranslationProvider,
    *,
    source_lang: str = "en",
    target_lang: str = "de",
    overwrite_existing: bool = False,
    batch_size: int = 50,
) -> TranslationStats:
    files = sorted(src_dir.glob("survey-*.json"))
    stats = TranslationStats(files_processed=len(files))

    for path in files:
        data = read_json(path)
        file_stats = translate_survey_template(
            data,
            provider,
            source_lang=source_lang,
            target_lang=target_lang,
            overwrite_existing=overwrite_existing,
            batch_size=batch_size,
        )
        if file_stats.localized_entries_added > 0:
            stats.files_changed += 1
            stats.localized_entries_added += file_stats.localized_entries_added
            write_json(dst_dir / path.name, data)
        elif src_dir != dst_dir:
            write_json(dst_dir / path.name, data)

        stats.unique_source_texts += file_stats.unique_source_texts

    return stats
