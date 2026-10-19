import os
import torch
import pandas as pd
from sentence_transformers import SentenceTransformer, util

# --- NETWORK PROTECTION FOR LARGE DOWNLOADS ---
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "600"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

file_a = "A_sheet.xlsx"
file_b = "B_sheet.xlsx"

print("Reading spreadsheets...")
df_a = pd.read_excel(file_a)
df_b = pd.read_excel(file_b)

# Clean and extract unique company names to optimize processing time
df_a["_clean_search_name"] = df_a["Company"].fillna("").astype(str).str.strip()
df_b["_clean_ref_name"] = df_b["conm"].fillna("").astype(str).str.strip()

unique_a = df_a["_clean_search_name"].unique().tolist()
unique_b = df_b["_clean_ref_name"].unique().tolist()

device = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Success! Running on: {device.upper()}")
print(num_unique_a := len(unique_a), "unique names in Sheet A")
print(num_unique_b := len(unique_b), "unique names in Sheet B")

print("Initializing model...")
model = SentenceTransformer("BAAI/bge-m3", device=device, model_kwargs={"low_cpu_mem_usage": True})

print("Encoding unique entries from Sheet A...")
embeddings_a = model.encode(unique_a, convert_to_tensor=True, show_progress_bar=True)
print("Encoding unique entries from Sheet B...")
embeddings_b = model.encode(unique_b, convert_to_tensor=True, show_progress_bar=True)

best_matches = []
batch_size = 2000
similarity_threshold = 0.80

print("Running vector matching...")
for i in range(0, len(embeddings_a), batch_size):
    batch_a = embeddings_a[i : i + batch_size]
    similarity_matrix = util.cos_sim(batch_a, embeddings_b)
    max_vals, max_idxs = torch.max(similarity_matrix, dim=1)
    
    for val, idx in zip(max_vals, max_idxs):
        if val.item() >= similarity_threshold:
            best_matches.append(unique_b[idx.item()])
        else:
            best_matches.append(None)

match_map = dict(zip(unique_a, best_matches))
df_a["_matched_conm"] = df_a["_clean_search_name"].map(match_map)

df_b_lookup = df_b[["_clean_ref_name", "tic", "gvkey", "cusip"]].drop_duplicates(subset=["_clean_ref_name"])

df_final = df_a.merge(df_b_lookup, left_on="_matched_conm", right_on="_clean_ref_name", how="left")

# Dynamically assign columns whether they had naming conflicts or came over cleanly
for col in ["tic", "gvkey", "cusip"]:
    col_x = f"{col}_x"
    col_y = f"{col}_y"
    
    if col_y in df_final.columns:
        # Naming conflict existed, fallback to original if match is missing
        df_final[col] = df_final[col_y].fillna(df_final.get(col_x, None))
    elif col in df_final.columns:
        # No conflict, column brought over cleanly from Sheet B
        pass
    else:
        # Fallback if column is entirely missing
        df_final[col] = None

# Drop temporary engineering columns safely
cols_to_drop = ["_clean_search_name", "_matched_conm", "_clean_ref_name"]
cols_to_drop += [c for c in df_final.columns if c.endswith("_x") or c.endswith("_y")]
df_final.drop(columns=cols_to_drop, errors="ignore", inplace=True)

print("Writing results back to Excel...")
df_final.to_excel("A_sheet_updated.xlsx", index=False)
print("Saved to A_sheet_updated.xlsx")