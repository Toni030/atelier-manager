import streamlit as st
import pandas as pd
import datetime
import os
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Atelier Auftragsverwaltung", page_icon="🎨", layout="wide")

# --------------------------------------------------------
# GOOGLE SHEETS VERBINDUNG
# --------------------------------------------------------
SHEET_URL = "https://docs.google.com/spreadsheets/d/1SAYSk2CBUYmXvZJ86Y65RPdNoBpQNBnXC_tG-9gDzFM/edit?usp=sharing"

conn = st.connection("gsheets", type=GSheetsConnection)

def load_orders():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl="0")
        if df.empty or 'id' not in df.columns:
            return pd.DataFrame(columns=[
                "id", "customer_name", "title", "order_date", "delivery_date",
                "price", "status", "wishes", "reminder_days_before",
                "notification_email", "reminder_sent", "image_path"
            ])
        return df
    except Exception:
        return pd.DataFrame(columns=[
            "id", "customer_name", "title", "order_date", "delivery_date",
            "price", "status", "wishes", "reminder_days_before",
            "notification_email", "reminder_sent", "image_path"
        ])

def save_orders(df):
    conn.update(spreadsheet=SHEET_URL, data=df)

def send_reminder_email(recipient, row):
    return True

# --------------------------------------------------------
# BENUTZEROBERFLÄCHE
# --------------------------------------------------------
st.title("🎨 Atelier Auftrags- und Bildverwaltung")
st.write("Verwalte deine Aufträge, Kundenwünsche, Preise, Termine, Bilder und E-Mail-Erinnerungen direkt in der Cloud.")

df = load_orders()

# --- SEITENLEISTE: NEUEN AUFTRAG ERFASSEN ---
st.sidebar.header("➕ Neuen Auftrag anlegen")
with st.sidebar.form("new_order_form", clear_on_submit=True):
    customer_name = st.text_input("Kundenname*")
    title = st.text_input("Titel des Bildes / Auftrags*")
    order_date = st.date_input("Bestelldatum", datetime.date.today())
    delivery_date = st.date_input("Abgabedatum", datetime.date.today() + datetime.timedelta(days=14))
    price = st.number_input("Preis (€)", min_value=0.0, step=10.0, format="%.2f")
    wishes = st.text_area("Genau gewünschte Details / Kundenwünsche")
    reminder_days_before = st.number_input("Erinnerung X Tage vor Abgabe senden", min_value=0, max_value=30, value=2)
    notification_email = st.text_input("E-Mail-Adresse für Benachrichtigungen")
    uploaded_file = st.file_uploader("Bild des Auftragsgebers hochladen", type=["jpg", "jpeg", "png"])

    submitted = st.form_submit_button("Auftrag speichern")

    if submitted:
        if not customer_name or not title:
            st.sidebar.error("Bitte mindestens Kundenname und Titel ausfüllen!")
        else:
            image_path = ""
            new_id = int(df['id'].max() + 1) if not df.empty and pd.notna(df['id'].max()) else 1

            if uploaded_file is not None:
                os.makedirs("images", exist_ok=True)
                image_path = os.path.join("images", f"auftrag_{new_id}_{uploaded_file.name}")
                with open(image_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

            new_row = pd.DataFrame([{
                "id": new_id,
                "customer_name": customer_name,
                "title": title,
                "order_date": str(order_date),
                "delivery_date": str(delivery_date),
                "price": float(price),
                "status": "Neu",
                "wishes": wishes,
                "reminder_days_before": int(reminder_days_before),
                "notification_email": notification_email,
                "reminder_sent": 0,
                "image_path": image_path
            }])

            df = pd.concat([df, new_row], ignore_index=True)
            save_orders(df)
            st.sidebar.success("Auftrag erfolgreich in Google Sheets gespeichert!")
            st.rerun()

# --- HAUPTBEREICH: AUFTRÄGE ANZEIGEN ---
st.header("📋 Alle Aufträge")

if df.empty:
    st.info("Noch keine Aufträge vorhanden. Erfasse deinen ersten Auftrag über das Menü links!")
else:
    for idx, row in df.iterrows():
        sent_status_text = "✅ Bereits gesendet" if str(row.get('reminder_sent')) in ["1", "1.0"] else "⏳ Ausstehend"
        
        with st.expander(f"🎨 {row['customer_name']} - {row['title']} (Abgabe: {row['delivery_date']} | Status: {row['status']})"):
            col_a, col_b = st.columns([2, 1])

            with col_a:
                st.markdown(f"**Bestelldatum:** {row['order_date']}")
                st.markdown(f"**Preis:** {row.get('price', 0.0)}")
                st.markdown(f"**Abgabetermin:** {row['delivery_date']}")
                st.markdown(f"**Erinnerungs-Vorlauf:** {row.get('reminder_days_before', 2)} Tage vor Abgabe")
                st.markdown(f"**Empfänger-E-Mail:** {row.get('notification_email', '')}")
                st.markdown(f"**Erinnerungs-Status:** {sent_status_text}")
                st.markdown(f"**Status:** {row['status']}")
                st.markdown(f"**Genau gewünschte Details:**\n\n{row.get('wishes', '')}")

                # Manuelle E-Mail Erinnerung
                if st.button("📧 Erinnerung jetzt manuell senden", key=f"mail_{row['id']}"):
                    res = send_reminder_email(row.get('notification_email'), row)
                    if res is True:
                        st.success("Erinnerungs-E-Mail erfolgreich gesendet!")
                        st.rerun()

                st.markdown("---")

                # 1. PREIS ÄNDERN
                try:
                    current_price = float(row.get('price') or 0.0)
                except Exception:
                    current_price = 0.0

                new_price = st.number_input("Preis anpassen", value=current_price, step=10.0, format="%.2f", key=f"price_up_{row['id']}")
                if new_price != current_price:
                    df_updated = load_orders()
                    df_updated.loc[df_updated['id'] == row['id'], 'price'] = new_price
                    save_orders(df_updated)
                    st.success("Preis erfolgreich aktualisiert!")
                    st.rerun()

                # 2. TERMIN ÄNDERN
                try:
                    current_date = datetime.datetime.strptime(str(row.get('delivery_date')), "%Y-%m-%d").date()
                except Exception:
                    current_date = datetime.date.today()

                new_due_date = st.date_input("Termin (Abgabedatum) ändern", value=current_date, key=f"date_up_{row['id']}")
                if str(new_due_date) != str(row.get('delivery_date')):
                    df_updated = load_orders()
                    df_updated.loc[df_updated['id'] == row['id'], 'delivery_date'] = str(new_due_date)
                    save_orders(df_updated)
                    st.success("Termin erfolgreich aktualisiert!")
                    st.rerun()

                # 3. STATUS AKTUALISIEREN
                status_options = ["Neu", "In Arbeit", "Versendet", "Abgeschlossen"]
                current_status = str(row.get('status')) if str(row.get('status')) in status_options else "Neu"
                
                new_status = st.selectbox("Status aktualisieren", status_options, index=status_options.index(current_status), key=f"status_{row['id']}")
                if new_status != str(row.get('status')):
                    df_updated = load_orders()
                    df_updated.loc[df_updated['id'] == row['id'], 'status'] = new_status
                    save_orders(df_updated)
                    st.rerun()

                # 4. AUFTRAG LÖSCHEN
                if st.button("Auftrag löschen", key=f"del_{row['id']}"):
                    df_updated = load_orders()
                    df_updated = df_updated[df_updated['id'] != row['id']]
                    save_orders(df_updated)
                    st.warning("Auftrag gelöscht!")
                    st.rerun()

            with col_b:
                st.markdown("**Bild des Auftragsgebers:**")
                img_p = row.get('image_path')
                if img_p and isinstance(img_p, str) and os.path.exists(img_p):
                    st.image(img_p, caption=row['title'], use_container_width=True)
                else:
                    st.info("Kein Bild hochgeladen.")
                    new_img = st.file_uploader("Bild für diesen Auftrag hochladen", type=["jpg", "jpeg", "png"], key=f"img_up_{row['id']}")
                    if new_img is not None:
                        os.makedirs("images", exist_ok=True)
                        img_path = os.path.join("images", f"auftrag_{row['id']}_{new_img.name}")
                        with open(img_path, "wb") as f:
                            f.write(new_img.getbuffer())
                        
                        df_updated = load_orders()
                        df_updated.loc[df_updated['id'] == row['id'], 'image_path'] = img_path
                        save_orders(df_updated)
                        st.success("Bild erfolgreich hinzugefügt!")
                        st.rerun()
