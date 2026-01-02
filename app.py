import os
import json
import re
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
# 2. VERIFISERT KONTAKTDATABASE (SKJERPET!)
# ==========================================
VERIFIED_CONTACTS = {
    # --- FLYSELSKAP (Direktelenker til kravskjema) ---
    "sas": {
        "web": "https://www.sas.no/kundeservice/kontakt/skjemaer/sertifikat-forsinket-innstilt-fly",
        "navn": "SAS",
        "advarsel": "Bruk dette skjemaet for EU261-kompensasjon."
    },
    "norwegian": {
        "web": "https://www.norwegian.com/no/reiseinformasjon/forsinkelser-og-kanselleringer/forsinkelser/",
        "navn": "Norwegian",
        "advarsel": "Norwegian krever at du velger refusjon/krav via denne portalen."
    },
    "widerøe": {
        "web": "https://www.wideroe.no/hjelp-og-kontakt/flight-claim",
        "navn": "Widerøe",
        "advarsel": "Bruk Widerøes eget skjema for refusjon og erstatning."
    },
    "ryanair": {
        "web": "https://onlineform.ryanair.com/no/no/eu-261",
        "navn": "Ryanair",
        "advarsel": "Ryanair godtar KUN sitt eget webskjema (EU261)."
    },
    "wizz": {
        "web": "https://wizzair.com/en-gb/information-and-services/prices-discounts/refunds-and-compensations",
        "navn": "Wizz Air",
        "advarsel": "Du må logge inn på din Wizz-konto for å sende krav."
    },
    "klm": {
        "web": "https://www.klm.no/en/information/refund-compensation",
        "navn": "KLM",
        "advarsel": "KLM har en egen portal for 'Refund and compensation'."
    },
    "lufthansa": {
        "web": "https://www.lufthansa.com/no/en/feedback",
        "navn": "Lufthansa",
        "advarsel": "Velg 'Flight disruption' i skjemaet deres."
    },
    "air france": {
        "web": "https://wwws.airfrance.no/en/claim",
        "navn": "Air France",
        "advarsel": "Bruk deres online 'Claim'-portal."
    },
    "finnair": {
        "web": "https://www.finnair.com/no-en/customer-care/feedback-and-claims",
        "navn": "Finnair",
        "advarsel": "Velg 'Give feedback or make a claim'."
    },
    "british airways": {
        "web": "https://www.britishairways.com/content/information/delayed-or-cancelled-flights/compensation",
        "navn": "British Airways",
        "advarsel": "Bruk skjemaet under 'Claim compensation'."
    },
    "icelandair": {
        "web": "https://www.icelandair.com/support/contact-us/claims/",
        "navn": "Icelandair",
        "advarsel": "Direktelink til deres krav-portal."
    },
    "iberia": {
        "web": "https://www.iberia.com/no/customer-relations/",
        "navn": "Iberia",
        "advarsel": "Gå via 'Customer Relations' -> 'Claims'."
    },
    "qatar": {
        "web": "https://www.qatarairways.com/en/help.html#feedback",
        "navn": "Qatar Airways",
        "advarsel": "Velg 'Feedback' og deretter 'Claim'."
    },
    "emirates": {
        "web": "https://www.emirates.com/no/english/help/forms/complaint/",
        "navn": "Emirates",
        "advarsel": "Bruk skjemaet for 'Complaint/Feedback'."
    },
    "turkish": {
        "web": "https://www.turkishairlines.com/en-no/any-questions/customer-relations/feedback/",
        "navn": "Turkish Airlines",
        "advarsel": "Du må opprette en 'Feedback' sak."
    },

    # --- PARKERING (Direktelenker til klage) ---
    "apcoa": {"web": "https://www.kontrollavgift.no/", "navn": "Apcoa/Europark (Kontrollavgift.no)"},
    "europark": {"web": "https://www.kontrollavgift.no/", "navn": "Apcoa/Europark (Kontrollavgift.no)"},
    "aimo": {"web": "https://www.aimopark.no/kontakt-oss/kontrollsanksjon/", "navn": "Aimo Park"},
    "onepark": {"web": "https://onepark.no/klage/", "navn": "ONEPARK"},
    "easypark": {"email": "kundeservice@easypark.no", "navn": "EasyPark"},
    "riverty": {"web": "https://www.riverty.com/no-no/kundeservice/", "navn": "Riverty (Faktura)", "advarsel": "Gjelder ofte selve betalingen/fakturaen."},

    # --- VAREKJØP (Her er e-post ofte OK, men web er bedre for noen) ---
    "elkjop": {"email": "kundesenter@elkjop.no", "navn": "Elkjøp Kundeservice"},
    "elkjøp": {"email": "kundesenter@elkjop.no", "navn": "Elkjøp Kundeservice"},
    "power": {"email": "kundeservice@power.no", "navn": "Power Kundeservice"},
    "komplett": {"email": "kundeservice@komplett.no", "navn": "Komplett.no"},
    "netonnet": {"email": "kundeservice@netonnet.no", "navn": "NetOnNet"},
    "ikea": {"email": "kundeservice.no@ikea.com", "navn": "IKEA Kundeservice"},
    "zalando": {"email": "service@zalando.no", "navn": "Zalando"},
    "apple": {"email": "contactus.no@euro.apple.com", "navn": "Apple Store"},
    "xxl": {"email": "kundeservice@xxl.no", "navn": "XXL"}
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
    if not company_name_from_ai:
        return None
    search_term = company_name_from_ai.lower().strip()
    
    # Eksakt søk eller delvis match
    for key, info in VERIFIED_CONTACTS.items():
        if key in search_term:
            return info
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

def generate_complaint(prompt: str, image=None) -> dict:
    model_name = "gemini-2.0-flash"
    generation_config = {"response_mime_type": "application/json"}
    try:
        model = genai.GenerativeModel(model_name, generation_config=generation_config)
        inputs = [prompt]
        if image: inputs.append(image)
        response = model.generate_content(inputs)
        return json.loads(response.text)
    except Exception as e:
        try:
            fallback = "gemini-1.5-flash"
            model = genai.GenerativeModel(fallback, generation_config=generation_config)
            inputs = [prompt]
            if image: inputs.append(image)
            response = model.generate_content(inputs)
            return json.loads(response.text)
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
    st.link_button("☕ Spander en kaffe", "https://buymeacoffee.com/klagehjelpen")

# ==========================================
# 5. HOVEDAPP
# ==========================================
st.header("Få hjelp til å skrive klagen din ✍️")

# Session state init
if "generated_complaint" not in st.session_state:
    st.session_state.generated_complaint = None
if "detected_company" not in st.session_state:
    st.session_state.detected_company = None
if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None

tab_auto, tab_manuell = st.tabs(["✨ Automatisk (Last opp dokument)", "✍️ Manuell (Skriv selv)"])

# --- TAB 1: AUTOMATISK ---
with tab_auto:
    st.info("🔒 **Trygg opplasting:** Dokumentet analyseres midlertidig og lagres ikke.", icon="🛡️")
    
    col_upload, col_info = st.columns([1, 1])
    with col_upload:
        uploaded_file = st.file_uploader("Last opp kvittering, bot eller billett", type=["jpg", "jpeg", "png", "pdf"])
    with col_info:
        hendelsesdato = st.date_input("Når skjedde dette?", value=date.today())
        feil_beskrivelse = st.text_area("Kort beskrivelse av problemet", height=100)
        losning = st.selectbox("Ønsket løsning", ["Kostnadsfri reparasjon", "Ny vare (omlevering)", "Pengene tilbake (heving)", "Prisavslag", "Erstatning", "Usikker - la AI vurdere"])

    tone = st.radio("Tonefall:", ["Saklig (Anbefalt)", "Vennlig", "Veldig formell"], horizontal=True)

    if st.button("Generer klageutkast 🚀", type="primary"):
        if not uploaded_file:
            st.error("⚠️ Du må laste opp et dokument først.")
            st.stop()

        try:
            # Lagre filnavn for senere påminnelse
            st.session_state.uploaded_filename = uploaded_file.name

            image_input = None
            text_input = ""
            if uploaded_file.type == "application/pdf":
                text_input, image_input = extract_pdf_data(uploaded_file)
            else:
                image_input = Image.open(uploaded_file)
            
            # --- PROMPT ---
            prompt_auto = f"""
            Du er en profesjonell, norsk klagehjelper.
            DOKUMENT-TEKST: {text_input[:4000]}
            
            OPPGAVE:
            1. Analyser dokumentet. IDENTIFISER SELSKAPSNAVN (Viktig!).
            2. Skriv en reklamasjon basert på NORSK LOV.
            
            DATA:
            - DATO: {hendelsesdato}
            - PROBLEM: "{feil_beskrivelse}"
            - KRAV: {losning}
            - KLAGER: {mitt_navn} ({min_epost})
            - ROLLE: {rolle}
            - TONE: {tone}
            
            JURIDISK HUKOMMELSE:
            - Elektronikk/møbler = 5 års frist (Forbrukerkjøpsloven § 27).
            - Fly = EU261.
            - P-bot = Parkeringsforskriften.
            - Svarfrist: 14 dager.
            
            OUTPUT FORMAT (JSON):
            {{
                "selskapsnavn_funnet": "string (f.eks 'Elkjøp' eller 'SAS')",
                "emne": "string",
                "mottaker_epost_gjetning": "string",
                "brødtekst": "string"
            }}
            """
            
            with st.spinner("Analyserer dokument og sjekker kontaktdatabase..."):
                result_json = generate_complaint(prompt_auto, image_input)
                st.session_state.generated_complaint = result_json
                st.session_state.detected_company = result_json.get("selskapsnavn_funnet", "")
                
        except Exception as e:
            st.error(f"En feil oppstod: {e}")

# --- TAB 2: MANUELL ---
with tab_manuell:
    kategori_man = st.selectbox("Kategori", list(CATEGORY_HINTS.keys()))
    st.info(f"⚖️ {CATEGORY_HINTS[kategori_man]}")
    
    col_sel, col_det = st.columns(2)
    with col_sel:
        # Sortert liste av unike navn fra databasen
        unique_companies = sorted(list(set([v["navn"] for k, v in VERIFIED_CONTACTS.items()])))
        valgt_selskap_navn = st.selectbox("Velg selskap (valgfritt)", ["Annet / Skriv selv"] + unique_companies)
        
        custom_company = ""
        if valgt_selskap_navn == "Annet / Skriv selv":
            custom_company = st.text_input("Skriv inn selskapsnavn")
    
    with col_det:
        desc_man = st.text_area("Hva har skjedd?", height=100)
        req_man = st.text_input("Hva krever du?")

    if st.button("Skriv klage (Manuelt)"):
        company_for_prompt = custom_company if custom_company else valgt_selskap_navn
        
        # Finn info fra DB for manuell modus
        found_info = None
        # Må søke på navn her siden dropdown bruker navn, ikke nøkler
        for k, v in VERIFIED_CONTACTS.items():
            if v["navn"] == valgt_selskap_navn:
                found_info = v
                break
        
        forced_email = found_info.get("email", "") if found_info else ""

        # Nullstiller filnavn
        st.session_state.uploaded_filename = None

        prompt_man = f"""
        Skriv en klage.
        Avsender: {mitt_navn}
        Mottaker: {company_for_prompt}
        Sak: {desc_man}
        Krav: {req_man}
        Lovverk: {CATEGORY_HINTS[kategori_man]}
        
        OUTPUT FORMAT (JSON):
        {{
            "selskapsnavn_funnet": "{company_for_prompt}",
            "emne": "string",
            "mottaker_epost_gjetning": "{forced_email}",
            "brødtekst": "string"
        }}
        """
        try:
            with st.spinner("Skriver..."):
                res = generate_complaint(prompt_man)
                st.session_state.generated_complaint = res
                st.session_state.detected_company = company_for_prompt
        except Exception as e:
            st.error(str(e))


# ==========================================
# 6. RESULTATVISNING & KONTAKT-LOGIKK
# ==========================================
if st.session_state.generated_complaint:
    data = st.session_state.generated_complaint
    detected_name = st.session_state.detected_company
    
    # 1. SLÅ OPP I DATABASEN (Vasker og sjekker)
    contact_info = get_best_contact_method(detected_name)
    
    st.markdown("---")
    st.subheader("📍 Mottaker & Sendingsmetode")
    
    final_email = ""
    web_link = ""

    if contact_info:
        # Vi fant selskapet i vår "Gull-liste"
        st.success(f"✅ Identifisert selskap: **{contact_info.get('navn', detected_name)}**")
        
        if "advarsel" in contact_info:
            st.warning(f"⚠️ **OBS:** {contact_info['advarsel']}")
            
        if "web" in contact_info:
            web_link = contact_info["web"]
            st.info(f"🌐 Dette selskapet bruker primært webskjema/portal.")
            # Viser stor, tydelig knapp til riktig skjema
            st.link_button(f"Gå til {contact_info['navn']} sitt klageskjema ↗️", web_link)
            
            # Instruks til brukeren
            st.caption("👇 1. Kopier teksten under.")
            st.caption("👉 2. Trykk på knappen over for å lime det inn i skjemaet deres.")
            
            if "email" in contact_info:
                final_email = contact_info["email"]
                st.markdown(f"*(Alternativ e-post funnet: `{final_email}` - men webskjema anbefales)*")
        else:
            final_email = contact_info.get("email", "")
            
    else:
        # Fant ikke i DB -> Bruk AI-gjetning
        st.warning(f"⚠️ Fant ikke '{detected_name}' i vår verifiserte database. Sjekk at e-posten under er riktig.")
        final_email = data.get("mottaker_epost_gjetning", "")

    # 2. UI FOR Å ENDRE MOTTAKER (Vises kun hvis relevant)
    if not web_link:
        col_rec_ui, col_subj_ui = st.columns([1, 1])
        with col_rec_ui:
            user_email = st.text_input("Mottaker e-post (kan endres):", value=final_email)
        with col_subj_ui:
            user_subject = st.text_input("Emnefelt:", value=data.get("emne", ""))
    else:
        # Hvis webskjema, trenger vi ikke vise e-post feltet like prominent, men emne er greit å ha
        user_subject = st.text_input("Emnefelt (til skjemaet):", value=data.get("emne", ""))
        user_email = final_email # Beholder verdien i bakgrunnen

    # 3. SELVE BREVET
    st.markdown("### 📝 Klagebrev")
    user_body = st.text_area("Innhold (Redigerbar):", value=data.get("brødtekst", ""), height=400)
    
    # 4. SJEKKLISTE & KNAPPER
    st.markdown("---")
    
    # SJEKKLISTE
    st.subheader("✅ Sjekkliste før sending")
    c1, c2, c3 = st.columns(3)
    
    check_rec = c1.checkbox("Mottaker/Skjema er korrekt")
    check_txt = c2.checkbox("Mine detaljer stemmer")
    check_att = c3.checkbox("Jeg husker vedlegg")
    
    st.markdown("---")
    col_btn, col_copy = st.columns([1, 1])
    
    with col_btn:
        if web_link:
             st.info("👈 Kopier teksten til høyre, og bruk 'Gå til klageskjema'-knappen lenger opp.")
        elif user_email and "@" in user_email:
            if check_rec and check_txt and check_att:
                if st.session_state.uploaded_filename:
                    st.info(f"📎 **Husk:** Legg ved filen **{st.session_state.uploaded_filename}** manuelt i e-posten.", icon="⚠️")
                else:
                    st.info("📎 **Husk:** Du må legge ved eventuelle bilder/kvitteringer manuelt.", icon="⚠️")

                safe_s = urllib.parse.quote(user_subject)
                safe_b = urllib.parse.quote(user_body)
                mailto = f"mailto:{user_email}?subject={safe_s}&body={safe_b}"
                
                st.link_button("📧 Åpne i E-postprogram", mailto, type="primary", use_container_width=True)
            else:
                st.caption("🛑 Huk av alle tre punktene i sjekklisten for å aktivere e-postknappen.")
        else:
            st.warning("Mangler e-postadresse.")

    with col_copy:
        st.code(user_body, language=None)
        # BOKSEN MED "TRYKK HER FOR Å KOPIERE" ER NÅ FJERNET
