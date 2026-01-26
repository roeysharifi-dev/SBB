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

# --- 1. הגדרות עמוד ---
st.set_page_config(
    page_title="SBB Construction ERP",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="collapsed"
)

# --- 2. עיצוב CSS מתקדם ו-RTL ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;700&display=swap');
    
    html, body, .stApp, [class*="css"] {
        font-family: 'Rubik', sans-serif !important;
        direction: rtl !important;
        text-align: right !important;
    }
    
    [data-testid="column"] { display: flex; flex-direction: column; align-items: flex-start; }
    .stApp { background-color: #f1f5f9; }
    section[data-testid="stSidebar"], #MainMenu, footer, header { display: none; }

    /* Header */
    .top-header-container {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 16px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
        display: flex; justify-content: space-between; align-items: center;
    }
    .header-title { font-size: 1.8rem; font-weight: 700; color: #ffffff; }
    .header-subtitle { color: #94a3b8; font-size: 0.9rem; }

    /* Navigation Tabs */
    div[role="radiogroup"] {
        background: rgba(255, 255, 255, 0.1); padding: 5px; border-radius: 12px;
        display: inline-flex; flex-direction: row-reverse;
    }
    div[role="radiogroup"] > label > div:first-of-type { display: none !important; }
    div[role="radiogroup"] label {
        background: transparent; border: none; color: #cbd5e1 !important;
        padding: 8px 24px; border-radius: 8px; font-weight: 500; margin: 0 !important;
        transition: all 0.3s ease;
    }
    div[role="radiogroup"] label:hover { background: rgba(255,255,255,0.05); color: white !important; }
    div[role="radiogroup"] label[data-checked="true"] {
        background: #f59e0b !important; color: white !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    div[role="radiogroup"] label[data-checked="true"] p { color: white !important; }

    /* General UI Elements */
    div[data-testid="stMetric"] {
        background: white; border-radius: 12px; padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border-right: 5px solid #3b82f6;
    }
    .stButton > button {
        background-color: #2563eb; color: white; border-radius: 8px; border: none;
        padding: 0.6rem 1.2rem; transition: all 0.2s; width: 100%;
    }
    .stButton > button:hover { background-color: #1d4ed8; transform: translateY(-1px); }
    div[data-testid="stForm"] { background: white; padding: 2rem; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    
    /* Custom Card for Optimization */
    .css-card {
        background-color: white; border-radius: 12px; padding: 20px;
        border: 1px solid #e2e8f0; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }

    /* Status Badges */
    .status-badge { padding: 6px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; }
    .status-ok { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .status-err { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
    .status-warn { background: rgba(245, 158, 11, 0.2); color: #b45309; border: 1px solid rgba(245, 158, 11, 0.3); }
</style>
""", unsafe_allow_html=True)

# --- 3. חיבור ל-Supabase ---
SUPABASE_URL = "https://lffmftqundknfdnixncg.supabase.co"
SUPABASE_KEY = "sb_publishable_E7mEuBsARmEyoIi_8SgboQ_32DYIPB2"

@st.cache_resource
def init_connection():
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except: return None

supabase: Client = init_connection()

# --- 4. נתונים (Matrix) ---
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

# --- 5. לוגיקה ואלגוריתמים ---

# פונקציית DP לאופטימיזציה כללית או חילוץ פרויקט
def optimize_construction_plan(budget_limit, stages_to_optimize=None):
    """
    מבצע אופטימיזציה באמצעות תכנון דינאמי.
    אם stages_to_optimize לא מסופק, משתמש בכל השלבים (לפרויקט חדש).
    אם מסופק, מבצע אופטימיזציה רק לשלבים שנותרו (לחילוץ פרויקט).
    """
    
    # מאגר האפשרויות הגנרי
    all_stages_data = {
        "שלד ומבנה": [
            {"name": "בטון רגיל (B30)", "cost": 1500000, "score": 60, "desc": "סטנדרט בסיסי"},
            {"name": "פלדה מתועשת", "cost": 2200000, "score": 85, "desc": "מהיר ומדויק"},
            {"name": "בנייה ירוקה מתקדמת", "cost": 2800000, "score": 95, "desc": "בידוד תרמי מקסימלי"}
        ],
        "גמרים ועיצוב": [
            {"name": "סטנדרט קבלן", "cost": 800000, "score": 50, "desc": "ריצוף 60x60"},
            {"name": "משופר", "cost": 1200000, "score": 75, "desc": "ריצוף 80x80 + דלתות פנים"},
            {"name": "פרימיום", "cost": 1800000, "score": 100, "desc": "שיש טבעי + פרקט עץ"}
        ],
        "מערכות (חשמל/אינסטלציה)": [
            {"name": "בסיסי", "cost": 400000, "score": 40, "desc": "עמידה בתקן מינימלי"},
            {"name": "בית חכם בסיסי", "cost": 700000, "score": 70, "desc": "שליטה בתריסים ודוד"},
            {"name": "מערכות מלאות", "cost": 1100000, "score": 90, "desc": "VRF + Smart Home"}
        ]
    }

    # אם קיבלנו רשימת שלבים ספציפית (למשל רק גמרים ומערכות), נסנן את המילון
    if stages_to_optimize:
        current_stages_data = {k: v for k, v in all_stages_data.items() if k in stages_to_optimize}
    else:
        current_stages_data = all_stages_data

    stage_names = list(current_stages_data.keys())
    memo = {}

    def dp_solve(idx, remaining_budget):
        if remaining_budget < 0: return -1, [], 0
        if idx == len(stage_names): return 0, [], 0
        
        state = (idx, remaining_budget)
        if state in memo: return memo[state]

        best_score = -1
        best_path = []
        best_cost = 0

        for option in current_stages_data[stage_names[idx]]:
            if option["cost"] <= remaining_budget:
                future_score, future_path, future_cost = dp_solve(idx + 1, remaining_budget - option["cost"])
                if future_score != -1:
                    current_total_score = option["score"] + future_score
                    if current_total_score > best_score:
                        best_score = current_total_score
                        best_path = [option] + future_path
                        best_cost = option["cost"] + future_cost

        memo[state] = (best_score, best_path, best_cost)
        return best_score, best_path, best_cost

    max_score, path, total_cost = dp_solve(0, budget_limit)
    return max_score, path, total_cost, all_stages_data

# פונקציות עזר (DB, PDF, Excel) - ללא שינוי
def get_project_stages(project_id):
    if not supabase: return pd.DataFrame()
    try:
        res = supabase.table("project_stages").select("*").eq("project_id", int(project_id)).execute()
        return pd.DataFrame(res.data).sort_values('id') if res.data else pd.DataFrame()
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

def create_pdf(project_name, df):
    pdf = FPDF(); pdf.add_page()
    font_path = "arial.ttf"
    has_font = os.path.exists(font_path)
    if has_font: pdf.add_font("MyArial", "", font_path, uni=True); pdf.set_font("MyArial", size=11)
    else: pdf.set_font("helvetica", size=11)
    
    pdf.set_fill_color(30, 41, 59); pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 20, txt="SBB Project Report", ln=True, align='C', fill=True); pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    
    display_name = project_name[::-1] if has_font else "Project Name"
    pdf.cell(0, 10, txt=f"Project: {display_name}", ln=True, align='R'); pdf.ln(5)

    pdf.set_fill_color(241, 245, 249)
    headers = ["Actual", "Planned", "Stage"]
    if has_font: headers = ["בפועל"[::-1], "מתוכנן"[::-1], "שלב"[::-1]]
    
    for h in headers: pdf.cell(63, 10, h, 1, 0, 'C', fill=True)
    pdf.ln()

    for _, row in df.iterrows():
        pdf.cell(63, 10, f"{row['actual_cost']:,.0f}", 1, 0, 'C')
        pdf.cell(63, 10, f"{row['planned_cost']:,.0f}", 1, 0, 'C')
        txt = str(row['stage_name'])[::-1] if has_font else str(row['stage_name'])
        pdf.cell(63, 10, txt, 1, 1, 'C' if not has_font else 'R')
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name); return open(tmp.name, "rb").read()

def create_excel(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as w:
        df.to_excel(w, index=False, sheet_name='Report')
    return out.getvalue()

# --- 6. ממשק משתמש (UI) ---

st.markdown("""
<div class="top-header-container">
    <div style="display: flex; align-items: center; gap: 15px;">
        <span style="font-size: 2.5rem; background: rgba(255,255,255,0.1); padding: 10px; border-radius: 12px;">🏗️</span>
        <div>
            <div class="header-title">SBB Construction</div>
            <div class="header-subtitle">מערכת ניהול תקציב ופרויקטים מתקדמת</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if supabase:
    st.markdown('<div style="margin-top: -80px; margin-bottom: 50px; float: left; position: relative; z-index: 999;"><span class="status-badge status-ok">🟢 מחובר לשרת</span></div>', unsafe_allow_html=True)
else:
    st.markdown('<div style="margin-top: -80px; margin-bottom: 50px; float: left; position: relative; z-index: 999;"><span class="status-badge status-err">🔴 אין תקשורת</span></div>', unsafe_allow_html=True)

menu_options = ["לוח בקרה", "פרויקט חדש", "ניתוח נתונים", "בקרת תקציב", "אופטימיזציה"]
selected_tab = st.radio("", menu_options, horizontal=True, label_visibility="collapsed")
st.markdown("<br>", unsafe_allow_html=True)

# --- תוכן הלשוניות ---

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
        st.dataframe(projects, use_container_width=True, hide_index=True,
                     column_config={"name": "שם הפרויקט", "total_budget": st.column_config.NumberColumn("תקציב", format="₪%d")})
    else: st.info("המערכת ריקה.")

elif selected_tab == "פרויקט חדש":
    st.markdown("### 🆕 הקמת פרויקט חדש")
    c_form, c_info = st.columns([2, 1])
    with c_info:
        st.info("💡 **מחירון בסיס**")
        for cat, methods in MATRIX.items():
            with st.expander(cat):
                for m, d in methods.items(): st.markdown(f"**{m}**: ₪{d['base']}")
    with c_form:
        with st.form("new_proj"):
            usage = st.selectbox("ייעוד", list(MATRIX.keys()))
            method = st.selectbox("שיטה", list(MATRIX[usage].keys())) if usage else None
            price = MATRIX[usage][method]['base'] if method else 0
            name = st.text_input("שם הפרויקט")
            units = st.number_input("שטח/יחידות", value=100)
            cost = st.number_input("עלות למ\"ר", value=price)
            p1 = st.number_input("תכנון (%)", 0, 100, 15)
            p2 = st.number_input("ביצוע (%)", 0, 100, 60)
            if st.form_submit_button("שמור", type="primary"):
                total = units * cost
                stages = pd.DataFrame({"שלב": ["תכנון", "ביצוע", "מסירה"], "אחוז": [p1,p2,100-(p1+p2)], 
                                       "עלות תכנון": [(p1/100)*total, (p2/100)*total, ((100-(p1+p2))/100)*total]})
                if save_project(name, units, cost, total, stages, usage, method): st.success("נשמר!")

elif selected_tab == "ניתוח נתונים":
    st.markdown("### 📈 דוחות")
    df = get_all_projects()
    if not df.empty:
        c1, c2 = st.columns([1.5, 1])
        with c1: st.plotly_chart(px.bar(df, x='name', y='total_budget', color='total_budget', template="plotly_white"), use_container_width=True)
        with c2: st.plotly_chart(px.pie(df, names='usage_type', values='total_budget'), use_container_width=True)

elif selected_tab == "בקרת תקציב":
    st.markdown("### 📉 ניהול ביצוע ובקרה")
    projs = get_all_projects()
    if not projs.empty:
        sel = st.selectbox("בחר פרויקט לניהול", projs['name'].unique())
        selected_proj_row = projs[projs['name']==sel].iloc[0]
        pid = int(selected_proj_row['id'])
        total_budget_approved = float(selected_proj_row['total_budget'])
        
        stages = get_project_stages(pid)
        
        if not stages.empty:
            spent_so_far = stages['actual_cost'].sum()
            
            # חישוב התקציב שנותר בקופה
            remaining_money = total_budget_approved - spent_so_far
            
            c1, c2, c3 = st.columns(3)
            c1.metric("תקציב פרויקט כולל", f"₪{total_budget_approved:,.0f}")
            c2.metric("בוצע (נוצל בפועל)", f"₪{spent_so_far:,.0f}")
            
            # בדיקת יתרה צפויה בסיום (על בסיס תכנון של מה שנשאר)
            future_stages = stages[stages['actual_cost'] == 0]
            cost_to_complete = future_stages['planned_cost'].sum()
            projected_balance = remaining_money - cost_to_complete
            
            delta_color = "normal" if projected_balance >= 0 else "inverse"
            c3.metric("יתרה צפויה בסיום", f"₪{projected_balance:,.0f}", delta_color=delta_color)
            
            # === אזור חילוץ פרויקט (DP) ===
            if projected_balance < 0:
                st.markdown("""
                <div style="background-color: #fef2f2; border: 1px solid #fee2e2; padding: 15px; border-radius: 10px; margin: 20px 0;">
                    <h4 style="color: #991b1b; margin:0;">⚠️ התראת חריגה: הפרויקט צפוי לחרוג מהתקציב!</h4>
                    <p style="color: #7f1d1d;">ישנה חריגה צפויה של <b>₪{:,}</b>. מומלץ להפעיל תכנון מחדש.</p>
                </div>
                """.format(abs(int(projected_balance))), unsafe_allow_html=True)
                
                if st.button("🤖 הפעל חילוץ פרויקט (DP Optimization)", key="rescue_btn"):
                    # מיפוי פשוט לשם הדגמה
                    stages_to_fix = ["גמרים ועיצוב", "מערכות (חשמל/אינסטלציה)"]
                    best_score, best_path, best_cost, _ = optimize_construction_plan(remaining_money, stages_to_fix)
                    
                    if best_score > 0:
                        st.success(f"נמצא פתרון! ניתן לסיים את הפרויקט בעלות של ₪{best_cost:,.0f} (בתוך היתרה: ₪{remaining_money:,.0f})")
                        st.markdown("**התוכנית המוצעת להמשך:**")
                        for item in best_path:
                             st.info(f"🔹 **{item['name']}** - עלות: ₪{item['cost']:,.0f}")
                    else:
                        st.error("המצב קריטי - גם בבחירת המפרט הזול ביותר לא ניתן לסיים בתקציב הקיים.")

            st.markdown("---")
            
            ce, cg = st.columns([1, 1])
            with ce:
                st.markdown("#### עדכון ביצוע")
                edited = st.data_editor(stages, column_config={
                        "stage_name": st.column_config.TextColumn("שלב", disabled=True),
                        "planned_cost": st.column_config.NumberColumn("תקציב", format="₪%d", disabled=True),
                        "actual_cost": st.column_config.NumberColumn("בפועל", format="₪%d", required=True),
                        "id": None, "project_id": None, "planned_percent": None, "created_at": None
                    }, hide_index=True, use_container_width=True, key="editor")
                if st.button("💾 שמור נתונים", type="primary"):
                    if update_stage_costs(pid, edited): st.rerun()

            with cg:
                fig = go.Figure()
                fig.add_trace(go.Bar(name='תכנון', x=edited['stage_name'], y=edited['planned_cost'], marker_color='#cbd5e1'))
                fig.add_trace(go.Bar(name='ביצוע', x=edited['stage_name'], y=edited['actual_cost'], marker_color='#0f172a'))
                fig.update_layout(barmode='group', plot_bgcolor='white', font=dict(family="Rubik"), legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)

            # === ייצוא (חזר למקום!) ===
            st.markdown("---")
            st.markdown("#### ייצוא דוחות")
            c_pdf, c_xls, _ = st.columns([1, 1, 3])
            safe_n = re.sub(r'[\\/*?:"<>|]', "", sel)
            
            with c_pdf:
                try:
                    pdf_bytes = create_pdf(sel, edited)
                    st.download_button("📄 הורד PDF", pdf_bytes, f"{safe_n}.pdf", "application/pdf")
                except Exception as e: st.error(f"שגיאה: {e}")
            
            with c_xls:
                try:
                    xls_bytes = create_excel(edited)
                    st.download_button("📗 הורד Excel", xls_bytes, f"{safe_n}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except: st.error("שגיאה")

# --- לשונית אופטימיזציה (חזרה למצב מלא) ---
elif selected_tab == "אופטימיזציה":
    st.markdown("### 🧠 אשף תכנון אופטימלי (DP)")
    
    st.markdown("""
    כלי זה משתמש ב**תכנון דינאמי** כדי למצוא את המפרט הטוב ביותר לפרויקט,
    תוך התחשבות באילוצי תקציב ומקסום ציון האיכות המשוקלל.
    """)
    
    col_input, col_res = st.columns([1, 2])
    
    with col_input:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.markdown("#### הגדרות אופטימיזציה")
        user_budget = st.number_input("תקציב מקסימלי (₪)", min_value=1000000, max_value=20000000, value=4000000, step=100000)
        
        if st.button("🚀 הרץ אופטימיזציה", type="primary"):
            best_score, best_path, best_cost, raw_data = optimize_construction_plan(user_budget)
            
            st.session_state['opt_result'] = {
                'score': best_score,
                'path': best_path,
                'cost': best_cost
            }
        st.markdown('</div>', unsafe_allow_html=True)
        
        # הצגת האפשרויות הקיימות (מקרא)
        with st.expander("📚 צפה במפרט האפשרויות המלא"):
            _, _, _, stages_data_raw = optimize_construction_plan(0) # רק כדי לשלוף את המילון
            for cat, opts in stages_data_raw.items():
                st.markdown(f"**{cat}**")
                for o in opts:
                    st.caption(f"- {o['name']}: ₪{o['cost']:,.0f} (ציון: {o['score']})")

    with col_res:
        if 'opt_result' in st.session_state:
            res = st.session_state['opt_result']
            
            if res['score'] > 0:
                # מדדים ראשיים
                m1, m2, m3 = st.columns(3)
                m1.metric("ציון איכות כולל", f"{res['score']}/300")
                m2.metric("עלות בפועל", f"₪{res['cost']:,.0f}")
                utilization = (res['cost'] / user_budget) * 100
                m3.metric("ניצול תקציב", f"{utilization:.1f}%")
                
                st.markdown("#### 🏆 ההרכב הנבחר")
                
                # הצגת הנתיב הנבחר בצורה ויזואלית
                for idx, item in enumerate(res['path']):
                    st.info(f"**שלב {idx+1}: {item['name']}** \n"
                            f"💰 עלות: ₪{item['cost']:,.0f} | ⭐ ציון: {item['score']}  \n"
                            f"📝 {item.get('desc', '')}")
                
                # גרף התפלגות
                st.markdown("#### התפלגות עלויות בפתרון")
                df_chart = pd.DataFrame(res['path'])
                fig = px.bar(df_chart, x='name', y='cost', text='cost', color='cost', color_continuous_scale='Blues')
                fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
                fig.update_layout(plot_bgcolor="white", font=dict(family="Rubik"), yaxis_title="עלות בשקלים", xaxis_title=None)
                st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.error("⚠️ התקציב נמוך מדי! לא ניתן להרכיב מפרט מינימלי בגישה זו. נסה להגדיל את התקציב.")
        else:
            st.info("הכנס תקציב ולחץ על כפתור ההרצה כדי לראות את הקסם של DP בפעולה.")
