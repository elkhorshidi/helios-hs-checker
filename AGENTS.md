# V4 UI/UX extension (2026-10-18)

- Maintain the historical/legal limitation for each route. Do not render a green "approved" badge for source-list membership.
- The app renders from `app.py`, while deterministic eligibility logic remains in `eligibility.py` (do not merge or weaken it).
- Keep `ui_components.py` presentation-only and HTML-escape all descriptions, company names, IDs, and notes before interpolation into HTML.
- Keep the three route options (all/general/metals); only metals checks company IDs, including in all mode.
- Use Vazirmatn via Streamlit theme config and `assets/theme.css`; do not bundle font binaries. External font fetching requires user browser connectivity.
- Mobile is supported by responsive CSS. Keep form controls native Streamlit, not custom JS widgets.
- Run `python -m unittest discover -s tests -v` after edits and verify that `.streamlit/config.toml` parses as TOML.

---

# Codex instructions — Helios HS Eligibility Checker

## Purpose
Build a secure, Persian/RTL HS tariff + company-based internal lookup app. The workflow screens requests for potential Iranian import FX routes, but must **never claim that a tariff is currently legally permitted** based on the attached historical sources.

## Ground truth (do not override or interpolate)
- Proposed general-industry list: 368 HS codes. Sheet title says *proposed* transfer of FX sourcing to exporters' own/others' proceeds. Not current definitive approval.
- Metal-chain list: 2,053 input rows, 2,051 unique HS codes after Persian-digit normalization. Two trailing duplicated HS values are `84145920`, `85444900`. Preserve raw rows for audit; match unique (source_id, hs_code) pairs.
- National ID list: 1,996 rows. 1,648 IDs have 11 digits; 223 have 10; 81 have 9; 44 have 8. Two repeated-digit 11-digit values are suspicious. Some names are individuals. Never autocorrect, pad, silently discard or certify these IDs.
- Unique HS across both lists: 2,399; shared across lists: 20; metal-only additions: 2,031.
- Legal basis for metal lists: Iran Trade Promotion Organization letter 4129177 dated 1403/09/13, referring to earlier working group/central bank documents. It has COMPANY and HS preconditions plus use-case/register requirements. Its current effect has not been independently verified.
- The supplied sources DO NOT reliably map HS to band 1 or band 2. Show Unknown until an explicit versioned official reference is loaded.

## Safety semantics
- Distinguish source membership from live legal approval.
- Keep routes independent when one HS appears in both. Never let an older confirmed historical source upgrade a merely proposed list.
- For metal chain: HS alone is **not** enough; take company identifier and check against company register. Even matching both indicates historical list membership, not approval today.
- Match exact 8-digit HS codes after translating Persian and Arabic numerals. No 6-digit prefix expansion, no zero-padding.
- For company ID, only exact matching with the supplied string is allowed. A 8–10 digit value may have lost leading zeroes or belong to a natural person; flag it. Do not assert verified validity.
- Not found means not found **in the uploaded sources**, not prohibited.
- Include source_id, document date/status, and limitations with every check.
- Never imply live connectivity with government systems unless actually implemented and tested.

## Implementation
- `eligibility.py` contains matching / tests and should not depend on Streamlit.
- `app.py` contains display/UI only. Don't hardwire tariff outcomes into UI.
- v3 includes three top-level query modes (`all`, `general`, `metals`) in a single persistent selector above the query tabs. Apply the same selector to single and batch lookups. In `all` mode, render **both independent pathways** including absent results for one pathway; never treat membership in the other pathway as approval.
- Use `route_filter` in `assess` / `assess_routes` to filter underlying source matches. In bulk `all` mode, use `format_assessment_row` for separate General and Steel & Metals columns in the on-screen table and CSV export. Preserve metal-chain ID lookup even if its HS overlaps with General.
- Never skip or weaken company-ID verification to make a metal result look approved. Without a company identifier, state `company_required`; with no historical match, state `company_not_found`. Matching both is only `historical_pair`.
- Keep source files unedited under `source/` and derived CSVs under `data/`.
- Run `python -m unittest discover -s tests -v` after changes.
- Avoid adding network dependencies that execute on every dashboard load.
- Treat company names and identifiers as potentially sensitive when publishing or logging; require access control for deployments.
