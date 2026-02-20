import streamlit as st
import sqlite3
import pandas as pd
import smtplib
import time
import matplotlib.pyplot as plt
import io
import os
from email.mime.text import MIMEText
from datetime import datetime, time as dt_time
from fpdf import FPDF
import plotly.express as px

# --- 1. DATABASE SETUP ---


def init_db():
    conn = sqlite3.connect("ssn_research.db")
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS departments 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, 
                  head_email TEXT, coord_email TEXT, password TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS presentations 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, presenter TEXT, designation TEXT, 
                  guide_name TEXT, title TEXT, abstract TEXT, date TEXT, time TEXT, 
                  duration TEXT, venue_hall TEXT, dept_id INTEGER)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS subscriptions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE)"""
    )
    # ✅ ADMIN NOTIFICATION TABLE

    c.execute(
        """CREATE TABLE IF NOT EXISTS activity_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  action TEXT,
                  title TEXT,
                  presenter TEXT,
                  dept_name TEXT,
                  done_by TEXT,
                  action_time TEXT)"""
    )

    conn.commit()
    conn.close()


# --- 2. HELPERS ---


def send_mail(subject, body, recipients, sender_email, app_password):
    if not sender_email or not app_password:
        return "Mail credentials missing."
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = ", ".join(recipients)
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender_email, app_password)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        return f"Mail Error: {str(e)}"


def delayed_refresh(message, icon="✅"):
    st.success(f"{icon} {message}")
    time.sleep(1.2)
    st.rerun()


# --- 3. ANALYTICS & PDF ENGINE ---


def get_plots(df):
    # Chart 1: Presentations per Department

    fig1 = px.bar(
        df["Dept"].value_counts().reset_index(),
        x="Dept",
        y="count",
        title="Presentations by Department",
        color_discrete_sequence=["#003366"],
    )
    # Chart 2: Presenter Designation Distribution

    fig2 = px.pie(
        df,
        names="designation",
        title="Presenter Roles",
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    return fig1, fig2


def generate_pdf_report(df):

    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics
    import matplotlib.pyplot as plt
    import pandas as pd
    import numpy as np
    import os

    file_path = "institutional_analytics_report.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()

    # ===============================
    # EXECUTIVE SUMMARY PAGE
    # ===============================

    elements.append(Paragraph("<b>SNU Brown Bag Research Analytics Report</b>", styles["Title"]))
    elements.append(Spacer(1, 0.3 * inch))

    total_presentations = len(df)
    total_departments = df["Dept"].nunique()
    total_presenters = df["presenter"].nunique()

    df["date"] = pd.to_datetime(df["date"])
    df["Year"] = df["date"].dt.year
    df["YearMonth"] = df["date"].dt.to_period("M").astype(str)

    yearly_counts = df.groupby("Year").size()
    monthly_counts = df.groupby("YearMonth").size()

    if len(yearly_counts) > 1:
        yoy_growth = round(yearly_counts.pct_change().iloc[-1] * 100, 2)
    else:
        yoy_growth = 0

    intensity_index = round(total_presentations / total_departments, 2)

    summary_data = [
        ["Total Presentations", total_presentations],
        ["Departments Engaged", total_departments],
        ["Unique Presenters", total_presenters],
        ["Research Intensity Index", intensity_index],
        ["Year-over-Year Growth %", f"{yoy_growth}%"]
    ]

    summary_table = Table(summary_data, colWidths=[250, 100])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.whitesmoke, colors.lightblue]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('TEXTCOLOR', (1,0), (1,-1), colors.darkblue)
    ]))

    elements.append(summary_table)
    elements.append(PageBreak())

    # ===============================
    # MONTHLY TRENDS CHART
    # ===============================

    plt.figure(figsize=(8,4))
    monthly_counts.plot(kind="bar", color="#1f77b4")
    plt.title("Monthly Presentation Trends")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("monthly.png")
    plt.close()

    elements.append(Paragraph("<b>Monthly Trends Analysis</b>", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Image("monthly.png", width=6*inch, height=3*inch))
    elements.append(PageBreak())

    # ===============================
    # DEPARTMENT PERFORMANCE
    # ===============================

    dept_counts = df.groupby("Dept").size().sort_values(ascending=False)
    dept_counts = dept_counts.reset_index()
    dept_counts.columns = ["Department", "Presentations"]

    dept_counts["Rank"] = dept_counts["Presentations"].rank(ascending=False).astype(int)
    dept_counts["Performance Score"] = round(
        (dept_counts["Presentations"] / dept_counts["Presentations"].max()) * 100, 2
    )

    table_data = [dept_counts.columns.tolist()] + dept_counts.values.tolist()

    dept_table = Table(table_data)
    dept_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))

    elements.append(Paragraph("<b>Department Ranking & Performance Score</b>", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(dept_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Department Distribution Chart
    plt.figure(figsize=(8,4))
    dept_counts.set_index("Department")["Presentations"].plot(kind="bar", color="#ff7f0e")
    plt.title("Department Distribution")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("dept.png")
    plt.close()

    elements.append(Image("dept.png", width=6*inch, height=3*inch))
    elements.append(PageBreak())

    # ===============================
    # YEARLY GROWTH VISUAL
    # ===============================

    if len(yearly_counts) > 1:
        plt.figure(figsize=(8,4))
        yearly_counts.plot(kind="line", marker='o', color="green")
        plt.title("Yearly Growth Trend")
        plt.tight_layout()
        plt.savefig("yearly.png")
        plt.close()

        elements.append(Paragraph("<b>Year-over-Year Growth Analysis</b>", styles["Heading2"]))
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Image("yearly.png", width=6*inch, height=3*inch))

    # ===============================
    # BUILD PDF
    # ===============================

    doc.build(elements)

    for f in ["monthly.png", "dept.png", "yearly.png"]:
        if os.path.exists(f):
            os.remove(f)

    with open(file_path, "rb") as f:
        pdf_data = f.read()

    os.remove(file_path)

    return pdf_data

# --- 4. APP INTERFACE ---


st.set_page_config(page_title="SNU | Brown Bag Portal", layout="wide")
init_db()

TIME_SLOTS = [
    dt_time(h, m).strftime("%I:%M %p") for h in range(8, 20) for m in (0, 15, 30, 45)
]
DURATIONS = ["30 mins", "45 mins", "1 hour", "1.5 hours", "2 hours"]

if "auth" not in st.session_state:
    st.session_state["auth"] = False
if "dept" not in st.session_state:
    st.session_state["dept"] = None
st.title("🎓 Shiv Nadar University | Brown Bag Portal")
tabs = st.tabs(
    ["📅 Public Schedule", "📊 Analytics", "🔐 Coordinator Access", "🛠️ Admin Control"]
)

conn = sqlite3.connect("ssn_research.db")
df = pd.read_sql_query(
    "SELECT p.*, d.name as Dept FROM presentations p JOIN departments d ON p.dept_id = d.id",
    conn,
)
conn.close()
# 🔹 Columns used across tabs


display_cols = [
    "id",
    "date",
    "time",
    "title",
    "presenter",
    "designation",
    "guide_name",
    "duration",
    "venue_hall",
    "Dept",
]

# --- TAB 1: PUBLIC SCHEDULE ---


with tabs[0]:
    st.subheader("📅 Public Presentation Schedule")

    conn = sqlite3.connect("ssn_research.db")
    today = datetime.now().strftime("%Y-%m-%d")

    # 🔹 Upcoming

    upcoming = pd.read_sql_query(
        """
        SELECT p.*, d.name as Dept
        FROM presentations p
        JOIN departments d ON p.dept_id = d.id
        WHERE date >= ?
        ORDER BY date ASC, time ASC
    """,
        conn,
        params=(today,),
    )

    st.markdown("## 📌 Upcoming Presentations")

    if upcoming.empty:
        st.info("No upcoming presentations.")
    else:
        display_cols = [
            "date",
            "time",
            "Dept",
            "title",
            "presenter",
            "designation",
            "guide_name",
            "duration",
            "venue_hall/Meeting Link",
        ]
        safe_cols = [col for col in display_cols if col in upcoming.columns]
        st.dataframe(
            upcoming[safe_cols].sort_values(["date", "time"]),
            use_container_width=True,
        )
    # 🔹 Previous

    previous = pd.read_sql_query(
        """
        SELECT p.*, d.name as Dept
        FROM presentations p
        JOIN departments d ON p.dept_id = d.id
        WHERE date < ?
        ORDER BY date DESC, time DESC
    """,
        conn,
        params=(today,),
    )

    st.markdown("## 📜 Previous Presentations")

    if previous.empty:
        st.info("No previous presentations.")
    else:
        display_cols = [
            "date",
            "time",
            "Dept",
            "title",
            "presenter",
            "designation",
            "guide_name",
            "duration",
            "venue_hall",
        ]

        safe_cols = [col for col in display_cols if col in previous.columns]

        st.dataframe(
            previous[safe_cols].sort_values(["date", "time"], ascending=False),
            use_container_width=True,
        )
    conn.close()
# --- TAB 2: ANALYTICS ---


with tabs[1]:

    st.markdown("## 🎓 VC Executive Research Dashboard")
    st.caption("Institution-Level Research Monitoring & Performance Insights")

    if not df.empty:

        # =========================
        # DATA PREPARATION
        # =========================
        df["date"] = pd.to_datetime(df["date"])
        df["Year"] = df["date"].dt.year
        df["Month"] = df["date"].dt.month_name()
        df["YearMonth"] = df["date"].dt.to_period("M").astype(str)

        # =========================
        # INTERACTIVE FILTERS
        # =========================
        colf1, colf2 = st.columns(2)

        selected_dept = colf1.multiselect(
            "Select Department",
            options=df["Dept"].unique(),
            default=df["Dept"].unique(),
        )

        selected_year = colf2.multiselect(
            "Select Year",
            options=sorted(df["Year"].unique()),
            default=sorted(df["Year"].unique()),
        )

        filtered_df = df[
            (df["Dept"].isin(selected_dept)) &
            (df["Year"].isin(selected_year))
        ]

        if filtered_df.empty:
            st.warning("No data for selected filters.")
            st.stop()

        # =========================
        # KPI SECTION
        # =========================
        total_presentations = len(filtered_df)
        total_departments = filtered_df["Dept"].nunique()
        total_presenters = filtered_df["presenter"].nunique()
        intensity_index = round(total_presentations / total_departments, 2)

        yearly_counts = filtered_df.groupby("Year").size()
        if len(yearly_counts) > 1:
            yoy_growth = round(yearly_counts.pct_change().iloc[-1] * 100, 2)
        else:
            yoy_growth = 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Presentations", total_presentations)
        c2.metric("Departments Active", total_departments)
        c3.metric("Research Intensity Index", intensity_index)
        c4.metric("YoY Growth %", f"{yoy_growth}%")

        st.divider()

        # =========================
        # MONTHLY TREND
        # =========================
        monthly_counts = filtered_df.groupby("YearMonth").size().reset_index(name="Count")

        fig_month = px.line(
            monthly_counts,
            x="YearMonth",
            y="Count",
            markers=True,
            title="📈 Monthly Research Trend",
            color_discrete_sequence=["#003366"],
        )

        st.plotly_chart(fig_month, use_container_width=True)

        # =========================
        # DEPARTMENT PERFORMANCE
        # =========================
        dept_rank = filtered_df["Dept"].value_counts().reset_index()
        dept_rank.columns = ["Department", "Presentations"]
        dept_rank["Rank"] = dept_rank["Presentations"].rank(ascending=False).astype(int)
        dept_rank["Performance Score"] = round(
            (dept_rank["Presentations"] / dept_rank["Presentations"].max()) * 100, 2
        )

        colA, colB = st.columns([2, 1])

        with colA:
            st.subheader("🏆 Department Ranking")
            st.dataframe(dept_rank, use_container_width=True)

        with colB:
            fig_dept = px.bar(
                dept_rank,
                x="Department",
                y="Presentations",
                title="Department Distribution",
                color="Department",
            )
            st.plotly_chart(fig_dept, use_container_width=True)

        st.divider()

        # =========================
        # ROLE DISTRIBUTION
        # =========================
        role_fig = px.pie(
            filtered_df,
            names="designation",
            title="🎯 Presenter Role Distribution",
            color_discrete_sequence=px.colors.qualitative.Bold,
        )
        st.plotly_chart(role_fig, use_container_width=True)

        # =========================
        # HEATMAP
        # =========================
        st.subheader("🔥 Academic Activity Heatmap")

        heat_df = filtered_df.groupby(["Dept", "Month"]).size().unstack(fill_value=0)

        heat_fig = px.imshow(
            heat_df,
            text_auto=True,
            aspect="auto",
            color_continuous_scale="Blues",
            title="Department vs Month Activity",
        )

        st.plotly_chart(heat_fig, use_container_width=True)

        # =========================
        # EXPORT ANALYTICS TO EXCEL
        # =========================
        st.divider()
        st.subheader("⬇ Export Options")

        excel_file = "analytics_export.xlsx"
        filtered_df.to_excel(excel_file, index=False)

        with open(excel_file, "rb") as f:
            st.download_button(
                "📊 Download Full Analytics (Excel)",
                f,
                file_name="SNU_Analytics.xlsx",
            )

        os.remove(excel_file)

        # =========================
        # DOWNLOAD DASHBOARD IMAGE
        # =========================
        dashboard_image = "dashboard_snapshot.png"
        st.markdown("### 📥 Download VC Dashboard Image")

dashboard_image = io.BytesIO()

# Prepare monthly data
monthly_data = filtered_df.groupby(["year", "month"]).size().reset_index(name="count")

plt.figure(figsize=(10,6))
plt.plot(monthly_data["month"], monthly_data["count"])
plt.title("Monthly Presentation Trends")
plt.xlabel("Month")
plt.ylabel("Number of Presentations")

plt.tight_layout()
plt.savefig(dashboard_image, format="png")
plt.close()

dashboard_image.seek(0)

st.download_button(
    "Download Dashboard as Image",
    data=dashboard_image,
    file_name="VC_Dashboard.png",
    mime="image/png"
)
        
        os.remove(dashboard_image)

    else:
        st.warning("No data available for analytics.")
# --- TAB 3: COORDINATOR ---


with tabs[2]:

    if not st.session_state["auth"]:

        # --- LOGIN INTERFACE ---

        conn = sqlite3.connect("ssn_research.db")
        d_df = pd.read_sql_query("SELECT * FROM departments", conn)
        conn.close()

        dept_choice = st.selectbox(
            "Select Dept", d_df["name"].tolist() if not d_df.empty else ["No Depts"]
        )

        pass_in = st.text_input("Password", type="password")

        if st.button("Login"):
            if (
                not d_df.empty
                and pass_in == d_df[d_df["name"] == dept_choice]["password"].values[0]
            ):
                st.session_state["auth"] = True
                st.session_state["dept"] = dept_choice
                st.rerun()
            else:
                st.error("Invalid Credentials.")
    else:
        # --- LOGGED IN DASHBOARD ---

        st.subheader(f"Coordinator: {st.session_state['dept']}")

        if st.button("Logout"):
            st.session_state["auth"] = False
            st.rerun()
        c_mode = st.radio("Mode", ["Add New", "Manage Presentations"], horizontal=True)
        st.divider()

        # --- SUB-SECTION: ADD NEW ---

        if c_mode == "Add New":
            st.subheader("➕ Schedule New Presentation")

            with st.form("add_pres_form", clear_on_submit=True):

                col1, col2 = st.columns(2)

                with col1:
                    p_name = st.text_input("Presenter Name")
                    p_role = st.selectbox(
                        "Designation", ["Faculty", "Scholar", "Student"]
                    )
                    p_guide = st.text_input("Guide/Supervisor Name")
                    p_title = st.text_input("Presentation Title")
                with col2:
                    p_date = st.date_input("Date", min_value=datetime.now())
                    p_time = st.selectbox("Start Time", TIME_SLOTS)
                    p_dur = st.selectbox("Duration", DURATIONS)
                    p_venue = st.text_input("Venue/Hall/Meeting Link")
                p_abstract = st.text_area("Abstract/Description")

                submit_btn = st.form_submit_button("Confirm & Schedule")

                if submit_btn:

                    if not p_name or not p_title:
                        st.error("Please fill in Name and Title.")
                    else:
                        conn = sqlite3.connect("ssn_research.db")

                        dept_res = conn.execute(
                            "SELECT id FROM departments WHERE name=?",
                            (st.session_state["dept"],),
                        ).fetchone()

                        if dept_res:

                            conn.execute(
                                """
                                INSERT INTO presentations 
                                (presenter, designation, guide_name, title, abstract, date, time, duration, venue_hall, dept_id)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    p_name,
                                    p_role,
                                    p_guide,
                                    p_title,
                                    p_abstract,
                                    str(p_date),
                                    p_time,
                                    p_dur,
                                    p_venue,
                                    dept_res[0],
                                ),
                            )

                            # LOG ACTIVITY

                            conn.execute(
                                """
                                INSERT INTO activity_logs
                                (action, title, presenter, dept_name, done_by, action_time)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    "ADDED",
                                    p_title,
                                    p_name,
                                    st.session_state["dept"],
                                    st.session_state["dept"],
                                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                ),
                            )

                            conn.commit()
                            conn.close()

                            delayed_refresh("Presentation Added!")
                # --- SUB-SECTION: MANAGE ---
        elif c_mode == "Manage Presentations":

            conn = sqlite3.connect("ssn_research.db")
            dept_name = st.session_state["dept"]

            pres_df = pd.read_sql_query(
                """
                SELECT p.*, d.name as Dept 
                FROM presentations p 
                JOIN departments d ON p.dept_id = d.id 
                WHERE d.name = ?
                """,
                conn,
                params=(dept_name,),
            )
            conn.close()

            if pres_df.empty:
                st.info("No presentations found.")
            else:
                st.subheader("📋 Department Presentations")

                display_cols = [
                    "id",
                    "date",
                    "time",
                    "title",
                    "presenter",
                    "designation",
                    "guide_name",
                    "duration",
                    "venue_hall",
                ]

                st.dataframe(
                    pres_df[display_cols].sort_values(["date", "time"]),
                    use_container_width=True,
                )

                st.divider()

                # 🔽 SELECT ROW FOR ACTION

                selected_id = st.selectbox(
                    "Select Presentation ID to Edit/Delete", pres_df["id"]
                )

                col1, col2 = st.columns(2)

                # EDIT

                if col1.button("✏️ Edit Selected"):
                    st.session_state["edit_id"] = selected_id
                    # DELETE
                if col2.button("🗑 Delete Selected"):

                    conn = sqlite3.connect("ssn_research.db")

                    row = pres_df[pres_df["id"] == selected_id].iloc[0]

                    conn.execute(
                        """
                        INSERT INTO activity_logs
                        (action, title, presenter, dept_name, done_by, action_time)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "DELETED",
                            row["title"],
                            row["presenter"],
                            row["Dept"],
                            st.session_state["dept"],
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )

                    conn.execute("DELETE FROM presentations WHERE id=?", (selected_id,))
                    conn.commit()
                    conn.close()

                    delayed_refresh("Deleted & Logged")
        # --- EDIT FORM LOGIC (OUTSIDE LOOP) ---
if "edit_id" in st.session_state:

    edit_id = st.session_state["edit_id"]

    conn = sqlite3.connect("ssn_research.db")
    edit_data = pd.read_sql_query(
        "SELECT * FROM presentations WHERE id=?", conn, params=(edit_id,)
    )
    conn.close()

    if not edit_data.empty:

        erow = edit_data.iloc[0]

        st.divider()
        st.subheader("✏️ Edit Presentation")

        with st.form("edit_form"):

            new_title = st.text_input("Title", erow["title"])
            new_venue = st.text_input("Venue", erow["venue_hall"])
            new_time = st.selectbox(
                "Time", TIME_SLOTS, index=TIME_SLOTS.index(erow["time"])
            )
            new_duration = st.selectbox(
                "Duration", DURATIONS, index=DURATIONS.index(erow["duration"])
            )

            update_btn = st.form_submit_button("Update Presentation")

            if update_btn:

                conn = sqlite3.connect("ssn_research.db")

                conn.execute(
                    """
                    UPDATE presentations
                    SET title=?, venue_hall=?, time=?, duration=?
                    WHERE id=?
                """,
                    (new_title, new_venue, new_time, new_duration, edit_id),
                )

                conn.commit()
                conn.close()

                del st.session_state["edit_id"]

                delayed_refresh("Presentation Updated!")
# --- TAB 4: ADMIN CONTROL ---


with tabs[3]:
    admin_pass = st.text_input("Admin Pass", type="password", key="admin_pwd_input")
    if admin_pass == "admin123":
        adm = st.radio(
            "Tool",
            ["Departments", "Subscribers", "Broadcast", "Reports", "Notifications"],
            horizontal=True,
        )

        if adm == "Reports":
            if not df.empty:
                st.subheader("Generate Institutional Report")
                if st.button("Generate PDF"):
                    with st.spinner("⏳ Preparing PDF with charts..."):
                        pdf_data = generate_pdf_report(df)
                        st.download_button(
                            "📘 Download PDF Report",
                            pdf_data,
                            "SNU_Research_Report.pdf",
                        )
            else:
                st.error("Cannot generate report: No data found.")
        elif adm == "Subscribers":
            with st.form("sub_ui"):
                new_sub = st.text_input("Add Subscriber Email")
                if st.form_submit_button("Add"):
                    with st.spinner("⏳ Saving..."):
                        conn = sqlite3.connect("ssn_research.db")
                        try:
                            conn.execute(
                                "INSERT INTO subscriptions (email) VALUES (?)",
                                (new_sub,),
                            )
                            conn.commit()
                            delayed_refresh("Subscriber Added.")
                        except:
                            st.error("Already subscribed.")
                        finally:
                            conn.close()
            st.divider()
            conn = sqlite3.connect("ssn_research.db")
            subs = pd.read_sql_query("SELECT * FROM subscriptions", conn)
            conn.close()
            for _, s in subs.iterrows():
                sc1, sc2 = st.columns([4, 1])
                sc1.text(s["email"])
                if sc2.button("Remove", key=f"rs_{s['id']}"):
                    conn = sqlite3.connect("ssn_research.db")
                    conn.execute("DELETE FROM subscriptions WHERE id=?", (s["id"],))
                    conn.commit()
                    conn.close()
                    delayed_refresh("Removed.")
        elif adm == "Departments":
            with st.expander("➕ Register Department"):
                with st.form("new_d"):
                    dn = st.text_input("Name")
                    dh = st.text_input("HOD Email")
                    dc = st.text_input("Coord Email")
                    dp = st.text_input("Pass", type="password")
                    if st.form_submit_button("Create"):
                        conn = sqlite3.connect("ssn_research.db")
                        conn.execute(
                            "INSERT INTO departments (name,head_email,coord_email,password) VALUES (?,?,?,?)",
                            (dn, dh, dc, dp),
                        )
                        conn.commit()
                        conn.close()
                        delayed_refresh("Created.")
            conn = sqlite3.connect("ssn_research.db")
            depts = pd.read_sql_query("SELECT * FROM departments", conn)
            conn.close()
            for _, r in depts.iterrows():
                with st.expander(f"Edit {r['name']}"):
                    with st.form(f"ed_{r['id']}"):
                        en = st.text_input("Dept Name", r["name"])
                        eh = st.text_input("HOD Email", r["head_email"])
                        ec = st.text_input("Coord Email", r["coord_email"])
                        ep = st.text_input("Password", r["password"])
                        if st.form_submit_button("Update"):
                            conn = sqlite3.connect("ssn_research.db")
                            conn.execute(
                                "UPDATE departments SET name=?, head_email=?, coord_email=?, password=? WHERE id=?",
                                (en, eh, ec, ep, r["id"]),
                            )
                            conn.commit()
                            conn.close()
                            delayed_refresh("Updated.")
        elif adm == "Broadcast":
            st.subheader("📢 Email Notifications")
            aud = st.selectbox("Target", ["Coordinators Only", "Include Subscribers"])
            sem = st.text_input("Admin Gmail")
            spa = st.text_input("App Password", type="password")

            if st.button("🚀 Send Emails"):
                with st.spinner("⏳ Broadcasting..."):
                    conn = sqlite3.connect("ssn_research.db")
                    list_re = (
                        pd.read_sql_query(
                            "SELECT head_email, coord_email FROM departments", conn
                        )
                        .values.flatten()
                        .tolist()
                    )
                    if "Include" in aud:
                        list_re += pd.read_sql_query(
                            "SELECT email FROM subscriptions", conn
                        )["email"].tolist()
                    conn.close()

                    today = datetime.now().strftime("%Y-%m-%d")

                    conn = sqlite3.connect("ssn_research.db")

                    upcoming_mail = pd.read_sql_query(
                        """
                        SELECT p.date, p.time, p.title, p.presenter, p.venue_hall, d.name as Dept
                        FROM presentations p
                        JOIN departments d ON p.dept_id = d.id
                        WHERE date >= ?
                        ORDER BY date ASC, time ASC
                        """,
                        conn,
                        params=(today,),
                    )

                    conn.close()
                    portal_link = "https://your-streamlit-app-link.streamlit.app"

                    if upcoming_mail.empty:
                        body = f"""
        SNU Brown Bag Research Portal Update

        There are currently no upcoming presentations.

        Visit Portal:
        {portal_link}
        """
                    else:
                        body = "SNU Brown Bag Research – Upcoming Presentations\n\n"

                        for _, row in upcoming_mail.iterrows():
                            body += f"""
        Department: {row['Dept']}
        Title: {row['title']}
        Presenter: {row['presenter']}
        Date: {row['date']}
        Time: {row['time']}
        Venue: {row['venue_hall']}
        -------------------------------------------
        """
                        body += f"\nView Full Schedule Here:\n{portal_link}"
                    res = send_mail("Research Schedule Update", body, list_re, sem, spa)
                    if res == True:
                        st.success("Broadcast successful!")
                    else:
                        st.error(res)
        elif adm == "Notifications":

            st.subheader("🔔 Coordinator Activity Notifications")
            conn = sqlite3.connect("ssn_research.db")

            conn = sqlite3.connect("ssn_research.db")
            log_df = pd.read_sql_query(
                """
                SELECT action_time, action, title, presenter, dept_name, done_by
                FROM activity_logs
                ORDER BY id DESC""",
                conn,
            )
            conn.close()

            if not log_df.empty:
                st.dataframe(log_df, use_container_width=True)
            else:
                st.info("No activity yet.")










