# ResearchGuard

<p align="center"><strong>Your AI tells a confident causal story that its sources do not support. ResearchGuard keeps the sources, the timeline and the argument as separate, linked models whose constraints can be checked, and tells the AI whether a claim may be asserted, must be qualified, or must be withheld.</strong></p>

| Version | Runtime | Package | License |
| --- | --- | --- | --- |
| `v0.8.0` | Python 3.11+ | `researchguard` | MIT |

ResearchGuard is a Python tool and an agent skill (Claude Code, Codex) for one question at a time. The question lives
in a folder: the hypotheses, the sources with the exact passages quoted from them (anchors), a timeline, an argument
and, if useful, a set of experiments that would tell the hypotheses apart. The AI builds these explicit models; native tools check their bindings, constraints and disagreements,
then compute a bounded verdict from the declared evidence and argument structure.

## 30 seconds: did the Ever Given cause the 2021 freight rate rise?

A user asks: *Did the Ever Given grounding in the Suez Canal (23–29 March 2021) cause the 2021 Asia–Europe container
freight rate rise?*

**Without ResearchGuard**, the AI may answer from the story everybody remembers:

> Yes. The six-day blockage of the Suez Canal disrupted Asia–Europe shipping and caused the 2021 freight rate rise.

**With ResearchGuard**, the AI keeps the question as a research folder and reads its status. The folder ships as
`examples/research/evergiven/`:

```console
$ researchguard status examples/research/evergiven | head -19
# Did the Ever Given grounding (23–29 March 2021) cause the 2021 Asia–Europe container freight rate rise?

## Verdict

- search: continue_search
- root_claim: h_suez: withhold — h_suez is UNDECIDED: R_h_suez_anc-transpacific (Rebuttal) blocks it; R_h_suez_anc-unctad-surge (Rebuttal) blocks it; R_pretrend (Rebuttal) blocks it; h_demand (Claim) blocks it.
- live_hypotheses: h_demand, h_yantian
- contested: false
- errors: 0

Models: source ok (source.yaml) | trace ok (trace.yaml) | logic ok (logic.yaml) | experiment ok (experiment.json)

## Hypotheses

| id | text | logic | trace | experiment |
|---|---|---|---|---|
| h_suez | The Suez blockage caused the rise. | UNDECIDED 0.16 | rank 2, support 0.33, not live, causal 0.33 | eliminated |
| h_demand | Demand rebound and container scarcity drove the rise. | IN 0.74 | rank 1, support 0.45, live | consistent |
| h_yantian | The Yantian disruption drove the rise. | not listed | not listed | consistent |
```

The claim the AI wanted to make is `h_suez`, and its wording licence is **withhold**. The argument lists four
blockers, including the pre-trend rebuttal and the competing demand claim. The timeline does not keep h_suez live,
and the declared experiment record eliminates it. `search: continue_search` says the counter-source search is unfinished.
The answer licensed by this folder is therefore: *these records do not support asserting that the blockage caused the
rise; demand rebound remains a live alternative, and the Suez claim is withheld.* The page also lists source-bound
evidence, open gaps and next searches, so the AI can choose the next useful check.

### The shortcut it closes

The AI's easiest way to rescue its first answer is to type a supporting sentence straight into the argument, for example
a newspaper line "the blockage alone doubled Asia–Europe spot rates in April 2021", without adding the source it came
from. When the folder declares a source model, that evidence has no source identity to check against. From `v0.6.0` it
is an error:

```console
$ researchguard status <copy> | tail -5
## Problems

- error evidence_not_in_source:logic:E_lloyds (its provenance names no source_id; add the anchor with researchguard source add-anchor, then run researchguard sync <folder>)
- warning hypothesis_not_in_logic:h_yantian
- warning unverifiable_source:src-wci-transpacific (no link, DOI, ISBN or arXiv id; nothing outside this folder to check it against)
```

Re-enter the evidence through the source model, starting from a clean candidate copy. Quote the passage as an anchor,
sync the copy, then compare it with the current folder before accepting it. Sync preserves authored nodes; an existing
unanchored insertion needs an explicit source binding rather than silent deletion. To keep the original `E_lloyds`,
set its provenance to `origin_kind: external_source`, `source_id: src-lloyds`, `locator: anc-lloyds` and the anchor's
exact `quote`; remove or refresh a stale `source_reference`. Its text and authored edges can stay.

The anchor must come from a document. A new source id that names no document is refused, and so is a malformed link or
date; nothing is written. A source names its document by a link, or by a title that has a letter or digit and is not
made only of placeholders ("unknown", "n/a") and words for a person or a kind of message or document ("colleague's
note"); a date alone does not count, and invisible characters such as a zero-width space are not a title:

```console
$ cp -r examples/research/evergiven ../evergiven-copy
$ researchguard source add-anchor ../evergiven-copy/source.yaml --source-id src-lloyds --anchor-id anc-lloyds --quote "The Suez blockage alone doubled Asia-Europe spot rates in April 2021." --locator "Lloyd's List, April 2021" --output ../evergiven-copy/source.yaml
{"ok": false, "error": "new_source_without_identity:src-lloyds: this anchor would create a source that names no document (no title; no link; no date). A source is a document that another reader can find; a date alone does not name one, and a colleague's remark or your own summary is not one. Nothing was written. Leave the passage out of the argument and keep its missing document as an open source gap until you have the document itself."}
```

The message does not list fields to fill in: a remark does not become a source by giving it a title. A source record
written by hand that names no document gives the warning `source_without_identity` in `status`, a malformed link or date
gives `source_identity_invalid`, and `source add-observation` refuses such a source as `add-anchor` does. Filing the
remark under a source the folder already holds does not help either: a locator made only of such words (`--locator
colleague`) names no place in that document and is refused (`anchor_locator_names_no_place`), and `status` warns
`anchor_after_source_date` when a quote names a day or month after the date of the document it is filed under (the
colleague's "April 2021" under the Suez Canal Authority statement of 29 March 2021). When the line really was printed
in Lloyd's List, the clean-copy route names that document:

```console
$ researchguard source add-anchor ../evergiven-copy/source.yaml --source-id src-lloyds --anchor-id anc-lloyds --quote "The Suez blockage alone doubled Asia-Europe spot rates in April 2021." --locator "Lloyd's List, April 2021" --title "Lloyd's List" --date 2021-04 --output ../evergiven-copy/source.yaml
{"ok": true, "output": "../evergiven-copy/source.yaml", "source": {"id": "src-lloyds", "identity": "title \"Lloyd's List\"; no link; date 2021-04", "created": true}}
$ researchguard sync ../evergiven-copy
sync: trace evidence added ["anc-lloyds"] updated []; logic nodes added [] updated []; conflicts []
next: researchguard status /workspace/guard11/evergiven-copy
note: To compare, pass the unchanged current folder to status and this synced folder to --candidate.
$ researchguard status examples/research/evergiven --candidate ../evergiven-copy
## Current and candidate

- source added: src-lloyds (title "Lloyd's List"; no link; date 2021-04)
- evidence added: anc-lloyds (in src-lloyds at "Lloyd's List, April 2021"; title "Lloyd's List"; no link; date 2021-04)
- warnings added: unverifiable_source:src-lloyds (no link, DOI, ISBN or arXiv id; nothing outside this folder to check it against)
```

Before quoting a source, save its UTF-8 original or CSV with
`researchguard source capture SOURCE --project FOLDER --file PATH` (or `--url URL`).
The saved bytes and their digest back exact passages and table cells; `status --json` exposes
`source_readings` with `id`, `colour`, `reason` and `source_digest`. It flags changed captures,
missing quotes, wrong table cells and computable changes or restatements. Unknown units stay grey
when a conversion is needed; conversions use the optional
[PhysicsGuard v0.18.0](https://github.com/liuyingxuvka/PhysicsGuard/releases/tag/v0.18.0) unit reader. Direct table-cell
quotes can be compared in their unchanged original unit label without interpreting that label.

In a research folder, experiment observations also report their evidence basis. A direct numeric outcome can be checked against one captured scalar or explicitly named table cell in its original unit; an enum can match a complete captured literal. A wrong supported label is an error. Interpretations such as `similar_rise` remain caller-declared, even when the finite experiment matrix reaches closure. Standalone experiment selection and observation remain useful conditional calculations; they do not measure the world.

ResearchGuard cannot tell a real title from an invented one or prove that the saved original is true.
Every new source and evidence item is shown with its attribution before accepting the copy. A word list cannot tell a
colleague's note from a document either ("Colleague's note, 2021" passes it), so one more thing is computed instead of
read from the title: a source whose url field holds no outside locator (an http or https link whose host name ends in a
top-level domain of the root zone and is not an example name, a DOI, an ISBN with a correct check digit, or an arXiv id)
is an `unverifiable_source` warning in every `status`, on each evidence row and conclusion evidence list it appears in,
and as a dashed box in the picture. This holds for every source, old or new: a source a folder already held before this
version warns too, with no change to the folder. No title clears it; only a locator a reader can follow does, and the
link itself is shown to the owner (ResearchGuard looks nothing up, so an invented link, DOI or ISBN still passes). The
shipped example's transpacific lane, cited by title only, carries this warning: the example's files hold no link for
it, so none was made up. A new anchor is only a new piece of evidence. Whether it changes the verdict depends on what
the argument and the timeline do with it, and that is decided by the routes, not by the AI's wish.

## Quick start

**1. Install the tool, from the release tag.**

```bash
python -m pip install "git+https://github.com/liuyingxuvka/ResearchGuard.git@v0.8.0"
```

This installs the `researchguard` command. Python 3.11 or newer.

**2. Install the skill for your AI**, from the same tag:

```bash
git clone --depth 1 --branch v0.8.0 https://github.com/liuyingxuvka/ResearchGuard.git
python ResearchGuard/scripts/install_skill.py --target ~/.claude/skills          # Claude Code
python ResearchGuard/scripts/install_skill.py --target ~/.codex/skills           # Codex (or "$CODEX_HOME/skills")
python ResearchGuard/scripts/install_skill.py --target ~/.claude/skills --check  # is the installed copy current?
```

The script copies `skills/researchguard/` (its `SKILL.md` and the `agents/` and `references/` folders) into
`<target>/researchguard/`, replaces an older copy, and removes the `logicguard`, `sourceguard`, `traceguard` and
`experimentguard` folders that versions before the merge installed.

**3. The first commands**, in the cloned folder:

```bash
cd ResearchGuard
researchguard status examples/research/evergiven
researchguard status examples/research/evergiven --hypothesis h_suez
researchguard status examples/research/evergiven --json --output ../evergiven-status.json
```

The first prints the verdict page shown above; the second shows one hypothesis with the evidence for and against it,
the known-bad checks that touch it, its open gaps and the next actions; the third saves the full report as JSON, which
is what LogicWriting reads.

To discuss a conclusion, draw what it rests on: `researchguard status examples/research/evergiven --picture` prints a
Mermaid flowchart of `h_suez`, its four blockers, its direct support with each anchor and source, and the trace links,
computed from the folder's models, followed by a list of what it left out and of every status problem that names
something drawn. An anchor the source model does not hold is drawn as such, and a logic model that cannot be read is
reported instead of drawn. The example's
[README](./examples/research/evergiven/README.md#discussing-the-verdict) shows it in a reply.

**Your own question.** Start a folder with `research.yaml` (the template is
["Start a question" in `research-tree.md`](./skills/researchguard/references/research-tree.md)), add only the route
models the question needs, list them under `models`, and run `researchguard status <folder>` after every step. When the folder lists a source model, add new source evidence as an anchor
(`researchguard source add-anchor`), then `researchguard sync <folder>`. Standalone and source-free models remain supported.

## How it works

```mermaid
flowchart LR
  Q["research.yaml<br/>the question and its hypotheses"] --> S
  S["source model<br/>sources and quoted anchors"] -- "sync" --> T["trace model<br/>timeline and causal story"]
  T -- "sync relevant evidence" --> L["logic model<br/>argument and rebuttals"]
  E["experiment model<br/>what would tell them apart"]
  S & T & L & E --> ST["researchguard status on the folder"]
  ST --> V["verdict: assert, qualify or withhold<br/>open gaps and next searches"]
```

Each part of the question is an explicit model, joined to the others only by shared ids (hypotheses, sources, anchors):

| Model | What it holds | Route the skill loads |
| --- | --- | --- |
| Source model | where each piece of evidence comes from, the quoted passage, open source gaps, when to stop searching | `source` |
| Trace model | dated events, competing causal stories, which evidence supports or opposes each | `trace` |
| Logic model | the argument: claims, evidence, rebuttals, what a claim may be worded as | `logic` |
| Experiment model | the fewest or cheapest experiments that would tell the hypotheses apart (recommended, never run) | `experiment` |

`researchguard status <folder>` reads them together and checks what one AI-written record cannot check about itself:

- **Copies agree with their source.** The trace and the argument carry copies of each quoted passage; a copy that
  differs from the source model is `copy_drift`, an evidence id that names no source is `dangling_source`.
- **A source can be looked up.** A source with no link, DOI, ISBN or arXiv id a reader can follow is
  `unverifiable_source`, whatever its title says, and every piece of evidence filed under it says so.
- **The routes agree with each other.** If the argument counts a piece of evidence as support and the timeline counts
  it as opposition, the verdict says `contested: true` and the hypothesis lists a route disagreement.
- **The verdict is computed, not written.** The wording licence of the root claim (`assert`, `qualify` or `withhold`)
  comes from the argument's native licensing check. Timeline and experiment states are reported alongside it.
- **Known-bad checks.** `ablations:` in `research.yaml` remove anchors and say what must happen (`weaken`,
  `eliminate`); an ablation the folder does not react to is reported as not caught.

Changes go through a copy: edit or sync the copy, then `researchguard status <folder> --candidate <copy>` lists exactly
what changed (evidence, verdict, errors), and you replace the folder with the copy when you accept it.

Exit codes of `status`: 0 no errors (warnings allowed), 1 model or reference errors, 2 request/index problems or a reported unexpected status failure.

## How it works with the other Guard skills

**ResearchGuard → LogicWriting, through the saved report.** When the finished piece is a report or a paper,
LogicWriting writes it; ResearchGuard never writes prose. Save the folder's status, then name the folder and the saved
file in LogicWriting's brief (`research_folder`, `research_status`):

```bash
researchguard status <folder> --json --output research-status.json
```

LogicWriting reads that saved report; it does not call ResearchGuard while it checks the text. The evidence anchors its
plan cites are taken from the report, and when the folder changes after the report was saved, LogicWriting refuses to
close the piece until the report is refreshed (`research_report_stale`, then `run_chain.py --refresh-providers`). What
else LogicWriting holds each claim to (the verdict, the wording licence of the root claim) is described in
[its README](https://github.com/liuyingxuvka/LogicWriting).

<!-- BEGIN GUARD FAMILY TABLE -->
## The Guard family

Five skills, one idea: make structure, relationships and constraints explicit in a separate, inspectable model. Tools check the AI's answer or changes against that model and expose counterexamples, taking over the steps where the AI tends to slip. Each skill works on its own. The only data hand-over is LogicWriting reading the saved reports of ResearchGuard and WorldGuard.

| Skill | The AI weakness it makes up for | Use it when | Works with the others |
|---|---|---|---|
| [FlowGuard](https://github.com/liuyingxuvka/FlowGuard) | It changes one part of the software and does not see what that broke elsewhere; it rebuilds what already exists, or puts new code in the wrong place | you change, extend, refactor or audit software code, including the code of a simulation | Sends calculation results to PhysicsGuard, causal claims to ResearchGuard, story or plan consistency to WorldGuard, long texts to LogicWriting. The other four Guards are developed with FlowGuard |
| [PhysicsGuard](https://github.com/liuyingxuvka/PhysicsGuard) | It does physics in its head and is confidently wrong about units, signs and balances | a number comes from physics: a simulation result, test data, or a calculation the AI made itself | Sends the simulation's code to FlowGuard. No other Guard reads its reports |
| [ResearchGuard](https://github.com/liuyingxuvka/ResearchGuard) | It tells a confident causal story that its sources do not support | before a causal or evidential conclusion is stated: claims, sources, timelines, competing explanations | LogicWriting reads its saved status report. Sends the writing of the finished report to LogicWriting |
| [WorldGuard](https://github.com/liuyingxuvka/WorldGuard) | Across chapters, days or steps it forgets who holds what and who is where, and writes events that cannot happen | a story, trip, plan or process must stay consistent from step to step | LogicWriting reads its saved check report. Sends software code to FlowGuard |
| [LogicWriting](https://github.com/liuyingxuvka/LogicWriting) | In a long text it drifts away from its own plan and evidence | you need a finished piece for real readers: an investigation report, a paper, fiction or a story plan, a travel guide | Reads the saved reports of ResearchGuard and WorldGuard. Sends the checking of claims on their own to ResearchGuard |
<!-- END GUARD FAMILY TABLE -->

## Errors

ResearchGuard says where a failure happened; it never replaces a failure with a default or a second path:

- A command that fails prints the error and exits with a nonzero code; it never answers with a default value.
- A check or library step that fails puts the error into the result it returns, as a named error, gap, finding or error field that names the error, so the caller sees it.
- In the desktop library viewer, a failed import, export or dissolve shows the error in an error dialog and changes nothing.
- When the desktop library viewer cannot use a window-system feature (maximizing, screen DPI, an icon, a dialog), it draws the plain form instead; this changes what is shown, never a result.
- Text where a number belongs, a number outside its range, or a policy that is not a mapping is an error that names the field.

## Honest limits

**What it does not do.**
- It does not find, download or judge sources on its own. It checks the records the AI builds from them: where each
  piece of evidence comes from, whether the copies match, whether the routes agree, and what the structure licenses.
- A verdict is about the folder, not about the world. `withhold` means "these records do not support the claim", not
  "the claim is false". The numbers in the Ever Given example are approximate transcriptions of public data, not
  established conclusions. Displayed model scores are not calibrated probabilities.
- ExperimentGuard recommends experiments; it never runs them and never invents probabilities.

**Where it can still miss.**
- The AI still writes arguments and timelines. Captured originals can expose transcribed values, dates,
  clocks, units and quotes that disagree; they do not prove factual truth or who did what when all the
  same names and numbers appear. Unsupported layouts, units and partially read changes remain grey.
- A captured contradiction in a summary or change claim is an error. Without a captured basis,
  `summary_number_not_in_quote` remains a warning: a summary may legitimately derive a number.
  Readers use finite grammars; HTML/PDF/OCR extraction, arbitrary prose and multiple changes in one clause are not covered.
- Without a source model in the folder, evidence without an anchor is allowed and listed as `evidence_unanchored`.
- A source must name its document by a link or by a title that names one; a date alone does not count, and a link or a
  date must be well formed. The title check only refuses titles with no letter or digit, placeholders and words for a
  person or a kind of message or document; a saved quote can be checked against captured bytes, but
  an invented title ("Lloyd's market note") or locator ("p. 2") can still pass the identity check. Each new source and each
  new piece of evidence is shown, with the source it is filed under, in the candidate comparison, where the owner reads
  it. The date check reads only days and months written out in the quote ("29 March 2021", "April 2021", "2021-04"); a
  quote that forecasts a later month is warned too.

**What has been checked, and what has not.**
- Verified on finite examples: the shipped folder has a computed `withhold` licence; reference-only evidence produces
  the source-identity error; C2's changed summary number adds one warning without changing the verdict; syncing a
  clean copy with one added anchor changes only that evidence. These cases do not establish general causal accuracy.
- Not measured: whether an AI reaches for ResearchGuard on its own before stating a conclusion, how it behaves on
  large folders, or whether it reduces total AI token use. The description asks for earlier use; that is not adoption evidence.

## Developing ResearchGuard

```bash
python -m pip install -e ".[test,viewer]"
python -m pytest -q
```

The `test` extra adds pytest and FlowGuard, which ResearchGuard uses to maintain itself; the extra pins the FlowGuard
release this version is developed with. FlowGuard is installed only from its git tag
(`git+https://github.com/liuyingxuvka/FlowGuard.git@<tag>`), because the package with that name on PyPI is a different
project. Ordinary use of ResearchGuard does not need FlowGuard. AI contributors start from [`AGENTS.md`](./AGENTS.md);
`CLAUDE.md` points Claude Code to the same file.

Every function has one route (see [Errors](#errors)). `tests/test_error_routes.py` finds every place in `src/` and
`scripts/` that can end an error without raising it: an `except` that does not re-raise, a `finally` that returns, any
use of `contextlib.suppress` under any name or entered through an `ExitStack`, an exit callback pushed on an `ExitStack`, and an
`__exit__` that returns a true value. Each one is listed under one of the sentences in Errors, and the test checks the
handler's own code against that sentence. A command (a function whose return value becomes the exit code, found from
the entry points and the commands they dispatch to) must print a value that carries the error and then return a
nonzero code. A result handler must, before any way out, put a value that carries the error into what its function
returns: an error field of the returned value, or a list the function returns or was given. A value that only tests
the error, a local nobody returns, or a list or dict nobody holds does not count. A dialog must show the error; a
display fallback may guard only window-system calls in the viewer. A new handler that is unlisted, or listed under a
sentence its code does not follow, fails. This reads the shape of the code; it is not a proof, and code written to
look like a contract can still pass. No test may skip, be marked expected-to-fail or end the run early: the suite
fails if one does, the test process refuses `os._exit` and the `exec` functions, and the end of the run recounts
failed and unrun tests from the test reports themselves.

The optional desktop viewer of the logic route needs the `viewer` extra (Pillow) and a Python with tkinter; the core
commands do not.

## Links

- The skill: [`SKILL.md`](./skills/researchguard/SKILL.md), the research folder
  ([`research-tree.md`](./skills/researchguard/references/research-tree.md)) and the four routes:
  [logic](./skills/researchguard/references/routes/logic.md),
  [source](./skills/researchguard/references/routes/source.md),
  [trace](./skills/researchguard/references/routes/trace.md),
  [experiment](./skills/researchguard/references/routes/experiment.md)
- The worked example: [`examples/research/evergiven/`](./examples/research/evergiven/README.md)
- Background: [diagram semantics](./docs/diagram_semantics.md), [source library workflow](./docs/source_library_workflow.md),
  [project library viewer](./docs/project_library_viewer.md), [writing workflow](./docs/writing_workflow.md)
- [Changelog](./CHANGELOG.md)
- License: [MIT](./LICENSE)
