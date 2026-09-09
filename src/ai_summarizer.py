import os
import time
import json
import pandas as pd
from pathlib import Path
from docx import Document

# Import ONLY the modern, lightweight Google GenAI SDK
from google import genai
from google.genai import types

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_FILE = os.path.join(DATA_DIR, 'processed', 'unified_legislation_log.xlsx')

# Google Cloud Platform Identity Parameters
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

# Dynamic path resolution for the Service Account JSON key
SERVICE_ACCOUNT_JSON_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

# Point the application to your Service Account credentials
# Authentication is supplied by the operator, never bundled with the app.

SYSTEM_PROMPT = """
הנחיות למערכת:
תפקיד: אתה מומחה לניתוח חקיקה ורגולציה בישראל, הפועל לפי "חוק עקרונות האסדרה, התשפ"ב 2021". תפקידך הוא להנגיש מידע משפטי מורכב לאדם הפשוט ולנתח האם דבר חקיקה מהווה "אסדרה" (רגולציה) לפי החוק.

Output Structure (Mandatory JSON only):
{
    "נושא": "<שם לא רשמי, ומובן לאדם הממוצע>",
    "סיכום AI": "<פסקה אחת (אך ניתן יותר אם יש צורך לתת יותר רקע או להסביר מה בדיוק השינוי) על מהות הנושא. תמיד בתחילת הפסקה, לפני ההסבר על השינוי, ציין האם זו רגולציה (השתמש רק ב-"זו רגולציה" או ב-"זו אינה רגולציה" בדיוק) ואם זו אינה רגולציה תן נימוק ספציפי אחד מתוך הרשימה כללי החלטה קשיחים.>"
}
הנחיות למערכת:
תפקיד: אתה מומחה לניתוח חקיקה ורגולציה בישראל, הפועל לפי "חוק עקרונות האסדרה, התשפ"ב–2021". תפקידך הוא להנגיש מידע משפטי מורכב לאדם הפשוט ולנתח האם דבר חקיקה מהווה "אסדרה" (רגולציה) לפי החוק ולפי תפיסתו של האדם הממוצע.

אינטואיציית הבסיס להגדרה:
מה שאנשים באמת מתכוונים אליו כשהם אומרים "רגולציה" (או "בירוקרטיה" ו"חנק של השוק") זה לא עצם קיום החוק, אלא מנגנון הפיקוח היומיומי שיושב למישהו על הווריד. רגולציה היא מערכת של כללים טכניים, אישורים, רישיונות, תקנים וטפסים, שמנוהלת על ידי גוף ממשלתי ספציפי (הרגולטור) שתפקידו לבדוק עסקים, חברות או אזרחים פרטיים המנהלים פעילות כלכלית/ציבורית. שינוי חקיקתי שרק מוסיף אופציות/תמריצים נוספים למשק אבל לא מטיל מגבלות לא ייחשב ככלל ברגולציה. אם הוא אינו עונה על האינטואיציה הבסיסית הזו אתה מוכרח לא להחשיב את זה כרגולציה, אבל עלייך כשאתה מפרט למה עלייך להשתמש בכללי ההחלטה הקשיחים.

מבחן הזהב החיובי: האם יש כאן רשות מפקחת (גננת) שדורשת אישור/דיווח/עמידה בתקן מגורם פרטי או עסקי כדי לפעול? אם כן -> רגולציה.
מבחן הזהב השלילי: האם החוק רק קובע איך המדינה, משרדי הממשלה, או המאגרים שלה מנהלים את עצמם מבפנים? אם כן -> אינה רגולציה (אלא חקיקה מנהלית/פרוצדורלית).

כללי החלטה קשיחים לקביעת "אינה רגולציה" (כאשר אתה מנמק שמשהו הוא לא רגולציה עלייך לבחור רק באחד הנימוקים האלו):
עליך לקבוע שמשהו הוא "אינה רגולציה" אם הוא עונה על אחת מהסיבות הבאות (בחר את המדויקת ביותר):
1. החרגת המגזר הציבורי / חקיקה מנהלית: הוראה שחלה אך ורק על גופים בתוך המגזר הציבורי (למשל אופן התקצוב של מערכת הבריאות או החינוך או תקצוב בכלל של משרדי ממשלה. כל התנהלות צה"ל, משטרה, רשויות מקומיות, ניהול מאגרי מידע ממשלתיים וכו').
2. אינה ניתנת לאכיפה רציפה: אירוע נקודתי חולף, או שאין כלל אלמנט של פיקוח, אכיפה, מפקחים וקנסות כלפי חוץ.
3. החרגת שירותים חברתיים: מבחני תמיכה, שירותי מדינה כמו חינוך, טיפול רפואי או סוציאלי הניתנים ישירות ע"י הממשלה.
4. אינה בעלת אופי כללי: הוראה החלה באופן ספציפי ונקודתי על חברה אחת, תאגיד אחד, יישוב או אדם ספציפי.
5. החרגות מהתוספת לחוק: פיקוח מחירים, קביעת תעריפים, היטלים, אגרות, תמלוגים, מסים, או מכרזים.
6. תכניות סטטוטוריות: תכניות לפי חוק התכנון והבנייה, משק הגז הטבעי, חוק המים או ניקוז.

אינדיקציות מיוחדות:
- קיים פטור מ-RIA: ציין בתחילת הטקסט "צורף פטור RIA" והמשך להסבר.
- קיים דוח RIA: ציין בתחילת הטקסט "צורף דוח RIA" והמשך להסבר. (זו אינדיקציה חזקה שמדובר ברגולציה, ולכן אין צורך לציין "זו רגולציה" בנוסף).
תשתדל להיות קצר בהסבר אם ניתן.
"""


def get_genai_client():
    """Initializes the modern GenAI Client using Service Account credentials via Vertex AI."""
    print("[*] Initializing GenAI Client using Service Account identity...")
    try:
        # Enforcing vertexai=True routes the payload directly to the enterprise cloud ecosystem.
        # It automatically authenticates using the GOOGLE_APPLICATION_CREDENTIALS environment variable.
        return genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=LOCATION
        )
    except Exception as e:
        print(f"[!] Error initializing GenAI Client: {e}")
        raise RuntimeError("Could not initialize Vertex AI; check local credentials") from e


def extract_text_from_docx(docx_path):
    """Extracts text from Word documents."""
    try:
        doc = Document(docx_path)
        full_text = [para.text for para in doc.paragraphs if para.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text for cell in row.cells if cell.text.strip()]
                if row_text:
                    full_text.append(" | ".join(row_text))
        return "\n".join(full_text)
    except Exception as e:
        print(f"      [!] Error reading DOCX: {e}")
        return ""


def get_absolute_path(relative_path):
    """Converts relative path from CSV to absolute path."""
    if pd.isna(relative_path) or not str(relative_path).strip() or str(relative_path).lower() == 'nan':
        return None
    return os.path.join(DATA_DIR, os.path.normpath(str(relative_path)))


def save_intermediate_results(df):
    """Saves the current state of the DataFrame to the Excel log file."""
    try:
        with pd.ExcelWriter(LOG_FILE, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Regulatory_Log')
            workbook = writer.book
            worksheet = writer.sheets['Regulatory_Log']
            header_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1})
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 24)
            worksheet.freeze_panes(1, 0)
        print(f"    [V] Table updated and saved successfully.")
    except Exception as e:
        raise RuntimeError('Could not save AI results') from e


def process_ai_summaries():
    print(f"\n{'=' * 70}")
    print("[*] STARTING AI SUMMARIZATION PROCESS (v5.0 - Final Clean Architecture)")
    print(f"{'=' * 70}")

    if not os.path.exists(LOG_FILE):
        print(f"[!] Error: Log file not found at {LOG_FILE}")
        raise FileNotFoundError(LOG_FILE)

    df = pd.read_excel(LOG_FILE)

    # Ensure AI columns exist
    if 'נושא' not in df.columns: df['נושא'] = None
    if 'סיכום AI' not in df.columns: df['סיכום AI'] = None

    client = get_genai_client()
    if not client:
        print("[!] Critical: GenAI Client initialization failed.")
        return

    # Vertex AI requires explicitly versioned model endpoints
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    for idx, row in df.iterrows():
        # Check if processing is needed
        topic_empty = pd.isna(row.get('נושא')) or not str(row.get('נושא')).strip()
        summary_empty = pd.isna(row.get('סיכום AI')) or not str(row.get('סיכום AI')).strip()

        if topic_empty or summary_empty:
            title = row.get('Regulation_Title', f"Row_{idx}")
            print(f"\n[*] Processing: '{title}'")

            # Selection Logic: Max 2 files (1 Regulation, 1 RIA)
            reg_file = get_absolute_path(row.get('Portal_Local_Regulation_Path')) or get_absolute_path(
                row.get('Submission_Local_Regulation_Path'))
            ria_file = get_absolute_path(row.get('Portal_Local_RIA_Path')) or get_absolute_path(
                row.get('Submission_Local_RIA_Path'))

            valid_files = [f for f in [reg_file, ria_file] if f and os.path.exists(f)]
            print(f"    -> Selected {len(valid_files)} files for context.")

            # Prepare content objects for the API call
            contents = []
            desc = row.get('Portal_Description', '')
            if pd.notna(desc) and str(desc).strip():
                contents.append(f"Description of the regulation from the legislation website: {desc}")

            for fp in valid_files:
                path_obj = Path(fp)
                if path_obj.suffix.lower() == ".docx":
                    text = extract_text_from_docx(path_obj)
                    if text:
                        contents.append(f"Document content ({path_obj.name}):\n{text[:15000]}")
                elif path_obj.suffix.lower() == ".pdf":
                    try:
                        with open(path_obj, 'rb') as f:
                            pdf_bytes = f.read()
                        contents.append(
                            types.Part.from_bytes(
                                data=pdf_bytes,
                                mime_type='application/pdf',
                            )
                        )
                    except Exception as e:
                        print(f"      [!] Could not read PDF {path_obj.name}: {e}")

            try:
                # Execute generation using the structured client interface
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json"
                    ),
                )

                raw_text = response.text.strip()
                print("    [AI] Received structured summary")

                res_json = json.loads(raw_text)

                # Update DataFrame
                df.at[idx, 'נושא'] = res_json.get('נושא')
                df.at[idx, 'סיכום AI'] = res_json.get('סיכום AI')

                # Save immediately after each success
                save_intermediate_results(df)

                # Rate limit safety
                time.sleep(4)

            except Exception as e:
                raise RuntimeError(f"AI processing failed for row {idx}") from e

    print(f"\n{'=' * 70}\n[*] Process Finished.\n{'=' * 70}")


if __name__ == "__main__":
    process_ai_summaries()
