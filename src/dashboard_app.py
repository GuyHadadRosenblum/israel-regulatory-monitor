import streamlit as st
import subprocess
import os
import sys
import time
import glob
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

MASTER_SYNC_SCRIPT = os.path.join(BASE_DIR, "master_sync.py")
PROCESSED_DIR = os.path.join(PROJECT_DIR, "data", "processed")
RESULT_FILE = os.path.join(PROCESSED_DIR, "user_friendly_summary_he.xlsx")

GANTT_SCRIPT = os.path.join(BASE_DIR, "gantt_maker.py")
REG_TABLE_SCRIPT = os.path.join(BASE_DIR, "Regulation_current_table_generator.py")

GANTT_OUTPUT_DIR = os.path.join(PROJECT_DIR, "data", "gantt and tracking table")
GANTT_MONDAY_DIR = os.path.join(GANTT_OUTPUT_DIR, "monday_table")

REG_TABLE_OUTPUT_DIR = os.path.join(
    PROJECT_DIR,
    "data",
    "Regulation current table",
    "new Regulation current table"
)
REG_TABLE_MONDAY_DIR = os.path.join(
    PROJECT_DIR,
    "data",
    "Regulation current table",
    "monday_table"
)

# Relative path mapping for the tutorial images folder
GUIDE_IMAGES_DIR = os.path.join(PROJECT_DIR, "תמונות הדרכה")


# =============================================================================
# HELPERS
# =============================================================================
def open_file(path):
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="Regulatory Monitoring Command Center",
    page_icon="📊",
    layout="wide"
)

# Center-Aligned Header Components
st.markdown("<h1 dir='rtl' style='text-align: center;'>📊 מערכת ניטור ובקרה</h1>", unsafe_allow_html=True)
st.markdown(
    "<p dir='rtl' style='text-align: center; color: gray;'>לוח בקרה קומפקטי לניטור, סנכרון נתונים, הפקת טבלאות זרם ותרשימי גאנט מובנים.</p>",
    unsafe_allow_html=True)

# =============================================================================
# TOP STATUS BAR
# =============================================================================
top1, top2 = st.columns([3, 1])

with top1:
    if os.path.exists(RESULT_FILE):
        last_mod = datetime.fromtimestamp(
            os.path.getmtime(RESULT_FILE)
        ).strftime('%Y-%m-%d %H:%M')
        st.markdown(
            f"<div dir='rtl' style='text-align: right;'><span style='color: #155724; background-color: #d4edda; border-color: #c3e6cb; padding: 8px 12px; border-radius: 4px; display: inline-block; width: 100%;'>דוח מסונכרן אחרון: {last_mod}</span></div>",
            unsafe_allow_html=True)
    else:
        st.markdown(
            "<div dir='rtl' style='text-align: right;'><span style='color: #856404; background-color: #fff3cd; border-color: #ffeeba; padding: 8px 12px; border-radius: 4px; display: inline-block; width: 100%;'>לא נמצא דוח מסונכרן במערכת.</span></div>",
            unsafe_allow_html=True)

with top2:
    if st.button("📂 פתח תיקיית פלטים", use_container_width=True):
        open_file(PROCESSED_DIR)

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# MAIN DASHBOARD ROW
# =============================================================================
col1, col2, col3 = st.columns([1.2, 1.5, 1])

# -----------------------------------------------------------------------------
# CARD 1: FULL SYNC
# -----------------------------------------------------------------------------
with col1:
    st.markdown("<h3 dir='rtl' style='text-align: right;'>🔄 ניטור אוטומטי</h3>", unsafe_allow_html=True)
    st.markdown(
        "<div dir='rtl' style='text-align: right; color: gray; font-size: 14px; margin-bottom: 15px; line-height: 1.6;'> "
        "לחיצה על כפתור זה מנטרת אוטומטית אחרי כל הרגולציה החדשה שאתר החקיקה הממשלתי, ומצליבה את הנתונים עם הפניות הרשמיות שמוזנות בשאלון שבכתובת:<br>"
        "<a href='https://tally.so/r/rj0Y0R' target='_blank'>https://tally.so/r/rj0Y0R</a> דרך ה-google sheet שמסונכרן עם השאלון.<br><br>"
        "כל מידע חד משמעי שנמצא באופן זה נדרס על ידי המערכת, ואילו מידע פנימי (כמו מועדי שליחת מיילים) לא נדרס ונשמר בעת העלאה מחדש למונדיי."
        "</div>",
        unsafe_allow_html=True
    )

    if st.button("🚀 הפעל ניטור אוטומטי", use_container_width=True):
        with st.status("מריץ סנכרון נתונים...", expanded=True) as status:

            # Add the GIF animation while the process is running
            gif_path = os.path.join(GUIDE_IMAGES_DIR, "Winnie The Pooh Sleeping GIF.gif")
            if os.path.exists(gif_path):
                st.image(gif_path, width=200)

            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"sync_log_{timestamp_str}.txt"
            log_filepath = os.path.join(PROCESSED_DIR, log_filename)

            os.makedirs(PROCESSED_DIR, exist_ok=True)

            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"

                process = subprocess.Popen(
                    [sys.executable, "-u", MASTER_SYNC_SCRIPT],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    env=env
                )

                log_output = ""
                console = st.empty()
                last_ui_update = time.time()

                with open(log_filepath, "w", encoding="utf-8", errors='replace') as log_file:
                    while True:
                        output = process.stdout.readline()

                        if output == '' and process.poll() is not None:
                            break

                        if output:
                            clean = output.replace('\r', '\n')
                            log_output += clean

                            log_file.write(clean)
                            log_file.flush()

                            # Throttle UI updates to keep the dashboard responsive
                            current_time = time.time()
                            if current_time - last_ui_update > 0.5:
                                console.code(log_output[-4000:], language="log")
                                last_ui_update = current_time

                console.code(log_output[-4000:], language="log")

                rc = process.poll()

                if rc == 0:
                    status.update(label="הסנכרון הושלם בהצלחה", state="complete", expanded=False)
                    st.success("תהליך הסנכרון הסתיים בהצלחה.")
                    st.info(f"קובץ לוג נשמר בשם: {log_filename}")

                    if os.path.exists(RESULT_FILE):
                        open_file(RESULT_FILE)
                else:
                    st.error("תהליך הסנכרון נכשל. בדוק את פלט הלוג למעלה.")

            except Exception as e:
                st.error(f"שגיאה בהפעלת תסריט הסנכרון: {e}")

    st.markdown("---")

    # Integrated Tutorial Expander containing explicit layout steps and markdown images
    with st.expander("📖 מדריך: העלאת הטבלה חזרה למונדיי", expanded=False):

        # Step 1
        img1_path = os.path.join(GUIDE_IMAGES_DIR, "איך להעלות את הטבלה 1.png")
        if os.path.exists(img1_path):
            st.image(img1_path)
            st.markdown(
                "<div dir='rtl' style='text-align: right; font-size: 14px;'><b>שלב 1:</b> בלוח ה-Monday, לחץ על שלוש הנקודות המופיעות בפינה העליונה. משם, בחר באפשרות more actions ולאחר מכן בחר ב-\"Import נושא\".</div>",
                unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Step 2
        img2_path = os.path.join(GUIDE_IMAGES_DIR, "איך להעלות את הטבלה 2.png")
        if os.path.exists(img2_path):
            st.image(img2_path)
            st.markdown(
                "<div dir='rtl' style='text-align: right; font-size: 14px;'><b>שלב 2:</b> לאחר פתיחת חלון הייבוא, בחר את קובץ האקסל המעודכן שנוצר על ידי המערכת. הקובץ נמצא בתיקיית ה-data/processed ושמו: user_friendly_summary_he.xlsx.</div>",
                unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Step 3
        img3_path = os.path.join(GUIDE_IMAGES_DIR, "איך להעלות את הטבלה 3.png")
        if os.path.exists(img3_path):
            st.image(img3_path)
            st.markdown(
                "<div dir='rtl' style='text-align: right; font-size: 14px;'><b>שלב 3:</b> בחר את העמודה \"נושא\" מתוך קובץ האקסל וקבע אותה כעמודת-Item Name.</div>",
                unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Step 4
        img4_path = os.path.join(GUIDE_IMAGES_DIR, "איך להעלות את הטבלה 4.png")
        if os.path.exists(img4_path):
            st.image(img4_path)
            st.markdown(
                "<div dir='rtl' style='text-align: right; font-size: 14px;'><b>שלב 4:</b> לאחר בחירת עמודת השם, המערכת תציג דף הגדרות כלליות. פשוט לחץ על כפתור Next.</div>",
                unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Step 5
        img5_path = os.path.join(GUIDE_IMAGES_DIR, "איך להעלות את הטבלה 5.png")
        if os.path.exists(img5_path):
            st.image(img5_path)
            st.markdown(
                "<div dir='rtl' style='text-align: right; font-size: 14px;'><b>שלב 5:</b> בחר באפשרות השלישית: \"Overwrite existing items\". לאחר מכן הגדר את העמודה \"מזהה קישור ייחודי\" כעמודת המפתח שעל פיה המערכת תבצע את העדכון. כך תבטיח שהסיכומים שהמערכת יצרה יידרסו ויעודכנו על גבי הפריטים הקיימים בלוח, ללא כפילויות.</div>",                unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# CARD 2: MONDAY PROCESSORS
# -----------------------------------------------------------------------------
with col2:
    st.markdown("<h3 dir='rtl' style='text-align: right;'>📈 טבלאות זרם ותרשימי גאנט</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p dir='rtl' style='text-align: right; color: gray; font-size: 14px; margin-bottom: 15px;'>העלו קבצי מונדיי בכדי לייצר באופן אוטומטי טבלאות זרם ותרשימים למעקב אחר משימות.</p>",
        unsafe_allow_html=True)

    # Label for File Uploader in RTL
    st.markdown(
        "<p dir='rtl' style='text-align: right; margin-bottom: 2px; font-size: 14px;'>העלאת קובץ ייצוא ממונדיי (.xlsx)</p>",
        unsafe_allow_html=True)
    uploaded_monday_file = st.file_uploader(
        "Upload Monday export (.xlsx)",
        type=["xlsx"],
        label_visibility="collapsed"
    )

    # Label for Selectbox in RTL
    st.markdown("<p dir='rtl' style='text-align: right; margin-bottom: 2px; font-size: 14px;'>בחר סוג פלט מבוקש</p>",
                unsafe_allow_html=True)

    # Custom display mapping to keep options clean while storing programmatic names
    options_mapping = {
        "תרשימי גאנט בלבד": "Gantt Charts Only",
        "טבלת זרם עדכנית בלבד": "Regulation Current Table Only",
        "שניהם יחד (גאנט + טבלת זרם)": "Both (Gantt + Regulation Table)"
    }

    selected_display_option = st.selectbox(
        "Output type",
        list(options_mapping.keys()),
        label_visibility="collapsed"
    )
    process_option = options_mapping[selected_display_option]

    if st.button("⚙️ הפק תוצרים", use_container_width=True):

        if uploaded_monday_file is None:
            st.warning("אנא העלה קובץ אקסל של מונדיי תחילה.")

        else:
            with st.status("מעבד קובץ נתונים ממונדיי...", expanded=True) as status:

                file_bytes = uploaded_monday_file.read()

                # -------------------------------------------------------------
                # GANTT
                # -------------------------------------------------------------
                if process_option in [
                    "Gantt Charts Only",
                    "Both (Gantt + Regulation Table)"
                ]:
                    os.makedirs(GANTT_MONDAY_DIR, exist_ok=True)

                    gantt_path = os.path.join(
                        GANTT_MONDAY_DIR,
                        uploaded_monday_file.name
                    )

                    with open(gantt_path, "wb") as f:
                        f.write(file_bytes)

                    rc1 = subprocess.call([sys.executable, GANTT_SCRIPT])

                    if rc1 == 0:
                        st.success("תרשימי גאנט הופקו בהצלחה.")

                        # --- NEW: Trigger the Telegram Bot Notification ---
                        bot_script = os.path.join(BASE_DIR, "telegram_bot.py")
                        if os.path.exists(bot_script):
                            st.info("שולח עדכון לבוט הטלגרם...")
                            subprocess.call([sys.executable, bot_script])
                        # ---------------------------------------------------

                        gantt_files = [
                            os.path.join(GANTT_OUTPUT_DIR, "gantt_official_submissions.html"),
                            os.path.join(GANTT_OUTPUT_DIR, "gantt_missing_ria.html"),
                            os.path.join(GANTT_OUTPUT_DIR, "gantt_enforcement_portal.html")
                        ]

                        for file in gantt_files:
                            if os.path.exists(file):
                                open_file(file)

                    else:
                        st.error("הפקת תרשימי גאנט נכשלה.")

                # -------------------------------------------------------------
                # REGULATION TABLE
                # -------------------------------------------------------------
                if process_option in [
                    "Regulation Current Table Only",
                    "Both (Gantt + Regulation Table)"
                ]:
                    os.makedirs(REG_TABLE_MONDAY_DIR, exist_ok=True)

                    reg_path = os.path.join(
                        REG_TABLE_MONDAY_DIR,
                        uploaded_monday_file.name
                    )

                    with open(reg_path, "wb") as f:
                        f.write(file_bytes)

                    reg_script_name = "Regulation_current_table_generator.py"
                    rc2 = subprocess.call([sys.executable, REG_TABLE_SCRIPT])

                    if rc2 == 0:
                        st.success("טבלת הרגולציה והזרם עודכנה בהצלחה.")

                        files = glob.glob(
                            os.path.join(REG_TABLE_OUTPUT_DIR, "*.xlsx")
                        )

                        if files:
                            latest_file = max(files, key=os.path.getctime)
                            open_file(latest_file)

                    else:
                        st.error("עדכון טבלת הרגולציה נכשל.")

                status.update(label="עיבוד הנתונים הסתיים", state="complete", expanded=False)

    st.markdown("---")

    # Expander 1: Manual Regulation Data Overrides and Updates
    with st.expander("📖 כיצד להעלות חוות דעת ולעדכן את טבלת הזרם ידנית", expanded=False):
        st.markdown(
            "<div dir='rtl' style='text-align: right; line-height: 1.6; font-size: 14px;'>"
            "המערכת מתבססת בכל הרצה על קובץ האקסל האחרון שנוצר כבסיס לגרסה הבאה. כדי לבצע שינויים ידניים "
            "(כמו עדכון החלטה או הוספת תמצית חוות דעת) מבלי שיידרסו בעתיד, לחץ על כפתור <b>📑 תיקיית טבלת זרם</b> "
            "בגישה המהירה, עלה תיקייה אחת למעלה לתיקיית האב <code>Regulation current table</code>, היכנס לתיקייה "
            "<code>old Regulation current table</code> ופתח לעריכה את קובץ האקסל העדכני ביותר לפי תאריך ושעה. "
            "לאחר ביצוע השינויים שמור את הקובץ בשמו המקורי, ובריצה הבאה המערכת תזהה אותו אוטומטית, תתבסס עליו "
            "כמקור, ותמזג לתוכו את השורות החדשות ממונדיי ללא דריסת העדכונים שלך."
            "</div>",
            unsafe_allow_html=True
        )

    # Expander 2: Exporting group targets correctly out of Monday (with Description-First structural format)
    with st.expander("📖 כיצד להוריד קובץ אקסל תקין מלוח המונדיי", expanded=False):

        # Step 1
        st.markdown("<div dir='rtl' style='text-align: right; font-size: 14px; font-weight: bold;'>לחצו על שלוש הנקודות ליד קבוצת הניטור האוטומטי כדי להוריד את הקבוצה הזו בלבד</div>", unsafe_allow_html=True)
        img_dl1_path = os.path.join(GUIDE_IMAGES_DIR, "איך להוריד קובץ מונדיי 1.png")
        if os.path.exists(img_dl1_path):
            st.image(img_dl1_path, width=400)
        st.markdown("<br>", unsafe_allow_html=True)

        # Step 2
        st.markdown("<div dir='rtl' style='text-align: right; font-size: 14px; font-weight: bold;'>לחצו על Export to Excel</div>", unsafe_allow_html=True)
        img_dl2_path = os.path.join(GUIDE_IMAGES_DIR, "איך להוריד קובץ מונדיי 2.png")
        if os.path.exists(img_dl2_path):
            st.image(img_dl2_path, width=400)
        st.markdown("<br>", unsafe_allow_html=True)

        # Step 3
        st.markdown("<div dir='rtl' style='text-align: right; font-size: 14px; font-weight: bold;'>רצוי לסמן גם את תיבת ה-update כדי לשמור גם את ההתכתבויות שבמונדיי. לחצו על Export. את קובץ המונדיי שהורד יש להעלות למערכת הזו כדי לייצר תרשימי גאנט וטבלאות זרם.</div>", unsafe_allow_html=True)
        img_dl3_path = os.path.join(GUIDE_IMAGES_DIR, "איך להוריד קובץ מונדיי 3.png")
        if os.path.exists(img_dl3_path):
            st.image(img_dl3_path, width=400)

# -----------------------------------------------------------------------------
# CARD 3: QUICK ACCESS
# -----------------------------------------------------------------------------
with col3:
    st.markdown("<h3 dir='rtl' style='text-align: right;'>📂 גישה לתיקיות</h3>", unsafe_allow_html=True)

    if st.button("📊 תיקיית פלטי סנכרון", use_container_width=True):
        open_file(PROCESSED_DIR)

    if st.button("📈 תיקיית תרשימי גאנט", use_container_width=True):
        os.makedirs(GANTT_OUTPUT_DIR, exist_ok=True)
        open_file(GANTT_OUTPUT_DIR)

    if st.button("📑 תיקיית טבלת זרם", use_container_width=True):
        os.makedirs(REG_TABLE_OUTPUT_DIR, exist_ok=True)
        open_file(REG_TABLE_OUTPUT_DIR)

# =============================================================================
# FOOTER
# =============================================================================
st.divider()
st.caption("Developed for the Israeli Regulatory Authority | 2026")