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

# --- 1. הגדרות עמוד ועיצוב מתקדם (CSS) ---
st.set_page_config(
    page_title="SBB Construction ERP",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

# הזרקת CSS לעיצוב תפריט עליון (Navbar)
st.markdown("""
<style>
    /* ייבוא פונט Heebo */
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;700&display=swap');
    
    /* פונט גלובלי */
    html, body, p, h1, h2, h3, h4, h5, h6, span, div, button, input, select, textarea, label, .stTooltip {
        font-family: 'Heebo', sans-serif;
    }
    
    /* תיקון אייקונים */
    .material-symbols-rounded, .st-emotion-cache-1pb1bi, i {
        font-family: 'Material Symbols Rounded' !important;
    }

    /* רקע כללי */
    .stApp {
        background-color: #F8FAFC; /* אפור-כחלחל בהיר מאוד */
    }

    /* --- הסתרת אלמנטים מיותרים --- */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* --- עיצוב תפריט ניווט עליון (Tabs) --- */
    
    /* 1. מיכל התפריט */
    div[role="radiogroup"] {
        background-color: white;
        padding: 8px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #E2E8F0;
        display: flex;
        justify-content: center; /* מירכוז התפריט */
        gap: 10px;
        margin-bottom: 25px;
    }

    /* 2. העלמת העיגול (Radio Circle) - החלק הכי חשוב! */
    div[role="radiogroup"] > label > div:first-of-type {
        display: none !important;
    }

    /* 3. עיצוב כפתור רגיל (לא נבחר) */
    div[role="radiogroup"] label {
        background-color: transparent;
        border: none;
        padding: 10px 24px;
        border-radius: 8px;
        transition: all 0.3s;
        cursor: pointer;
        color: #64748B !important; /* אפור */
        font-weight: 500;
        font-size: 1rem;
        margin: 0 !important;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    /* 4. עיצוב כפתור בעת ריחוף */
    div[role="radiogroup"] label:hover {
        background-color: #F1F5F9;
        color: #0F172A !important;
    }

    /* 5. עיצוב כפתור נבחר (Active Tab) */
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #1E293B !important; /* כחול-שחור כהה */
        color: white !important;
        font-weight: 700;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* וידוא שהטקסט בתוך הכפתור הנבחר לבן */
    div[role="radiogroup"] label[data-checked="true"] p {
        color: white !important;
    }

    /* --- סרגל צד (Sidebar) - צמצום ועיצוב --- */
    section[data-testid="stSidebar"] {
        background-color: #111827;
        width: 250px !important;
    }

    /* --- כרטיסים וקונטיינרים --- */
    div[data-testid="stExpander"], div[data-testid="stForm"], .css-card {
        background-color: white;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        padding: 20px;
    }

    /* --- מטריקות --- */
    div[data-testid="stMetric"] {
        background-color: white;
        border-radius: 12px;
        padding: 15px;
        border: 1px solid #E2E8F0;
        border-right: 5px solid #3B82F6;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        direction: rtl; 
        text-align: right;
    }
    div[data-testid="stMetricLabel"] { font-size: 0.9rem; color: #64748B; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #0F172A; font-weight: 700; }

    /* --- כפתורים כלליים --- */
    .stButton > button {
        background-color: #0F172A;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1.2rem;
        font-weight: 500;
        transition: transform 0.1s;
    }
    .stButton > button:hover {
        background-color: #334155;
        transform: translateY(-1px);
    }

    /* כיוון טקסט */
    h1, h2, h3, p, div { direction: rtl; }
    
</style>
""", unsafe_allow_html=True)

# --- 2. חיבור ל-Supabase ---
SUPABASE_URL = "https://lffmftqundknfdnixncg.supabase.co"
SUPABASE_KEY = "sb_publishable_E7mEuBsARmEyoIi_8SgboQ_32DYIPB2"

@st.cache_resource
def init_connection():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        return None

supabase: Client = init_connection()

# --- 3. נתונים (Matrix) ---
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

# --- 4. פונקציות לוגיקה ---
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

# --- 5. יצירת PDF ---
def create_pdf(project_name, df):
    pdf = FPDF()
    pdf.add_page()
    
    font_path = "arial.ttf"
    has_font = os.path.exists(font_path)
    
    if has_font:
        pdf.add_font("MyArial", "", font_path, uni=True)
        pdf.set_font("MyArial", size=11)
    else:
        pdf.set_font("helvetica", size=11)

    # כותרת דוח
    pdf.set_fill_color(30, 41, 59) 
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 20, txt="SBB Project Report", ln=True, align='C', fill=True)
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    
    # שם פרויקט
    if has_font:
        display_name = project_name[::-1]
        pdf.cell(0, 10, txt=f"Project: {display_name}", ln=True, align='R')
    else:
        pdf.cell(0, 10, txt="Project Name (Font Missing)", ln=True, align='R')
    pdf.ln(5)

    # כותרות טבלה
    pdf.set_fill_color(241, 245, 249)
    h_act = "בפועל"[::-1] if has_font else "Actual"
    h_plan = "מתוכנן"[::-1] if has_font else "Planned"
    h_stg = "שלב"[::-1] if has_font else "Stage"
    
    pdf.set_font("MyArial", size=10) if has_font else None
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
                display_stage = s_name
                align_set = 'C'
            
            pdf.cell(70, 10, display_stage, border=1, ln=1, align=align_set)
        except:
            pdf.cell(70, 10, "-", border=1, ln=1, align='C')

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
        fmt = book.add_format({'bold': True, 'fg_color': '#111827', 'font_color': 'white', 'border': 1})
        for i, val in enumerate(df.columns):
            sheet.write(0, i, val, fmt)
    return out.getvalue()

# --- 6. ממשק משתמש (UI) ---

# --- סרגל צד (לוגו וסטטוס בלבד) ---
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <div style="font-size: 3rem; margin-bottom: 10px;">🏗️</div>
            <h3 style="color: white; margin:0;">SBB Pro</h3>
            <p style="color: #94A3B8; font-size: 0.8rem;">System V2.0</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    if supabase:
        st.markdown('<div style="background:#064E3B; color:#D1FAE5; padding:8px; border-radius:6px; text-align:center; font-size:0.8rem; border:1px solid #059669;">🟢 מערכת מחוברת</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:#7F1D1D; color:#FECACA; padding:8px; border-radius:6px; text-align:center; font-size:0.8rem; border:1px solid #DC2626;">🔴 אין תקשורת</div>', unsafe_allow_html=True)

# --- תפריט עליון ראשי (Horizontal Menu) ---
# שימוש ב-st.radio אופקי, ה-CSS למעלה מעלים את העיגולים והופך אותם לטאבים
menu_options = ["לוח בקרה", "פרויקט חדש", "ניתוח נתונים", "בקרת תקציב"]
selected_tab = st.radio("", menu_options, horizontal=True, label_visibility="collapsed")

# --- דף: לוח בקרה ---
if selected_tab == "לוח בקרה":
    st.markdown("### 📊 סקירה ניהולית")
    
    projects = get_all_projects()
    
    if not projects.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("פרויקטים פעילים", len(projects))
        c2.metric("שווי כולל", f"₪{projects['total_budget'].sum()/1000000:.1f}M")
        c3.metric("ממוצע למ\"ר", f"₪{projects['unit_cost'].mean():,.0f}")
        c4.metric("סה\"כ יח\"ד", int(projects['units'].sum()))
        
        st.markdown("#### רשימת פרויקטים")
        st.dataframe(
            projects, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "name": st.column_config.TextColumn("שם הפרויקט", width="medium"),
                "total_budget": st.column_config.NumberColumn("תקציב", format="₪%d"),
                "usage_type": "ייעוד",
                "build_method": "שיטה",
                "created_at": st.column_config.DateColumn("נוצר בתאריך", format="DD/MM/YYYY"),
                "id": None, "unit_cost": None, "units": None
            }
        )
    else:
        st.info("👋 המערכת ריקה. עבור ללשונית 'פרויקט חדש' כדי להתחיל.")

# --- דף: פרויקט חדש ---
elif selected_tab == "פרויקט חדש":
    st.markdown("### 🆕 הקמת פרויקט")
    
    c_form, c_info = st.columns([2, 1])
    
    with c_info:
        st.info("💡 **מחירון דקל (בסיס)**")
        for cat, methods in MATRIX.items():
            with st.expander(cat):
                for m, d in methods.items():
                    st.markdown(f"**{m}**: ₪{d['base']}")
                    st.caption(d['info'])

    with c_form:
        with st.form("new_proj_form"):
            st.markdown("#### 1. הגדרות מבנה")
            c1, c2 = st.columns(2)
            usage = c1.selectbox("ייעוד", list(MATRIX.keys()))
            method = None
            price = 0
            if usage:
                method = c2.selectbox("שיטת הבנייה", list(MATRIX[usage].keys()))
                price = MATRIX[usage][method]['base']
            
            st.markdown("#### 2. נתונים כספיים")
            name = st.text_input("שם הפרויקט")
            cc1, cc2 = st.columns(2)
            units = cc1.number_input("שטח (מ\"ר) / יחידות", value=100)
            cost = cc2.number_input("עלות למ\"ר (₪)", value=price)
            
            st.markdown("#### 3. חלוקת תקציב")
            cp1, cp2, cp3 = st.columns(3)
            p1 = cp1.number_input("תכנון", 0, 100, 15)
            p2 = cp2.number_input("ביצוע", 0, 100, 60)
            p3 = 100 - (p1 + p2)
            cp3.metric("יתרה", f"{p3}%")
            
            if st.form_submit_button("שמור פרויקט", type="primary"):
                if not name: st.error("חסר שם פרויקט")
                elif p3 < 0: st.error("שגיאה בחלוקת האחוזים")
                else:
                    total = units * cost
                    stages = pd.DataFrame({
                        "שלב": ["תכנון", "ביצוע", "מסירה"], "אחוז": [p1,p2,p3],
                        "עלות תכנון": [(p1/100)*total, (p2/100)*total, (p3/100)*total]
                    })
                    if save_project(name, units, cost, total, stages, usage, method):
                        st.balloons()
                        st.success("הפרויקט נשמר בהצלחה!")

# --- דף: ניתוח נתונים ---
elif selected_tab == "ניתוח נתונים":
    st.markdown("### 📈 דוחות וניתוחים")
    df = get_all_projects()
    if not df.empty:
        df['שם'] = df['name']
        df['תקציב'] = df['total_budget']
        df['סוג'] = df['usage_type']
        
        c1, c2 = st.columns([1.5, 1])
        with c1:
            st.markdown("#### תקציב לפי פרויקט")
            fig = px.bar(df, x='שם', y='תקציב', color='תקציב', text_auto='.2s', 
                         color_continuous_scale='Blues')
            fig.update_layout(plot_bgcolor="white", font=dict(family="Heebo"), xaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("#### פילוח סוגים")
            fig2 = px.pie(df, names='סוג', values='total_budget', hole=0.6,
                          color_discrete_sequence=px.colors.sequential.Teal)
            fig2.update_layout(font=dict(family="Heebo"), showlegend=False)
            fig2.update_traces(textinfo='label+percent')
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("אין נתונים להצגה.")

# --- דף: בקרת תקציב ---
elif selected_tab == "בקרת תקציב":
    st.markdown("### 📉 ניהול ביצוע תקציבי")
    projs = get_all_projects()
    if not projs.empty:
        sel = st.selectbox("בחר פרויקט", projs['name'].unique())
        pid = int(projs[projs['name']==sel].iloc[0]['id'])
        stages = get_project_stages(pid)
        
        if not stages.empty:
            tp, ta = stages['planned_cost'].sum(), stages['actual_cost'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("תקציב מאושר", f"₪{tp:,.0f}")
            c2.metric("נוצל בפועל", f"₪{ta:,.0f}")
            # לוגיקה לצבע החריגה
            delta_color = "off" if ta <= tp else "inverse"
            c3.metric("יתרה/חריגה", f"₪{tp-ta:,.0f}", delta_color=delta_color)
            
            st.markdown("---")
            
            ce, cg = st.columns([1, 1])
            
            with ce:
                st.markdown("#### הזנת ביצוע")
                edited = st.data_editor(
                    stages,
                    column_config={
                        "stage_name": st.column_config.TextColumn("שלב", disabled=True),
                        "planned_cost": st.column_config.NumberColumn("תקציב", format="₪%d", disabled=True),
                        "actual_cost": st.column_config.NumberColumn("בפועל", format="₪%d", required=True),
                        "id": None, "project_id": None, "planned_percent": None, "created_at": None
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor"
                )
                if st.button("💾 שמור ביצוע", type="primary"):
                    if update_stage_costs(pid, edited): 
                        st.toast("עודכן בהצלחה", icon="✅")
                        st.rerun()

            with cg:
                st.markdown("#### תמונת מצב")
                fig = go.Figure()
                fig.add_trace(go.Bar(name='תכנון', x=edited['stage_name'], y=edited['planned_cost'], marker_color='#E2E8F0'))
                fig.add_trace(go.Bar(name='ביצוע', x=edited['stage_name'], y=edited['actual_cost'], marker_color='#0F172A'))
                fig.update_layout(barmode='group', plot_bgcolor='white', font=dict(family="Heebo"), 
                                  legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.markdown("#### ייצוא")
            c_pdf, c_xls, _ = st.columns([1, 1, 3])
            safe_n = re.sub(r'[\\/*?:"<>|]', "", sel)
            
            with c_pdf:
                try:
                    pdf_bytes = create_pdf(sel, edited)
                    st.download_button("📄 PDF", pdf_bytes, f"{safe_n}.pdf", "application/pdf")
                except Exception as e: st.error(f"שגיאה: {e}")
            
            with c_xls:
                try:
                    xls_bytes = create_excel(edited)
                    st.download_button("📗 Excel", xls_bytes, f"{safe_n}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except: st.error("שגיאה")
