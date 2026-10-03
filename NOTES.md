# NOTES

## Assumptions given (in the README, so not repeated here)
Weeks run Monday to Sunday; the week in progress when the data stops is the one predicted; a breach is more than 10 overtime hours (more than 55 in total); overtime is paid at 1.5x and Sunday/holiday work at 2x; one prediction row per employee. Everything else is in `docs/assumptions.md`.

## Assumptions we made
- **Clock-out time:** a clock-out earlier than the clock-in means the shift ended the next day (+24h). This uses the times only, not `shift_pattern`. A shift crossing midnight goes whole to the day holding most of it, and that day sets the week and the 2x rate. No meal break is deducted.
- **Excluding:** a shift with no (or an unreadable) clock-out is excluded and flagged, not guessed. Filling the gap with the person's usual shift is only a sensitivity run (it adds about 18 breach-weeks, so exclusion understates breaches). Shifts over 12 hours are flagged but counted.
- **Cost to the client:** we price hours the way the client would pay if our checks ran first. Employee IDs sharing an ID number, bank account or tax number are one person, held for escalation and not paid. A person with hours at two sites on the same day is paid for the site with more hours only, and overlapping time is paid once. Over the 9 complete weeks this costs R141k (4.0%) less than the client's own counting, and the client's weekly summary understates the cost by about R432k because it cannot see the Sunday/holiday premium (`notebooks/cost_analysis.ipynb`). This is our reading of 1.5x and 2x, not payroll's rule, and we cannot tell which of two duplicate IDs is real, so both are held back.

## How the note-sorting was checked
No language model: the notes are about 60 repeated sentences with typos and translations, and I had no independent labels to train on. I used typo-tolerant rules and, separately, clusters labelled once by reading, and checked both against 205 notes I hand-labelled blind. The rules scored 99.0% as first written (the honest number) and 100% after fixes (tuned). The clusters scored 100%.

It found about 55% operational failures (60% to 74% depending on how absence cover is counted) and 24% client requests, with no concentration by supervisor, guard or site, so it looks systemic. **Limit:** the labels and both methods share my judgement, so this shows consistent definitions, not correct ones, and 100% says nothing about new free text.

## What a trained model would learn that this approach does not
For the notes, a trained classifier would mostly memorise the templates, so it would match the rules here. Its edge would be new phrasings; its risk is shortcuts such as supervisor or site. For the breach model I did train one (logistic regression). It beats the simple projection (PR-AUC 0.43 against 0.33), but extra features added little, because the real unknown is the roster for the rest of the week.

**Testing on about 200 people without fooling yourself:** split forward in time, never at random, fix the threshold before looking at the test weeks, compare with the simple baseline, and report the uncertainty. Only about 13 people breach a week, so a small gain is noise.
