import os
import re
import time
import urllib.parse
from datetime import date
from dotenv import load_dotenv
from PIL import Image
import fitz  # PyMuPDF for PDF-håndtering

import streamlit as st
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

# ==========================================
# 1. SETUP & CONFIG
# ==========================================
load_dotenv()
ENV_API_KEY = os.getenv("GOOGLE_API_KEY", "")

st.set_page_config(page_title="KlageHjelpen", page_icon="⚖️", layout="wide")
st.title("⚖️ KlageHjelpen")
st.markdown("**Din profesjonelle forbruker-agent.**")

# --- DATABASE (Beholdes for manuell del) ---
COMPANY_DB = {
    "Varekjøp": {
        "Elkjøp": "hello@elkjop.no", "Power": "kundeservice@power.no",
        "Komplett": "kundeservice@komplett.no", "NetOnNet": "kundeservice@netonnet.no",
        "IKEA": "kundeservice.no@ikea.com", "XXL": "kundeservice@xxl.no",
        "Zalando": "service@zalando.no", "Apple Store": "contactus.no@euro.apple.com"
    },
    "Flyforsinkelse": {
        "SAS": "customer.care@sas.no", "Norwegian": "post.reception@norwegian.com",
        "Widerøe": "support@wideroe.no"
    },
    "Parkeringsbot": {
        "Apcoa": "kundesenter@apcoa.no", "Aimo Park": "kunde@aimopark.no",
        "EasyPark": "kundeservice@easypark.no"
    },
    "Annet": {
        "Telenor": "telenor.klager@telenor.no", "Telia": "kundesenter@telia.no",
        "Vy": "tog@vy.no", "Ruter": "post@ruter.no"
    }
}

# ==========================================
# 2. HJELPEFUNKSJONER
# ==========================================
def clean_text(text: str) -> str:
    text = text.replace("**", "").replace("##", "").replace("__", "").replace("*", "").replace("#", "")
    text = text.replace("Problembeskrivelse:", "").replace("Juridisk grunnlag:", "")
    return text.strip()

def extract_email(text: str) -> str:
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text or "")
    return match.group(0) if match else ""

def parse_ai_output(text: str, default_subject: str) -> tuple[str, str, str]:
    text = clean_text(text)
    emne = default_subject
    m_emne = re.search(r"MAIL_EMNE:\s*(.*)", text, re.IGNORECASE)
    if m_emne: emne = m_emne.group(1).strip()
    
    epost = ""
    m_rec = re.search(r"MAIL_MOTTAKER:\s*(.*)", text, re.IGNORECASE)
    if m_rec: epost = extract_email(m_rec.group(1).strip())

    m_body = re.search(r"MAIL_BODY:\s*", text, re.IGNORECASE)
    if m_body: body = text[m_body.end():].strip()
    else: body = text
    return emne, epost, body

def process_uploaded_file(uploaded_file):
    """Gjør om filen (bilde eller PDF) til et bilde-objekt AI kan lese"""
    if uploaded_file.type == "application/pdf":
        # Konverterer første side av PDF til bilde
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0)  # Tar side 1
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img
    else:
        # Det er allerede et bilde
        return Image.open(uploaded_file)

@st.cache_data(show_spinner=False, ttl=3600)
def generate_with_gemini(prompt: str, image=None) -> str:
    genai.configure(api_key=ENV_API_KEY)
    
    # ENDRET: Bruker 'latest' for å sikre at vi treffer en modell som finnes
    model_name = "gemini-1.5-flash-latest" 
    
    model = genai.GenerativeModel(model_name)
    
    inputs = [prompt]
    if image:
        inputs.append(image)

    try:
        response = model.generate_content(inputs)
        return response.text
    except Exception as e:
        raise e

# ==========================================
# 3. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("👤 Innstillinger")
    rolle = st.radio("Jeg klager som:", ["Privatperson", "Bedrift"], index=0)
    st.markdown("---")
    st.caption("Din kontaktinfo")
    mitt_navn = st.text_input("Ditt navn", placeholder="Ola Nordmann")
    min_epost = st.text_input("Din e-post", placeholder="ola@mail.no")
    
    st.markdown("---")
    st.link_button("☕ Spander en kaffe", "https://buymeacoffee.com/klagehjelpen")
    with st.expander("🧡 Vipps en gave"):
        st.markdown("**Vipps:** `920 573 95`")

# ==========================================
# 4. HOVEDAPP (TABS)
# ==========================================

tab_auto, tab_manuell = st.tabs(["✨ Automatisk (Last opp)", "✍️ Manuell (Skjema)"])

# --- TAB 1: AUTOMATISK (MAGISK) ---
with tab_auto:
    st.info("📸 **Last opp PDF (f.eks bot/faktura) eller bilde – la AI gjøre resten!**")
    
    col_upload, col_info = st.columns([1, 1])
    
    with col_upload:
        uploaded_file = st.file_uploader("Last opp dokument", type=["jpg", "jpeg", "png", "pdf"])
        
    with col_info:
        feil_beskrivelse = st.text_area("Hva er problemet? (Kort)", placeholder="F.eks: TV-en virker ikke lenger, eller flyet var 4 timer forsinket.", height=100)
        
    if st.button("Generer klage automatisk 🚀", type="primary"):
        if not ENV_API_KEY:
            st.error("Mangler API-nøkkel.")
            st.stop()
        if not uploaded_file:
            st.error("⚠️ Du må laste opp et dokument først.")
            st.stop()
        if not mitt_navn:
            st.warning("⚠️ Tips: Fyll ut navnet ditt i menyen til venstre for best resultat.")

        try:
            # Behandle filen (PDF eller Bilde)
            image = process_uploaded_file(uploaded_file)
            st.image(image, caption="Analyserer dokument...", width=300)

            prompt_auto = f"""
            Du er en ekspert på norsk forbrukerrett.
            
            OPPGAVE:
            1. Analyser bildet jeg har lastet opp. Finn: Mottaker (Selskap), Dato, Produkt/Tjeneste, Pris/Ref-nr.
            2. Skriv en formell klage/reklamasjon basert på bildet OG brukerens beskrivelse av feilen.
            
            BRUKERENS BESKRIVELSE AV FEILEN: "{feil_beskrivelse}"
            KLAGERENS NAVN: {mitt_navn} ({min_epost})
            ROLLE: {rolle} (Hvis privatperson: Bruk Forbrukerkjøpsloven/Flyrettigheter. Hvis bedrift: Kjøpsloven).
            
            VIKTIG:
            - Finn selv rett e-postadresse basert på firmanavnet i kvitteringen hvis mulig.
            - Skriv flytende norsk. Ingen overskrifter som "Problembeskrivelse".
            - Vær høflig men bestemt.
            
            FORMAT:
            MAIL_EMNE: <Kort emne>
            MAIL_MOTTAKER: <E-post (gjett hvis ukjent)>
            MAIL_BODY:
            <Selve teksten>
            """
            
            with st.spinner("🔍 Analyserer dokumentet og skriver klage..."):
                raw_text = generate_with_gemini(prompt_auto, image)
                emne, mottaker, body = parse_ai_output(raw_text, "Klage")
                
                st.success("✅ Klagen er klar!")
                st.text_input("Mottaker (fra analyse)", value=mottaker)
                st.text_area("Klagebrev", value=body, height=400)
                
                mailto = f"mailto:{mottaker}?subject={urllib.parse.quote(emne)}&body={urllib.parse.quote(body)}"
                st.link_button("📧 Send e-post", mailto)
                
        except Exception as e:
            st.error(f"Noe gikk galt under analysen: {e}")


# --- TAB 2: MANUELL (GAMLE MÅTEN) ---
with tab_manuell:
    st.caption("Fyll ut skjemaet manuelt hvis du ikke har dokumentasjon tilgjengelig.")
    
    kategori = st.selectbox("Kategori", list(COMPANY_DB.keys()))
    company_list = COMPANY_DB.get(kategori, {})
    
    c1, c2 = st.columns(2)
    with c1:
        options = sorted(list(company_list.keys())) + ["Annet"]
        valgt_selskap = st.selectbox("Velg selskap", options, index=None, placeholder="Velg...")
        
        motpart = valgt_selskap if valgt_selskap and valgt_selskap != "Annet" else ""
        prefilled_email = company_list.get(valgt_selskap, "")
        
        if valgt_selskap == "Annet" or not valgt_selskap:
            motpart = st.text_input("Selskapsnavn", value=motpart)
            prefilled_email = st.text_input("E-post (valgfritt)", value=prefilled_email)
    
    with c2:
        tone = st.selectbox("Tone", ["Formell", "Bestemt", "Vennlig"])
    
    beskrivelse_manuell = st.text_area("Hva har skjedd? (Stikkord)", height=150)
    krav_manuell = st.text_input("Hva krever du?", placeholder="F.eks. Ny vare, pengene tilbake...")

    if st.button("Opprett klage (Manuelt)"):
        if not motpart or not beskrivelse_manuell:
            st.error("Mangler selskap eller beskrivelse.")
            st.stop()
            
        prompt_manuell = f"""
        Skriv en klage.
        Avsender: {mitt_navn}
        Mottaker: {motpart}
        Sak: {beskrivelse_manuell}
        Krav: {krav_manuell}
        Tone: {tone}
        Lovverk: Bruk norsk lovverk for {rolle}.
        
        FORMAT:
        MAIL_EMNE: <Emne>
        MAIL_MOTTAKER: {prefilled_email}
        MAIL_BODY:
        <Tekst>
        """
        
        with st.spinner("Skriver..."):
            try:
                res = generate_with_gemini(prompt_manuell)
                em, rec, bd = parse_ai_output(res, "Klage")
                st.text_input("Mottaker", value=rec)
                st.text_area("Innhold", value=bd, height=400)
            except Exception as e:
                st.error(f"Feil: {e}")