import os
import re
import time
import urllib.parse
from datetime import date
from dotenv import load_dotenv

import streamlit as st
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

# ==========================================
# 1. SETUP & CONFIG
# ==========================================
load_dotenv()
# Vi henter nøkkelen direkte fra systemet/filen.
ENV_API_KEY = os.getenv("GOOGLE_API_KEY", "")

st.set_page_config(page_title="KlageHjelpen", page_icon="⚖️", layout="wide")
st.title("⚖️ KlageHjelpen")
st.markdown("**Din profesjonelle forbruker-agent.**")

# --- DATABASE OVER SELSKAPER OG E-POSTER ---
COMPANY_DB = {
    "Varekjøp": {
        "Elkjøp": "hello@elkjop.no",
        "Power": "kundeservice@power.no",
        "Komplett": "kundeservice@komplett.no",
        "NetOnNet": "kundeservice@netonnet.no",
        "IKEA": "kundeservice.no@ikea.com",
        "Bohus": "kundeservice@bohus.no",
        "Jysk": "kundeservice@jysk.no",
        "XXL": "kundeservice@xxl.no",
        "Zalando": "service@zalando.no",
        "H&M": "kundeservice.no@hm.com",
        "Apple Store": "contactus.no@euro.apple.com"
    },
    "Flyforsinkelse": {
        "SAS": "customer.care@sas.no", 
        "Norwegian": "post.reception@norwegian.com", 
        "Widerøe": "support@wideroe.no",
        "KLM": "mail.information.norway@klm.com",
        "Lufthansa": "customer.relations@lufthansa.com",
        "Ryanair": "Må bruke webskjema (kopier teksten)",
        "Wizz Air": "info@wizzair.com"
    },
    "Parkeringsbot": {
        "Apcoa / EuroPark": "kundesenter@apcoa.no",
        "Aimo Park (Q-Park)": "kunde@aimopark.no",
        "ONEPARK": "kundeservice@onepark.no",
        "Riverty (Faktura)": "parkering.no@riverty.com",
        "EasyPark": "kundeservice@easypark.no",
        "Trondheim Parkering": "post@trondheimparkering.no",
        "Bergen Parkering": "post@bergenparkering.no"
    },
    "Annet / Generell klage": {
        "Telenor": "telenor.klager@telenor.no",
        "Telia": "kundesenter@telia.no",
        "Ice": "kundeservice@ice.no",
        "NextGenTel": "kundeservice@nextgentel.com",
        "SATS": "kundeservice@sats.no",
        "EVO": "oss@evofitness.no",
        "Vy": "tog@vy.no",
        "Ruter": "post@ruter.no",
        "Posten": "kundeservice@posten.no",
        "PostNord": "kundeservice.no@postnord.com"
    },
    "Håndverkertjenester": {}
}

# Konfigurasjon
CATEGORY_CONFIG = {
    "Varekjøp": {
        "law_hint_priv": "Forbrukerkjøpsloven (FKjl). 5 års reklamasjon (hvis ment å vare vesentlig lenger enn 2 år). Bevisbyrde hos selger de første 2 årene.",
        "law_hint_biz": "Kjøpsloven (Kjl). 2 års reklamasjon. Streng undersøkelsesplikt.",
        "recipient_hint": "Kundeservice / Reklamasjonsavdeling",
        "needs": ["kjopsdato", "hendelsesdato", "produkt", "beskrivelse", "hva_har_du_provd", "vedlegg", "krav"],
        "required": {"produkt": "Hvilket produkt?", "beskrivelse": "Beskrivelse av feilen", "krav": "Krav"},
        "claim_options": ["Kostnadsfri reparasjon", "Omlevering (ny vare)", "Prisavslag", "Heving av kjøp"],
        "default_subject": "Reklamasjon – krav om utbedring",
        "placeholders": {
            "produkt": "F.eks. LG OLED TV, iPhone 15, Sovesofa...",
            "beskrivelse": "Stikkord: TV svart, ingen lyd, skjedde i går, kjøpt 2023...",
            "hva_har_du_provd": "Stikkord: Startet på nytt, byttet kabel..."
        }
    },
    "Flyforsinkelse": {
        "law_hint_override": "EU-forordning 261/2004 (EU261). Rett til standardkompensasjon ved forsinkelse > 3 timer.",
        "recipient_hint": "Customer Relations / Claims Department",
        "needs": ["dato", "flightnr", "fra_til", "forsinkelse_timer", "utgifter", "beskrivelse", "vedlegg", "krav"],
        "required": {"flightnr": "Flightnummer", "forsinkelse_timer": "Antall timer forsinket", "krav": "Krav"},
        "claim_options": ["Standardkompensasjon (EU261)", "Refusjon av utgifter", "Ombooking/refusjon"],
        "default_subject": "Krav om kompensasjon ved flyforsinkelse (EU261)",
        "placeholders": {
            "flightnr": "F.eks. SK123, DY456...",
            "fra_til": "F.eks. OSL - LHR (London)",
            "beskrivelse": "Stikkord: Kansellert 2 timer før, ingen mat, ventet 5 timer...",
            "utgifter": "Stikkord: Hotell 2000kr, Taxi 500kr (har kvittering)."
        }
    },
    "Håndverkertjenester": {
        "law_hint_priv": "Håndverkertjenesteloven. Fagmessig utførelse. 5 års reklamasjon på resultatet.",
        "law_hint_biz": "Avtalen/Kontrakten gjelder (NS-standarder e.l.).",
        "recipient_hint": "Daglig leder",
        "needs": ["dato", "arbeid", "mangel", "beskrivelse", "vedlegg", "krav"],
        "required": {"arbeid": "Hva ble utført?", "mangel": "Hva er feil?", "krav": "Krav"},
        "claim_options": ["Retting (utbedring)", "Prisavslag", "Heving", "Erstatning"],
        "default_subject": "Reklamasjon på håndverkertjeneste",
        "placeholders": {
            "motpart": "F.eks. Oslo Rørleggerservice AS...",
            "arbeid": "F.eks. Pusset opp badet, byttet varmtvannstank...",
            "beskrivelse": "Stikkord: Lekker vann under vasken, fugene sprekker, arbeid gjort for 3 mnd siden...",
            "mangel": "Stikkord: Lekkasje, skjeve fliser..."
        }
    },
    "Parkeringsbot": {
        "law_hint_override": "Parkeringsforskriften § 36 og vilkårene på stedet. Vurder om skilting var tydelig.",
        "recipient_hint": "Klageavdeling",
        "needs": ["dato", "sted", "kontrollsanksjon_nr", "grunn", "bevis", "vedlegg", "krav"],
        "required": {"kontrollsanksjon_nr": "Bot-nummer", "grunn": "Begrunnelse", "krav": "Krav"},
        "claim_options": ["Annullering av bot", "Omgjøring", "Reduksjon"],
        "default_subject": "Klage på kontrollsanksjon (parkeringsbot)",
        "placeholders": {
            "sted": "F.eks. Storsenteret P-hus...",
            "kontrollsanksjon_nr": "F.eks. KS-12345678 (se øverst på boten)",
            "beskrivelse": "Stikkord: Hadde gyldig billett i ruten, appen virket ikke, skilting dekket av snø...",
            "grunn": "Stikkord: Automat ute av drift, gyldig billett, dårlig skiltet..."
        }
    },
    "Annet / Generell klage": {
        "law_hint_priv": "Alminnelig avtalerett. Vurder kontrakten/avtalen og hva som er rimelig å forvente.",
        "law_hint_biz": "Avtalerett.",
        "recipient_hint": "Kundeservice",
        "needs": ["dato", "beskrivelse", "hva_har_du_provd", "vedlegg", "krav"],
        "required": {"beskrivelse": "Hva gjelder saken?", "krav": "Krav"},
        "claim_options": ["Erstatning", "Retting/Utbedring", "Heving/Oppsigelse", "Krav om forklaring"],
        "default_subject": "Klage vedrørende avtaleforhold",
        "placeholders": {
            "beskrivelse": "Stikkord: Fakturert feil beløp, sa opp abonnement i fjor, ingen svar fra kundeservice...",
            "hva_har_du_provd": "Stikkord: Sendt e-post, ringt..."
        }
    }
}

# ==========================================
# 2. HJELPEFUNKSJONER
# ==========================================

def show_if(field_name: str, needs_list: list) -> bool:
    return field_name in needs_list

def clean_text(text: str) -> str:
    # Fjerner markdown-symboler som stjerner og hashtags
    text = text.replace("**", "").replace("##", "").replace("__", "")
    text = text.replace("*", "") # Fjerner enkelt-stjerner også
    text = text.replace("#", "")
    # Fjerner også eksplisitte titler hvis AI-en skulle finne på å skrive dem
    text = text.replace("Problembeskrivelse:", "").replace("Juridisk grunnlag:", "")
    return text.strip()

def extract_email(text: str) -> str:
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text or "")
    return match.group(0) if match else ""

def parse_ai_output(text: str, default_subject: str) -> tuple[str, str, str]:
    text = clean_text(text)
    
    emne = default_subject
    m_emne = re.search(r"MAIL_EMNE:\s*(.*)", text, re.IGNORECASE)
    if m_emne:
        emne = m_emne.group(1).strip()
    
    epost = ""
    m_rec = re.search(r"MAIL_MOTTAKER:\s*(.*)", text, re.IGNORECASE)
    if m_rec:
        epost = extract_email(m_rec.group(1).strip())

    m_body = re.search(r"MAIL_BODY:\s*", text, re.IGNORECASE)
    if m_body:
        body = text[m_body.end():].strip()
    else:
        body = text

    return emne, epost, body

def validate_required(kategori: str, values: dict) -> list[str]:
    missing = []
    if not values.get("mitt_navn"): missing.append("Ditt navn")
    if not values.get("motpart"): missing.append("Selskap/Motpart")
    
    req_dict = CATEGORY_CONFIG[kategori].get("required", {})
    for key, label in req_dict.items():
        val = values.get(key)
        if val is None or val == "" or val is False:
            missing.append(label)
    return missing

def build_law_hint(cfg: dict, rolle: str) -> str:
    if "law_hint_override" in cfg:
        return cfg["law_hint_override"]
    return cfg["law_hint_priv"] if rolle == "Privatperson" else cfg["law_hint_biz"]

def format_vedlegg_list(uploaded_files) -> str:
    if not uploaded_files: return "Ingen"
    return ", ".join([f.name for f in uploaded_files])

@st.cache_data(show_spinner=False, ttl=3600)
def generate_with_gemini(prompt: str, api_key: str, use_search: bool) -> str:
    genai.configure(api_key=api_key)
    model_name = "gemini-1.5-flash"
    
    if use_search:
        model = genai.GenerativeModel(model_name, tools=[{"google_search": {}}])
    else:
        model = genai.GenerativeModel(model_name)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except ResourceExhausted:
            time.sleep(2 * (attempt + 1)) 
            if attempt == max_retries - 1:
                raise 
        except Exception as e:
            raise e
    
    return ""

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
    ordrenummer = st.text_input("Ordrenummer (hvis aktuelt)")
    
    # --- DONASJON ---
    st.markdown("---")
    st.header("☕ Støtt prosjektet")
    st.info("KlageHjelpen er gratis å bruke. Hvis vi hjalp deg med å spare penger, setter vi stor pris på en liten donasjon!")
    
    # Buy Me a Coffee
    st.link_button("☕ Spander en kaffe", "https://buymeacoffee.com/klagehjelpen")
    
    # Vipps Donasjon
    with st.expander("🧡 Vipps en gave"):
        st.markdown("**Vipps-nummer:** `901 135 31`")
        st.markdown("Merk gjerne med 'Klagehjelp'. Tusen takk!")

# ==========================================
# 4. HOVEDSKJEMA
# ==========================================

st.subheader("1. Hva gjelder saken?")

c_kat, c_sel = st.columns(2)

with c_kat:
    kategori = st.selectbox("Velg kategori:", list(CATEGORY_CONFIG.keys()))
    cfg = CATEGORY_CONFIG[kategori]
    needs = cfg["needs"]
    ph = cfg.get("placeholders", {})
    company_list = COMPANY_DB.get(kategori, {})

with c_sel:
    show_manual_inputs = True
    prefilled_email = ""
    valgt_fra_liste = None

    if company_list:
        options = sorted(list(company_list.keys())) + ["Annet / Ikke i listen"]
        valgt_fra_liste = st.selectbox("Velg selskap:", options, index=None, placeholder="Velg fra listen...")
        
        if valgt_fra_liste and valgt_fra_liste != "Annet / Ikke i listen":
            show_manual_inputs = False
            prefilled_email = company_list[valgt_fra_liste]
            st.success(f"✅ E-post funnet: {prefilled_email}")
    else:
        st.write("") 

# --- SELVE SKJEMAET ---
with st.form("klage_form"):
    
    c1, c2, c3 = st.columns([2, 1, 1])
    
    with c1:
        motpart = ""
        
        if show_manual_inputs:
            motpart = st.text_input("Navn på selskap/motpart", placeholder=ph.get("motpart", "F.eks. Firmanavn AS"))
            manuel_epost = st.text_input("E-post til mottaker (valgfritt)", placeholder="post@firma.no", help="Fylles ut hvis du har den.")
            if manuel_epost:
                prefilled_email = manuel_epost
        else:
            st.text_input("Mottaker", value=f"{valgt_fra_liste} ({prefilled_email})", disabled=True)
            motpart = valgt_fra_liste

    with c2:
        tone = st.selectbox("Tone", ["Kort og bestemt", "Formell juridisk", "Vennlig"], index=1)
    with c3:
        lengde = st.select_slider("Lengde", options=["Kort", "Medium", "Detaljert"], value="Medium")

    st.subheader("2. Detaljer om saken")
    
    kjopsdato = hendelsesdato = dato = None
    produkt = flightnr = fra_til = forsinkelse_timer = sted = kontrollsanksjon_nr = arbeid = None
    beskrivelse = hva_har_du_provd = utgifter = grunn = bevis = mangel = None

    d1, d2 = st.columns(2)
    if show_if("kjopsdato", needs):
        with d1: kjopsdato = st.date_input("Kjøpsdato", value=date(2023, 1, 1))
    if show_if("hendelsesdato", needs):
        with d2: hendelsesdato = st.date_input("Når oppstod feilen?", value=date.today())
    if show_if("dato", needs):
        with d1: dato = st.date_input("Dato for hendelse", value=date.today())

    if show_if("produkt", needs):
        produkt = st.text_input("Produkt (modell)", placeholder=ph.get("produkt", "F.eks. Varenavn..."))
    
    if show_if("flightnr", needs):
        flightnr = st.text_input("Flightnummer", placeholder=ph.get("flightnr", "SK123..."))
    if show_if("fra_til", needs):
        fra_til = st.text_input("Strekning", placeholder=ph.get("fra_til", "OSL - CPH"))
    if show_if("forsinkelse_timer", needs):
        forsinkelse_timer = st.number_input("Forsinkelse (timer)", min_value=0.0, step=0.5)

    if show_if("sted", needs):
        sted = st.text_input("Sted / P-plass", placeholder=ph.get("sted", "Gateadresse..."))
    if show_if("kontrollsanksjon_nr", needs):
        kontrollsanksjon_nr = st.text_input("Bot-nummer", placeholder=ph.get("kontrollsanksjon_nr", "KS-nummer..."))

    if show_if("arbeid", needs):
        arbeid = st.text_area("Hva ble avtalt/utført?", height=80, placeholder=ph.get("arbeid", "Beskriv jobben..."))
    
    beskr_label = "Beskrivelse (stikkord er nok)"
    if show_if("grunn", needs): beskr_label = "Hvorfor er boten feil? (stikkord)" 
    if show_if("mangel", needs): beskr_label = "Hva er mangelen? (stikkord)"
    
    if show_if("beskrivelse", needs) or show_if("grunn", needs) or show_if("mangel", needs):
        beskr_hint = ph.get("beskrivelse", ph.get("grunn", ph.get("mangel", "Stikkord: ...")))
        beskrivelse = st.text_area(beskr_label, height=120, placeholder=beskr_hint)
    
    if show_if("hva_har_du_provd", needs):
        hva_har_du_provd = st.text_area("Har du forsøkt å løse det?", height=80, placeholder=ph.get("hva_har_du_provd", "Stikkord: Kontaktet kundeservice..."))
    
    if show_if("utgifter", needs):
        utgifter = st.text_area("Dine utgifter (husk kvittering)", height=80, placeholder=ph.get("utgifter", "Stikkord: Sum og type utgift..."))
        
    if show_if("bevis", needs):
        bevis = st.text_area("Bevis", height=80, placeholder="Stikkord: Bilder, logg...")

    vedlegg_files = None
    if show_if("vedlegg", needs):
        vedlegg_files = st.file_uploader("Vedlegg (Bilder/Kvittering)", accept_multiple_files=True)

    st.subheader("3. Krav")
    krav = st.selectbox("Hva krever du?", cfg["claim_options"])

    submit = st.form_submit_button("Opprett klage")

# ==========================================
# 5. LOGIKK & GENERERING
# ==========================================
if submit:
    if not ENV_API_KEY:
        st.error("❌ Fant ingen API-nøkkel i .env-filen! Kontakt administrator.")
        st.stop()
        
    if kjopsdato and hendelsesdato and kjopsdato > hendelsesdato:
        st.error("⚠️ Kjøpsdato kan ikke være etter at feilen oppstod.")
        st.stop()

    raw_values = {
        "mitt_navn": mitt_navn, "motpart": motpart, "produkt": produkt, "beskrivelse": beskrivelse,
        "flightnr": flightnr, "forsinkelse_timer": forsinkelse_timer, "arbeid": arbeid, 
        "mangel": beskrivelse, "kontrollsanksjon_nr": kontrollsanksjon_nr, "grunn": beskrivelse, "krav": krav
    }
    
    missing = validate_required(kategori, raw_values)
    if missing:
        st.error(f"⚠️ Du må fylle ut: {', '.join(missing)}")
        st.stop()

    law_hint = build_law_hint(cfg, rolle)
    vedlegg_txt = format_vedlegg_list(vedlegg_files)
    
    case_summary_list = [f"Rolle: {rolle}", f"Kategori: {kategori}", f"Lovverk: {law_hint}"]
    if prefilled_email: case_summary_list.append(f"Kjent E-post (BRUK DENNE): {prefilled_email}")
    if produkt: case_summary_list.append(f"Produkt: {produkt}")
    if flightnr: case_summary_list.append(f"Flight: {flightnr} ({fra_til}), {forsinkelse_timer}t forsinket")
    if kontrollsanksjon_nr: case_summary_list.append(f"Bot-nr: {kontrollsanksjon_nr} på {sted}")
    if arbeid: case_summary_list.append(f"Arbeid: {arbeid}")
    if kjopsdato: case_summary_list.append(f"Kjøpsdato: {kjopsdato}")
    if hendelsesdato: case_summary_list.append(f"Hendelsesdato: {hendelsesdato}")
    if dato: case_summary_list.append(f"Dato: {dato}")
    
    case_summary_list.append(f"Beskrivelse/Problem (Stikkord): {beskrivelse}")
    if hva_har_du_provd: case_summary_list.append(f"Forsøkt: {hva_har_du_provd}")
    if utgifter: case_summary_list.append(f"Utgifter: {utgifter}")
    if bevis: case_summary_list.append(f"Bevis: {bevis}")
    
    case_summary_list.append(f"KRAV: {krav}")
    case_summary_str = "\n".join(case_summary_list)

    with st.expander("🧾 Se hva agenten bruker av info", expanded=False):
        st.text(case_summary_str)
        if vedlegg_txt != "Ingen": st.caption(f"Vedlegg notert: {vedlegg_txt}")

    prompt = f"""
    Du skriver en klage PÅ VEGNE AV en bruker. Skriv i JEG-form.
    IKKE utgi deg for å være advokat. 

    VIKTIG: 
    1. Brukeren skriver ofte kun stikkord i beskrivelsen. DIN JOBB: Omskriv stikkordene til fullstendige, flytende og profesjonelle setninger.
    2. ALDRI bruk markdown, stjerner (*), hashtags (#) i teksten.
    3. ALDRI bruk overskrifter som "Problembeskrivelse" eller "Juridisk grunnlag" inne i teksten.
    4. Skriv alt som et sammenhengende brev med naturlige avsnitt.
    
    E-POST HÅNDTERING:
    Jeg har lagt ved en e-post i dataene under (se etter 'Kjent E-post').
    - HVIS den finnes: Bruk den som MAIL_MOTTAKER.
    - HVIS IKKE: Søk på nettet etter kundeservice/klage e-post for {motpart}.
    
    OPPGAVE:
    Skriv en profesjonell klage basert på fakta under.
    
    STIL: {tone}. Lengde: {lengde}.
    MOTPART: {motpart} (Hint: {cfg.get('recipient_hint')})
    
    OUTPUT FORMAT (MÅ FØLGES):
    MAIL_EMNE: <Emne>
    MAIL_MOTTAKER: <E-posten>
    MAIL_BODY:
    <Selve teksten>

    INNHOLD:
    - Start med "Hei," eller "Til {motpart},".
    - Vær konkret på hva som har skjedd (gjør stikkord om til tekst) i et flytende språk.
    - Gå naturlig over til å henvise til lovverk ({law_hint}) uten å bruke overskrifter.
    - Fremsett kravet tydelig med frist (f.eks 7-10 dager).
    - Avslutt med navn og kontaktinfo.

    DATA:
    Avsender: {mitt_navn} ({min_epost})
    Ordrenr: {ordrenummer if ordrenummer else "Se vedlegg"}
    Vedlegg referanse: {vedlegg_txt}
    
    SAK:
    {case_summary_str}
    """

    with st.spinner("Agenten søker og skriver..."):
        try:
            raw_text = generate_with_gemini(prompt, ENV_API_KEY, use_search=True)
        except Exception:
            raw_text = generate_with_gemini(prompt, ENV_API_KEY, use_search=False)

    emne, epost_mottaker, body = parse_ai_output(raw_text, cfg["default_subject"])
    
    if prefilled_email and (not epost_mottaker or "@" not in epost_mottaker or epost_mottaker == "None"):
        epost_mottaker = prefilled_email
    elif prefilled_email:
        epost_mottaker = prefilled_email

    st.success("✅ Klagen er klar!")

    final_email = st.text_input("Mottaker e-post", value=epost_mottaker)
    
    if kategori == "Flyforsinkelse":
        st.warning("⚠️ OBS: Flyselskaper krever ofte at du bruker deres webskjema. Du kan kopiere teksten under og lime inn i skjemaet deres.")

    safe_subject = urllib.parse.quote(emne)
    safe_body = urllib.parse.quote(body)
    mailto_link = f"mailto:{final_email}?subject={safe_subject}&body={safe_body}"

    col_btn, col_msg = st.columns([1, 2])
    with col_btn:
        st.link_button("📧 Åpne E-post", mailto_link, type="primary")
    with col_msg:
        if not final_email:
            st.warning("⚠️ Ingen mottaker. Du må lime inn e-posten selv.")
        else:
            st.info(f"Klar til sending: **{final_email}**")

    st.text_area("Innhold (Kopier/Lim inn):", value=body, height=450)