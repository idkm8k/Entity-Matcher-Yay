# Hi :D



# Entity-Matcher-Yay

Matches company names in one spreadsheet (Sheet A) to a reference spreadsheet (Sheet B) and pulls over the identifiers `tic`, `gvkey`, and `cusip`.

## Why

We had two datasets with different levels of information that we wanted to merge, but the company names didn't line up. Example: "Coca-Cola Co" vs "The Coca-Cola Company". Exact filtering and string fuzzy matching don't handle this well, so we used semantic embeddings.

Embeddings, however, are not enough either. They get close but can still make mistakes. Sending every comparison to an LLM like Gemini would be slow and expensive on large datasets. So embeddings do the bulk matching, and Gemini only checks the new or uncertain matches.

The repo compares two embedding methods and includes experimental scripts that use Gemini to verify the matches.

## Scripts

| Script | Status | What it does |
|---|---|---|
| `Simple Vector.py` | Works | Baseline. Embeds company names with `all-MiniLM-L6-v2` and matches each Sheet A name to its closest Sheet B name (cosine similarity > 0.85). |
| `Advanced Vector.py` | Mostly done, a few bugs left | Same idea with the stronger `BAAI/bge-m3` model, batched matching, and a 0.80 threshold. |
| `Delta Checker against Two Methods.py` | Experimental | Finds matches not already in the trusted final sheet and has Gemini check them. |
| `Another Delta Checker.py` | Experimental | Another version of the Gemini checker. |

## How it works

1. A vector script embeds the company names in both sheets.
2. Each Sheet A company is matched to the most similar Sheet B name.
3. If the similarity is above the threshold, `tic`, `gvkey`, and `cusip` are copied over.
4. The delta checkers send new matches to Gemini to confirm they are the same company.

## Input data (not included)

The spreadsheets are **not** part of this repo, because the data is private and `.xlsx` files are git-ignored. To run the scripts, you need to provide your own files with the same names and columns:

- `A_sheet.xlsx`: the companies you want to match. Needs a `Company` column.
- `B_sheet.xlsx`: the reference list. Needs `conm` (company name), `tic`, `gvkey`, and `cusip` columns.
- `Final Version.xlsx` and a matches sheet: only needed by the delta checker scripts. The exact filenames are near the top of each script.

## Setup

    pip install pandas openpyxl sentence-transformers torch google-generativeai

The delta checkers ask for a Gemini API key when run. It is typed at the prompt and is not stored in the code.

## Usage

Run the simple vector script first, then a delta checker on its output:

    python "Simple Vector.py"
    python "Delta Checker against Two Methods.py"

There are two versions of the delta checker (`Delta Checker against Two Methods.py` and `Another Delta Checker.py`). Which one is better is still being worked out.

`Advanced Vector.py` isn't part of the main pipeline yet (a few bugs left).

## Known issues

- `Advanced Vector.py` has a few bugs left.
- The `bge-m3` model is a ~2 GB download the first time it runs.
- The two models use different similarity thresholds, so scores are not directly comparable.
- If a Gemini batch fails, the delta checkers skip it and treat those companies as verified.

## Status

Work in progress.
