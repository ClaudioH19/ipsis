# V4 evaluation: conversation memory, local synonyms and intent fallback

This report describes the initial V4 snapshot (`b23ad8a`). Subsequent
[conversation and intent corrections](mediciones/v4-correcciones/README.md)
retain this comparison as their baseline and report verification separately.
The defects listed below describe that initial snapshot.

The engine now keeps bounded conversation topics with inactivity expiry,
uses versioned local WordNet tables for conservative BM25 expansion, and
can infer an unknown intention from measured examples. These features
preserve the extractive design: source text supplies the answer, the answer
policy retains its thresholds, and no model weights are trained.

The stored lexical inventory contains **3,635,200 written forms and
expressions** across es/en/pt. This includes inflections, names and phrases;
it is not a count of interchangeable synonyms. Original downloads remain
in the repository for offline work. The query engine uses only the filtered
WordNet tables, not the complete dictionaries or thesauri.

## Evidence and comparability

[F2 measurements](mediciones/f2/README.md) isolate local synonym integration
against the working tree that already contained conversation topics.
[Final V4 measurements](mediciones/v4/README.md) compare the final engine
both with that continuation baseline and with the original F1 runtime
(`39c7878`). All three banks use light/medium × es/en/pt.

F1 is remeasured with the corrected literal evaluation and no change to its
engine. A QA reader's selected span takes precedence over the enclosing
evidence: a correct fact elsewhere in a citation does not make an incomplete
selected answer correct. The earlier F1 medium counts therefore cannot be
compared directly with the corrected counts. The
[generated tables](mediciones/v4/tablas.md) and
[case comparison](mediciones/v4/comparacion.json) retain the comparable results.

That F1 comparison caught a lost correct Spanish answer about not submitting
expenses on time. The initial memory implementation made `tiempo/tempo`
globally generic and thereby also changed answer selection. The correction
uses a separate `genericas_memoria` list: topic recognition ignores those
words, while focus and the reader retain their original weight. The rejected
round is archived with its failed G3 check, and the correction receives new
bank measurements, latency rounds and a complete test run.

## Memory and answer quality

The light conversations bank inherits correctly in 36/35/34 of 38 labelled
turns (es/en/pt), compared with 26/25/21 in F1. The two conversations that
return to a previous topic (-007 and -015) inherit in all languages and both
profiles. Incorrect inheritance and direct answers on the four explicitly
negative turns per language remain zero.

Those aggregate improvements have costs: four previously correct literal
answers are lost relative to F1 (light pt-conv-003:2 and pt-conv-016:2;
medium es-conv-013:3 and en-conv-013:3). Three become related evidence after
the inherited core/last follow-up changes the focus. The Spanish medium
case remains direct and displays the correct source sentence, but selects
only `gratuito` as its QA span. The
[characterization](mediciones/v4/caracterizacion.md) records each state change
and the selected-span loss. G4's negative-turn checks do not establish
that every positive answer retains its literal correctness.

Five positive turns become new direct answers without the expected literal
span relative to F1. Two select the wrong role: medium es/pt-conv-007:3 asks
who drafts the resolution, but the reader selects the person who signs it.
The unchanged source sentence contains both roles. The other three spans
are incomplete values. These cases remain defects, even though G4's
negative-turn counts do not increase; no medium accuracy improvement is
claimed.

## Intent fallback

Ten independently written examples for each of seven intentions and three
languages provide 210 examples. Patterns win; fallback runs only for an
unknown intention with a corpus topic, reuses the existing query vector,
and contributes sentence cues without removing question terms. BM25 and
models without separately measured settings skip fallback.

For E5-small, the dev-only threshold search enables end/procedure in Spanish,
end in English, and procedure in Portuguese. It adds eight correctly labelled
intentions per profile to the natural-query bank (four/two/two). The isolated
F3 round changes no answer correctness or wrong-answer counts; the later
topic-word correction recovers the Spanish answer described above. The six dev and
two test intention successes are reported separately. Development iterations,
including their errors, are retained; test was observed during iteration
review and is not described as an untouched certification set. Other
intentions continue to use patterns.

The secondary banks expose incorrect inferred intentions even though their
answer decisions do not change. For example, a follow-up asking the amount
of a foreign allowance is inferred as `fin`, and a question asking which
carrier collects a return is inferred as `procedimiento`. Their full raw
diagnostics are retained. Correct dev/test labels in the natural-query bank
therefore do not establish that fallback labels are correct in other
domains or inherited contexts. Answer guards still apply; no broader
classification accuracy is claimed.

See [ADR 0005](../decisions/0005-deterministic-query-understanding.md),
[ADR 0006](../decisions/0006-conversation-memory.md) and
[ADR 0007](../decisions/0007-versioned-lexical-sources.md) for decisions and
limits.

## Verification and limits

The final complete suite passed **1,054 tests with two skips** (21 min 53 s).
The first round passed 1,052 tests with two skips; its diagnostic ranking
correction then passed 19 targeted tests. The topic-word separation passed
62 focused tests before this final complete run. Diagnostics use the same
effective intent and conversation context as selection. Source archives and
all XML results retain the sequence, including the failed G3 round and a
temporary-folder setup failure unrelated to the engine.

Latency comparisons use three alternating pairs per baseline with the same
offline model snapshots and two ONNX threads. Startup example encoding is
outside this warm-query budget. Machine load varied; the paired raw rounds
are retained and the service's thread default is unchanged.

These small banks detect defects and regressions. They do not certify a
production risk bound or a general accuracy improvement. Medium still
selects incomplete or incorrect literal spans in many existing cases;
better conversation inheritance and more recognized intentions do not
resolve those reader limitations. Heavy is not evaluated in this plan.
