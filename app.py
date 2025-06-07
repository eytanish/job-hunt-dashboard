import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from urllib.parse import urlparse
import re
import hashlib
import json

# קונפיגורציה של הדף
st.set_page_config(
    page_title="🎯 Job Hunt Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS מותאם אישית לעיצוב יפה
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #1f77b4;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    .job-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: #f9f9f9;
    }
    .job-card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        transition: 0.3s;
    }
    .applied {
        border-left: 5px solid #28a745;
    }
    .not-applied {
        border-left: 5px solid #ffc107;
    }
    .rejected {
        border-left: 5px solid #dc3545;
    }
    .status-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        color: white;
        font-weight: bold;
        display: inline-block;
    }
    .status-not-applied { background-color: #ffc107; }
    .status-applied { background-color: #28a745; }
    .status-rejected { background-color: #dc3545; }
    .status-interview { background-color: #17a2b8; }
    .user-info {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# הגדרות משתמשים
USERS_CONFIG = {
    "user1": {
        "name": "איתן חזון",
        "email": "eytan.hazon@gmail.com",
        "spreadsheet_name": "קובץ משרות",
        "sheet_name": "Sheet1"
    },
    "user2": {
        "name": "משתמש דוגמה 2",
        "email": "user2@example.com", 
        "spreadsheet_name": "קובץ משרות - משתמש 2",
        "sheet_name": "Sheet1"
    },
    "user3": {
        "name": "משתמש דוגמה 3",
        "email": "user3@example.com",
        "spreadsheet_name": "קובץ משרות - משתמש 3", 
        "sheet_name": "Sheet1"
    }
    # הוסף עוד משתמשים כאן...
}

def get_user_from_url():
    """חילוץ מזהה משתמש מה-URL"""
    query_params = st.experimental_get_query_params()
    return query_params.get("user", [None])[0]

def authenticate_user(user_id):
    """אימות משתמש"""
    if user_id not in USERS_CONFIG:
        return None
    return USERS_CONFIG[user_id]

@st.cache_data(ttl=300)
def load_data_from_sheets(spreadsheet_name, sheet_name):
    """טעינת נתונים מגוגל שיטס לפי משתמש"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # קריאת credentials מ-Streamlit Secrets
        credentials_info = st.secrets["credentials"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open(spreadsheet_name)
        sheet = spreadsheet.worksheet(sheet_name)
        
        # קבלת כל הנתונים
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # ניקוי ועיבוד הנתונים
        if not df.empty:
            # המרת תאריכים
            if 'תאריך' in df.columns:
                df['תאריך'] = pd.to_datetime(df['תאריך'], errors='coerce')
            
            # ניקוי עמודות ריקות
            df = df.dropna(how='all', axis=1)
            df = df.fillna('')
            
        return df
    except Exception as e:
        st.error(f"שגיאה בטעינת נתונים: {e}")
        return pd.DataFrame()

def update_job_status(spreadsheet_name, sheet_name, row_index, status, cv_version="", intro_email="", applied_date="", rating=""):
    """עדכון סטטוס משרה בגוגל שיטס"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # קריאת credentials מ-Streamlit Secrets
        credentials_info = st.secrets["credentials"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open(spreadsheet_name)
        sheet = spreadsheet.worksheet(sheet_name)
        
        # עדכון הערכים ברלוונטיים לעמודות
        if cv_version:
            sheet.update_cell(row_index + 2, 11, cv_version)  # עמודה K
        if intro_email:
            sheet.update_cell(row_index + 2, 12, intro_email)  # עמודה L
        if status:
            sheet.update_cell(row_index + 2, 13, status)  # עמודה M
        if rating:
            sheet.update_cell(row_index + 2, 14, rating)  # עמודה N
        if applied_date:
            sheet.update_cell(row_index + 2, 13, f"{status} - {applied_date}")  # עמודה M
            
        return True
    except Exception as e:
        st.error(f"שגיאה בעדכון: {e}")
        return False

def calculate_days_since_posted(post_date_str):
    """חישוב ימים מאז פרסום המשרה"""
    if not post_date_str or post_date_str == "לא נמצא תאריך":
        return None
    
    try:
        # ניתוח טקסט כמו "2 days ago", "1 week ago"
        if "day" in post_date_str.lower():
            days = re.findall(r'\d+', post_date_str)
            return int(days[0]) if days else None
        elif "week" in post_date_str.lower():
            weeks = re.findall(r'\d+', post_date_str)
            return int(weeks[0]) * 7 if weeks else None
        elif "month" in post_date_str.lower():
            months = re.findall(r'\d+', post_date_str)
            return int(months[0]) * 30 if months else None
        elif "hour" in post_date_str.lower():
            return 0  # פחות מיום
    except:
        pass
    return None

def generate_user_links():
    """יצירת לינקים אישיים לכל המשתמשים"""
    base_url = "https://your-app-name.streamlit.app"  # החלף בכתובת האמיתית
    links = {}
    
    for user_id, user_info in USERS_CONFIG.items():
        links[user_id] = {
            "name": user_info["name"],
            "link": f"{base_url}?user={user_id}"
        }
    
    return links

def main():
    # קבלת מזהה משתמש מה-URL
    user_id = get_user_from_url()
    
    # אם אין משתמש - הצג דף ברירת מחדל עם לינקים
    if not user_id:
        st.markdown('<h1 class="main-header">🎯 Job Hunt Dashboard</h1>', unsafe_allow_html=True)
        st.markdown("### ברוכים הבאים למערכת ניהול חיפוש עבודה!")
        
        st.info("זהו דאשבורד אישי לניהול חיפוש עבודה. כל משתמש מקבל לינק אישי.")
        
        # הצגת לינקים לדוגמה (למפתח)
        if st.checkbox("הצג לינקים לדוגמה (למפתח בלבד)"):
            st.markdown("### לינקים אישיים:")
            links = generate_user_links()
            for user_id, info in links.items():
                st.markdown(f"**{info['name']}:** `{info['link']}`")
        
        st.markdown("---")
        st.markdown("**להפעלה:** הוסף `?user=USER_ID` לכתובת, למשל: `?user=user1`")
        return
    
    # אימות משתמש
    user_info = authenticate_user(user_id)
    if not user_info:
        st.error("🚫 משתמש לא מורשה")
        st.stop()
    
    # הצגת פרטי משתמש
    st.markdown(f"""
    <div class="user-info">
        <h3>👋 שלום {user_info['name']}!</h3>
        <p>📧 {user_info['email']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # כותרת ראשית
    st.markdown('<h1 class="main-header">🎯 Job Hunt Dashboard</h1>', unsafe_allow_html=True)
    
    # טעינת נתונים לפי משתמש
    with st.spinner('טוען נתונים מגוגל שיטס...'):
        df = load_data_from_sheets(user_info['spreadsheet_name'], user_info['sheet_name'])
    
    if df.empty:
        st.warning(f"לא נמצאו נתונים עבור {user_info['name']}. ודא שקובץ '{user_info['spreadsheet_name']}' קיים ומכיל נתונים.")
        return
    
    # sidebar עם פילטרים
    st.sidebar.header("🔍 פילטרים")
    
    # פילטר לפי חברה
    companies = df['שם החברה'].unique() if 'שם החברה' in df.columns else []
    selected_companies = st.sidebar.multiselect("בחר חברות:", companies)
    
    # פילטר לפי תחום
    if 'סוג החברה' in df.columns:
        industries = df['סוג החברה'].unique()
        selected_industries = st.sidebar.multiselect("בחר תחומים:", industries)
    else:
        selected_industries = []
    
    # פילטר לפי סטטוס הגשה
    status_filter = st.sidebar.selectbox(
        "סטטוס הגשה:",
        ["הכל", "לא הגשתי", "הגשתי", "ממתין לתשובה", "נדחה", "ראיון"]
    )
    
    # פילטר לפי תאריך פרסום
    freshness_filter = st.sidebar.selectbox(
        "רעננות המשרה:",
        ["הכל", "עד 3 ימים", "עד שבוע", "עד חודש"]
    )
    
    # החלת פילטרים
    filtered_df = df.copy()
    
    if selected_companies:
        filtered_df = filtered_df[filtered_df['שם החברה'].isin(selected_companies)]
    
    if selected_industries:
        filtered_df = filtered_df[filtered_df['סוג החברה'].isin(selected_industries)]
    
    # פילטר רעננות
    if freshness_filter != "הכל" and 'תאריך פרסום המשרה' in df.columns:
        def filter_by_freshness(row):
            days = calculate_days_since_posted(row['תאריך פרסום המשרה'])
            if days is None:
                return True
            if freshness_filter == "עד 3 ימים":
                return days <= 3
            elif freshness_filter == "עד שבוע":
                return days <= 7
            elif freshness_filter == "עד חודש":
                return days <= 30
            return True
        
        filtered_df = filtered_df[filtered_df.apply(filter_by_freshness, axis=1)]
    
    # סטטיסטיקות עליונות
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_jobs = len(filtered_df)
        st.metric("📊 סה\"כ משרות", total_jobs)
    
    with col2:
        applied_jobs = len(filtered_df[filtered_df['שלחתי קורות חיים?'].str.contains('הגשתי|כן', na=False)])
        st.metric("✅ הגשתי", applied_jobs)
    
    with col3:
        if total_jobs > 0:
            application_rate = (applied_jobs / total_jobs) * 100
            st.metric("📈 שיעור הגשות", f"{application_rate:.1f}%")
        else:
            st.metric("📈 שיעור הגשות", "0%")
    
    with col4:
        fresh_jobs = len(filtered_df[filtered_df.apply(
            lambda row: calculate_days_since_posted(row.get('תאריך פרסום המשרה', '')) is not None 
            and calculate_days_since_posted(row.get('תאריך פרסום המשרה', '')) <= 3, axis=1
        )])
        st.metric("🔥 משרות חדשות", fresh_jobs)
    
    # גרפים
    col1, col2 = st.columns(2)
    
    with col1:
        if 'סוג החברה' in filtered_df.columns:
            st.subheader("📊 פילוח לפי תחום")
            industry_counts = filtered_df['סוג החברה'].value_counts()
            if not industry_counts.empty:
                fig_pie = px.pie(values=industry_counts.values, names=industry_counts.index,
                               title="פילוח משרות לפי תחום")
                st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        if 'תאריך' in filtered_df.columns:
            st.subheader("📈 משרות לאורך זמן")
            daily_counts = filtered_df.groupby(filtered_df['תאריך'].dt.date).size()
            if not daily_counts.empty:
                fig_line = px.line(x=daily_counts.index, y=daily_counts.values,
                                 title="מספר משרות חדשות ביום")
                st.plotly_chart(fig_line, use_container_width=True)
    
    # רשימת משרות עם אפשרות עדכון
    st.subheader("💼 רשימת משרות")
    
    # מיון
    sort_by = st.selectbox("מיין לפי:", ["תאריך", "שם החברה", "שם המשרה", "תאריך פרסום"])
    
    if sort_by == "תאריך" and 'תאריך' in filtered_df.columns:
        filtered_df = filtered_df.sort_values('תאריך', ascending=False)
    elif sort_by in filtered_df.columns:
        filtered_df = filtered_df.sort_values(sort_by)
    
    # הצגת משרות עם אפשרות עדכון
    for index, row in filtered_df.iterrows():
        with st.container():
            # קביעת צבע לפי סטטוס
            status = row.get('שלחתי קורות חיים?', '')
            if 'הגשתי' in status or 'כן' in status:
                card_class = "applied"
                status_class = "status-applied"
                status_text = "הגשתי ✅"
            elif 'נדחה' in status:
                card_class = "rejected"
                status_class = "status-rejected"
                status_text = "נדחה ❌"
            elif 'ראיון' in status:
                card_class = "interview"
                status_class = "status-interview"
                status_text = "ראיון 🎯"
            else:
                card_class = "not-applied"
                status_class = "status-not-applied"
                status_text = "לא הגשתי ⏳"
            
            # כרטיס משרה
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"""
                <div class="job-card {card_class}">
                    <h3>🎯 {row.get('שם המשרה', 'לא צוין')}</h3>
                    <p><strong>🏢 חברה:</strong> {row.get('שם החברה', 'לא צוין')}</p>
                    <p><strong>🏷️ תחום:</strong> {row.get('סוג החברה', 'לא צוין')}</p>
                    <p><strong>📍 מיקום:</strong> {row.get('מיקום המשרה', 'לא צוין')}</p>
                    <p><strong>📅 פורסם:</strong> {row.get('תאריך פרסום המשרה', 'לא נמצא')}</p>
                    <span class="status-badge {status_class}">{status_text}</span>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                # כפתור לפתיחת המשרה
                if row.get('לינק למשרה'):
                    if st.button(f"🔗 פתח משרה", key=f"open_{index}_{user_id}"):
                        st.markdown(f'<meta http-equiv="refresh" content="0; url={row["לינק למשרה"]}">', 
                                  unsafe_allow_html=True)
            
            with col3:
                # כפתור עדכון סטטוס
                if st.button(f"✏️ עדכן", key=f"update_{index}_{user_id}"):
                    st.session_state[f"show_update_{index}_{user_id}"] = True
            
            # טופס עדכון (אם נלחץ הכפתור)
            if st.session_state.get(f"show_update_{index}_{user_id}", False):
                with st.expander("עדכון פרטי המשרה", expanded=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_status = st.selectbox(
                            "סטטוס:",
                            ["לא הגשתי", "הגשתי", "ממתין לתשובה", "נדחה", "ראיון"],
                            key=f"status_{index}_{user_id}"
                        )
                        
                        cv_version = st.text_input(
                            "גרסת קו\"ח:",
                            value=row.get('גרסת קו"ח מתאימה', ''),
                            key=f"cv_{index}_{user_id}"
                        )
                    
                    with col2:
                        intro_email = st.text_area(
                            "טיוטת מייל מבוא:",
                            value=row.get('טיוטת introduction למייל', ''),
                            key=f"intro_{index}_{user_id}"
                        )
                        
                        rating = st.slider(
                            "ציון התאמה (1-5):",
                            1, 5,
                            value=int(row.get('ציון התאמה (1–5)', 3)) if row.get('ציון התאמה (1–5)') else 3,
                            key=f"rating_{index}_{user_id}"
                        )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 שמור", key=f"save_{index}_{user_id}"):
                            applied_date = datetime.now().strftime("%Y-%m-%d") if new_status == "הגשתי" else ""
                            
                            if update_job_status(user_info['spreadsheet_name'], user_info['sheet_name'], 
                                               index, new_status, cv_version, intro_email, applied_date, str(rating)):
                                st.success("נשמר בהצלחה!")
                                st.rerun()
                            else:
                                st.error("שגיאה בשמירה")
                    
                    with col2:
                        if st.button("❌ ביטול", key=f"cancel_{index}_{user_id}"):
                            st.session_state[f"show_update_{index}_{user_id}"] = False
                            st.rerun()
            
            # מפריד
            st.markdown("---")
    
    # סטטיסטיקות תחתונות
    st.subheader("📊 סטטיסטיקות מפורטות")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if 'ציון התאמה (1–5)' in filtered_df.columns:
            ratings = filtered_df['ציון התאמה (1–5)'].dropna()
            if len(ratings) > 0:
                avg_rating = ratings.astype(float).mean()
                st.metric("⭐ ציון התאמה ממוצע", f"{avg_rating:.1f}")
    
    with col2:
        if 'שם החברה' in filtered_df.columns:
            unique_companies = filtered_df['שם החברה'].nunique()
            st.metric("🏢 מספר חברות", unique_companies)

if __name__ == "__main__":
    main()
