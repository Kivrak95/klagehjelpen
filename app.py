import os
import re
import time
import urllib.parse
from datetime import date
from dotenv import load_dotenv
from PIL import Image
import fitz  # PyMuPDF

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

# --- DATABASE MED JURIDISK INFO ---
# Her kobler vi kategorier mot lovverk slik at Manuell-fanen blir super-smart.
CATEGORY_INFO = {
    "Varekjøp": {
        "lov": "Forbrukerkjøpsloven",
        "hint": "§ 27 (5 års reklamasjonsfrist for varer ment å vare lenge). § 16 (Mangel). § 29 (Krav om retting/omlevering).",
        "selskaper": {
            "Elkjøp": "hello@elkjop.no", "Power": "kundeservice@power.no",
            "Komplett": "kundeservice@komplett.no", "NetOnNet": "kundeservice@netonnet.no",
            "IKEA": "kundeservice.no@ikea.com", "XXL": "kundeservice@xxl.no",
            "Zalando": "service@zalando.no", "Apple Store": "contactus.no@euro.apple.com"
        }
    },
    "Flyforsinkelse": {
        "lov": "EU-forordning 261/2004",
        "hint": "Rett til standardkompensasjon (250-600 EUR) ved forsinkelse over 3 timer, med mindre det er 'ekstraordinære omstendigheter'. Rett til mat/drikke.",
        "selskaper": {
            "SAS": "customer.care@sas.no", "Norwegian": "post.reception@norwegian.com",
            "Widerøe": "support@wideroe.no"
        }
    },
    "Parkeringsbot": {
        "lov": "Parkeringsforskriften og Avtaleloven",
        "hint": "§ 36 (Rimelighet). Var skiltingen tydelig nok? Var automaten i ustand? (Parkeringsklagenemnda-praksis).",
        "selskaper": {
            "Apcoa": "kundesenter@apcoa.no", "Aimo Park": "kunde@aimopark.no",
            "EasyPark": "kundeservice@easypark.no"
        }
    },
    "Håndverkertjenester": {
        "lov": "Håndverkertjenesteloven",
        "hint": "§ 5 (Fagmessig utførelse). § 22 (Reklamasjon). 5 års frist på resultatet.",
        "selskaper": {} 
    },
    "Annet": {
        "lov": "Alminnelig avtalerett",
        "hint": "Avtalen er bindende. Er det levert som avtalt?",
        "selskaper": {
            "Telenor": "telenor.klager@telenor.no", "Telia": "kundesenter@telia.no",
            "Vy": "tog@vy.no", "Ruter": "post@ruter.no"
        }
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
    if uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img
    else:
        return Image.open(uploaded_file)

@st.cache_data(show_spinner=False, ttl=3600)
def generate_with_gemini(prompt: str, image=None) -> str:
    genai.configure(api_key=ENV_API_KEY)
    model_name = "gemini-2.0-flash" # Din kraftige modell
    
    try:
        model = genai.GenerativeModel(model_name)
        inputs = [prompt]
        if image:
            inputs.append(image)
        
        response = model.generate_content(inputs)
        return response.text

    except Exception as e:
        # Fallback
        try:
            fallback = "gemini-2.0-flash-001"
            model = genai.GenerativeModel(fallback)
            inputs = [prompt]
            if image:
                inputs.append(image)
            response = model.generate_content(inputs)
            return response.text
        except:
            raise e

# ==========================================
# 3. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("👤 Innstillinger")
    rolle = st.radio("Jeg klager som:", ["Privatperson", "Bedrift"], index=0)
    st.markdown("---")
    mitt_navn = st.text_input("Ditt navn", placeholder="Ola Nordmann")
    min_epost = st.text_input("Din e-post", placeholder="ola@mail.no")
    
    st.markdown("---")
    st.link_button("☕ Spander en kaffe", "https://buymeacoffee.com/klagehjelpen")
    with st.expander("🧡 Vipps en gave"):
        st.markdown("**Vipps:** `920 573 95`")

    # --- DEBUG VERKTØY ---
    st.markdown("---")
    with st.expander("🛠️ Debug: Se modeller"):
        if st.button("List opp tilgjengelige modeller"):
            try:
                genai.configure(api_key=ENV_API_KEY)
                models = []
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        models.append(m.name)
                st.write("Modeller funnet:")
                st.code("\n".join(models))
            except Exception as e:
                st.error(f"Kunne ikke liste modeller: {e}")

# ==========================================
# 4. HOVEDAPP
# ==========================================

tab_auto, tab_manuell = st.tabs(["✨ Automatisk (Last opp)", "✍️ Manuell (Skjema)"])

# --- TAB 1: AUTOMATISK ---
with tab_auto:
    st.info("📸 **Last opp PDF (f.eks bot, billett, kvittering) eller bilde – la AI gjøre resten!**")
    
    col_upload, col_info = st.columns([1, 1])
    
    with col_upload:
        uploaded_file = st.file_uploader("Last opp dokument", type=["jpg", "jpeg", "png", "pdf"])
        
    with col_info:
        hendelsesdato = st.date_input("Når oppstod feilen?", value=date.today())
        feil_beskrivelse = st.text_area("Hva er problemet?", placeholder="F.eks: Flyet var 4t forsinket, eller jeg fikk p-bot selv om jeg betalte...", height=100)
        
    if st.button("Generer klage automatisk 🚀", type="primary"):
        if not ENV_API_KEY:
            st.error("Mangler API-nøkkel.")
            st.stop()
        if not uploaded_file:
            st.error("⚠️ Du må laste opp et dokument først.")
            st.stop()

        try:
            image = process_uploaded_file(uploaded_file)
            st.image(image, caption="Analyserer dokument...", width=300)

            # --- HER ER DEN STORE OPPDATERINGEN FOR ALLE KATEGORIER ---
            prompt_auto = f"""
            Du er en streng og svært dyktig norsk forbrukeradvokat.
            
            OPPGAVE:
            1. SE PÅ BILDET: Identifiser hva slags dokument dette er (Kvittering? Flybillett? Parkeringsbot? Håndverkerfaktura?).
            2. VELG RIKTIG LOVVERK basert på dokumenttypen (se listen under).
            3. Skriv en formell klage.
            
            SAKSDATA:
            - DATO FOR FEIL: {hendelsesdato}
            - BRUKERENS BESKRIVELSE: "{feil_beskrivelse}"
            - KLAGER: {mitt_navn} ({min_epost})
            - ROLLE: {rolle}
            
            LOVVERK-BIBLIOTEK (VELG ETT):
            
            A) VAREKJØP (Elektronikk, Klær, Møbler):
               - Lov: Forbrukerkjøpsloven.
               - Argument: § 27 (5 års reklamasjonsfrist for ting ment å vare lenge, ellers 2 år). § 16 (Mangel). § 29 (Krav om retting).
               
            B) FLYREISE (Forsinkelse/Kansellering):
               - Lov: EU-forordning 261/2004.
               - Argument: Rett til standardkompensasjon (250-600 EUR) ved forsinkelse > 3 timer. Rett til forpleining.
               
            C) PARKERINGSBOT (Kontrollsanksjon):
               - Lov: Parkeringsforskriften & Avtaleloven § 36.
               - Argument: Var skiltingen tydelig? Var det rimelig? Henvis til § 36 om urimelige vilkår.
               
            D) HÅNDVERKERTJENESTER:
               - Lov: Håndverkertjenesteloven.
               - Argument: § 5 (Krav til fagmessig utførelse). § 22 (Reklamasjon). 5 års frist.
            
            FORMAT:
            MAIL_EMNE: <Kort og tydelig emne med referansenummer fra bildet hvis synlig>
            MAIL_MOTTAKER: <Gjett kundeservice-epost basert på firmanavn>
            MAIL_BODY:
            <Selve teksten. Vær formell, vis til riktig paragraf/lov, men skriv flytende.>
            """
            
            with st.spinner("Analyserer dokumenttype og lovverk..."):
                raw_text = generate_with_gemini(prompt_auto, image)
                emne, mottaker, body = parse_ai_output(raw_text, "Klage")
                
                st.success("✅ Klagen er klar!")
                st.text_input("Mottaker (fra analyse)", value=mottaker)
                st.text_area("Klagebrev", value=body, height=500)
                
                mailto = f"mailto:{mottaker}?subject={urllib.parse.quote(emne)}&body={urllib.parse.quote(body)}"
                st.link_button("📧 Send e-post", mailto)
                
        except Exception as e:
            st.error(f"En feil oppstod: {e}")

# --- TAB 2: MANUELL ---
with tab_manuell:
    st.caption("Fyll ut skjemaet manuelt.")
    
    # Henter kategoriene fra den nye databasen vår
    kategori = st.selectbox("Hva gjelder saken?", list(CATEGORY_INFO.keys()))
    
    # Henter info basert på valg
    info = CATEGORY_INFO[kategori]
    selskapsliste = info["selskaper"]
    lov_hint = info["lov"] + ": " + info["hint"]
    
    st.info(f"💡 **Juridisk tips:** {lov_hint}")
    
    c1, c2 = st.columns(2)
    with c1:
        options = sorted(list(selskapsliste.keys())) + ["Annet"]
        valgt_selskap = st.selectbox("Velg selskap", options, index=None, placeholder="Velg...")
        
        motpart = valgt_selskap if valgt_selskap and valgt_selskap != "Annet" else ""
        prefilled_email = selskapsliste.get(valgt_selskap, "")
        
        if valgt_selskap == "Annet" or not valgt_selskap:
            motpart = st.text_input("Selskapsnavn", value=motpart)
            prefilled_email = st.text_input("E-post (valgfritt)", value=prefilled_email)
    
    with c2:
        tone = st.selectbox("Tone", ["Formell (Juridisk)", "Bestemt", "Vennlig"])
    
    beskrivelse_manuell = st.text_area("Hva har skjedd?", height=150)
    krav_manuell = st.text_input("Hva krever du?", placeholder="F.eks. Erstatning, Ny vare...")

    if st.button("Opprett klage (Manuelt)"):
        if not motpart or not beskrivelse_manuell:
            st.error("Mangler info.")
            st.stop()
            
        prompt_manuell = f"""
        Skriv en reklamasjon/klage.
        Avsender: {mitt_navn}
        Mottaker: {motpart}
        Sak: {beskrivelse_manuell}
        Krav: {krav_manuell}
        Tone: {tone}
        Rolle: {rolle}
        Kategori: {kategori}
        
        VIKTIG JURIDISK INFO DU SKAL BRUKE:
        Lovverk: {info['lov']}
        Argumentasjonstips: {info['hint']}
        
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
