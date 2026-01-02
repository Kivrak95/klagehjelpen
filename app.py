import os
import re
import time
import urllib.parse
from datetime import date, timedelta
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

# --- DATABASE MED JURIDISK INFO ---
CATEGORY_INFO = {
    "Varekjøp": {
        "lov": "Forbrukerkjøpsloven",
        "hint": "§ 27 (5 års reklamasjonsfrist for varer ment å vare lenge). § 16 (Mangel). § 29 (Krav om retting/omlevering).",
        "selskaper": {
            "Elkjøp": "kundesenter@elkjop.no", "Power": "kundeservice@power.no",
            "Komplett": "kundeservice@komplett.no", "NetOnNet": "kundeservice@netonnet.no",
            "IKEA": "kundeservice.no@ikea.com", "XXL": "kundeservice@xxl.no",
            "Zalando": "service@zalando.no", "Apple Store": "contactus.no@euro.apple.com"
        }
    },
    "Flyforsinkelse": {
        "lov": "EU-forordning 261/2004",
        "hint": "Rett til standardkompensasjon (250-600 EUR) ved forsinkelse > 3 timer. OBS: Mange flyselskap krever bruk av egne webskjema.",
        "selskaper": {
            "SAS": "Bruk webskjema (sas.no)", "Norwegian": "post.reception@norwegian.com",
            "Widerøe": "support@wideroe.no"
        }
    },
    "Parkeringsbot": {
        "lov": "Parkeringsforskriften og Avtaleloven",
        "hint": "§ 36 (Rimelighet). Var skiltingen tydelig? Var automaten i ustand?",
        "selskaper": {
            "Apcoa": "kundesenter@apcoa.no", "Aimo Park": "kunde@aimopark.no",
            "EasyPark": "kundeservice@easypark.no"
        }
    },
    "Håndverkertjenester": {
        "lov": "Håndverkertjenesteloven",
        "hint": "§ 5 (Krav til fagmessig utførelse). § 22 (Reklamasjon).",
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
    # Fjerner placeholders hvis AI finner på å skrive dem
    text = text.replace("[Ditt Navn]", "").replace("[Dato]", "")
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
    model_name = "gemini-2.0-flash" 
    
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
# 3. SIDEBAR (MED PERSONVERN)
# ==========================================
with st.sidebar:
    st.title("⚖️ KlageHjelpen")
    st.caption("Din tekstforfatter for reklamasjoner")
    
    st.header("👤 Innstillinger")
    rolle = st.radio("Jeg klager som:", ["Privatperson", "Bedrift"], index=0)
    
    st.markdown("---")
    st.caption("Din kontaktinfo (brukes i signaturen)")
    mitt_navn = st.text_input("Ditt navn", placeholder="Ola Nordmann")
    min_epost = st.text_input("Din e-post", placeholder="ola@mail.no")
    
    # --- PERSONVERN SEKSJON ---
    st.markdown("---")
    with st.expander("🔒 Personvern & Sikkerhet", expanded=False):
        st.markdown("""
        **Dine data er trygge:**
        1. **Ingen lagring:** Filer du laster opp analyseres i minnet og slettes umiddelbart etter at klagen er generert.
        2. **AI-behandling:** Data sendes kryptert til Google Gemini for analyse, men brukes ikke til å trene modellene.
        3. **Du har kontroll:** Du kan når som helst lukke vinduet for å fjerne all info.
        """)
        st.caption("Tjenesten er en ren tekstbehandler. Du er selv juridisk ansvarlig avsender av klagen.")

    st.markdown("---")
    st.link_button("☕ Spander en kaffe", "https://buymeacoffee.com/klagehjelpen")

# ==========================================
# 4. HOVEDAPP
# ==========================================

st.header("Få hjelp til å skrive klagen din ✍️")
st.markdown("Velg metode under. AI-en analyserer saken og skriver et forslag til deg basert på gjeldende norsk lov.")

tab_auto, tab_manuell = st.tabs(["✨ Automatisk (Last opp dokument)", "✍️ Manuell (Skriv selv)"])

# --- TAB 1: AUTOMATISK ---
with tab_auto:
    # Personvern-disclaimer rett ved opplasting
    st.info("🔒 **Trygg opplasting:** Dokumentet ditt analyseres kun for å skrive teksten og lagres ikke.", icon="🛡️")
    
    col_upload, col_info = st.columns([1, 1])
    
    with col_upload:
        uploaded_file = st.file_uploader("Last opp kvittering, bot eller billett", type=["jpg", "jpeg", "png", "pdf"])
        
    with col_info:
        hendelsesdato = st.date_input("Når skjedde dette?", value=date.today())
        feil_beskrivelse = st.text_area("Kort beskrivelse av problemet", placeholder="F.eks: TV-en slår seg ikke på, eller flyet var 4 timer forsinket...", height=100)
        
        # Ønsket løsning - nytt felt
        losning = st.selectbox("Hva ønsker du?", ["Kostnadsfri reparasjon", "Ny vare (omlevering)", "Pengene tilbake (heving)", "Prisavslag", "Erstatning", "Usikker - la AI vurdere"])

    # tone-velger
    tone = st.radio("Velg tonefall:", ["Saklig og bestemt (Anbefalt)", "Vennlig", "Veldig formell/juridisk"], horizontal=True)

    if st.button("Generer klageutkast 🚀", type="primary"):
        if not ENV_API_KEY:
            st.error("Mangler API-nøkkel.")
            st.stop()
        if not uploaded_file:
            st.error("⚠️ Du må laste opp et dokument først.")
            st.stop()

        try:
            image = process_uploaded_file(uploaded_file)
            st.image(image, caption="Analyserer dokument...", width=300)

            # --- PROMPT ---
            prompt_auto = f"""
            Du er en profesjonell, norsk klagehjelper. Din oppgave er å skrive et utkast til en klage på vegne av brukeren.
            
            OPPGAVE:
            1. Analyser bildet. Identifiser dokumenttype (Kvittering, Bot, Billett). Finn referansenummer, pris, dato og selger.
            2. Skriv en reklamasjon basert på NORSK LOV.
            
            DATA:
            - DATO FOR FEIL: {hendelsesdato}
            - PROBLEM: "{feil_beskrivelse}"
            - ØNSKET LØSNING: {losning}
            - KLAGER: {mitt_navn} ({min_epost})
            - ROLLE: {rolle}
            - TONE: {tone}. Vær saklig, men ikke aggressiv. Bruk formuleringer som "Jeg er av den oppfatning at..." eller "Dette fremstår som en mangel..." fremfor å være bastant.
            
            JURIDISK HUKOMMELSE:
            - Varekjøp: Forbrukerkjøpsloven. Elektronikk/møbler har ofte 5 års frist (§ 27). Krev avhjelp (§ 29).
            - Fly: EU261.
            - P-bot: Parkeringsforskriften/Avtaleloven § 36.
            
            VIKTIG: 
            - Sett en svarfrist på 14 dager.
            - Hvis flyselskap: Nevn at hvis de krever webskjema, er denne teksten grunnlaget for det som limes inn der.
            
            FORMAT:
            MAIL_EMNE: <Emne>
            MAIL_MOTTAKER: <E-post>
            MAIL_BODY:
            <Tekst>
            """
            
            with st.spinner("Juristen analyserer saken..."):
                raw_text = generate_with_gemini(prompt_auto, image)
                emne, mottaker, body = parse_ai_output(raw_text, "Klage")
                
                # --- RESULTATVISNING ---
                st.markdown("### 📝 Ditt klageutkast")
                
                # Redigerbar mottaker
                st.caption("👇 Sjekk at e-posten stemmer. AI kan gjette feil.")
                col_rec, col_subj = st.columns([1, 1])
                with col_rec:
                    final_email = st.text_input("Mottaker e-post:", value=mottaker)
                with col_subj:
                    final_subject = st.text_input("Emnefelt:", value=emne)

                # Viser teksten i en kodeblokk for enkel kopiering
                st.markdown("**Innhold (Kopier og lim inn i e-posten din):**")
                st.code(body, language=None)
                
                # --- SJEKKLISTE FØR SENDING ---
                st.markdown("---")
                st.subheader("✅ Sjekkliste før du sender")
                
                c1, c2, c3 = st.columns(3)
                check_rec = c1.checkbox("Mottaker e-post er korrekt")
                check_info = c2.checkbox("Mine detaljer stemmer")
                check_att = c3.checkbox("Jeg husker vedlegg")
                
                if check_rec and check_info and check_att:
                    # Bygger mailto-link
                    safe_subj = urllib.parse.quote(final_subject)
                    safe_body = urllib.parse.quote(body)
                    mailto = f"mailto:{final_email}?subject={safe_subj}&body={safe_body}"
                    
                    st.success("Alt klart! Lykke til med klagen.")
                    st.link_button("📧 Åpne i E-postprogram", mailto, type="primary")
                else:
                    st.caption("⚠️ Huk av sjekkpunktene over for å aktivere send-knappen.")
                
        except Exception as e:
            st.error(f"En feil oppstod: {e}")

# --- TAB 2: MANUELL ---
with tab_manuell:
    st.info("Her kan du velge kategori og få hjelp med lovparagrafene selv om du ikke laster opp bilde.")
    
    kategori = st.selectbox("Hva gjelder saken?", list(CATEGORY_INFO.keys()))
    
    # Henter info
    info = CATEGORY_INFO[kategori]
    selskapsliste = info["selskaper"]
    lov_hint = info["lov"] + ": " + info["hint"]
    
    st.success(f"⚖️ **Lovverk:** {lov_hint}")
    
    c1, c2 = st.columns(2)
    with c1:
        options = sorted(list(selskapsliste.keys())) + ["Annet"]
        valgt_selskap = st.selectbox("Velg motpart", options, index=None, placeholder="Velg fra listen...")
        
        motpart = valgt_selskap if valgt_selskap and valgt_selskap != "Annet" else ""
        prefilled_email = selskapsliste.get(valgt_selskap, "")
        
        if valgt_selskap == "Annet" or not valgt_selskap:
            motpart = st.text_input("Navn på selskap", value=motpart)
            prefilled_email = st.text_input("E-post (hvis du har)", value=prefilled_email)
        else:
            # Hvis selskap er valgt fra listen, vis e-posten men gjør den redigerbar
             prefilled_email = st.text_input("E-post til mottaker", value=prefilled_email)
    
    with c2:
        tone_man = st.selectbox("Ønsket tone", ["Saklig (Anbefalt)", "Veldig formell", "Vennlig"])
        losning_man = st.selectbox("Ditt krav", ["Reparasjon", "Ny vare", "Pengene tilbake", "Erstatning"])
    
    beskrivelse_manuell = st.text_area("Beskriv hva som har skjedd", height=150, placeholder="F.eks: Jeg kjøpte en jakke for 2 måneder siden, nå har glidelåsen røket...")

    if st.button("Skriv klage (Manuelt)"):
        if not motpart or not beskrivelse_manuell:
            st.error("Du må fylle inn selskap og beskrivelse.")
            st.stop()
            
        prompt_manuell = f"""
        Skriv en klage/reklamasjon.
        Avsender: {mitt_navn}
        Mottaker: {motpart}
        Sak: {beskrivelse_manuell}
        Krav: {losning_man}
        Tone: {tone_man}
        Rolle: {rolle}
        Kategori: {kategori}
        
        VIKTIG: 
        - Bruk lovverk: {info['lov']}
        - Bruk formuleringer som "Jeg mener...", "Det fremstår som..." for å være robust men ikke aggressiv.
        - Sett svarfrist: 14 dager.
        
        FORMAT:
        MAIL_EMNE: <Emne>
        MAIL_MOTTAKER: {prefilled_email}
        MAIL_BODY:
        <Tekst>
        """
        
        with st.spinner("Skriver utkast..."):
            try:
                res = generate_with_gemini(prompt_manuell)
                em, rec, bd = parse_ai_output(res, "Klage")
                
                st.markdown("### 📝 Utkast")
                
                final_email_man = st.text_input("Mottaker:", value=rec, key="rec_man")
                final_subj_man = st.text_input("Emne:", value=em, key="subj_man")
                
                st.markdown("**Kopier teksten under:**")
                st.code(bd, language=None)
                
                st.markdown("---")
                c1m, c2m = st.columns(2)
                check_ok = c1m.checkbox("Teksten ser bra ut", key="check_man")
                
                if check_ok:
                    safe_s = urllib.parse.quote(final_subj_man)
                    safe_b = urllib.parse.quote(bd)
                    mail_link = f"mailto:{final_email_man}?subject={safe_s}&body={safe_b}"
                    st.link_button("📧 Gjør klar e-post", mail_link, type="primary")
                    
            except Exception as e:
                st.error(f"Feil: {e}")
