import os
import pandas as pd

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES_BASE_DIR = os.path.join(BASE_DIR, 'data', 'Regulation current table')
OLD_TABLE_DIR = os.path.join(TABLES_BASE_DIR, 'old Regulation current table')
MAPPING_DIR = os.path.join(TABLES_BASE_DIR, 'מיקומי שורות בבירור')


def get_first_excel_file(directory):
    if not os.path.exists(directory):
        return None
    files = [
        os.path.join(directory, f) for f in os.listdir(directory)
        if f.endswith('.xlsx') and not f.startswith('~')
    ]
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def run_string_debug():
    print("=================== STRING MATCHING DEBUGGER ===================")

    # 1. Load the Mapping File
    mapping_file = os.path.join(MAPPING_DIR, 'clash_report_old_excel_rows.csv')
    if not os.path.exists(mapping_file):
        print(f"[!] Mapping file not found at: {mapping_file}")
        return

    df_map = pd.read_csv(mapping_file)
    if df_map.empty:
        print("[!] Mapping file is empty.")
        return

    # 2. Load the Generation Target (Old table source)
    old_excel_path = get_first_excel_file(OLD_TABLE_DIR)
    if not old_excel_path:
        print("[!] No source Excel file found to cross-reference.")
        return

    df_excel_raw = pd.read_excel(old_excel_path, header=None)

    # Find header row index
    header_row_idx = None
    for idx, row in df_excel_raw.iterrows():
        if 'כותרת טיוטת הרגולציה' in str(row.values):
            header_row_idx = idx
            break

    if header_row_idx is None:
        print("[!] Could not locate header row in Excel file.")
        return

    df_excel = pd.read_excel(old_excel_path, header=header_row_idx)

    # 3. Extract the first row's titles from both sources
    map_title_raw = str(df_map.iloc[0].get('כותרת טיוטת הרגולציה', ''))

    # Find matching string row in Excel manually by checking contains
    excel_title_raw = ""
    for _, row in df_excel.iterrows():
        val = str(row.get('כותרת טיוטת הרגולציה', ''))
        if "תקנות התקשורת" in val:
            excel_title_raw = val
            break

    if not excel_title_raw:
        excel_title_raw = str(df_excel.iloc[0].get('כותרת טיוטת הרגולציה', ''))

    print(f"\n[RAW MAP TITLE]:   {map_title_raw}")
    print(f"[RAW EXCEL TITLE]: {excel_title_raw}")

    # 4. Standard clean comparison test
    cleaned_map = map_title_raw.strip().replace('"', '').replace('\\', '')
    cleaned_excel = excel_title_raw.strip().replace('"', '').replace('\\', '')

    print(f"\n[*] Python Direct Equality Check (==): {cleaned_map == cleaned_excel}")
    print(f"[*] Map Title Length: {len(cleaned_map)} characters")
    print(f"[*] Excel Title Length: {len(cleaned_excel)} characters")

    # 5. Character-by-Character Decomposition
    print("\n--- BINARY CODE-POINT ANALYSIS ---")
    max_len = max(len(cleaned_map), len(cleaned_excel))

    print(f"{'Index':<6} | {'Map Char':<10} | {'Map Ord':<8} | {'Excel Char':<10} | {'Excel Ord':<9} | {'Match'}")
    print("-" * 65)

    for i in range(max_len):
        m_char = cleaned_map[i] if i < len(cleaned_map) else "[OUT]"
        m_ord = ord(m_char) if i < len(cleaned_map) else "-"

        e_char = cleaned_excel[i] if i < len(cleaned_excel) else "[OUT]"
        e_ord = ord(e_char) if i < len(cleaned_excel) else "-"

        match_status = "✓" if m_ord == e_ord else "X <--- CLASH"

        # Format printing for hidden characters like quotes/spaces
        m_disp = f"'{m_char}'" if m_char not in ['\n', '\r', '\t', ' '] else f"SPACE"
        e_disp = f"'{e_char}'" if e_char not in ['\n', '\r', '\t', ' '] else f"SPACE"

        print(f"{i:<6} | {m_disp:<10} | {m_ord:<8} | {e_disp:<10} | {e_ord:<9} | {match_status}")


if __name__ == "__main__":
    run_string_debug()