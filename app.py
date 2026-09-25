import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# Setup Datenbank und Ordner
DB_FILE = "kuenstler_auftraege.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_date TEXT,
            customer_name TEXT,
            title TEXT,
            price REAL,
            wishes TEXT,
            delivery_date TEXT,
            status TEXT,
            image_path TEXT,
            reminder_days_before INTEGER,
            notification_email TEXT,
            reminder_sent INTEGER DEFAULT 0
        )
    ''')
    for col_def in [
        ("reminder_days_before", "INTEGER DEFAULT 2"),
        ("notification_email", "TEXT"),
        ("reminder_sent", "INTEGER DEFAULT 0")
    ]:
        try:
            cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_def[0]} {col_def[1]}")
        except:
            pass
    conn.commit()
    conn.close()

init_db()

st.set_page_config(page_title="Kunstmaler Auftragsmanager", page_icon="🎨", layout="wide")

st.title("🎨 Atelier Auftrags- und Bildverwaltung")
st.markdown("Verwalte deine Aufträge, Kundenwünsche, Preise, Termine, Bilder und automatische E-Mail-Erinnerungen.")

# Sidebar für E-Mail Einstellungen (angepasst an art-molina.ch und Port 465)
st.sidebar.markdown("---")
st.sidebar.subheader("📧 E-Mail Erinnerungs-Setup")
st.sidebar.markdown("Zugangsdaten für art-molina.ch (Port 465 SSL/TLS)")
smtp_server = st.sidebar.text_input("SMTP Server", value="art-molina.ch")
smtp_port = st.sidebar.text_input("SMTP Port", value="465")
sender_email = st.sidebar.text_input("Deine E-Mail-Adresse", value="info@art-molina.ch")
sender_password = st.sidebar.text_input("E-Mail Passwort", type="password", value="")

# Sidebar Navigation
menu = st.sidebar.selectbox("Navigation", ["Übersicht & Dashboard", "Neuen Auftrag erfassen", "Auftragsliste & Verwaltung"])

def add_order(order_date, customer_name, title, price, wishes, delivery_date, status, image_path, reminder_days_before, notification_email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (order_date, customer_name, title, price, wishes, delivery_date, status, image_path, reminder_days_before, notification_email, reminder_sent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    ''', (order_date, customer_name, title, price, wishes, delivery_date, status, image_path, reminder_days_before, notification_email))
    conn.commit()
    conn.close()

def get_all_orders():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM orders ORDER BY delivery_date ASC", conn)
    conn.close()
    return df

def update_status(order_id, new_status):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

def mark_reminder_sent(order_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET reminder_sent = 1 WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

def delete_order(order_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT image_path FROM orders WHERE id = ?", (order_id,))
    res = cursor.fetchone()
    if res and res[0] and os.path.exists(res[0]):
        try:
            os.remove(res[0])
        except:
            pass
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

def send_reminder_email(receiver_email, order_row):
    if not sender_email or not sender_password:
        return "Fehler: Absender-E-Mail oder Passwort in der Sidebar nicht ausgefüllt!"
    if not receiver_email:
        return "Fehler: Keine Empfänger-E-Mail für diesen Auftrag hinterlegt!"
        
    msg = MIMEMultipart()
    msg['Subject'] = f"🎨 Atelier Erinnerung: Abgabetermin für '{order_row['title']}' ({order_row['customer_name']})"
    msg['From'] = sender_email
    msg['To'] = receiver_email
    
    body = f"""Hallo!

Dies ist deine automatische Erinnerung. Der Abgabetermin rückt näher!

- Kunde: {order_row['customer_name']}
- Titel / Thema: {order_row['title']}
- Preis: {order_row['price']:,.2f}
- Bestelldatum: {order_row['order_date']}
- Auslieferungstermin: {order_row['delivery_date']} (in {order_row['reminder_days_before']} Tagen oder weniger fällig)
- Status: {order_row['status']}

Gewünschte Details:
{order_row['wishes']}

Das zugehörige Bild des Auftraggebers findest du im Anhang dieser E-Mail.
"""
    msg.attach(MIMEText(body, 'plain'))
    
    image_path = order_row['image_path']
    if image_path and os.path.exists(image_path):
        with open(image_path, 'rb') as f:
            img_data = f.read()
        img = MIMEImage(img_data, name=os.path.basename(image_path))
        msg.attach(img)
        
    try:
        port_int = int(smtp_port)
        # Port 465 nutzt direkt SSL/TLS (SMTP_SSL)
        if port_int == 465:
            server = smtplib.SMTP_SSL(smtp_server, port_int)
        else:
            server = smtplib.SMTP(smtp_server, port_int)
            server.starttls()
            
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        mark_reminder_sent(order_row['id'])
        return True
    except Exception as e:
        return str(e)

if menu == "Übersicht & Dashboard":
    df = get_all_orders()
    if df.empty:
        st.info("Noch keine Aufträge vorhanden. Erfasse deinen ersten Auftrag über das Menü!")
    else:
        col1, col2, col3 = st.columns(3)
        total_orders = len(df)
        total_revenue = df['price'].sum()
        open_orders = len(df[df['status'] != 'Abgeschlossen'])
        
        col1.metric("Gesamte Aufträge", total_orders)
        col2.metric("Offene Aufträge", open_orders)
        col3.metric("Gesamtumsatz", f"{total_revenue:,.2f} CHF/EUR")
        
        st.markdown("---")
        st.subheader("⏰ Fällige & anstehende Erinnerungen (Vorlauf-Check)")
        
        today = datetime.today().date()
        open_df = df[df['status'] != 'Abgeschlossen'].copy()
        
        reminder_due_count = 0
        if not open_df.empty:
            for idx, row in open_df.iterrows():
                try:
                    delivery_dt = datetime.strptime(row['delivery_date'], '%Y-%m-%d').date()
                    days_before = int(row['reminder_days_before']) if pd.notnull(row['reminder_days_before']) else 2
                    reminder_trigger_date = delivery_dt - timedelta(days=days_before)
                    
                    if today >= reminder_trigger_date and row['reminder_sent'] == 0:
                        reminder_due_count += 1
                        st.warning(f"⚠️ **Erinnerung fällig!** Auftrag **{row['title']}** für **{row['customer_name']}** (Abgabe am **{row['delivery_date']}**). Der eingestellte Vorlauf betrug {days_before} Tage.")
                        if st.button(f"📧 Jetzt Erinnerung senden für {row['customer_name']}", key=f"dash_mail_{row['id']}"):
                            res = send_reminder_email(row['notification_email'], row)
                            if res is True:
                                st.success(f"Erinnerung für {row['customer_name']} erfolgreich versendet!")
                                st.rerun()
                            else:
                                st.error(f"Fehler beim Senden: {res}")
                except Exception as ex:
                    pass
                    
        if reminder_due_count == 0:
            st.success("Aktuell sind keine Erinnerungen fällig. Alles im grünen Bereich!")
            
        st.markdown("---")
        st.subheader("📅 Alle anstehenden Abgabetermine")
        for idx, row in open_df.iterrows():
            st.markdown(f"- **{row['customer_name']}** – *{row['title']}* | Abgabe: **{row['delivery_date']}** (Erinnerung {row['reminder_days_before']} Tage vorher)")

elif menu == "Neuen Auftrag erfassen":
    st.subheader("Neuen Auftrags-Eintrag erstellen")
    
    with st.form("order_form"):
        col1, col2 = st.columns(2)
        with col1:
            order_date = st.date_input("Eingang der Bestellung", value=datetime.today())
            customer_name = st.text_input("Kundenname / Kontakt")
            title = st.text_input("Was wurde bestellt (Bildtitel / Thema)")
            price = st.number_input("Preis des Bildes", min_value=0.0, step=50.0, format="%.2f")
            reminder_days_before = st.number_input("Erinnerung X Tage vor Abgabetermin senden", min_value=1, max_value=30, value=2, step=1)
        
        with col2:
            delivery_date = st.date_input("Auslieferungs- / Abgabetermin", value=datetime.today())
            status = st.selectbox("Status", ["Neu", "In Arbeit", "Versendet", "Abgeschlossen"])
            notification_email = st.text_input("Deine E-Mail für die Erinnerung", value=sender_email)
            uploaded_file = st.file_uploader("Bild des Auftragsgebers hochladen", type=["jpg", "jpeg", "png"])
        
        if uploaded_file is not None:
            st.image(uploaded_file, caption="Vorschau des Bildes vom Auftraggeber", width=300)
        
        wishes = st.text_area("Genau gewünschte Details (Farben, Größe, Motivwünsche, Besonderheiten)")
        
        submitted = st.form_submit_button("Auftrag speichern")
        if submitted:
            image_path = None
            if uploaded_file is not None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_filename = f"{timestamp}_{uploaded_file.name}"
                image_path = os.path.join(UPLOAD_DIR, image_filename)
                with open(image_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
            
            add_order(
                str(order_date),
                customer_name,
                title,
                price,
                wishes,
                str(delivery_date),
                status,
                image_path,
                reminder_days_before,
                notification_email
            )
            st.success("Auftrag und Vorlauf-Erinnerung erfolgreich gespeichert!")

elif menu == "Auftragsliste & Verwaltung":
    st.subheader("Alle Aufträge im Detail & Erinnerungen verwalten")
    df = get_all_orders()
    
    if df.empty:
        st.info("Keine Aufträge vorhanden.")
    else:
        search = st.text_input("Suche nach Kunde oder Titel...")
        if search:
            df = df[df['customer_name'].str.contains(search, case=False, na=False) | df['title'].str.contains(search, case=False, na=False)]
        
        for idx, row in df.iterrows():
            sent_status_text = "✅ Bereits gesendet" if row['reminder_sent'] == 1 else "⏳ Ausstehend"
            with st.expander(f"🎨 {row['customer_name']} – {row['title']} (Abgabe: {row['delivery_date']} | Erinnerung: {row['reminder_days_before']} Tage vorher | {sent_status_text})"):
                col_a, col_b = st.columns([2, 1])
                
                with col_a:
                    st.markdown(f"**Bestelldatum:** {row['order_date']}")
                    st.markdown(f"**Preis:** {row['price']:,.2f}")
                    st.markdown(f"**Abgabetermin:** {row['delivery_date']}")
                    st.markdown(f"**Erinnerungs-Vorlauf:** {row['reminder_days_before']} Tage vor Abgabe")
                    st.markdown(f"**Empfänger-E-Mail:** {row['notification_email']}")
                    st.markdown(f"**Erinnerungs-Status:** {sent_status_text}")
                    st.markdown(f"**Status:** {row['status']}")
                    st.markdown(f"**Genau gewünschte Details:**\n> {row['wishes']}")
                    
                    if st.button("📧 Erinnerung jetzt manuell senden", key=f"mail_{row['id']}"):
                        res = send_reminder_email(row['notification_email'], row)
                        if res is True:
                            st.success("Erinnerungs-E-Mail mit Bild wurde erfolgreich gesendet!")
                            st.rerun()
                        else:
                            st.error(f"Fehler beim Senden: {res}")

                    new_status = st.selectbox("Status aktualisieren", ["Neu", "In Arbeit", "Versendet", "Abgeschlossen"], index=["Neu", "In Arbeit", "Versendet", "Abgeschlossen"].index(row['status']), key=f"status_{row['id']}")
                    if new_status != row['status']:
                        update_status(row['id'], new_status)
                        st.rerun()
                        
                    if st.button("Auftrag löschen", key=f"del_{row['id']}"):
                        delete_order(row['id'])
                        st.warning("Auftrag gelöscht!")
                        st.rerun()

                with col_b:
                    st.markdown("**Bild des Auftragsgebers:**")
                    if row.get('image_path') and isinstance(row['image_path'], str) and os.path.exists(row['image_path']):
                        st.image(row['image_path'], caption=row['title'], use_container_width=True)
                    else:
                        st.info("Kein Bild hochgeladen.")
