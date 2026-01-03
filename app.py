import os
import json
import re
import random
import urllib.parse
from datetime import date
from dotenv import load_dotenv
from PIL import Image
import fitz  # PyMuPDF
import streamlit as st
import google.generativeai as genai

# ==========================================
# 1. SETUP & CONFIG
# ==========================================
load_dotenv()
ENV_API_KEY = os.getenv("GOOGLE_API_KEY", "")

if ENV_API_KEY:
    genai.configure(api_key=ENV_API_KEY)

st.set_page_config(page_title="KlageHjelpen", page_icon="⚖️", layout="wide")

# ==========================================
# 2. VERIFISERT KONTAKTDATABASE
# ==========================================
VERIFIED_CONTACTS = {
    # --- ELEKTRONIKK ---
    "elkjop": {"email": "hello@elkjop.no", "navn": "Elkjøp"},
    "elkjøp": {"email": "hello@elkjop.no", "navn": "Elkjøp"},
    "power": {"email": "kundeservice@power.no", "navn": "Power"},
    "komplett": {"email": "kundeservice@komplett.no", "navn": "Komplett.no"},
    "netonnet": {"email": "kundeservice@netonnet.no", "navn": "NetOnNet"},
    "apple": {"email": "contactus.no@euro.apple.com", "navn": "Apple Store"},
    
    # --- MØBLER & HUS ---
    "ikea": {"web": "https://www.ikea.com/no/no/customer-service/contact-us/", "navn": "IKEA"},
    "jysk": {"email": "kundeservice@jysk.no", "navn": "JYSK"},
    "bohus": {"email": "kundeservice@bohus.no", "navn": "Bohus"},
    "skeidar": {"email": "netthandel@skeidar.no", "navn": "Skeidar"},
    "clas ohlson": {"email": "kundesenter@clasohlson.no", "navn": "Clas Ohlson"},
    "biltema": {"email": "kundeservice@biltema.no", "navn": "Biltema"},
    "jula": {"web": "https://www.jula.no/kundeservice/kontakt-oss/", "navn": "Jula"},
    
    # --- KLÆR ---
    "zalando": {"email": "service@zalando.no", "navn": "Zalando"},
    "xxl": {"email": "kundeservice@xxl.no", "navn": "XXL"},
    "hm": {"web": "https://www2.hm.com/no_no/customer-service/contact.html", "navn": "H&M"},
    
    # --- FLY & REISE ---
    "sas": {"web": "https://www.sas.no/kundeservice/kontakt/skjemaer/sertifikat-forsinket-innstilt-fly", "navn": "SAS", "advarsel": "Bruk skjema for EU261-krav."},
    "norwegian": {"web": "https://www.norwegian.com/no/reiseinformasjon/forsinkelser-og-kanselleringer/forsinkelser/", "navn": "Norwegian", "advarsel": "Bruk portalen deres for krav."},
    "widerøe": {"web": "https://www.wideroe.no/hjelp-og-kontakt/flight-claim", "navn": "Widerøe"},
    "ryanair": {"web": "https://onlineform.ryanair.com/no/no/eu-261", "navn": "Ryanair"},
    "vy": {"web": "https://www.vy.no/kundeservice/klage-og-erstatning", "navn": "Vy"},
    "ruter": {"web": "https://ruter.no/fa-hjelp-og-kontakt/kontaktskjema/", "navn": "Ruter"},
    
    # --- PARKERING ---
    "apcoa": {"web": "https://www.kontrollavgift.no/", "navn": "Apcoa / EuroPark"},
    "europark": {"web": "https://www.kontrollavgift.no/", "navn": "Apcoa / EuroPark"},
    "aimo": {"web": "https://www.aimopark.no/kontakt-oss/kontrollsanksjon/", "navn": "Aimo Park"},
    "easypark": {"email": "kundeservice@easypark.no", "navn": "EasyPark"},
    "riverty": {"web": "https://www.riverty.com/no-no/kundeservice/", "navn": "Riverty (Faktura)"}
}

CATEGORY_HINTS = {
    "Varekjøp": "Forbrukerkjøpsloven § 27 (5 års reklamasjonsfrist).",
    "Flyforsinkelse": "EU-forordning 261/2004 (Standardkompensasjon).",
    "Parkeringsbot": "Parkeringsforskriften & Avtaleloven § 36.",
    "Håndverkertjenester": "Håndverkertjenesteloven § 22.",
    "Annet": "Alminnelig avtalerett."
}

# ==========================================
# 3. HJELPEFUNKSJONER
# ==========================================

def get_best_contact_method(company_name_from_ai):
    if not company_name_from_ai: return None
    search_term = company_name_from_ai.lower().strip()
    for key, info in VERIFIED_CONTACTS.items():
        if key in search_term: return info
    return None

def extract_pdf_data(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    full_text = ""
    first_page_img = None
    for page in doc: 
        full_text += page.get_text() + "\n"
    if len(doc) > 0:
        page = doc.load_page(0)
        pix = page.get_pixmap()
        first_page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return full_text, first_page_img

def check_name_similarity(name_on_doc, user_name):
    # Hvis en av dem mangler, antar vi det er greit (f.eks manuell inntasting)
    if not name_on_doc or not user_name: return True
    if name_on_doc.lower() == "null" or name_on_doc.lower() == "none": return True
    
    doc_clean = re.sub(r'[^\w\s]', '', name_on_doc.lower()).split()
    user_clean = re.sub(r'[^\w\s]', '', user_name.lower()).split()
    match_found = False
    for part in user_clean:
        if part in doc_clean and len(part) > 2:
            match_found = True
            break
    return match_found

def clean_json_text(text):
    """Fjerner markdown code blocks hvis AI legger det til."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def generate_complaint(prompt: str, images=None) -> dict:
    model_name = "gemini-2.0-flash"
    generation_config = {"response_mime_type": "application/json"}
    
    inputs = [prompt]
    if images:
        if isinstance(images, list):
            inputs.extend(images)
        else:
            inputs.append(images)

    try:
        model = genai.GenerativeModel(model_name, generation_config=generation_config)
        response = model.generate_content(inputs)
        cleaned_text = clean_json_text(response.text)
        return json.loads(cleaned_text)
    except Exception as e:
        # Fallback
        try:
            fallback = "gemini-1.5-flash"
            model = genai.GenerativeModel(fallback, generation_config=generation_config)
            response = model.generate_content(inputs)
            cleaned_text = clean_json_text(response.text)
            return json.loads(cleaned_text)
        except:
            raise e

# ==========================================
# 4. SIDEBAR
# ==========================================
with st.sidebar:
    st.title("⚖️ KlageHjelpen")
    st.caption("Din tekstforfatter for reklamasjoner")
    st.header("👤 Innstillinger")
    rolle = st.radio("Jeg klager som:", ["Privatperson", "Bedrift"], index=0)
    st.markdown("---")
    mitt_navn = st.text_input("Ditt navn", placeholder="Ola Nordmann")
    min_epost = st.text_input("Din e-post", placeholder="ola@mail.no")
    with st.expander("🔒 Personvern", expanded=False):
        st.markdown("Vi lagrer ingen filer. Data sendes kryptert til AI for analyse og slettes fra minnet etterpå.")
    st.markdown("---")
    st.link_button("☕ Spander en kaffe", "[https://buymeacoffee.com/klagehjelpen](https://buymeacoffee.com/klagehjelpen)")

# ==========================================
# 5. HOVEDAPP
# ==========================================
st.header("Få hjelp til å skrive klagen din ✍️")

if "generated_complaint" not in st.session_state:
    st.session_state.generated_complaint = None
if "detected_company" not in st.session_state:
    st.session_state.detected_company = None
if "uploaded_filenames" not in st.session_state: 
    st.session_state.uploaded_filenames = []

if "random_placeholder" not in st.session_state:
    eksempler = [
        "F.eks: TV-en slår seg ikke på lenger...",
        "F.eks: Flyet var 4 timer forsinket...",
        "F.eks: Glidelåsen røk etter 2 måneder...",
        "F.eks: Parkeringsbot selv om jeg betalte..."
    ]
    st.session_state.random_placeholder = random.choice(eksempler)

tab_auto, tab_manuell = st.tabs(["✨ Automatisk (Last opp dokumenter)", "✍️ Manuell (Skriv selv)"])

# --- TAB 1: AUTOMATISK ---
with tab_auto:
    st.info("🔒 **Trygg opplasting:** Dokumentene analyseres midlertidig og lagres ikke.", icon="🛡️")
    c1, c2 = st.columns([1, 1])
    with c1:
        uploaded_files = st.file_uploader("Last opp filer", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)
    with c2:
        hendelsesdato = st.date_input("Når skjedde dette?", value=date.today())
        feil_beskrivelse = st.text_area("Kort beskrivelse", height=100, placeholder=st.session_state.random_placeholder)
        losning = st.selectbox("Ønsket løsning", ["Kostnadsfri reparasjon", "Ny vare (omlevering)", "Pengene tilbake (heving)", "Prisavslag", "Erstatning", "Usikker - la AI vurdere"])
    tone = st.radio("Tonefall:", ["Saklig (Anbefalt)", "Vennlig", "Veldig formell"], horizontal=True)

    if st.button("Generer klageutkast 🚀", type="primary"):
        if not uploaded_files:
            st.error("⚠️ Du må laste opp minst én fil.")
            st.stop()
        
        try:
            st.session_state.uploaded_filenames = [f.name for f in uploaded_files]
            all_images = []
            combined_text = ""
            for uploaded_file in uploaded_files:
                if uploaded_file.type == "application/pdf":
                    text, img = extract_pdf_data(uploaded_file)
                    combined_text += f"\nTEXT FROM {uploaded_file.name}:\n{text}"
                    if img: all_images.append(img)
                else:
                    img = Image.open(uploaded_file)
                    all_images.append(img)
            
            prompt_auto = f"""
            Du er en profesjonell, norsk klagehjelper.
            DOKUMENT-TEKST: {combined_text[:6000]}
            OPPGAVE: 1. Analyser vedlagte bilder/dokumenter. 2. Identifiser SELSKAPSNAVN og PERSONNAVN. 3. Skriv reklamasjon.
            VIKTIG: Hele brevet SKAL være på NORSK bokmål. Avslutt med "Med vennlig hilsen, [Ditt Navn]". IKKE gjenta kontaktinfo to ganger.
            DATA: Dato: {hendelsesdato}, Problem: {feil_beskrivelse}, Krav: {losning}, Navn: {mitt_navn}, Rolle: {rolle}, Tone: {tone}.
            JUSS: Elektronikk=5 år (§27). Fly=EU261. Parkering=Forskrift. Svarfrist=14 dager.
            OUTPUT JSON: {{ "selskapsnavn_funnet": "string", "navn_paa_kvittering": "string (eller null)", "emne": "string", "mottaker_epost_gjetning": "string", "brødtekst": "string" }}
            """
            with st.spinner("Analyserer..."):
                res = generate_complaint(prompt_auto, all_images)
                st.session_state.generated_complaint = res
                st.session_state.detected_company = res.get("selskapsnavn_funnet", "")
        except Exception as e:
            st.error(f"Feil: {e}")

# --- TAB 2: MANUELL ---
with tab_manuell:
    kategori_man = st.selectbox("Kategori", list(CATEGORY_HINTS.keys()))
    st.info(f"⚖️ {CATEGORY_HINTS[kategori_man]}")
    c1, c2 = st.columns(2)
    with c1:
        unique_companies = sorted(list(set([v["navn"] for k, v in VERIFIED_CONTACTS.items()])))
        valgt_selskap_navn = st.selectbox("Velg selskap", ["Annet / Skriv selv"] + unique_companies)
        custom_company = ""
        if valgt_selskap_navn == "Annet / Skriv selv":
            custom_company = st.text_input("Skriv inn selskapsnavn")
    with c2:
        desc_man = st.text_area("Hva har skjedd?", height=100, placeholder="F.eks: TVen ble svart...")
        req_man = st.selectbox("Hva krever du?", ["Kostnadsfri reparasjon", "Ny vare (omlevering)", "Pengene tilbake (heving)", "Prisavslag", "Erstatning", "Usikker - la AI vurdere"])

    if st.button("Skriv klage (Manuelt)"):
        company_for_prompt = custom_company if custom_company else valgt_selskap_navn
        found_info = None
        for k, v in VERIFIED_CONTACTS.items():
            if v["navn"] == valgt_selskap_navn:
                found_info = v
                break
        forced_email = found_info.get("email", "") if found_info else ""
        st.session_state.uploaded_filenames = [] # Nullstill filer

        prompt_man = f"""
        Skriv en klage på NORSK. Avsender: {mitt_navn}. Mottaker: {company_for_prompt}. Sak: {desc_man}. Krav: {req_man}. Lov: {CATEGORY_HINTS[kategori_man]}.
        VIKTIG: Norsk bokmål. Avslutt med "Med vennlig hilsen, [Navn]". Ingen dobbel signatur.
        OUTPUT JSON: {{ "selskapsnavn_funnet": "{company_for_prompt}", "navn_paa_kvittering": null, "emne": "string", "mottaker_epost_gjetning": "{forced_email}", "brødtekst": "string" }}
        """
        try:
            with st.spinner("Skriver..."):
                res = generate_complaint(prompt_man)
                st.session_state.generated_complaint = res
                st.session_state.detected_company = company_for_prompt
        except Exception as e:
            st.error(f"Feil: {e}")

# ==========================================
# 6. RESULTATVISNING (ROBUST)
# ==========================================
if st.session_state.generated_complaint:
    data = st.session_state.generated_complaint
    
    # SIKKERHETSSJEKK: Er data faktisk en ordbok (dict)?
    if isinstance(data, dict):
        detected_name = st.session_state.detected_company
        
        # Navnesjekk
        doc_name = data.get("navn_paa_kvittering")
        if doc_name and mitt_navn:
            if not check_name_similarity(doc_name, mitt_navn):
                st.error(f"⚠️ Navnevarsel: Dokumentet ser ut til å tilhøre **{doc_name}**, men du heter **{mitt_navn}**.", icon="🚫")

        contact_info = get_best_contact_method(detected_name)
        
        st.markdown("---")
        st.subheader("📍 Mottaker & Sendingsmetode")
        
        final_email = ""
        web_link = ""

        if contact_info:
            st.success(f"✅ Identifisert selskap: **{contact_info.get('navn', detected_name)}**")
            if "advarsel" in contact_info:
                st.warning(f"⚠️ **OBS:** {contact_info['advarsel']}")
            
            if "web" in contact_info:
                web_link = contact_info["web"]
                st.info(f"🌐 Dette selskapet bruker primært webskjema.")
                st.link_button(f"Gå til {contact_info['navn']} sitt skjema ↗️", web_link)
                st.caption("👇 1. Kopier teksten under. 2. Lim inn i skjemaet.")
                if "email" in contact_info:
                    final_email = contact_info["email"]
            else:
                final_email = contact_info.get("email", "")
        else:
            st.warning(f"⚠️ Fant ikke '{detected_name}' i databasen. Sjekk e-posten under.")
            final_email = data.get("mottaker_epost_gjetning", "")

        if not web_link:
            c1, c2 = st.columns([1, 1])
            with c1: user_email = st.text_input("Mottaker e-post", value=final_email)
            with c2: user_subject = st.text_input("Emnefelt", value=data.get("emne", ""))
        else:
            user_subject = st.text_input("Emnefelt (til skjema)", value=data.get("emne", ""))
            user_email = final_email

        st.markdown("### 📝 Klagebrev")
        user_body = st.text_area("Innhold (Redigerbar)", value=data.get("brødtekst", ""), height=400)
        
        st.markdown("---")
        st.subheader("✅ Sjekkliste før sending")
        c1, c2 = st.columns(2)
        check_rec = c1.checkbox("Mottaker/Skjema er korrekt")
        check_txt = c2.checkbox("Mine detaljer stemmer")
        is_ready = check_rec and check_txt
        
        st.markdown("---")
        if web_link:
            st.info("👈 Kopier teksten, og bruk knappen lenger opp.")
        elif user_email and "@" in user_email:
            if st.session_state.uploaded_filenames:
                files_str = ", ".join(st.session_state.uploaded_filenames)
                st.info(f"📎 **Husk:** Legg ved disse filene manuelt: **{files_str}**", icon="⚠️")
            else:
                st.info("📎 **Husk:** Du må legge ved vedlegg manuelt.", icon="⚠️")

            safe_s = urllib.parse.quote(user_subject)
            safe_b = urllib.parse.quote(user_body)
            mailto = f"mailto:{user_email}?subject={safe_s}&body={safe_b}"
            
            st.link_button("📧 Åpne i E-postprogram", mailto, type="primary", use_container_width=True, disabled=not is_ready)
            if not is_ready:
                st.caption("🛑 Huk av sjekkpunktene over for å aktivere knappen.")
        else:
            st.warning("Mangler e-postadresse.")
    
    else:
        st.error("Kunne ikke lese svaret fra AI. Prøv å trykke på knappen en gang til.")
