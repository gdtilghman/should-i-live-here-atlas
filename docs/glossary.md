# Glossary and writing rules

Every word a visitor reads on the site follows these rules. That includes
labels, notes, caveats, reasons, messages and screen-reader text. Code,
audits and commit messages are not in scope here.

## Writing rules (Simplified Technical English)

1. One idea per sentence. 20 words or fewer; aim for 15 in the interface.
2. Active voice. Present tense. Say who does the action when it matters.
3. Use the approved term from the table below. Use one term for one meaning.
4. No jargon. If a technical term is necessary, explain it in plain words
   the first time it appears in that text.
5. No asides: no parentheses for extra clauses, no semicolons that join
   two sentences, no dashes that start a second idea. Make two sentences.
6. Give instructions as commands: "Choose a state." Not "You may wish to".
7. A caveat says what the value is not, in plain words, and why that
   matters to the reader. Keep every limit the old text stated.
8. Do not show source field names, table codes or file names to the
   visitor (for example B25070, *_ALRB, BUILDVALUE). Keep them in the
   hidden `method` field and in the source audits.
9. Legal notices that a source requires word for word stay unchanged.
   Today: the FEMA OpenFEMA notice ("This product uses the Federal
   Emergency Management Agency's OpenFEMA API, but is not endorsed by
   FEMA...").
10. Numbers: use digits. Units after the number. "per 100,000 people a
    year", not "per 100,000 persons per year".

## Approved terms

| Term | Meaning | Do not use |
|---|---|---|
| topic | A group of related measures, such as "Air quality" | family, dataset (for the group) |
| measure | One thing you can map, such as "Traffic deaths" | dataset, layer, metric |
| value | The number the site shows for a county | reading, figure, statistic |
| unavailable | The county has no value, for any reason | missing, not available, no data, no matching record |
| suppressed | The source hides the value, for example because the numbers are too small | withheld |
| not applicable | The hazard cannot happen in the county, for example hurricanes inland | n/a |
| extreme value | A value far above the others, shown in purple | outlier, extremity, 3×IQR |
| estimate | A number calculated from a survey of some people | — |
| model estimate | A number calculated by a computer model, not counted | modeled value, prediction |
| likely range | The range that probably contains the true value, with the stated certainty (95%) | confidence interval |
| margin of error | The "±" amount around an estimate, with the stated certainty (90%) | error bar |
| adjusted for age | Changed so that counties with older or younger people compare fairly | age-adjusted (without explanation) |
| My priorities | The page part where you combine measures | recipe (in visible text), composite |
| input | A measure you add to My priorities | component |
| weight | How much an input counts, in percent | importance |
| hard limit | A rule that removes counties above or below a value you set | filter, threshold |
| excluded | Removed by your hard limit | filtered out |
| concern score | The My priorities result for a county, 0 to 100. Lower is better. | burden points, combined score |
| lower 48 | The 48 states the map shows | contiguous United States |
| national scale | The same colors for the whole country, also in a state view | — |
| people | People in general | persons, population (as a noun for people) |
| residents | People who live in the county | — |

## Term popups

Defined words on the page get a dotted underline. A click opens a short
definition. The definitions live in `dist/terms.js`. When you change a term
here, change its popup text there too, in the same plain style.
