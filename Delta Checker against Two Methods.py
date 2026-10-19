import pandas as pd
import google.generativeai as genai
import json
import time
import getpass
import re

# ==========================================
# 1. SETUP & API
# ==========================================
api_key = getpass.getpass("Enter your Gemini API Key: ").strip()
genai.configure(api_key=api_key)

model = genai.GenerativeModel(
    'gemini-3.1-flash-lite',
    generation_config={"response_mime_type": "application/json"}
)

print("Reading spreadsheets...")
df_final = pd.read_excel("Final Version.xlsx")
df_merged = pd.read_excel("merged_A_and_B_audited.xlsx")
df_b = pd.read_excel("B_sheet.xlsx")

# ==========================================
# 2. ISOLATE THE DELTA (Y - X)
# ==========================================
# Identify X: The 100% pure companies from your Final Version
pure_companies = set(df_final.dropna(subset=["gvkey"])["Company"].astype(str).str.strip())

# Identify Y: All matched companies in the merged sheet
df_merged_matched = df_merged.dropna(subset=["gvkey"]).copy()

# Isolate Y-X: Matches in merged that are NOT in the pure Final Version
df_delta = df_merged_matched[~df_merged_matched["Company"].astype(str).str.strip().isin(pure_companies)].copy()

print(f"Base 'Final Version' matches (X): {len(pure_companies)}")
print(f"Merged sheet matches (Y): {len(df_merged_matched)}")
print(f"Delta to be audited by Gemini (Y - X): {len(df_delta)}")

if len(df_delta) == 0:
    print("No new matches to audit. Your Final Version already contains everything!")
    exit()

# Attach the 'conm' reference names from Sheet B to our delta
df_b_lookup = df_b[["gvkey", "conm"]].drop_duplicates(subset=["gvkey"])
df_audit = df_delta.merge(df_b_lookup, on="gvkey", how="left")

pairs_to_check = []
for idx, row in df_audit.iterrows():
    pairs_to_check.append({
        "row_id": int(idx), # Original delta index
        "search_name": str(row["Company"]).strip(),
        "ref_name": str(row["conm"]).strip()
    })

# ==========================================
# 3. GEMINI AUDIT ENGINE
# ==========================================
BATCH_SIZE = 25
mismatches = []
total_companies = len(pairs_to_check)

print(f"\nInitializing verification for {total_companies} delta companies...")

for i in range(0, total_companies, BATCH_SIZE):
    batch = pairs_to_check[i : i + BATCH_SIZE]
    current_batch_num = (i // BATCH_SIZE) + 1
    total_batches = (total_companies // BATCH_SIZE) + 1
    
    prompt = f"""
    You are a corporate data auditor. 
    Determine if 'search_name' and 'ref_name' are the exact same corporate entity.
    Ignore punctuation, spacing, capitalization, legal suffixes (Inc, LLC, etc), and standard industry abbreviations.
    Flag as FALSE only if clearly distinct.
    
    INPUT DATA:
    {json.dumps(batch, indent=2)}
    
    Respond ONLY with a valid JSON array:
    [ {{"row_id": 1, "is_match": true, "reason": "..."}} ]
    """
    
    try:
        response = model.generate_content(prompt)
        res_text = response.text.strip()
        
        # Clean up any markdown code blocks returned by accident
        if "```" in res_text:
            json_match = re.search(r'\[.*\]', res_text, re.DOTALL)
            res_text = json_match.group(0) if json_match else res_text
            
        batch_results = json.loads(res_text)
        
        for item in batch_results:
            if not item.get("is_match", True):
                original_pair = next((p for p in batch if p["row_id"] == item["row_id"]), None)
                if original_pair:
                    mismatches.append({
                        "Original_Company": original_pair["search_name"],
                        "Matched_To": original_pair["ref_name"],
                        "AI_Reasoning": item.get("reason", "No reason provided")
                    })
        
        processed_count = min(i + BATCH_SIZE, total_companies)
        print(f"Batch {current_batch_num}/{total_batches} done | Processed {processed_count} / {total_companies} companies")
        time.sleep(4)
        
    except Exception as e:
        print(f"Error on batch {current_batch_num}: {e}")

# ==========================================
# 4. MERGE & EXPORT THE ULTIMATE SHEET (FIXED)
# ==========================================
print("\n" + "="*40)
print(f"Audit Complete. Gemini flagged {len(mismatches)} mismatches from the delta.")
print("="*40)

# Get the names of companies Gemini rejected
rejected_names = set(m["Original_Company"] for m in mismatches)

# Filter our delta to strictly the ones Gemini verified as TRUE
df_verified_delta = df_delta[~df_delta["Company"].astype(str).str.strip().isin(rejected_names)].copy()
print(f"Successfully verified {len(df_verified_delta)} new matches to inject into the final sheet.")

# Create the ultimate master dataframe using Final Version as the base
df_master = df_final.copy()

# FIX: Safely drop index duplicates from the update data to completely prevent the ValueError
df_delta_clean = df_verified_delta[~df_verified_delta.index.duplicated(keep='first')]

print("Injecting verified matches safely into master sheet layout...")
# Map values using a clean dictionary mapping instead of index updates to circumvent string collisions
for col in ["tic", "gvkey", "cusip"]:
    # Enforce data types to object to allow strings and avoid mapping warnings
    df_master[col] = df_master[col].astype(object)
    
    # Build dictionary based on clean, non-duplicate records
    mapping_dict = df_delta_clean[col].to_dict()
    
    # Update master file row positions directly using the clean slice mapping
    for idx, val in mapping_dict.items():
        if idx in df_master.index:
            df_master.at[idx, col] = val

# Save the final masterpiece
output_file = "Ultimate_Final_Version.xlsx"
df_master.to_excel(output_file, index=False)

print(f"\n✅ Merge successful! Total confirmed matches is now: {df_master['gvkey'].notna().sum()}")
print(f"💾 Saved to: '{output_file}'")

# Optional: Save a log of what was rejected during this delta run
if mismatches:
    df_mismatches = pd.DataFrame(mismatches)
    def highlight_red(val):
        return 'background-color: #ffcccc'
    styled_df = df_mismatches.style.map(highlight_red, subset=['Matched_To', 'AI_Reasoning'])
    styled_df.to_excel("Delta_Mismatches_Audit.xlsx", index=False, engine='openpyxl')