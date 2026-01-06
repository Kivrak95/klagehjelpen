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
# 2. VERIFISERT KONTAKTDATABASE (50+ SELSKAPER)
# ==========================================
VERIFIED_CONTACTS = {
    # --- ELEKTRONIKK & HVITEVARER ---
    "elkjop": {"email": "hello@elkjop.no", "navn": "Elkjøp"},
    "elkjøp": {"email": "hello@elkjop.no", "navn": "Elkjøp"},
    "power": {"email": "kundeservice@power.no", "navn": "Power"},
    "komplett": {"email": "kundeservice@komplett.no", "navn": "Komplett.no"},
    "netonnet": {"email": "kundeservice@netonnet.no", "navn": "NetOnNet"},
    "apple": {"email": "contactus.no@euro.apple.com", "navn": "Apple Store"},
    "dustin": {"email": "kundeservice@dustinhome.no", "navn": "Dustin Home"},
    "fjellsport": {"email": "kundeservice@fjellsport.no", "navn": "Fjellsport"},

    # --- MØBLER, INTERIØR & BYGG ---
    "ikea": {
        "web": "https://www.ikea.com/no/no/customer-service/contact-us/",
        "navn": "IKEA",
        "advarsel": "IKEA krever ofte chat/tlf, men bruk dette kontaktskjemaet for reklamasjoner."
    },
    "jysk": {"email": "kundeservice@jysk.no", "navn": "JYSK"},
    "bohus": {"email": "kundeservice@bohus.no", "navn": "Bohus"},
    "skeidar": {"email": "netthandel@skeidar.no", "navn": "Skeidar"},
    "møbelringen": {"email": "kundeservice@mobelringen.no", "navn": "Møbelringen"},
    "kid": {"email": "kundeservice@kid.no", "navn": "Kid Interiør"},
    "princess": {"email": "kundeservice@princessgruppen.no", "navn": "Princess"},
    "clas ohlson": {"email": "kundesenter@clasohlson.no", "navn": "Clas Ohlson"},
    "biltema": {"email": "kundeservice@biltema.no", "navn": "Biltema"},
    "jula": {"web": "https://www.jula.no/kundeservice/kontakt-oss/", "navn": "Jula"},
    "megaflis": {"email": "kundeservice@megaflis.no", "navn": "Megaflis"},
    "thansen": {"email": "thansen@thansen.no", "navn": "Thansen"},
    "europris": {"email": "kundeservice@europris.no", "navn": "Europris"},
    "maxbo": {"web": "https://www.maxbo.no/kundeservice/kontakt-oss/", "navn": "Maxbo", "advarsel": "Bruk skjemaet for netthandel. Kjøp i butikk må tas i varehus."},

    # --- KLÆR & SPORT ---
    "zalando": {"email": "service@zalando.no", "navn": "Zalando"},
    "xxl": {"email": "kundeservice@xxl.no", "navn": "XXL"},
    "sport 1": {"email": "kundeservice@sport1.no", "navn": "Sport 1"},
    "intersport": {"email": "kundeservice@intersport.no", "navn": "Intersport"},
    "hm": {"web": "https://www2.hm.com/no_no/customer-service/contact.html", "navn": "H&M"},
    "h&m": {"web": "https://www2.hm.com/no_no/customer-service/contact.html", "navn": "H&M"},

    # --- MAT, LEVERING & DAGLIGVARE ---
    "oda": {"email": "hei@oda.com", "navn": "Oda"},
    "foodora": {"email": "support@foodora.no", "navn": "Foodora"},
    "wolt": {"email": "support@wolt.com", "navn": "Wolt"},
    "meny": {
        "web": "https://meny.no/kundeservice/reklamasjon/",
        "email": "nettbutikk@meny.no", 
        "navn": "Meny",
        "advarsel": "Bruk reklamasjonsskjemaet for raskest behandling."
    },
    "kiwi": {"web": "https://kiwi.no/kundeservice/kontakt-oss/", "navn": "Kiwi", "advarsel": "Kiwi håndterer klager via skjema."},
    "rema": {"web": "https://www.rema.no/kundeservice/", "navn": "Rema 1000"},

    # --- FLYSELSKAP (Mange krever webskjema!) ---
    "sas": {"web": "https://www.sas.no/kundeservice/kontakt/skjemaer/sertifikat-forsinket-innstilt-fly", "navn": "SAS", "advarsel": "Bruk dette skjemaet for EU261-kompensasjon."},
    "norwegian": {"web": "https://www.norwegian.com/no/reiseinformasjon/forsinkelser-og-kanselleringer/forsinkelser/", "navn": "Norwegian", "advarsel": "Norwegian krever at du velger refusjon/krav via denne portalen."},
    "widerøe": {"web": "https://www.wideroe.no/hjelp-og-kontakt/flight-claim", "navn": "Widerøe", "advarsel": "Bruk Widerøes eget skjema for refusjon og erstatning."},
    "ryanair": {"web": "https://onlineform.ryanair.com/no/no/eu-261", "navn": "Ryanair", "advarsel": "Ryanair godtar KUN sitt eget skjema."},
    "wizz": {"web": "https://wizzair.com/en-gb/information-and-services/prices-discounts/refunds-and-compensations", "navn": "Wizz Air"},
    "klm": {"web": "https://www.klm.no/en/information/refund-compensation", "navn": "KLM"},
    "lufthansa": {"web": "https://www.lufthansa.com/no/en/feedback", "navn": "Lufthansa"},
    "air france": {"web": "https://wwws.airfrance.no/en/claim", "navn": "Air France"},
    "british airways": {"web": "https://www.britishairways.com/content/information/delayed-or-cancelled-flights/compensation", "navn": "British Airways"},
    "finnair": {"web": "https://www.finnair.com/no-en/customer-care/feedback-and-claims", "navn": "Finnair"},
    "icelandair": {"web": "https://www.icelandair.com/support/contact-us/claims/", "navn": "Icelandair"},
    "qatar": {"web": "https://www.qatarairways.com/en/help.html", "navn": "Qatar Airways"},
    "emirates": {"web": "https://www.emirates.com/no/english/help/forms/complaint/", "navn": "Emirates"},

    # --- REISE & KOLLEKTIV (Tog, Buss, Ferge) ---
    "vy": {"web": "https://www.vy.no/kundeservice/klage-og-erstatning", "navn": "Vy", "advarsel": "Vy krever bruk av skjema for refusjon."},
    "ruter": {"web": "https://ruter.no/fa-hjelp-og-kontakt/kontaktskjema/", "navn": "Ruter", "advarsel": "Ruter behandler kun klager via skjema (ikke e-post)."},
    "flytoget": {"email": "flytoget@flytoget.no", "navn": "Flytoget"},
    "skyss": {"web": "https://www.skyss.no/hjelp-og-kontakt/kundesenter/kontaktskjema/", "navn": "Skyss (Bergen)"},
    "atb": {"web": "https://www.atb.no/kontakt/", "navn": "AtB (Trondheim)"},
    "kolumbus": {"web": "https://www.kolumbus.no/hjelp-og-kontakt/kontaktskjema/", "navn": "Kolumbus (Stavanger)"},
    "color line": {"web": "https://www.colorline.no/kundeservice/tilbakemelding", "navn": "Color Line"},
    "fjord line": {"email": "info@fjordline.com", "navn": "Fjord Line"},
    "dfds": {"email": "kundeservice@dfds.com", "navn": "DFDS"},

    # --- PARKERING ---
    "apcoa": {"web": "https://www.kontrollavgift.no/", "navn": "Apcoa / EuroPark"},
    "europark": {"web": "https://www.kontrollavgift.no/", "navn": "Apcoa / EuroPark"},
    "aimo": {"web": "https://www.aimopark.no/kontakt-oss/kontrollsanksjon/", "navn": "Aimo Park"},
    "onepark": {"web": "https://onepark.no/klage/", "navn": "ONEPARK"},
    "easypark": {"email": "kundeservice@easypark.no", "navn": "EasyPark"},
    "riverty": {"web": "https://www.riverty.com/no-no/kundeservice/", "navn": "Riverty (Faktura)"},

    # --- TELEKOM & BANK ---
    "telenor": {"web": "https://www.telenor.no/kundeservice/kontakt-oss/", "navn": "Telenor"},
    "telia": {"email": "kundekontakt-privat@telia.no", "navn": "Telia", "advarsel": "Denne e-posten gjelder primært formelle klager."},
    "onecall": {"email": "kundeservice@onecall.no", "navn": "OneCall"},
    "talkmore": {"email": "kundeservice@talkmore.no", "navn": "Talkmore"},
    "ice": {"web": "https://www.ice.no/kundeservice/kontakt-oss/", "navn": "Ice"},
    "vipps": {"web": "https://vipps.no/kontakt-oss/", "navn": "Vipps"},
    "klarna": {"web": "https://www.klarna.com/no/kundeservice/", "navn": "Klarna"},
    "dnb": {"web": "https://www.dnb.no/kundeservice", "navn": "DNB"}
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

# Session state init
if "generated_complaint" not in st.session_state:
    st.session_state.generated_complaint = None
if "detected_company" not in st.session_state:
    st.session_state.detected_company = None
if "uploaded_filenames" not in st.session_state: 
    st.session_state.uploaded_filenames = []

# Random placeholder logic
if "random_placeholder" not in st.session_state:
    eksempler = [
        "F.eks: TV-en slår seg ikke på lenger, og det er striper over skjermen...",
        "F.eks: Flyet fra Gardermoen til London var 4 timer forsinket, og vi fikk ingen matkuponger...",
        "F.eks: Glidelåsen på vinterjakken røk etter bare 2 måneders bruk...",
        "F.eks: Jeg fikk parkeringsbot selv om jeg hadde betalt billett via appen...",
        "F.eks: Sofaen har fått en nedsynk i setet som ikke går bort...",
        "F.eks: Håndverkeren møtte ikke opp til avtalt tid for befaring...",
        "F.eks: Matkassen ble levert med knuste egg og dårlig frukt...",
        "F.eks: Batteriet på mobilen lader ikke lenger over 50%..."
    ]
    st.session_state.random_placeholder = random.choice(eksempler)

# --- HOVEDINNHOLD (AUTOMATISK ER NÅ STANDARD) ---
st.info("🔒 **Trygg opplasting:** Dokumentene analyseres midlertidig og lagres ikke.", icon="🛡️")

col_upload, col_info = st.columns([1, 1])
with col_upload:
    uploaded_files = st.file_uploader(
        "Last opp filer (Kvittering, bilder av skade osv.)", 
        type=["jpg", "jpeg", "png", "pdf"], 
        accept_multiple_files=True
    )
    
with col_info:
    hendelsesdato = st.date_input("Når skjedde dette?", value=date.today())
    
    feil_beskrivelse = st.text_area(
        "Kort beskrivelse av problemet", 
        height=100, 
        placeholder=st.session_state.random_placeholder
    )
    
    losning = st.selectbox("Ønsket løsning", ["Kostnadsfri reparasjon", "Ny vare (omlevering)", "Pengene tilbake (heving)", "Prisavslag", "Erstatning", "Usikker - la AI vurdere"])

tone = st.radio("Tonefall:", ["Saklig (Anbefalt)", "Vennlig", "Veldig formell"], horizontal=True)

if st.button("Generer klageutkast 🚀", type="primary"):
    if not uploaded_files:
        st.error("⚠️ Du må laste opp minst én fil.")
        st.stop()
    if not mitt_navn:
        st.warning("⚠️ Tips: Fyll ut navnet ditt i menyen til venstre for best resultat.")

    try:
        # Lagre filnavn for senere påminnelse
        st.session_state.uploaded_filenames = [f.name for f in uploaded_files]

        all_images = []
        combined_text = ""

        for uploaded_file in uploaded_files:
            if uploaded_file.type == "application/pdf":
                text, img = extract_pdf_data(uploaded_file)
                combined_text += f"\n--- TEKST FRA {uploaded_file.name} ---\n{text}"
                if img: all_images.append(img)
            else:
                img = Image.open(uploaded_file)
                all_images.append(img)
        
        # --- PROMPT ---
        prompt_auto = f"""
        Du er en profesjonell, norsk klagehjelper.
        
        DOKUMENT-TEKST: {combined_text[:6000]}
        
        OPPGAVE:
        1. Analyser vedlagte bilder/dokumenter.
        2. Identifiser hvilket bilde som er KVITTERING (hent kjøpsinfo) og hvilket som er SKADEBEVIS (beskriv feilen).
        3. Skriv en reklamasjon basert på NORSK LOV.
        
        VIKTIG OM SPRÅK:
        - Hele klagebrevet SKAL skrives på NORSK (Bokmål).
        - Oversett all info fra dokumentene til norsk.
        
        VIKTIG OM SIGNATUR (UNNGÅ DOBBEL TEKST):
        - Avslutt brevet kun én gang slik: "Med vennlig hilsen, [Ditt Navn]".
        - IKKE legg til navn, adresse eller e-post på nytt under signaturen hvis det allerede står der.
        
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
            "selskapsnavn_funnet": "string",
            "navn_paa_kvittering": "string (eller null)",
            "emne": "string (På Norsk)",
            "mottaker_epost_gjetning": "string",
            "brødtekst": "string (Kun på Norsk)"
        }}
        """
        
        with st.spinner(f"Analyserer {len(uploaded_files)} dokument(er) og skriver klage..."):
            result_json = generate_complaint(prompt_auto, all_images)
            st.session_state.generated_complaint = result_json
            st.session_state.detected_company = result_json.get("selskapsnavn_funnet", "")
            
    except Exception as e:
        st.error(f"En feil oppstod: {e}")


# ==========================================
# 6. RESULTATVISNING
# ==========================================
if st.session_state.generated_complaint:
    data = st.session_state.generated_complaint
    
    if isinstance(data, dict):
        detected_name = st.session_state.detected_company
        
        doc_name = data.get("navn_paa_kvittering")
        if doc_name and mitt_navn:
            if not check_name_similarity(doc_name, mitt_navn):
                st.error(
                    f"⚠️ **Navnevarsel:** Dokumentet ser ut til å tilhøre **{doc_name}**, "
                    f"men du har registrert navnet ditt som **{mitt_navn}**. "
                    "Sjekk at du bruker ditt eget dokument.", 
                    icon="🚫"
                )

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
                st.info(f"🌐 Dette selskapet bruker primært webskjema/portal.")
                st.link_button(f"Gå til {contact_info['navn']} sitt klageskjema ↗️", web_link)
                
                st.caption("👇 1. Kopier teksten under.")
                st.caption("👉 2. Trykk på knappen over for å lime det inn i skjemaet deres.")
                
                if "email" in contact_info:
                    final_email = contact_info["email"]
                    st.markdown(f"*(Alternativ e-post funnet: `{final_email}` - men webskjema anbefales)*")
            else:
                final_email = contact_info.get("email", "")
                
        else:
            st.warning(f"⚠️ Fant ikke '{detected_name}' i vår verifiserte database. Sjekk at e-posten under er riktig.")
            final_email = data.get("mottaker_epost_gjetning", "")

        if not web_link:
            col_rec_ui, col_subj_ui = st.columns([1, 1])
            with col_rec_ui:
                user_email = st.text_input("Mottaker e-post (kan endres):", value=final_email)
            with col_subj_ui:
                user_subject = st.text_input("Emnefelt:", value=data.get("emne", ""))
        else:
            user_subject = st.text_input("Emnefelt (til skjemaet):", value=data.get("emne", ""))
            user_email = final_email

        st.markdown("### 📝 Klagebrev")
        user_body = st.text_area("Innhold (Redigerbar):", value=data.get("brødtekst", ""), height=400)
        
        st.markdown("---")
        
        st.subheader("✅ Sjekkliste før sending")
        
        c1, c2 = st.columns(2)
        check_rec = c1.checkbox("Mottaker/Skjema er korrekt")
        check_txt = c2.checkbox("Mine detaljer stemmer")
        
        # Knappen er alltid synlig, men 'disabled' til sjekklisten er ok
        is_ready = check_rec and check_txt
        
        st.markdown("---")
        
        if web_link:
                st.info("👈 Kopier teksten til høyre, og bruk 'Gå til klageskjema'-knappen lenger opp.")
        elif user_email and "@" in user_email:
            
            # VIS PÅMINNELSE OM VEDLEGG ALLTID
            if st.session_state.uploaded_filenames:
                files_str = ", ".join(st.session_state.uploaded_filenames)
                st.info(f"📎 **Husk:** Legg ved disse filene manuelt i e-posten: **{files_str}**", icon="⚠️")
            else:
                st.info("📎 **Husk:** Du må legge ved eventuelle bilder/kvitteringer manuelt.", icon="⚠️")

            safe_s = urllib.parse.quote(user_subject)
            safe_b = urllib.parse.quote(user_body)
            mailto = f"mailto:{user_email}?subject={safe_s}&body={safe_b}"
            
            st.link_button(
                "📧 Åpne i E-postprogram", 
                mailto, 
                type="primary", 
                use_container_width=True,
                disabled=not is_ready 
            )
            
            if not is_ready:
                st.caption("🛑 Du må huke av sjekkpunktene over for å aktivere knappen.")
        else:
            st.warning("Mangler e-postadresse.")
    else:
        st.error("Kunne ikke lese svaret fra AI. Prøv å trykke på knappen en gang til.")
