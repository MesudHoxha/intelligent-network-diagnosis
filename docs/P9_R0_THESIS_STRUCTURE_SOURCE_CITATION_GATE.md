# P9-R0 Thesis Structure and Source/Citation Gate

Date: 2026-08-12

Status: ACCEPTED — STRUCTURE AND SOURCE/CITATION GATE PASSED

## 1. Purpose and accepted input

P9-R0 is the first writing milestone after the Phase 8 empirical closeout. It
binds the exact public P8-R3 checkpoint
`01d6d356fbac6444bbd89fd2bcbc7a6e5e1cdea7`, preserves all eight supported
bounded claims and eight prohibited claim expansions, and establishes the
structure and citation controls that must exist before chapter drafting.

This milestone does not write the thesis chapters. It does not start the
laboratory, reopen the test partition, deserialize the estimator, recalculate a
metric, add an experiment, or enlarge an empirical claim. Its two generated
traceability assets are a seven-row chapter map and a sixteen-row verified
source seed.

## 2. University of Prishtina alignment

The controlling institutional source is the 2026 University of Prishtina
Bachelor thesis guide, independently verified from the official University
domain:

```text
Udhëzues për temën e diplomës për studentët e programeve Bachelor
https://fa.uni-pr.edu/desk/inc/media/6A814270-6BC0-4EDC-8B08-4CE239A207E7.pdf
```

The accepted project is an empirical engineering thesis. The guide establishes
the following writing boundary:

- 8,000–10,000 words, approximately 30–50 pages, excluding references and
  appendices;
- an abstract of at most 350 words and three to five keywords;
- a literature review, research purpose/questions, methodology, data analysis,
  results, conclusions, and references;
- a recommended minimum of 30 credible and relevant scientific references;
- APA author-date citations and an alphabetical reference list containing only
  cited sources; and
- a declaration of originality and transparent use of artificial-intelligence
  tools.

No separate public FIEK chapter-format guide was located as of 2026-08-12. The
University-wide guide therefore controls this gate. A later documented FIEK or
mentor instruction may change chapter labels, page layout, or the exact APA
edition used for final rendering. It may not change the accepted experiment,
values, claims, or limitations.

## 3. Frozen seven-chapter structure

| ID | Chapter | Primary role | Target words | Accepted boundary |
| --- | --- | --- | ---: | --- |
| CH01 | Hyrje | Problem, motivation, bounded question, contributions, scope | 900–1,100 | E01, E04, E05; C01, C03 |
| CH02 | Shqyrtimi i literaturës dhe bazat teorike | Network diagnosis, Rule-based, ML, Hybrid, explainability, gap | 1,600–2,000 | E01, E03 plus verified external literature |
| CH03 | Metodologjia dhe dizajni eksperimental | Controlled lab, taxonomy, contexts, split, freeze, metrics | 1,400–1,700 | E02, E04, E05; C01–C03, C08; T01 |
| CH04 | Arkitektura dhe implementimi i sistemit | Pipeline, three methods, provenance, contracts, interface | 1,400–1,700 | E01, E03, E06; C01, C06, C07 |
| CH05 | Rezultatet | Exact accepted descriptive results | 1,000–1,300 | E04, E05; T01–T02, F01–F02 |
| CH06 | Diskutimi, kufizimet dhe vlefshmëria | Interpretation, validity, limitations, claim traceability | 1,200–1,500 | E05, E06; T03; bounded claims and blocked claims |
| CH07 | Përfundimet dhe puna e ardhshme | Bounded answers, contributions, limitations, scoped future work | 600–700 | E01, E05, E06; no new empirical claim |

The chapter targets total 8,100–10,000 body words. Front matter, references, and
appendices are outside that total. Chapter titles may be adjusted for documented
University/FIEK requirements while their evidence roles remain unchanged.

## 4. Research-question contract

The primary question is deliberately comparative rather than superiority-seeking:

> Si krahasohen qasja me rregulla, Machine Learning dhe qasja hibride në
> diagnostikimin e problemeve të rrjetit brenda laboratorit të kontrolluar, dhe
> çfarë vlere operative sjell politika hibride pa presupozuar epërsi numerike?

Four secondary questions cover experimental coverage, the clean report-only
comparison, deterministic missing evidence, and operational traceability. Every
question maps to one or more accepted claims. No question authorizes a Hybrid
advantage, population significance, real-world generalization, simultaneous
multiple-fault diagnosis, OSPF support, production monitoring, live inference,
or automatic remediation.

## 5. Source and citation gate

The source seed contains sixteen independently checked records:

- nine scientific publications with DOI or primary publication records;
- two official Internet standards;
- two University/FIEK institutional documents; and
- three official technical documentation/specification records.

The seed covers network fault localization, Machine Learning for networking and
fault management, structured-data splitting, model-selection separation,
classification metrics, explainability terminology, scikit-learn provenance,
controlled fault injection, ICMP/IPv4 router behavior, Containerlab, JSON Schema,
and OpenAPI.

The nine scientific sources are a verified core, not the final bibliography.
The final thesis should satisfy the University guide's recommendation of at
least 30 credible and relevant scientific references. Every added source must
record author, title, year, venue, DOI/RFC/official URL, intended chapter, and a
bounded use. Search-result snippets and generative AI are not citable academic
authorities. Publisher metadata or an abstract may establish relevance at the
gate, but detailed claims require reading the relevant primary text.

The citation family is APA author-date. Direct quotations require a page or
section locator. DOI references use canonical `https://doi.org/...` links. The
official 2026 guide requires APA and illustrates sixth-edition examples; the
exact edition for final rendering remains guarded for documented FIEK or mentor
confirmation. The stored metadata remains edition-neutral.

## 6. Tables, figures, integrity, and claim traceability

Tables and figures use sequential numbering, a title/caption, and a source or
note. The five Phase 8 assets remain the only accepted numerical presentation
boundary. Exact values must be copied from the accepted JSON/CSV assets, never
recomputed from runtime data. Styling, translation, pagination, and captions may
change only if numerical content and limitations remain intact.

Every supported project claim must retain its P8 limitation. External literature
provides background and methodological context; it cannot turn an unsupported
project assertion into a result. The 96 masks remain transformations of 24 clean
inputs, not independent experiments. Hybrid remains operationally distinct by
rule-first/ML-fallback provenance and numerically equal to Machine Learning in
every accepted aggregate scope.

The final thesis must include the University originality and AI-use declaration.
AI may support language, organization, and technical editing only under the
University rule; sources, analysis, interpretation, and scientific content must
be verified and owned by the student.

## 7. Acceptance and next milestone

P9-R0 passes when:

- the manifest validates against Draft 2020-12 and rebuilds byte-identically;
- the exact P8-R3 closeout retains its path, size, SHA-256, claims, and writing
  constraints;
- all seven chapter roles, five research questions, sixteen source records, and
  two CSV traceability assets verify;
- the University requirements and FIEK/mentor override guard remain explicit;
- all prohibited empirical and citation actions remain false; and
- the full regression remains green without starting the laboratory.

The next milestone is P9-R1 — Thesis Skeleton and Traceability Matrix. It may
create the document skeleton, headings, source-to-section matrix, and
claim-to-paragraph plan. It may not draft unsupported conclusions or alter the
accepted empirical boundary.
