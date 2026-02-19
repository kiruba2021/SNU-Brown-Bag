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
    conn = sqlite3.connect('ssn_research.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS departments 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, 
                  head_email TEXT, coord_email TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS presentations 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, presenter TEXT, designation TEXT, 
                  guide_name TEXT, title TEXT, abstract TEXT, date TEXT, time TEXT, 
                  duration TEXT, venue_hall TEXT, dept_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE)''')
    conn.commit()
    conn.close()

# --- 2. HELPERS ---
def send_mail(subject, body, recipients, sender_email, app_password):
    if not sender_email or not app_password: return "Mail credentials missing."
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipients)
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()
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
    fig1 = px.bar(df['Dept'].value_counts().reset_index(), x='Dept', y='count', 
                  title="Presentations by Department", color_discrete_sequence=['#003366'])
    # Chart 2: Presenter Designation Distribution
    fig2 = px.pie(df, names='designation', title="Presenter Roles", 
                  color_discrete_sequence=px.colors.qualitative.Pastel)
    return fig1, fig2

def generate_pdf_report(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_text_color(0, 51, 102)
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(200, 20, txt="SNU Brown Bag Research Analytics Report", ln=True, align='C')
    
    fig1, fig2 = get_plots(df)
    fig1.write_image("plot_dept.png")
    fig2.write_image("plot_role.png")
    
    # Image 1 placement
    pdf.image("plot_dept.png", x=10, y=40, w=180)
    
    # Descent spacing: Image 2 starts much lower (y=150) to avoid overlap
    pdf.image("plot_role.png", x=50, y=150, w=110)
    
    os.remove("plot_dept.png")
    os.remove("plot_role.png")
    return pdf.output(dest='S').encode('latin-1')

# --- 4. APP INTERFACE ---
st.set_page_config(page_title="SNU | Brown Bag Portal", layout="wide")
init_db()

TIME_SLOTS = [dt_time(h, m).strftime("%I:%M %p") for h in range(8, 20) for m in (0, 15, 30, 45)]
DURATIONS = ["30 mins", "45 mins", "1 hour", "1.5 hours", "2 hours"]

if 'auth' not in st.session_state: st.session_state['auth'] = False
if 'dept' not in st.session_state: st.session_state['dept'] = None

st.title("🎓 Shiv Nadar University | Brown Bag Portal")
tabs = st.tabs(["📅 Public Schedule", "📊 Analytics", "🔐 Coordinator Access", "🛠️ Admin Control"])

conn = sqlite3.connect('ssn_research.db')
df = pd.read_sql_query("SELECT p.*, d.name as Dept FROM presentations p JOIN departments d ON p.dept_id = d.id", conn)
conn.close()

# --- TAB 1: PUBLIC SCHEDULE ---
with tabs[0]:
    search = st.text_input("🔍 Search Anything (Topic, Dept, Guide)...")
    filtered = df[df.apply(lambda r: search.lower() in str(r).lower(), axis=1)] if search else df
    for _, row in filtered.sort_values('date', ascending=False).iterrows():
        with st.expander(f"📌 {row['date']} | {row['Dept']} - {row['title']}"):
            st.write(f"**Presenter:** {row['presenter']} ({row['designation']}) | **Guide:** {row['guide_name']}")
            st.write(f"**Timing:** {row['time']} ({row['duration']}) | **Venue:** {row['venue_hall']}")
            st.info(row['abstract'])

# --- TAB 2: ANALYTICS ---
with tabs[1]:
    if not df.empty:
        st.subheader("Presentation Statistics")
        f1, f2 = get_plots(df)
        col1, col2 = st.columns(2)
        with col1: st.plotly_chart(f1, use_container_width=True)
        with col2: st.plotly_chart(f2, use_container_width=True)
    else:
        st.warning("No data available for analytics yet.")

# --- TAB 3: COORDINATOR ---
with tabs[2]:
    if not st.session_state['auth']:
        conn = sqlite3.connect('ssn_research.db'); d_df = pd.read_sql_query("SELECT * FROM departments", conn); conn.close()
        dept_choice = st.selectbox("Select Dept", d_df['name'].tolist() if not d_df.empty else ["No Depts"])
        pass_in = st.text_input("Password", type="password")
        if st.button("Login"):
            with st.spinner("⏳ Verifying..."):
                if not d_df.empty and pass_in == d_df[d_df['name']==dept_choice]['password'].values[0]:
                    st.session_state['auth'], st.session_state['dept'] = True, dept_choice
                    st.rerun()
                else: st.error("Invalid Credentials.")
    else:
        st.subheader(f"Coordinator: {st.session_state['dept']}")
        if st.button("Logout"): st.session_state['auth'] = False; st.rerun()
        
        c_mode = st.radio("Mode", ["Add New", "Manage Presentations"], horizontal=True)
        if c_mode == "Add New":
            with st.form("add_form"):
                pn, pr, pg = st.text_input("Presenter"), st.selectbox("Role", ["Faculty", "Scholar", "Student"]), st.text_input("Guide Name"), st.text_input("Meeting Link")
                pt, pa = st.text_input("Title"), st.text_area("Abstract")
                c1, c2, c3, c4 = st.columns(4)
                pdte, ptime = c1.date_input("Date"), c2.selectbox("Time", TIME_SLOTS)
                pdur, phall = c3.selectbox("Duration", DURATIONS), c4.text_input("Hall")
                if st.form_submit_button("Submit"):
                    with st.spinner("⏳ Saving..."):
                        conn = sqlite3.connect('ssn_research.db')
                        did = conn.execute("SELECT id FROM departments WHERE name=?", (st.session_state['dept'],)).fetchone()[0]
                        conn.execute("INSERT INTO presentations (presenter,designation,guide_name, meeting_link, title,abstract,date,time,duration,venue_hall,dept_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                     (pn,pr,pg,pt,pa,str(pdte),ptime,pdur,phall,did))
                        conn.commit(); conn.close(); delayed_refresh("Scheduled!")

# --- TAB 4: ADMIN CONTROL ---
with tabs[3]:
    if st.text_input("Admin Pass", type="password") == "admin123":
        adm = st.radio("Tool", ["Departments", "Subscribers", "Broadcast", "Reports"], horizontal=True)

        if adm == "Reports":
            if not df.empty:
                st.subheader("Generate Institutional Report")
                if st.button("Generate PDF"):
                    with st.spinner("⏳ Preparing PDF with charts..."):
                        pdf_data = generate_pdf_report(df)
                        st.download_button("📘 Download PDF Report", pdf_data, "SNU_Research_Report.pdf")
            else:
                st.error("Cannot generate report: No data found.")

        elif adm == "Subscribers":
            # Add/Delete Subscribers
            with st.form("sub_ui"):
                new_sub = st.text_input("Add Subscriber Email")
                if st.form_submit_button("Add"):
                    with st.spinner("⏳ Saving..."):
                        conn = sqlite3.connect('ssn_research.db')
                        try:
                            conn.execute("INSERT INTO subscriptions (email) VALUES (?)", (new_sub,))
                            conn.commit(); delayed_refresh("Subscriber Added.")
                        except: st.error("Already subscribed.")
                        finally: conn.close()
            
            st.divider()
            conn = sqlite3.connect('ssn_research.db')
            subs = pd.read_sql_query("SELECT * FROM subscriptions", conn); conn.close()
            for _, s in subs.iterrows():
                sc1, sc2 = st.columns([4,1])
                sc1.text(s['email'])
                if sc2.button("Remove", key=f"rs_{s['id']}"):
                    with st.spinner("⏳ Deleting..."):
                        conn = sqlite3.connect('ssn_research.db'); conn.execute("DELETE FROM subscriptions WHERE id=?", (s['id'],)); conn.commit(); conn.close(); delayed_refresh("Removed.")

        elif adm == "Departments":
            # Add/Edit Departments
            with st.expander("➕ Register Department"):
                with st.form("new_d"):
                    dn, dh, dc, dp = st.text_input("Name"), st.text_input("HOD Email"), st.text_input("Coord Email"), st.text_input("Pass", type="password")
                    if st.form_submit_button("Create"):
                        conn = sqlite3.connect('ssn_research.db'); conn.execute("INSERT INTO departments (name,head_email,coord_email,password) VALUES (?,?,?,?)",(dn,dh,dc,dp)); conn.commit(); conn.close(); delayed_refresh("Created.")

            conn = sqlite3.connect('ssn_research.db'); depts = pd.read_sql_query("SELECT * FROM departments", conn); conn.close()
            for _, r in depts.iterrows():
                with st.expander(f"Edit {r['name']}"):
                    with st.form(f"ed_{r['id']}"):
                        en = st.text_input("Name", r['name']); eh = st.text_input("HOD", r['head_email']); ep = st.text_input("Pass", r['password'])
                        if st.form_submit_button("Update"):
                            with st.spinner("⏳ Updating..."):
                                conn = sqlite3.connect('ssn_research.db'); conn.execute("UPDATE departments SET name=?, head_email=?, password=? WHERE id=?", (en,eh,ep,r['id'])); conn.commit(); conn.close(); delayed_refresh("Updated.")

        elif adm == "Broadcast":
            st.subheader("📢 Email Notifications")
            aud = st.selectbox("Target", ["Coordinators Only", "Include Subscribers"])
            sem, spa = st.text_input("Admin Gmail"), st.text_input("App Password", type="password")
            
            body = "SNU Research Presentation Schedule:\n\n"
            for _, r in df.iterrows():
                body += f"🔹 {r['title']}\n🗓️ {r['date']} | 🕒 {r['time']}\n👤 {r['presenter']} (Guide: {r['guide_name']})\n {r['Meeting Link']} 📍 {r['venue_hall']}\n\n"
            
            if st.button("🚀 Send Emails"):
                with st.spinner("⏳ Broadcasting..."):
                    conn = sqlite3.connect('ssn_research.db')
                    list_re = pd.read_sql_query("SELECT head_email, coord_email FROM departments", conn).values.flatten().tolist()
                    if "Include" in aud:
                        list_re += pd.read_sql_query("SELECT email FROM subscriptions", conn)['email'].tolist()
                    conn.close()
                    res = send_mail("Research Schedule Update", body, list_re, sem, spa)
                    if res == True: st.success("Broadcast successful!")
                    else: st.error(res)


