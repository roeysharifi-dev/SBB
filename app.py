import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client
from fpdf import FPDF
import io
import os
import re
import tempfile
import base64

# --- 1. הגדרות עמוד ועיצוב CSS קיצוני ---
st.set_page_config(
    page_title="SBB Pro Platform",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* ייבוא פונט Heebo - מראה הייטקי נקי */
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;700&display=swap');
    
    * {
        font-family: 'Heebo', sans-serif !important;
    }
    
    /* צבע רקע כללי */
    .stApp {
        background-color: #F8FAFC;
    }

    /* הסתרת אלמנטים מיותרים */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* --- עיצוב Sidebar (תפריט צד) --- */
    section[data-testid="stSidebar"] {
        background-color: #0F172A; /* כחול-שחור כהה */
        padding-top: 20px;
    }
    
    /* תיקון צבע טקסט בתפריט הצד - לבן בוהק */
    div[role="radiogroup"] p {
        color: #FFFFFF !important;
        font-size: 1.1rem;
        font-weight: 500;
        margin: 0;
    }
    
    /* עיצוב כפתורי התפריט */
    .stRadio > label { display: none; }
    div[role="radiogroup"] > label > div:first-of-type {
        display: none; /* הסתרת העיגול */
    }
    div[role="radiogroup"] {
        gap: 8px;
    }
    div[role="radiogroup"] label {
        background-color: transparent;
        padding: 12px 20px;
        border-radius: 8px;
        transition: all 0.3s;
        border: 1px solid transparent;
        margin-bottom: 5px;
        cursor: pointer;
    }
    div[role="radiogroup"] label:hover {
        background-color: #1E293B; /* צבע רקע בהובר */
        border-color: #334155;
    }
    
    /* פריט נבחר בתפריט */
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #3B82F6 !important; /* כחול בוהק */
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    div[role="radiogroup"] label[data-checked="true"] p {
        color: #FFFFFF !important;
        font-weight: 700;
    }

    /* --- עיצוב תוכן ראשי --- */
    
    /* Navbar עליון */
    .top-nav {
        background-color: white;
        padding: 15px 30px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #E2E8F0;
    }

    /* כרטיסים (Cards) */
    div[data-testid="stExpander"], div[data-testid="stForm"], .css-card {
        background-color: white;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        padding: 20px;
        margin-bottom: 20px;
    }

    /* מטריקות */
    div[data-testid="stMetric"] {
        background-color: white;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #E2E8F0;
        border-right: 5px solid #3B82F6;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02);
    }
    div[data-testid="stMetricLabel"] {
        color: #64748B;
        font-size: 0.9rem;
        direction: rtl;
        text-align: right;
    }
    div[data-testid="stMetricValue"] {
        color: #0F172A;
        font-weight: 700;
        font-size: 1.8rem;
        direction: rtl;
        text-align: right;
    }

    /* כפתורים */
    .stButton > button {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        color: white;
        border: none;
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 600;
        letter-spacing: 0.5px;
        transition: transform 0.2s;
        width: 100%;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }

    /* כותרות וטקסט כללי */
    h1, h2, h3 {
        color: #1E293B;
        direction: rtl;
        text-align: right;
    }
    .stMarkdown, p, div {
        direction: rtl;
    }
    
</style>
""", unsafe_allow_html=True)

# --- 2. Supabase Connection ---
SUPABASE_URL = "https://lffmftqundknfdnixncg.supabase.co"
SUPABASE_KEY = "sb_publishable_E7mEuBsARmEyoIi_8SgboQ_32DYIPB2"

@st.cache_resource
def init_connection():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        return None

supabase: Client = init_connection()

# --- 3. Data & Matrix ---
MATRIX = {
    "מגורים (בנייה רוויה)": {
        "בנייה קונבנציונלית": {"base": 5500, "info": "שיטה נפוצה, גמישות גבוהה."},
        "בנייה טרומית/מתועשת": {"base": 5800, "info": "מהירות ביצוע גבוהה."},
        "בנייה ירוקה": {"base": 6200, "info": "עלות גבוהה ב-10%, חסכון באנרגיה."},
        "בנייה קלה": {"base": 0, "info": "לא מתאים למגדלים."}
    },
    "מגורים (צמודי קרקע)": {
        "בנייה קונבנציונלית": {"base": 7000, "info": "סטנדרט שוק."},
        "בנייה קלה": {"base": 5500, "info": "מהיר מאוד, בידוד תרמי מעולה."},
        "בנייה ירוקה": {"base": 7700, "info": "עמידה בתקן 5281."},
        "בנייה טרומית/מתועשת": {"base": 7500, "info": "דורש שינוע אלמנטים."}
    },
    "מסחר ומשרדים": {
        "בנייה קונבנציונלית": {"base": 6500, "info": "שלד פלדה/בטון."},
        "בנייה טרומית/מתועשת": {"base": 6300, "info": "חיסכון בזמן."},
        "בנייה ירוקה": {"base": 7200, "info": "תקן LEED."},
        "בנייה קלה": {"base": 5000, "info": "חד-קומתי בלבד."}
    }
}

# --- 4. Logic Functions ---
def get_project_stages(project_id):
    if not supabase: return pd.DataFrame()
    try:
        res = supabase.table("project_stages").select("*").eq("project_id", int(project_id)).execute()
        df = pd.DataFrame(res.data)
        return df.sort_values('id') if not df.empty else df
    except: return pd.DataFrame()

def save_project(name, units, u_cost, total, stages_df, usage, method):
    if not supabase: return False
    try:
        proj = {"name": name, "units": int(units), "unit_cost": float(u_cost), 
                "total_budget": float(total), "usage_type": usage, "build_method": method}
        res = supabase.table("projects").insert(proj).execute()
        pid = res.data[0]['id']
        stages = []
        for _, r in stages_df.iterrows():
            stages.append({"project_id": pid, "stage_name": r['שלב'], 
                           "planned_percent": float(r['אחוז']), 
                           "planned_cost": float(r['עלות תכנון']), "actual_cost": 0})
        supabase.table("project_stages").insert(stages).execute()
        return True
    except: return False

def get_all_projects():
    if not supabase: return pd.DataFrame()
    try:
        res = supabase.table("projects").select("*").order("created_at", desc=True).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

def update_stage_costs(pid, df):
    if not supabase: return False
    try:
        for _, r in df.iterrows():
            supabase.table("project_stages").update({"actual_cost": float(r['actual_cost'])})\
                .eq("project_id", int(pid)).eq("stage_name", r['stage_name']).execute()
        return True
    except: return False

# --- 5. PDF Generation (FIXED) ---
def create_pdf(project_name, df):
    pdf = FPDF()
    pdf.add_page()
    
    font_path = "Arial.ttf"
    has_font = os.path.exists(font_path)
    
    if has_font:
        pdf.add_font("CustomArial", "", font_path, uni=True)
        pdf.set_font("CustomArial", size=12)
    else:
        pdf.set_font("helvetica", size=12)

    # כותרת
    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 20, txt="SBB Engineering Report", ln=True, align='C', fill=True)
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    
    # שם פרויקט
    if has_font:
        display_name = project_name[::-1]
        pdf.cell(0, 10, txt=f"Project: {display_name}", ln=True, align='R')
    else:
        pdf.cell(0, 10, txt="Project: (Hebrew font missing)", ln=True, align='R')
    pdf.ln(5)

    # כותרות טבלה
    pdf.set_fill_color(241, 245, 249)
    h_act = "בפועל"[::-1] if has_font else "Actual"
    h_plan = "מתוכנן"[::-1] if has_font else "Planned"
    h_stg = "שלב"[::-1] if has_font else "Stage"
    
    pdf.cell(60, 10, h_act, 1, 0, 'C', fill=True)
    pdf.cell(60, 10, h_plan, 1, 0, 'C', fill=True)
    pdf.cell(70, 10, h_stg, 1, 1, 'C', fill=True)

    # נתונים
    for _, row in df.iterrows():
        try:
            pdf.cell(60, 10, f"{row['actual_cost']:,.0f}", 1, 0, 'C')
            pdf.cell(60, 10, f"{row['planned_cost']:,.0f}", 1, 0, 'C')
            
            s_name = str(row['stage_name'])
            is_heb = any("\u0590" <= c <= "\u05EA" for c in s_name)
            
            if has_font and is_heb:
                display_stage = s_name[::-1]
                align_set = 'R'
            else:
                display_stage = s_name if has_font else "Stage Name"
                align_set = 'C'
            
            pdf.cell(70, 10, display_stage, border=1, ln=1, align=align_set)
        except:
            pdf.cell(70, 10, "Error", border=1, ln=1, align='C')

    # שמירה וקריאה בינארית לתיקון בעיות קידוד
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        pdf.output(tmp_file.name)
        tmp_file.close()
        with open(tmp_file.name, "rb") as f:
            pdf_bytes = f.read()
        os.unlink(tmp_file.name)
        return pdf_bytes

def create_excel(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as w:
        df.to_excel(w, index=False, sheet_name='Report')
        book = w.book
        sheet = w.sheets['Report']
        fmt = book.add_format({'bold': True, 'fg_color': '#0F172A', 'font_color': 'white', 'border': 1})
        for i, val in enumerate(df.columns):
            sheet.write(0, i, val, fmt)
    return out.getvalue()

# --- 6. ממשק UI ראשי ---

# Navbar
st.markdown("""
<div class="top-nav">
    <div style="display:flex; align-items:center; gap:10px;">
        <span style="font-size: 1.5rem;">🏗️</span>
        <span style="font-weight: 700; font-size: 1.2rem; color: #0F172A;">SBB Pro Platform</span>
    </div>
    <div style="color: #64748B; font-size: 0.9rem;">
        מחובר: <span style="color: #10B981; font-weight:bold;">Admin</span>
    </div>
</div>
""", unsafe_allow_html=True)

# סרגל צד
with st.sidebar:
    st.markdown("### תפריט ראשי")
    menu = st.radio(
        "", 
        ["לוח בקרה", "פרויקט חדש", "ניתוח נתונים", "בקרת תקציב"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### סטטוס מערכת")
    if supabase:
        st.success("שרת מחובר ותקין")
    else:
        st.error("אין תקשורת לשרת")

# ניתוב דפים
if menu == "לוח בקרה":
    st.markdown("## לוח בקרה ראשי")
    st.markdown("סקירה כללית של כל הפעילות בארגון")
    
    projects = get_all_projects()
    
    if not projects.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("פרויקטים פעילים", len(projects))
        c2.metric("שווי כולל", f"₪{projects['total_budget'].sum()/1000000:.1f}M")
        c3.metric("ממוצע למ\"ר", f"₪{projects['unit_cost'].mean():,.0f}")
        c4.metric("סה\"כ יח\"ד", int(projects['units'].sum()))
        
        st.markdown("### פרויקטים אחרונים")
        st.dataframe(
            projects, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "name": st.column_config.TextColumn("שם הפרויקט", width="medium"),
                "total_budget": st.column_config.NumberColumn("תקציב", format="₪%d"),
                "usage_type": "ייעוד",
                "build_method": "שיטה",
                "created_at": st.column_config.DateColumn("תאריך", format="DD/MM/YYYY"),
                "id": None, "unit_cost": None, "units": None
            }
        )
    else:
        st.info("אין נתונים להצגה. צור פרויקט חדש כדי להתחיל.")

elif menu == "פרויקט חדש":
    st.markdown("## יצירת פרויקט חדש")
    
    c_form, c_info = st.columns([2, 1])
    
    with c_info:
        st.info("💡 **טיפ:** המחירים נשאבים אוטומטית ממחירון דקל ומותאמים למדד תשומות הבנייה.")
        st.markdown("### מחירון בסיס")
        for cat, methods in MATRIX.items():
            with st.expander(cat):
                for m, d in methods.items():
                    st.markdown(f"**{m}:** ₪{d['base']}")
                    st.caption(d['info'])

    with c_form:
        with st.form("new_proj_form"):
            st.markdown("#### פרטי הקמה")
            c1, c2 = st.columns(2)
            usage = c1.selectbox("ייעוד המבנה", list(MATRIX.keys()))
            method = None
            price = 0
            if usage:
                method = c2.selectbox("שיטת בנייה", list(MATRIX[usage].keys()))
                price = MATRIX[usage][method]['base']
            
            st.markdown("---")
            name = st.text_input("שם הפרויקט")
            
            cc1, cc2 = st.columns(2)
            units = cc1.number_input("שטח במ\"ר / יח\"ד", value=100)
            cost = cc2.number_input("עלות למ\"ר (₪)", value=price)
            
            st.markdown("#### תקצוב (באחוזים)")
            cp1, cp2, cp3 = st.columns(3)
            p1 = cp1.number_input("תכנון", 0, 100, 15)
            p2 = cp2.number_input("ביצוע", 0, 100, 60)
            p3 = 100 - (p1 + p2)
            cp3.metric("יתרה למסירה", f"{p3}%")
            
            submit = st.form_submit_button("שמור והקם פרויקט")
            
            if submit:
                if not name: st.error("נא להזין שם")
                elif p3 < 0: st.error("חריגה מ-100%")
                else:
                    total = units * cost
                    stages = pd.DataFrame({
                        "שלב": ["תכנון", "ביצוע", "מסירה"], "אחוז": [p1,p2,p3],
                        "עלות תכנון": [(p1/100)*total, (p2/100)*total, (p3/100)*total]
                    })
                    if save_project(name, units, cost, total, stages, usage, method):
                        st.success("הפרויקט הוקם בהצלחה!"); st.balloons()

elif menu == "ניתוח נתונים":
    st.markdown("## ניתוח נתונים ודוחות")
    df = get_all_projects()
    if not df.empty:
        df['שם'] = df['name']
        df['תקציב'] = df['total_budget']
        df['סוג'] = df['usage_type']
        
        c1, c2 = st.columns([1.5, 1])
        with c1:
            st.markdown("### תקציב לפי פרויקט")
            # --- תיקון השגיאה בגרף כאן ---
            fig = px.bar(df, x='שם', y='תקציב', color='תקציב', text_auto='.2s', 
                         color_continuous_scale='Blues') # הוחלף מ-slate ל-Blues
            fig.update_layout(plot_bgcolor="white", font=dict(family="Heebo"), xaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("### פילוח לפי סוג")
            fig2 = px.pie(df, names='סוג', values='total_budget', hole=0.5,
                          color_discrete_sequence=px.colors.sequential.Blues_r)
            fig2.update_layout(font=dict(family="Heebo"))
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("אין מספיק נתונים לניתוח")

elif menu == "בקרת תקציב":
    st.markdown("## בקרת ביצוע תקציבי")
    projs = get_all_projects()
    if not projs.empty:
        sel = st.selectbox("בחר פרויקט לניהול", projs['name'].unique())
        pid = int(projs[projs['name']==sel].iloc[0]['id'])
        stages = get_project_stages(pid)
        
        if not stages.empty:
            tp, ta = stages['planned_cost'].sum(), stages['actual_cost'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("תקציב מתוכנן", f"₪{tp:,.0f}")
            c2.metric("ביצוע בפועל", f"₪{ta:,.0f}")
            c3.metric("חריגה / יתרה", f"₪{tp-ta:,.0f}", delta_color="normal")
            
            st.markdown("###")
            
            ce, cg = st.columns([1, 1])
            
            with ce:
                st.markdown("#### טבלת ביצוע")
                edited = st.data_editor(
                    stages,
                    column_config={
                        "stage_name": st.column_config.TextColumn("שלב", disabled=True),
                        "planned_cost": st.column_config.NumberColumn("מתוכנן", format="₪%d", disabled=True),
                        "actual_cost": st.column_config.NumberColumn("בפועל", format="₪%d", required=True),
                        "id": None, "project_id": None, "planned_percent": None, "created_at": None
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor"
                )
                if st.button("💾 שמור נתוני ביצוע"):
                    if update_stage_costs(pid, edited): st.toast("הנתונים נשמרו בהצלחה", icon="✅"); st.rerun()

            with cg:
                st.markdown("#### ויזואליזציה")
                fig = go.Figure()
                fig.add_trace(go.Bar(name='תכנון', x=edited['stage_name'], y=edited['planned_cost'], marker_color='#CBD5E1'))
                fig.add_trace(go.Bar(name='ביצוע', x=edited['stage_name'], y=edited['actual_cost'], marker_color='#0F172A'))
                fig.update_layout(barmode='group', plot_bgcolor='white', font=dict(family="Heebo"), 
                                  legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.markdown("#### ייצוא נתונים")
            c_pdf, c_xls, _ = st.columns([1, 1, 3])
            safe_n = re.sub(r'[\\/*?:"<>|]', "", sel)
            
            with c_pdf:
                try:
                    pdf_bytes = create_pdf(sel, edited)
                    st.download_button("📄 הורד דוח PDF", pdf_bytes, f"{safe_n}.pdf", "application/pdf")
                except Exception as e: st.error(f"שגיאה ביצירת PDF: {e}")
            
            with c_xls:
                try:
                    xls_bytes = create_excel(edited)
                    st.download_button("📗 הורד אקסל", xls_bytes, f"{safe_n}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except: st.error("שגיאה באקסל")
