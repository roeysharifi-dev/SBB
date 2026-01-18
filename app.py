import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client
from fpdf import FPDF
import io
import os
import re
import tempfile # נועד לפתרון בעיית ה-PDF

# --- 1. הגדרות עמוד ועיצוב מתקדם ---
st.set_page_config(
    page_title="SBB Pro",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

# CSS לניקוי ממשק ויישור לימין
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;700&display=swap');
    
    * { font-family: 'Heebo', sans-serif !important; }
    
    .stApp { background-color: #F8FAFC; direction: rtl; }
    
    /* יישור לימין של כל הטקסטים */
    .stMarkdown, .stSelectbox, .stInput, .stNumberInput, p, div {
        direction: rtl; text-align: right;
    }
    
    /* הסתרת אלמנטים של סטרימליט */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* עיצוב כרטיסים נקי */
    div[data-testid="stExpander"], div[data-testid="stForm"] {
        background-color: white;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #E2E8F0;
    }

    /* עיצוב כפתורים */
    .stButton > button {
        background-color: #0F172A;
        color: white;
        border-radius: 6px;
        padding: 10px 20px;
        font-weight: 500;
        width: 100%;
        border: none;
    }
    .stButton > button:hover {
        background-color: #334155;
    }

    /* מטריקות */
    div[data-testid="stMetric"] {
        background-color: white;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: right;
        direction: rtl;
    }
    div[data-testid="stMetricLabel"] { text-align: right; width: 100%; }
    div[data-testid="stMetricValue"] { text-align: right; width: 100%; color: #0F172A; }
</style>
""", unsafe_allow_html=True)

# --- 2. הגדרות Supabase ---
SUPABASE_URL = "https://lffmftqundknfdnixncg.supabase.co"
SUPABASE_KEY = "sb_publishable_E7mEuBsARmEyoIi_8SgboQ_32DYIPB2"

@st.cache_resource
def init_connection():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        return None

supabase: Client = init_connection()

# --- 3. נתונים ---
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

# --- פונקציות ---
def get_project_stages(project_id):
    if not supabase: return pd.DataFrame()
    res = supabase.table("project_stages").select("*").eq("project_id", int(project_id)).execute()
    df = pd.DataFrame(res.data)
    return df.sort_values('id') if not df.empty else df

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

# --- תיקון PDF קריטי ---
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
    pdf.cell(0, 15, txt="SBB Engineering Report", ln=True, align='C', fill=True)
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    
    # שם פרויקט
    d_name = project_name[::-1] if has_font else "Project Name"
    pdf.cell(0, 10, txt=f"Project: {d_name}", ln=True, align='R')
    pdf.ln(5)

    # טבלה
    pdf.set_fill_color(241, 245, 249)
    h_act = "בפועל"[::-1] if has_font else "Actual"
    h_plan = "מתוכנן"[::-1] if has_font else "Planned"
    h_stg = "שלב"[::-1] if has_font else "Stage"
    
    pdf.cell(60, 10, h_act, 1, 0, 'C', fill=True)
    pdf.cell(60, 10, h_plan, 1, 0, 'C', fill=True)
    pdf.cell(70, 10, h_stg, 1, 1, 'C', fill=True)

    for _, row in df.iterrows():
        pdf.cell(60, 10, f"{row['actual_cost']:,.0f}", 1, 0, 'C')
        pdf.cell(60, 10, f"{row['planned_cost']:,.0f}", 1, 0, 'C')
        
        s_name = str(row['stage_name'])
        is_heb = any("\u0590" <= c <= "\u05EA" for c in s_name)
        d_stg = s_name[::-1] if (has_font and is_heb) else s_name
        align = 'R' if (has_font and is_heb) else 'C'
        
        pdf.cell(70, 10, d_stg, border=1, ln=1, align=align)

    # *** הפתרון לבעיית הקידוד ***
    # במקום להחזיר מחרוזת ולעשות encode, אנחנו שומרים לקובץ זמני וקוראים את ה-Bytes
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.close() # סגירת הקובץ כדי שנוכל לקרוא אותו
        with open(tmp.name, "rb") as f:
            pdf_bytes = f.read()
        os.unlink(tmp.name) # מחיקת הקובץ הזמני
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

# --- ממשק ---
st.sidebar.title("🏗️ SBB Pro")
menu = st.sidebar.radio("תפריט ראשי", ["מסך הבית", "פרויקט חדש", "דאשבורד", "בקרת תקציב"])
st.sidebar.markdown("---")
if supabase: st.sidebar.success("מחובר ✅")
else: st.sidebar.error("מנותק ❌")

# --- דפים ---
if menu == "מסך הבית":
    st.title("מערכת ניהול תקציב")
    st.markdown("ברוכים הבאים ל-SBB Pro. בחר פעולה מהתפריט בצד.")
    
    projects = get_all_projects()
    if not projects.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("סה״כ פרויקטים", len(projects))
        c2.metric("שווי תיק", f"₪{projects['total_budget'].sum()/1000000:.1f}M")
        c3.metric("ממוצע למ\"ר", f"₪{projects['unit_cost'].mean():,.0f}")

    st.subheader("מחירון בסיס")
    m_data = []
    for cat, methods in MATRIX.items():
        for meth, det in methods.items():
            m_data.append({"סוג": cat, "שיטה": meth, "מחיר": det['base'], "הערות": det['info']})
    st.dataframe(pd.DataFrame(m_data), use_container_width=True, hide_index=True)

elif menu == "פרויקט חדש":
    st.header("הקמת פרויקט חדש")
    with st.expander("הגדרות בסיס", expanded=True):
        c1, c2 = st.columns(2)
        usage = c1.selectbox("ייעוד", list(MATRIX.keys()))
        method = c2.selectbox("שיטה", list(MATRIX[usage].keys())) if usage else None
        if method: st.info(MATRIX[usage][method]['info'])

    if usage and method:
        with st.form("new_proj"):
            c_name, c_unit, c_pr = st.columns([2,1,1])
            name = c_name.text_input("שם הפרויקט")
            units = c_unit.number_input("שטח/יחידות", 1, value=100)
            cost = c_pr.number_input("מחיר למ\"ר", value=MATRIX[usage][method]['base'])
            
            st.markdown("---")
            st.markdown("**חלוקת תקציב (באחוזים)**")
            cp1, cp2, cp3 = st.columns(3)
            p1 = cp1.number_input("תכנון ורישוי", 0, 100, 15)
            p2 = cp2.number_input("ביצוע", 0, 100, min(75, 100-p1))
            p3 = 100 - (p1+p2)
            cp3.metric("יתרה למסירה", f"{p3}%")
            
            if st.form_submit_button("שמור פרויקט"):
                if not name: st.error("חסר שם")
                elif p3 < 0: st.error("חריגה מאחוזים")
                else:
                    tot = units * cost
                    stages = pd.DataFrame({
                        "שלב": ["תכנון", "ביצוע", "מסירה"], "אחוז": [p1,p2,p3],
                        "עלות תכנון": [(p1/100)*tot, (p2/100)*tot, (p3/100)*tot]
                    })
                    if save_project(name, units, cost, tot, stages, usage, method):
                        st.success("נוצר בהצלחה!"); st.balloons()

elif menu == "דאשבורד":
    st.header("דאשבורד ניהולי")
    df = get_all_projects()
    if not df.empty:
        # התאמת שמות עמודות לעברית לגרפים
        df['שם פרויקט'] = df['name']
        df['תקציב'] = df['total_budget']
        df['ייעוד'] = df['usage_type']

        c1, c2 = st.columns([2,1])
        with c1:
            fig = px.bar(df, x='שם פרויקט', y='תקציב', text_auto='.2s', color='תקציב',
                         labels={'שם פרויקט': 'שם הפרויקט', 'תקציב': 'תקציב (₪)'})
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig2 = px.pie(df, names='ייעוד', values='id', title='פילוח לפי ייעוד')
            fig2.update_traces(textinfo='percent+label')
            st.plotly_chart(fig2, use_container_width=True)
            
        st.subheader("טבלת פרויקטים")
        # הצגה נקייה בלי אנגלית
        st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "name": "שם הפרויקט",
                "total_budget": st.column_config.NumberColumn("תקציב כולל", format="₪%d"),
                "unit_cost": st.column_config.NumberColumn("עלות למ\"ר", format="₪%d"),
                "units": "שטח/יח׳",
                "usage_type": "ייעוד",
                "build_method": "שיטה",
                "created_at": st.column_config.DatetimeColumn("תאריך הקמה", format="DD/MM/YYYY"),
                # הסתרת עמודות טכניות
                "id": None, "שם פרויקט": None, "תקציב": None, "ייעוד": None
            }
        )
    else: st.info("אין נתונים")

elif menu == "בקרת תקציב":
    st.header("בקרת תקציב")
    projs = get_all_projects()
    if not projs.empty:
        sel = st.selectbox("בחר פרויקט", projs['name'].unique())
        pid = int(projs[projs['name']==sel].iloc[0]['id'])
        stages = get_project_stages(pid)
        
        if not stages.empty:
            st.markdown("---")
            # מטריקות
            tp, ta = stages['planned_cost'].sum(), stages['actual_cost'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("מתוכנן", f"₪{tp:,.0f}")
            c2.metric("בפועל", f"₪{ta:,.0f}")
            c3.metric("יתרה", f"₪{tp-ta:,.0f}")
            
            # עריכה וגרף
            ce, cg = st.columns(2)
            with ce:
                st.subheader("עדכון עלויות")
                edited = st.data_editor(
                    stages,
                    column_config={
                        "stage_name": st.column_config.TextColumn("שם השלב", disabled=True),
                        "planned_cost": st.column_config.NumberColumn("תקציב מתוכנן", format="₪%d", disabled=True),
                        "actual_cost": st.column_config.NumberColumn("ביצוע בפועל", format="₪%d", required=True),
                        # הסתרת טכני
                        "id": None, "project_id": None, "planned_percent": None, "created_at": None
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor"
                )
                if st.button("שמור שינויים"):
                    if update_stage_costs(pid, edited): st.success("נשמר!"); st.rerun()
            
            with cg:
                st.subheader("סטטוס")
                fig = go.Figure()
                fig.add_trace(go.Bar(name='תכנון', x=edited['stage_name'], y=edited['planned_cost'], marker_color='#94A3B8'))
                fig.add_trace(go.Bar(name='ביצוע', x=edited['stage_name'], y=edited['actual_cost'], marker_color='#0F172A'))
                fig.update_layout(barmode='group', legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)

            # ייצוא
            st.markdown("---")
            c_pdf, c_xls = st.columns([1,4])
            safe_n = re.sub(r'[\\/*?:"<>|]', "", sel)
            
            with c_pdf:
                try:
                    pdf_b = create_pdf(sel, edited)
                    st.download_button("📄 PDF", pdf_b, f"{safe_n}.pdf", "application/pdf")
                except Exception as e: st.error(f"שגיאה: {e}")
            with c_xls:
                try:
                    xls_b = create_excel(edited)
                    st.download_button("📗 Excel", xls_b, f"{safe_n}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except: st.error("שגיאה")
    else: st.info("אין פרויקטים")
