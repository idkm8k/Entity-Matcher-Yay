import pandas as pd
from sentence_transformers import SentenceTransformer, util

# --- CONFIGURATION ---
MASTER_FILE = "A_sheet.xlsx"
DATA_FILE = "B_sheet.xlsx"
OUTPUT_FILE = "updated_master_semantic.xlsx"

# Configured based on your sheet properties
MASTER_COMPANY_COL = "Company"  # Column name in A_sheet
DATA_COMPANY_COL = "conm"      # Column name in B_sheet
# ---------------------

print("Loading files...")
df_master = pd.read_excel(MASTER_FILE)
df_data = pd.read_excel(DATA_FILE)

# Strip hidden trailing/leading spaces from headers just in case
df_master.columns = df_master.columns.str.strip()
df_data.columns = df_data.columns.str.strip()

# Initialize data columns in master if they don't already exist
for col in ['tic', 'gvkey', 'cusip']:
    if col not in df_master.columns:
        df_master[col] = None

# Extract lists using your explicit column headers
master_names = df_master[MASTER_COMPANY_COL].astype(str).tolist()
data_names = df_data[DATA_COMPANY_COL].astype(str).tolist()

print("Loading local semantic model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

print("Generating semantic embeddings...")
embeddings_master = model.encode(master_names, convert_to_tensor=True)
embeddings_data = model.encode(data_names, convert_to_tensor=True)

print("Finding semantic matches...")
for i, master_emb in enumerate(embeddings_master):
    cosine_scores = util.cos_sim(master_emb, embeddings_data)
    best_match_idx = cosine_scores.argmax().item()
    highest_score = cosine_scores[0][best_match_idx].item()
    
    # 0.85 threshold ensures tight, accurate alignment
    if highest_score > 0.85:
        matched_row = df_data.iloc[best_match_idx]
        df_master.at[i, 'tic'] = matched_row['tic']
        df_master.at[i, 'gvkey'] = matched_row['gvkey']
        df_master.at[i, 'cusip'] = matched_row['cusip']

print(f"Saving results to {OUTPUT_FILE}...")
df_master.to_excel(OUTPUT_FILE, index=False)
print("Process completed successfully!")