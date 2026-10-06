# Multilingual: language packs

## 1. Purpose

Make the library work in any language with no language text in the Python
code: everything that depends on the language lives in a pack.

## 2. Scope and non-scope

- **Scope:** stemmer, entities written with words (numbers, months, periods,
  references to parts of the document), exception and condition markers,
  conversational patterns, messages, widget texts and tones.
- **Non-scope:** detecting the language of each question, and corpora with
  several languages at once.

## 3. Versioned inputs and outputs

- `ipsis/recursos/idiomas/<code>.yaml`: the language pack.
- `ipsis/recursos/tonos/<code>/<tone>.yaml` and `_reglas.yaml`: the 7 tones
  and their linter.
- `config/language.yaml` (optional): the project's overrides.
- The index manifest stores the stemmer: changing the language requires
  reindexing.

## 4. Algorithm and tie-breaking

- `assistant.yaml::language` picks the pack. A regional variant (`pt-br`)
  uses its base language's pack. A code without a pack works with the
  universal rules, unstemmed `terminos()` and English texts; `ipsis doctor`
  warns about it.
- **Universal entities:** figures, percentages, numeric dates and amounts
  with a currency. Their `valor_norm` does not depend on the language
  (`2024-03-15`, `6_mes`).
- **Pack entities:** those written with words ("six months", "March
  fifteenth", "article four").
- **Sentences:** a single `dividir_oraciones()` with `. ? ! 。 ！ ？ ؟ ।`.
- **Tones:** 7 tones × 18 situations × 7 to 12 variants per language (154 per tone). The variant
  is chosen by (session, turn, situation) and does not repeat in consecutive
  turns.

## 5. Assumptions

Question and corpus in the project language. The models are multilingual: a
question in another language may work, but a high `s_oov` tends to lead to
abstaining (the safe side).

## 6. Invariants

- No language text in Python (a code rule). The widget receives its texts
  from the pack via `/config` and only carries English fallback texts in case
  `/config` does not answer.
- The included tones are neutral: no regionalisms, no gendered forms for the
  person and no greetings that depend on the time of day (neutrality test). In
  a project's own texts it is a warning.
- The tone linter requires a single line of up to 200 characters, without
  digits, URLs, HTML or Markdown, and with ¡ ¿ closed.

## 7. Parameters and defaults

Included packs: `en`, `es` and `pt`. Default language of `ipsis init`: the one
given with `--language`; otherwise the interface language (`en`, or `es` with
`IPSIS_LANG=es`).

## 8. Complexity and resources

Loaded once per process, cached.

## 9. Failures and fallback

Invalid language code: an error listing the available ones. Without a pack:
universal rules in English and a warning.

## 10. Security and privacy

No effect.

## 11. Technical tests

`tests/lenguaje/` (packs, entities, the linter over 3,234 templates and
neutrality) and the universal bank in three languages.

## 12. Limitations

- No per-question language detection.
- The universal bank is multilingual, not cross-lingual: it does not measure
  questions in one language over a corpus in another.

## 13. References and provenance

- [snowballstemmer](https://pypi.org/project/snowballstemmer/) (29 stemmers,
  28 languages).
- Unicode UAX #29 for word boundaries (`\w+`).

## 14. Status

Stable for `en`, `es` and `pt`; experimental for other languages.
