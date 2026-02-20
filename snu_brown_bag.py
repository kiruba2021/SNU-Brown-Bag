import streamlit as st
import sqlite3
import pandas as pd
import smtplib
import time
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
    pdf = FPDF()
    pdf.add_page()
    pdf.set_text_color(0, 51, 102)
    pdf.set_font("Arial", "B", 20)
    pdf.cell(200, 20, txt="SNU Brown Bag Research Analytics Report", ln=True, align="C")

    fig1, fig2 = get_plots(df)
    fig1.write_image("plot_dept.png")
    fig2.write_image("plot_role.png")

    # Image 1 placement

    pdf.image("plot_dept.png", x=10, y=40, w=180)

    # Descent spacing: Image 2 starts much lower (y=150) to avoid overlap

    pdf.image("plot_role.png", x=50, y=150, w=110)

    os.remove("plot_dept.png")
    os.remove("plot_role.png")
    return pdf.output(dest="S").encode("latin-1")


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
        safe_cols = [col for col in display_cols if col in upcoming.columns]
    st.dataframe(
        previous[safe_cols].sort_values(["date", "time"], ascending=False),
        use_container_width=True,
    )
    conn.close()
# --- TAB 2: ANALYTICS ---


with tabs[1]:
    if not df.empty:
        st.subheader("Presentation Statistics")
        f1, f2 = get_plots(df)
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(f1, use_container_width=True)
        with col2:
            st.plotly_chart(f2, use_container_width=True)
    else:
        st.warning("No data available for analytics yet.")
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
        Guide/Supervisor: {row['guide_name']}
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

