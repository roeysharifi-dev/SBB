import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client
from fpdf import FPDF
import io
import os
import re

# --- 1. הגדרות עמוד ועיצוב (CSS) ---
st.set_page_config(
    page_title="SBB Pro System",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* כיוון RTL ופונטים */
    .stApp { direction: rtl; text-align: right; font-family: 'Segoe UI', sans-serif; }
    .stMarkdown, .stSelectbox, .stInput, .stNumberInput, .stSlider { 
        direction: rtl; text-align: right; 
    }
    
    /* כפתורים בגווני כחול */
    .stButton > button {
        background-color: #2E86C1;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 24px;
        font-weight: bold;
        transition: all 0.3s;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #1B4F72;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }

    /* כרטיסים ואקספנדרים */
    div[data-testid="stExpander"] {
        background-color: #ffffff;
        border-radius: 10px;
        border: 1px solid #E5E8E8;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* עיצוב מדדים (Metrics) */
    div[data-testid="stMetric"] {
        background-color: #F8F9F9;
        padding: 15px;
        border-radius: 10px;
        border-right: 5px solid #2E86C1;
        text-align: center;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricLabel"] {
        text-align: center; 
        font-weight: bold;
        color: #566573;
        font-size: 0.9rem;
    }
    div[data-testid="stMetricValue"] {
        text-align: center;
        color: #154360;
        font-weight: bold;
    }

    /* כותרות */
    h1, h2, h3 { color: #154360; }
    
    /* תפריט צד */
    section[data-testid="stSidebar"] {
        background-color: #F4F6F6;
        border-left: 1px solid #D5D8DC;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. הגדרות Supabase API ---
SUPABASE_URL = "https://lffmftqundknfdnixncg.supabase.co"
SUPABASE_KEY = "sb_publishable_E7mEuBsARmEyoIi_8SgboQ_32DYIPB2"

@st.cache_resource
def init_connection():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

supabase: Client = init_connection()

# --- 3. לוגיקה ונתונים ---
MATRIX = {
    "מגורים (בנייה רוויה)": {
        "בנייה קונבנציונלית": {"base": 5500, "info": "שיטה נפוצה, גמישות גבוהה."},
        "בנייה טרומית/מתועשת": {"base": 5800, "info": "מהירות ביצוע גבוהה, מתאים למגדלים."},
        "בנייה ירוקה": {"base": 6200, "info": "עלות גבוהה ב-10%, חסכון עתידי באנרגיה."},
        "בנייה קלה": {"base": 0, "info": "לא מתאים קונסטרוקטיבית למגדלים."}
    },
    "מגורים (צמודי קרקע)": {
        "בנייה קונבנציונלית": {"base": 7000, "info": "סטנדרט שוק."},
        "בנייה קלה": {"base": 5500, "info": "מהיר מאוד, בידוד תרמי מעולה."},
        "בנייה ירוקה": {"base": 7700, "info": "עמידה בתקן 5281."},
        "בנייה טרומית/מתועשת": {"base": 7500, "info": "דורש שינוע אלמנטים כבדים לשטח."}
    },
    "מסחר ומשרדים": {
        "בנייה קונבנציונלית": {"base": 6500, "info": "שימוש בשלד פלדה/בטון."},
        "בנייה טרומית/מתועשת": {"base": 6300, "info": "חיסכון בזמן הקמה משמעותי."},
        "בנייה ירוקה": {"base": 7200, "info": "תקן LEED - מבוקש מאוד בשוק השכירות."},
        "בנייה קלה": {"base": 5000, "info": "מתאים למבנים חד-קומתיים בלבד."}
    }
}

# --- פונקציות עזר ---

def get_project_stages(project_id):
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table("project_stages").select("*").eq("project_id", int(project_id)).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            return df.sort_values('id')
        return df
    except Exception as e:
        st.error(f"Error fetching stages: {e}")
        return pd.DataFrame()

def save_project(name, units, u_cost, total, stages_df, usage, method):
    if not supabase:
        st.error("אין חיבור לשרת")
        return False
    try:
        project_data = {
            "name": name,
            "units": int(units),
            "unit_cost": float(u_cost),
            "total_budget": float(total),
            "usage_type": usage,
            "build_method": method
        }
        response = supabase.table("projects").insert(project_data).execute()
        if not response.data:
            st.error("שגיאת שרת בקבלת נתונים")
            return False

        new_project_id = response.data[0]['id']
        stages_data = []
        for _, row in stages_df.iterrows():
            stages_data.append({
                "project_id": new_project_id,
                "stage_name": row['שלב'],
                "planned_percent": float(row['אחוז']),
                "planned_cost": float(row['עלות תכנון']),
                "actual_cost": 0
            })
        supabase.table("project_stages").insert(stages_data).execute()
        return True
    except Exception as e:
        st.error(f"Save Error: {e}")
        return False

def get_all_projects():
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table("projects").select("*").order("created_at", desc=True).execute()
        return pd.DataFrame(response.data)
    except: return pd.DataFrame()

def update_stage_costs(project_id, stages_df):
    if not supabase: return False
    try:
        for _, row in stages_df.iterrows():
            supabase.table("project_stages").update({
                "actual_cost": float(row['actual_cost'])
            }).eq("project_id", int(project_id)).eq("stage_name", row['stage_name']).execute()
        return True
    except Exception as e:
        st.error(f"Update Error: {e}")
        return False

# --- 4. פונקציות ייצוא ---
def create_pdf(project_name, df):
    pdf = FPDF()
    pdf.add_page()
    font_path = "Arial.ttf" 
    has_font = os.path.exists(font_path)
    
    if has_font:
        try:
            pdf.add_font("Arial", "", font_path, uni=True)
            pdf.set_font("Arial", size=12)
        except:
            has_font = False
            pdf.set_font("helvetica", size=12)
    else:
        pdf.set_font("helvetica", size=12)

    pdf.set_fill_color(46, 134, 193)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 15, txt="SBB Engineering Report", ln=True, align='C', fill=True)
    pdf.ln(10)
    
    pdf.set_text_color(0, 0, 0)
    display_name = project_name[::-1] if has_font else project_name
    pdf.cell(0, 10, txt=f"Project: {display_name}", ln=True, align='R' if has_font else 'L')
    pdf.ln(5)

    pdf.set_fill_color(235, 245, 251)
    h_actual = "בפועל"[::-1] if has_font else "Actual"
    h_planned = "מתוכנן"[::-1] if has_font else "Planned"
    h_stage = "שלב"[::-1] if has_font else "Stage"
    
    pdf.cell(60, 10, h_actual, 1, 0, 'C', fill=True)
    pdf.cell(60, 10, h_planned, 1, 0, 'C', fill=True)
    pdf.cell(70, 10, h_stage, 1, 1, 'C', fill=True)

    for _, row in df.iterrows():
        pdf.cell(60, 10, f"{row['actual_cost']:,.0f}", 1, 0, 'C')
        pdf.cell(60, 10, f"{row['planned_cost']:,.0f}", 1, 0, 'C')
        s_name = str(row['stage_name'])
        display_stage = s_name[::-1] if has_font else "Stage"
        pdf.cell(70, 10, display_stage, 1, 1, 'C')
    return bytes(pdf.output())

def create_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Budget_Report')
        workbook = writer.book
        worksheet = writer.sheets['Budget_Report']
        header_fmt = workbook.add_format({'bold': True, 'fg_color': '#2E86C1', 'font_color': 'white', 'border': 1})
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
    return output.getvalue()

# --- 5. ממשק ראשי ---
st.sidebar.title("🏗️ SBB Pro")
st.sidebar.caption("מערכת ניהול תקציב הנדסי")
menu = st.sidebar.radio("", ["🏠 מסך הבית", "➕ פרויקט חדש", "📊 דאשבורד ניהולי", "📉 מעקב תקציב"])
st.sidebar.markdown("---")
if supabase:
    st.sidebar.success("🟢 מערכת מחוברת")
else:
    st.sidebar.error("🔴 שגיאת התחברות")

# --- מסך הבית ---
if menu == "🏠 מסך הבית":
    st.title("SBB Pro Dashboard")
    st.markdown("### ברוכים הבאים למערכת הניהול")
    
    projects = get_all_projects()
    if not projects.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("פרויקטים פעילים", len(projects))
        c2.metric("תקציב מנוהל", f"₪{projects['total_budget'].sum():,.0f}")
        c3.metric("עלות למ\"ר (ממוצע)", f"₪{projects['unit_cost'].mean():,.0f}")

    st.markdown("---")
    st.subheader("📚 מחירון בסיס (נתוני מערכת)")
    
    matrix_data = []
    for category, methods in MATRIX.items():
        for method, details in methods.items():
            matrix_data.append({
                "סוג מבנה": category,
                "שיטת בנייה": method,
                "מחיר בסיס": details['base'],
                "הערות": details['info']
            })
    st.dataframe(pd.DataFrame(matrix_data), use_container_width=True, hide_index=True)

# --- פרויקט חדש ---
elif menu == "➕ פרויקט חדש":
    st.markdown("## 🆕 הקמת פרויקט חדש")
    
    with st.expander("📝 1. הגדרות בסיס", expanded=True):
        col_u, col_m = st.columns(2)
        usage = col_u.selectbox("ייעוד המבנה:", list(MATRIX.keys()))
        method = None
        base_price = 0
        if usage:
            method_options = list(MATRIX[usage].keys())
            method = col_m.selectbox("שיטת הבנייה:", method_options)
            if method:
                base_price = MATRIX[usage][method]['base']
                info = MATRIX[usage][method]['info']
                st.info(f"ℹ️ {info}")

    if usage and method:
        with st.form("new_project_form"):
            st.markdown("### 🏗️ פרטי הפרויקט")
            c_name, c_units, c_cost = st.columns([2, 1, 1])
            p_name = c_name.text_input("שם הפרויקט")
            units = c_units.number_input("יחידות/מ\"ר", min_value=1, value=100)
            u_cost = c_cost.number_input("עלות למ\"ר (₪)", value=base_price)

            st.markdown("---")
            st.markdown("### 📊 חלוקת תקציב (100%)")
            st.caption("הגדר את אחוזי התקציב לשלבים השונים:")
            
            # 3 תיבות אחוזים, האחרונה מחושבת אוטומטית
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                p1 = st.number_input("🔹 תכנון ורישוי (%)", min_value=0, max_value=100, value=15, step=1)
            with col_p2:
                max_p2 = 100 - p1
                p2 = st.number_input("🏗️ ביצוע ובנייה (%)", min_value=0, max_value=100, value=min(75, max_p2), step=1)
            
            p3 = 100 - (p1 + p2)
            
            with col_p3:
                st.number_input("🔑 מסירה וגמר (יתרה)", value=p3, disabled=True)
                if p3 < 0:
                     st.error("חריגה מ-100%!")

            df_pie = pd.DataFrame({
                'Stage': ['תכנון', 'ביצוע', 'מסירה'],
                'Value': [p1, p2, p3]
            })
            fig_pie = px.pie(df_pie, values='Value', names='Stage', hole=0.4, 
                                color_discrete_sequence=['#AED6F1', '#2E86C1', '#154360'])
            fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=150)
            st.plotly_chart(fig_pie, use_container_width=True)
            
            st.markdown("---")
            submitted = st.form_submit_button("💾 צור פרויקט במערכת")
            
            if submitted:
                if not p_name:
                    st.warning("חובה להזין שם פרויקט")
                elif p3 < 0:
                    st.error("סך האחוזים חורג מ-100.")
                else:
                    total = units * u_cost
                    df_s = pd.DataFrame({
                        "שלב": ["תכנון", "ביצוע", "מסירה"],
                        "אחוז": [p1, p2, p3],
                        "עלות תכנון": [(p1/100)*total, (p2/100)*total, (p3/100)*total]
                    })
                    if save_project(p_name, units, u_cost, total, df_s, usage, method):
                        st.success(f"הפרויקט '{p_name}' נוצר בהצלחה!")
                        st.balloons()

# --- דאשבורד ניהולי משופר ---
elif menu == "📊 דאשבורד ניהולי":
    st.markdown("## 📊 דאשבורד ניהולי מתקדם")
    projects = get_all_projects()
    
    if not projects.empty:
        # 1. שורת מדדים (KPIs)
        st.markdown("### 💡 מדדי מפתח")
        k1, k2, k3, k4 = st.columns(4)
        
        total_projects = len(projects)
        total_budget = projects['total_budget'].sum()
        avg_budget = projects['total_budget'].mean()
        total_units = projects['units'].sum()
        
        k1.metric("פרויקטים", total_projects)
        k2.metric("תקציב כולל", f"₪{total_budget:,.0f}")
        k3.metric("תקציב ממוצע", f"₪{avg_budget:,.0f}")
        k4.metric("יח\"ד/משרדים", f"{total_units:,.0f}")
        
        st.markdown("---")

        # 2. אזור הגרפים (מסודר בשתי עמודות)
        c_charts1, c_charts2 = st.columns([1.6, 1])
        
        with c_charts1:
            st.subheader("💰 נפח תקציבי לפי פרויקט")
            fig_bar = px.bar(
                projects, 
                x='name', 
                y='total_budget',
                color='total_budget', # צביעה הדרגתית לפי גודל התקציב
                text_auto='.2s',
                labels={'name': 'שם הפרויקט', 'total_budget': 'תקציב (₪)'},
                color_continuous_scale=px.colors.sequential.Blues
            )
            fig_bar.update_layout(
                plot_bgcolor="white",
                xaxis_title=None,
                font=dict(family="Segoe UI", size=12),
                coloraxis_showscale=False
            )
            fig_bar.update_traces(textposition='outside')
            st.plotly_chart(fig_bar, use_container_width=True)

        with c_charts2:
            st.subheader("🏗️ פילוח סוגי פרויקטים")
            # הכנת נתונים לגרף דונאט
            df_pie = projects.groupby('usage_type').size().reset_index(name='count')
            fig_pie = px.pie(
                df_pie, 
                values='count', 
                names='usage_type', 
                hole=0.4,
                color_discrete_sequence=['#2E86C1', '#AED6F1', '#154360', '#5DADE2']
            )
            fig_pie.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                margin=dict(t=20, b=0, l=0, r=0)
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        # 3. טבלת נתונים
        st.markdown("### 📋 נתונים מפורטים")
        with st.expander("לחץ כאן לצפייה בטבלה המלאה", expanded=False):
            st.dataframe(
                projects, 
                use_container_width=True,
                column_config={
                    "name": "שם פרויקט",
                    "total_budget": st.column_config.NumberColumn("תקציב כולל", format="₪%d"),
                    "unit_cost": st.column_config.NumberColumn("עלות למ\"ר", format="₪%d"),
                    "units": "יחידות",
                    "usage_type": "ייעוד",
                    "build_method": "שיטה",
                    "created_at": st.column_config.DatetimeColumn("תאריך", format="DD/MM/YYYY")
                }
            )

    else:
        st.info("אין נתונים להצגה")

# --- מעקב תקציב ---
elif menu == "📉 מעקב תקציב":
    st.markdown("## 📉 בקרת תקציב")
    projects = get_all_projects()
    
    if not projects.empty:
        col_sel, _ = st.columns([1, 2])
        sel = col_sel.selectbox("בחר פרויקט:", projects['name'].unique())
        
        p_row = projects[projects['name'] == sel].iloc[0]
        p_id = int(p_row['id'])
        
        stages = get_project_stages(p_id)
        
        if not stages.empty:
            c1, c2, c3 = st.columns(3)
            total_plan = stages['planned_cost'].sum()
            total_actual = stages['actual_cost'].sum()
            diff = total_plan - total_actual
            
            c1.metric("תקציב מתוכנן", f"₪{total_plan:,.0f}")
            c2.metric("ביצוע בפועל", f"₪{total_actual:,.0f}")
            c3.metric("יתרה בתקציב", f"₪{diff:,.0f}", delta_color="normal")

            st.markdown("---")
            
            col_table, col_graph = st.columns([1, 1.5])
            
            with col_table:
                st.subheader("עדכון עלויות")
                edited = st.data_editor(
                    stages,
                    column_config={
                        "stage_name": st.column_config.TextColumn("שלב", disabled=True),
                        "planned_cost": st.column_config.NumberColumn("מתוכנן", format="₪%d", disabled=True),
                        "actual_cost": st.column_config.NumberColumn("בפועל", format="₪%d", required=True)
                    },
                    use_container_width=True,
                    hide_index=True,
                    key="editor"
                )
                if st.button("💾 שמור עדכון"):
                    if update_stage_costs(p_id, edited):
                        st.toast("הנתונים נשמרו!", icon="✅")
                        st.rerun()

            with col_graph:
                st.subheader("תחזית מול ביצוע")
                fig_compare = go.Figure()
                
                # תכנון
                fig_compare.add_trace(go.Bar(
                    name='תכנון', 
                    x=edited['stage_name'], 
                    y=edited['planned_cost'],
                    marker_color='#D6DBDF', 
                    texttemplate='%{y:.2s}',
                    textposition='auto'
                ))
                
                # ביצוע
                fig_compare.add_trace(go.Bar(
                    name='ביצוע', 
                    x=edited['stage_name'], 
                    y=edited['actual_cost'],
                    marker_color='#2874A6', 
                    texttemplate='%{y:.2s}',
                    textposition='auto'
                ))
                
                fig_compare.update_layout(barmode='group', plot_bgcolor='white', margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_compare, use_container_width=True)

            st.markdown("#### 📥 הפקת דוחות")
            c_pdf, c_xlsx, _ = st.columns([1, 1, 3])
            safe_name = re.sub(r'[\\/*?:"<>|]', "", sel)
            
            with c_pdf:
                try:
                    pdf_data = create_pdf(sel, edited)
                    st.download_button("PDF", data=pdf_data, file_name=f"{safe_name}.pdf", mime="application/pdf", use_container_width=True)
                except: 
                    st.error("שגיאה ביצירת PDF")
            
            with c_xlsx:
                excel_data = create_excel(edited)
                st.download_button("Excel", data=excel_data, file_name=f"{safe_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    else:

        st.info("אין פרויקטים במערכת")

# רועי

# הוספה בסוף הקובץ app.py
st.markdown("""
<style>
    /* אפקט צל וריחוף למדדים */
    div[data-testid="stMetric"] {
        transition: transform 0.2s, box-shadow 0.2s;
        cursor: pointer;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1) !important;
        border-right: 5px solid #1B4F72 !important;
    }

    /* עיצוב כפתורי הורדה (PDF/Excel) */
    .stDownloadButton > button {
        background-color: #ffffff !important;
        color: #2E86C1 !important;
        border: 1px solid #2E86C1 !important;
        border-radius: 5px !important;
        height: 40px;
        transition: all 0.3s ease;
    }
    .stDownloadButton > button:hover {
        background-color: #EBF5FB !important;
        color: #1B4F72 !important;
        border-color: #1B4F72 !important;
    }
</style>
""", unsafe_allow_html=True)

# בתוך מסך דאשבורד ניהולי
tab_summary, tab_charts, tab_data = st.tabs(["📌 סיכום מנהלים", "📈 ניתוח גרפי", "📄 טבלאות נתונים"])

with tab_summary:
    # תכניס כאן את ה-Metrics (שורת המדדים)
    st.write("נתונים כלליים של כל הפרויקטים")

with tab_charts:
    # תכניס כאן את הגרפים (fig_bar ו-fig_pie)
    st.plotly_chart(fig_bar, use_container_width=True)

with tab_data:
    # תכניס כאן את ה-dataframe המלא
    st.dataframe(projects, use_container_width=True)
