# Prompt Template: Generate config.py from CV
> Give this entire file to an AI (e.g. Claude) along with your CV attached.
> The AI will return a ready-to-use config.py personalised to your profession.
> No placeholders to fill in — just attach your CV and send.

---

## INSTRUCTIONS FOR THE AI

You are a configuration assistant for a Python job-search crawler that queries
the Swedish public employment API (Arbetsförmedlingen / JobTech Dev).

The user has attached their CV. Read it carefully and generate a complete,
ready-to-run `config.py` file personalised to their profession, experience
level, and skills.

---

## ⚠️ CRITICAL: EXACT VARIABLE NAMES — DO NOT DEVIATE

The generated config.py will be imported directly by a running Python program.
If you use any variable name other than the ones listed below, the program will
crash with an ImportError. These names are non-negotiable.

The program imports **exactly these variable names** — copy them letter-for-letter:

```
SEARCH_QUERIES               ← list of search query strings
OCCUPATION_FIELD_DATA_IT     ← single string: a JobTech concept ID or ""
REGION_CODES                 ← list of Swedish region code strings, or []
SCORE_HIGH                   ← list of high-weight keyword strings
SCORE_MEDIUM                 ← list of medium-weight keyword strings
SCORE_PENALTY                ← list of penalty keyword strings
DB_PATH                      ← string: always "output/jobs.db"
EXPORT_MIN_SCORE             ← float between 0.0 and 1.0
EXPORT_MAX_LISTINGS          ← integer: always 30
EXPORT_PATH                  ← string: always "output/job_listings.json"
EXPORT_ALL_PATH              ← string: always "output/job_listings_all.json"
EXPORT_CSV_PATH              ← string: always "output/job_listings.csv"   
EXPORT_ALL_CSV_PATH          ← string: always "output/job_listings_all.csv"
FETCH_LIMIT_PER_PAGE         ← integer: always 100
JOBSEARCH_FALLBACK_THRESHOLD ← integer: always 50
POLITE_DELAY_SECONDS         ← float: always 1.0
```

Common mistakes that will break the program — do NOT do these:
- ❌ `OCCUPATION_FIELD_ID`       → must be `OCCUPATION_FIELD_DATA_IT`
- ❌ `OCCUPATION_FIELD`          → must be `OCCUPATION_FIELD_DATA_IT`
- ❌ `HIGH_KEYWORDS`             → must be `SCORE_HIGH`
- ❌ `KEYWORDS_HIGH`             → must be `SCORE_HIGH`
- ❌ `PENALTY_KEYWORDS`          → must be `SCORE_PENALTY`
- ❌ `QUERIES`                   → must be `SEARCH_QUERIES`
- ❌ `REGION`                    → must be `REGION_CODES`

---

## RULES

1. **Output ONLY the config.py file.** No explanation before or after.
   Start your response with `# config.py` and end with the last line of Python.
   Do not wrap it in markdown code fences.

2. **Read the CV carefully before generating anything.** Infer profession,
   seniority level, skills, location, and preferred role types from the CV.

3. **All search queries must include both Swedish and English terms.**
   Swedish job ads dominate the API. Every role concept needs both languages.
   Example: a nurse needs both `"sjuksköterska"` and `"nurse"`.

4. **Infer seniority from the CV** and adjust SCORE_PENALTY accordingly:
   - Recent graduate / 0–2 years → penalise "senior", "chef", "manager",
     "director", "10 år", "15 år", "20 år", "ledare"
   - Mid-level / 3–7 years → penalise "director", "vd", "cto", "20 år"
   - Senior / 8+ years → minimal penalties; add "lead", "architect", "head of"
     to SCORE_HIGH instead

5. **OCCUPATION_FIELD_DATA_IT** — use the correct JobTech taxonomy concept ID.
   Despite its name, this variable holds the field ID for *any* profession, not
   just IT. Use `""` if the profession is not in the list below.

   Known occupation-field concept IDs:
   ```
   Data/IT                 →  apaJ_2ja_LuF
   Teknik/Ingenjör         →  K74W_rLE_5Ma   (engineering)
   Hälso- och sjukvård     →  YW5G_aHW_nHa   (healthcare)
   Pedagogik/Utbildning    →  mf6U_uQR_FYM   (education/teaching)
   Ekonomi/Finans          →  8jUB_bSq_HKL   (finance/accounting)
   Bygg/Anläggning         →  nssL_jwZ_Gb2   (construction)
   Handel/Försäljning      →  HZin_HTq_URk   (sales/retail)
   Transport/Logistik      →  TqSG_Xv8_Ujy   (transport/logistics)
   Hotell/Restaurang       →  spkG_bYu_niG   (hospitality)
   Juridik                 →  wZt3_LJb_4oR   (law)
   ```
   If uncertain between two fields, use `""` to avoid over-filtering.

6. **REGION_CODES** — if the CV shows a Swedish city or region, map it to
   the correct code. Leave as `[]` if location is unclear or the person is
   open to all of Sweden.

   Common region codes:
   ```
   01 = Stockholm          05 = Östergötland (Linköping)
   03 = Uppsala            06 = Jönköping
   04 = Södermanland       07 = Kronoberg (Växjö)
   08 = Kalmar             12 = Skåne (Malmö, Lund)
   13 = Halland            14 = Västra Götaland (Göteborg)
   17 = Värmland           18 = Örebro
   19 = Västmanland        20 = Dalarna
   21 = Gävleborg          22 = Västernorrland (Sundsvall)
   24 = Västerbotten (Umeå) 25 = Norrbotten (Luleå)
   ```

7. **All keyword lists must contain at least 8 items.**
   Add both Swedish and English variants where applicable.

8. **The locked settings block must be copied exactly** — do not alter the
   values of DB_PATH, EXPORT_PATH, EXPORT_ALL_PATH, EXPORT_MAX_LISTINGS,
   FETCH_LIMIT_PER_PAGE, JOBSEARCH_FALLBACK_THRESHOLD, or POLITE_DELAY_SECONDS.

9. **Add a comment block at the top** summarising your reading of the CV:
   ```python
   # Profession   : [what you inferred]
   # Seniority    : [graduate / junior / mid / senior]
   # Location     : [city and region code, or "all Sweden"]
   # Generated by : AI from CV
   ```

---

## EXACT TEMPLATE — COPY THIS STRUCTURE, FILL IN THE BRACKETED PARTS

# config.py
# Profession   : [INFERRED PROFESSION]
# Seniority    : [INFERRED LEVEL]
# Location     : [INFERRED LOCATION or "all Sweden"]
# Generated by : AI from CV
# ─────────────────────────────────────────────

# ── Search queries ────────────────────────────
SEARCH_QUERIES = [
    # Swedish terms first, then English equivalents
]

# ── Occupation field concept ID ───────────────
# NOTE: variable is named OCCUPATION_FIELD_DATA_IT for all professions
OCCUPATION_FIELD_DATA_IT = ""  # replace "" with the correct concept ID

# ── Swedish region codes ──────────────────────
REGION_CODES: list[str] = []  # replace [] with e.g. ["05"] or leave empty

# ── Relevance scoring ─────────────────────────
SCORE_HIGH = [
    # Role titles, core skills, and seniority markers that ARE a good fit
]

SCORE_MEDIUM = [
    # Tools, technologies, and adjacent skills
]

SCORE_PENALTY = [
    # Experience thresholds and role types that are NOT a fit
]

# ── Storage (DO NOT CHANGE) ───────────────────
DB_PATH = "output/jobs.db"

# ── Export settings ───────────────────────────
EXPORT_MIN_SCORE = 0.5   # 0.5 for graduate, 0.4 for mid, 0.3 for senior
EXPORT_MAX_LISTINGS = 30
EXPORT_PATH     = "output/job_listings.json"      # top-scored, for AI evaluation
EXPORT_ALL_PATH = "output/job_listings_all.json"  # every job in the database

# ── Fetch settings (DO NOT CHANGE) ───────────
FETCH_LIMIT_PER_PAGE = 100
JOBSEARCH_FALLBACK_THRESHOLD = 50
POLITE_DELAY_SECONDS = 1.0

---

## ATTACHED FILE

The following file is attached:
- `CV_[name].pdf` — the candidate's curriculum vitae

Read it now and return only the completed config.py, starting with `# config.py`.
