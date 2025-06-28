
import streamlit as st
import pandas as pd
import gspread
import openai
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import traceback

# קונפיגורציה
st.set_page_config(page_title="🎯 Job Dashboard v2", layout="wide")

# הגדרות חיבור לגוגל שיטס
def get_gsheet_data(spreadsheet_name, sheet_name):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        service_account_info = dict(st.secrets["credentials"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
        client = gspread.authorize(creds)

        sheet = client.open(spreadsheet_name).worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data), sheet
    except Exception as e:
        st.error("שגיאה בטעינת הנתונים:")
        st.text(traceback.format_exc())
        return pd.DataFrame(), None

# פונקציה לשליחת בקשה ל-GPT
def summarize_with_gpt(prompt_text):
    openai.api_key = st.secrets["openai_api_key"]
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "אתה מסכם משרות לעברית בצורה תמציתית ופשוטה, עבור מחפש עבודה."},
                {"role": "user", "content": f"""סכם את תיאור המשרה הבא בצורה פשוטה ותמציתית, והצג את עיקרי הדרישות והאחריות:

{prompt_text}"""}
            ],
            temperature=0.7,
            max_tokens=300
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        st.error("שגיאה מול OpenAI:")
        st.text(traceback.format_exc())
        return None

# פונקציה לעדכון שורה בגוגל שיטס
def update_summary(sheet, row_index, summary_text):
    try:
        sheet.update_cell(row_index + 2, 16 + 1, summary_text)  # עמודה P = index 16 (מתחיל ב-0)
        st.success("הסיכום עודכן בהצלחה בעמודה P")
    except Exception as e:
        st.error("שגיאה בעדכון גוגל שיטס:")
        st.text(traceback.format_exc())

# תוכן ראשי
def main():
    st.title("🎯 לוח משרות חכם – גרסה 2")

    spreadsheet_name = "קובץ משרות"
    sheet_name = "Sheet1"

    df, sheet = get_gsheet_data(spreadsheet_name, sheet_name)

    if df.empty:
        st.warning("לא נמצאו נתונים.")
        return

    for index, row in df.iterrows():
        with st.container():
            st.subheader(f"🎯 {row.get('שם המשרה', 'ללא שם')}")
            st.markdown(f"""
**חברה:** {row.get('שם החברה', 'לא צוין')}  
**מיקום:** {row.get('מיקום המשרה', 'לא צוין')}  
**תיאור:** {row.get('תקציר משרה') or row.get('תיאור משרה') or 'אין תיאור'}  
**סיכום GPT:** {row.get('תקציר משרה בעיבוד GPT', 'טרם עובדה')}
""")

            if st.button(f"✨ בצע תמצות GPT למשרה {index + 1}", key=f"gpt_{index}"):
                text_to_summarize = row.get('תקציר משרה') or row.get('תיאור משרה') or ''
                if text_to_summarize.strip():
                    with st.spinner("שולח ל-GPT..."):
                        summary = summarize_with_gpt(text_to_summarize)
                        if summary:
                            update_summary(sheet, index, summary)
                            st.rerun()
                else:
                    st.warning("אין טקסט לתמצות עבור משרה זו.")

if __name__ == "__main__":
    main()
