import os
import json
import uuid
import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# =========================================================
# OFFERTLY – FAS 13
# Online-deployment utan domänkoppling
# Bas: Fas 12
# Fix: publik kundlänk online + Streamlit secrets + företagsbeskrivning i PDF
# Offert → kundgodkännande → kontrakt → faktura
# =========================================================

load_dotenv()

st.set_page_config(
    page_title="Offertly",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# CONFIG
# =========================================================

def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass

    return os.getenv(name, default)


VAT_RATE = 0.25
ROT_RATE = float(get_secret("ROT_RATE", "0.30"))

APP_BASE_URL = get_secret("APP_BASE_URL", "http://localhost:8501").rstrip("/")
SUPABASE_URL = get_secret("SUPABASE_URL", "")
SUPABASE_ANON_KEY = get_secret("SUPABASE_ANON_KEY", "")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY", "")
OPENAI_MODEL = get_secret("OPENAI_MODEL", "gpt-4o-mini")


# =========================================================
# STYLE
# =========================================================

st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        .block-container {
            padding-top: 2rem;
            padding-bottom: 4rem;
            max-width: 1240px;
        }

        .offertly-hero {
            padding: 30px 32px;
            border-radius: 26px;
            background: linear-gradient(135deg, #0f172a 0%, #111827 48%, #334155 100%);
            color: white;
            margin-bottom: 24px;
            box-shadow: 0 18px 55px rgba(15, 23, 42, 0.22);
        }

        .offertly-hero h1 {
            margin: 0;
            font-size: 2.55rem;
            letter-spacing: -0.045em;
            line-height: 1.05;
        }

        .offertly-hero p {
            margin-top: 12px;
            color: #d1d5db;
            font-size: 1.05rem;
            max-width: 860px;
        }

        .premium-card {
            padding: 22px;
            border-radius: 22px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            box-shadow: 0 12px 35px rgba(15, 23, 42, 0.06);
            margin-bottom: 18px;
        }

        .soft-card {
            padding: 18px;
            border-radius: 18px;
            border: 1px solid #e5e7eb;
            background: #f9fafb;
            margin-bottom: 14px;
        }

        .status-pill {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 999px;
            background: #f3f4f6;
            color: #111827;
            font-size: 0.8rem;
            font-weight: 700;
        }

        .success-pill {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 999px;
            background: #dcfce7;
            color: #166534;
            font-size: 0.8rem;
            font-weight: 700;
        }

        .warning-pill {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 999px;
            background: #fef3c7;
            color: #92400e;
            font-size: 0.8rem;
            font-weight: 700;
        }

        .danger-pill {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 999px;
            background: #fee2e2;
            color: #991b1b;
            font-size: 0.8rem;
            font-weight: 700;
        }

        .metric-box {
            padding: 18px;
            border-radius: 18px;
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.04);
        }

        .metric-box h3 {
            margin: 0;
            font-size: 1.45rem;
            letter-spacing: -0.02em;
        }

        .metric-box p {
            margin: 4px 0 0 0;
            color: #6b7280;
            font-size: 0.9rem;
        }

        .flow-bar {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 8px;
            margin-bottom: 12px;
        }

        .flow-step {
            padding: 8px 10px;
            border-radius: 999px;
            background: #f3f4f6;
            color: #4b5563;
            font-size: 0.78rem;
            font-weight: 700;
            border: 1px solid #e5e7eb;
        }

        .flow-step-active {
            background: #111827;
            color: white;
            border: 1px solid #111827;
        }

        .flow-step-done {
            background: #dcfce7;
            color: #166534;
            border: 1px solid #bbf7d0;
        }

        .public-wrapper {
            max-width: 920px;
            margin: 0 auto;
        }

        .public-card {
            padding: 30px;
            border-radius: 26px;
            border: 1px solid #e5e7eb;
            background: white;
            box-shadow: 0 16px 45px rgba(15, 23, 42, 0.08);
            margin-bottom: 22px;
        }

        .public-header {
            padding: 30px;
            border-radius: 26px;
            background: linear-gradient(135deg, #0f172a 0%, #111827 65%, #334155 100%);
            color: white;
            margin-bottom: 22px;
            box-shadow: 0 18px 55px rgba(15, 23, 42, 0.18);
        }

        .public-header p {
            color: #d1d5db;
        }

        .small-muted {
            color: #6b7280;
            font-size: 0.88rem;
        }

        .stButton > button {
            border-radius: 12px;
            font-weight: 700;
        }

        .stDownloadButton > button {
            border-radius: 12px;
            font-weight: 700;
        }

        div[data-testid="stMetric"] {
            background: #f9fafb;
            padding: 14px;
            border-radius: 16px;
            border: 1px solid #e5e7eb;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HELPERS
# =========================================================

def money(value: Any) -> str:
    try:
        number = float(value or 0)
    except Exception:
        number = 0.0
    return f"{number:,.2f} kr".replace(",", "X").replace(".", ",").replace("X", " ")


def today_iso() -> str:
    return datetime.date.today().isoformat()


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def safe_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def pdf_text(value: Any, fallback: str = "") -> str:
    return escape(safe_text(value, fallback))


def safe_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def safe_json_loads(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback


def generate_offer_number() -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d")
    short = uuid.uuid4().hex[:6].upper()
    return f"OFF-{stamp}-{short}"


def generate_contract_number() -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d")
    short = uuid.uuid4().hex[:6].upper()
    return f"AVT-{stamp}-{short}"


def generate_invoice_number() -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d")
    short = uuid.uuid4().hex[:6].upper()
    return f"FAK-{stamp}-{short}"


def status_label(status: str) -> str:
    labels = {
        "draft": "Utkast",
        "sent": "Skickad",
        "approved": "Godkänd",
        "signed_with_bankid": "Signerad med BankID",
        "contract_created": "Kontrakt skapat",
        "invoiced": "Fakturerad",
    }
    return labels.get(status or "draft", status or "Utkast")


def status_badge(status: str) -> str:
    status = status or "draft"

    if status in ["approved", "signed_with_bankid", "contract_created", "invoiced"]:
        css = "success-pill"
    elif status == "sent":
        css = "warning-pill"
    elif status == "draft":
        css = "status-pill"
    else:
        css = "danger-pill"

    return f'<span class="{css}">{status_label(status)}</span>'


def status_order() -> List[str]:
    return ["draft", "sent", "approved", "contract_created", "invoiced"]


def status_progress_html(status: str) -> str:
    current = status or "draft"
    order = status_order()

    if current == "signed_with_bankid":
        current = "approved"

    try:
        current_index = order.index(current)
    except ValueError:
        current_index = 0

    labels = {
        "draft": "Utkast",
        "sent": "Skickad",
        "approved": "Godkänd",
        "contract_created": "Kontrakt",
        "invoiced": "Faktura",
    }

    html = '<div class="flow-bar">'

    for index, item in enumerate(order):
        if index < current_index:
            css = "flow-step flow-step-done"
        elif index == current_index:
            css = "flow-step flow-step-active"
        else:
            css = "flow-step"

        html += f'<span class="{css}">{labels[item]}</span>'

    html += "</div>"
    return html


def get_public_link(public_token: str) -> str:
    return f"{APP_BASE_URL}/?offer={public_token}"


def calculate_totals(price_rows: List[Dict[str, Any]], include_rot: bool) -> Dict[str, float]:
    subtotal_ex_vat = 0.0
    labor_ex_vat = 0.0

    for row in price_rows:
        qty = safe_float(row.get("qty", 1))
        unit_price = safe_float(row.get("unit_price", 0))
        row_type = row.get("type", "Övrigt")
        row_total = qty * unit_price

        subtotal_ex_vat += row_total

        if row_type == "Arbete":
            labor_ex_vat += row_total

    vat_amount = subtotal_ex_vat * VAT_RATE
    total_inc_vat = subtotal_ex_vat + vat_amount
    labor_total_inc_vat = labor_ex_vat * (1 + VAT_RATE)
    rot_deduction = labor_total_inc_vat * ROT_RATE if include_rot else 0.0
    total_after_rot = max(total_inc_vat - rot_deduction, 0)

    return {
        "subtotal_ex_vat": subtotal_ex_vat,
        "vat_amount": vat_amount,
        "total_inc_vat": total_inc_vat,
        "labor_total_inc_vat": labor_total_inc_vat,
        "rot_deduction": rot_deduction,
        "total_after_rot": total_after_rot,
    }


def normalize_price_rows(rows: Any) -> List[Dict[str, Any]]:
    loaded = safe_json_loads(rows, [])

    if not isinstance(loaded, list):
        return []

    normalized = []

    for row in loaded:
        if not isinstance(row, dict):
            continue

        description = safe_text(row.get("description") or row.get("name") or "")
        row_type = safe_text(row.get("type") or row.get("kind") or "Övrigt")
        qty = safe_float(row.get("qty", 1))
        unit = safe_text(row.get("unit") or "st")
        unit_price = safe_float(row.get("unit_price", row.get("price", 0)))

        normalized.append(
            {
                "description": description,
                "type": row_type,
                "qty": qty,
                "unit": unit,
                "unit_price": unit_price,
                "total": qty * unit_price,
            }
        )

    return normalized


def get_scope_rows(price_rows: List[Dict[str, Any]]) -> List[str]:
    scope = []

    for row in price_rows:
        description = safe_text(row.get("description", "")).strip()
        unit_price = safe_float(row.get("unit_price", 0))
        qty = safe_float(row.get("qty", 0))

        if description and unit_price <= 0 and qty <= 1:
            scope.append(description)

    return scope


def get_priced_rows(price_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in price_rows if safe_float(row.get("unit_price", 0)) > 0]


def is_company_profile_ready(profile: Optional[Dict[str, Any]]) -> bool:
    if not profile:
        return False

    required = [
        "company_name",
        "org_number",
        "contact_person",
        "phone",
        "email",
        "address",
        "company_description",
        "default_terms",
        "payment_info",
    ]

    return all(safe_text(profile.get(field)).strip() for field in required)


def company_profile_score(profile: Optional[Dict[str, Any]]) -> int:
    if not profile:
        return 0

    fields = [
        "company_name",
        "org_number",
        "contact_person",
        "phone",
        "email",
        "address",
        "website",
        "company_description",
        "default_terms",
        "payment_info",
    ]

    filled = sum(1 for field in fields if safe_text(profile.get(field)).strip())
    return int((filled / len(fields)) * 100)


def offer_has_valid_price(offer: Dict[str, Any]) -> bool:
    return safe_float(offer.get("total_inc_vat")) > 0


def render_profile_warning(profile: Optional[Dict[str, Any]]):
    if not is_company_profile_ready(profile):
        st.warning(
            "Företagsprofilen är inte helt färdig. Fyll i företagsnamn, org.nr, kontaktuppgifter, "
            "företagsbeskrivning, villkor och betalningsinformation innan Offertly används med riktiga kunder."
        )


def build_offer_validation_errors(
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    project_title: str,
    raw_project_description: str,
    labor_amount: float,
    material_amount: float,
    other_amount: float,
    include_rot: bool,
) -> List[str]:
    errors = []

    if not customer_name.strip():
        errors.append("Kundens namn saknas.")

    if not customer_email.strip() and not customer_phone.strip():
        errors.append("Fyll i minst kundens e-post eller telefon.")

    if not project_title.strip():
        errors.append("Projekttitel saknas.")

    if len(raw_project_description.strip()) < 20:
        errors.append("Projektinformationen är för kort. Skriv minst några meningar så AI och PDF blir professionella.")

    if labor_amount <= 0 and material_amount <= 0 and other_amount <= 0:
        errors.append("Minst en prisrad måste ha ett belopp större än 0 kr.")

    if include_rot and labor_amount <= 0:
        errors.append("ROT kan bara användas när arbetskostnad är större än 0 kr.")

    return errors


# =========================================================
# SUPABASE
# =========================================================

@st.cache_resource
def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        st.error("Supabase saknas. Kontrollera SUPABASE_URL och SUPABASE_ANON_KEY i .env lokalt eller Streamlit secrets online.")
        st.stop()

    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


supabase: Client = get_supabase()


def restore_session() -> Optional[Dict[str, Any]]:
    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")

    if access_token and refresh_token:
        try:
            supabase.auth.set_session(access_token, refresh_token)
        except Exception:
            pass

    return st.session_state.get("user")


def current_user() -> Optional[Dict[str, Any]]:
    return restore_session()


def sign_out():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    st.session_state.clear()
    st.rerun()


def fetch_company_profile(user_id: str) -> Optional[Dict[str, Any]]:
    try:
        res = (
            supabase.table("company_profiles")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if res.data:
            return res.data[0]

    except Exception:
        return None

    return None


def upsert_company_profile(user_id: str, data: Dict[str, Any]):
    payload = dict(data)
    payload["user_id"] = user_id

    return (
        supabase.table("company_profiles")
        .upsert(payload, on_conflict="user_id")
        .execute()
    )


def fetch_offers(user_id: str) -> List[Dict[str, Any]]:
    try:
        res = (
            supabase.table("offers")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        return res.data or []

    except Exception as e:
        st.error(f"Kunde inte hämta offerter: {e}")
        return []


def fetch_public_offer(public_token: str) -> Optional[Dict[str, Any]]:
    """
    Fas 13-fix:
    get_public_offer_by_token(uuid) returnerar normalt:
    {
        "success": true,
        "offer": {...},
        "company_profile": {...}
    }

    Kundvyn ska använda data["offer"], inte hela data-paketet.
    """
    try:
        res = supabase.rpc("get_public_offer_by_token", {"p_token": public_token}).execute()

        if res.data:
            data = res.data[0] if isinstance(res.data, list) else res.data

            if isinstance(data, dict) and "offer" in data:
                offer = data.get("offer") or {}
                company_profile = data.get("company_profile") or {}

                if isinstance(offer, dict):
                    offer["_company_profile"] = company_profile if isinstance(company_profile, dict) else {}
                    return offer

            if isinstance(data, dict):
                return data

    except Exception:
        pass

    try:
        res = (
            supabase.table("offers")
            .select("*")
            .eq("public_token", public_token)
            .limit(1)
            .execute()
        )

        if res.data:
            return res.data[0]

    except Exception:
        return None

    return None


def approve_public_offer(public_token: str):
    return supabase.rpc("approve_offer_by_token", {"p_token": public_token}).execute()


def create_offer(user_id: str, payload: Dict[str, Any]):
    payload["user_id"] = user_id
    payload["public_token"] = str(uuid.uuid4())
    payload["offer_number"] = payload.get("offer_number") or generate_offer_number()
    payload["status"] = payload.get("status") or "draft"

    res = supabase.table("offers").insert(payload).execute()
    return res.data[0] if res.data else None


def update_offer(offer_id: str, user_id: str, payload: Dict[str, Any]):
    return (
        supabase.table("offers")
        .update(payload)
        .eq("id", offer_id)
        .eq("user_id", user_id)
        .execute()
    )


def delete_offer(offer_id: str, user_id: str):
    return (
        supabase.table("offers")
        .delete()
        .eq("id", offer_id)
        .eq("user_id", user_id)
        .execute()
    )


# =========================================================
# AI
# =========================================================

def generate_ai_offer_text(
    project_type: str,
    project_title: str,
    project_description: str,
    customer_name: str,
    company_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    fallback = {
        "professional_description": project_description,
        "scope": [
            "Genomgång av projektets omfattning",
            "Planering och utförande enligt överenskommelse",
            "Utförande enligt branschpraxis och överenskommen omfattning",
            "Avstämning med kund vid behov",
        ],
        "terms": [
            "Priset gäller enligt angiven omfattning.",
            "Eventuella tilläggsarbeten debiteras efter separat överenskommelse.",
            "Betalning sker enligt angivna betalningsvillkor.",
        ],
        "customer_message": "Tack för möjligheten att lämna offert. Vi ser fram emot att hjälpa dig med projektet.",
    }

    if not OPENAI_API_KEY or OpenAI is None:
        return fallback

    company_name = ""

    if company_profile:
        company_name = safe_text(company_profile.get("company_name", ""))

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        prompt = f"""
Du är en svensk offertspecialist för hantverkare.

Skapa professionell offerttext på svenska.

Viktigt:
- Hitta inte på priser.
- Hitta inte på garantier som inte står i underlaget.
- Hitta inte på certifieringar som inte står i underlaget.
- Skriv tydligt, seriöst och säljande.
- Anpassa texten till bygg/hantverksbranschen.
- Skriv så att texten kan skickas till en riktig privatkund.
- Returnera endast JSON.

Företag: {company_name}
Kund: {customer_name}
Projekttyp: {project_type}
Projekttitel: {project_title}

Projektinformation från hantverkaren:
{project_description}

Returnera JSON med exakt dessa nycklar:
{{
  "professional_description": "...",
  "scope": ["...", "..."],
  "terms": ["...", "..."],
  "customer_message": "..."
}}
"""

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Du skriver professionella svenska offerter för hantverkare.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.35,
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        return {
            "professional_description": data.get("professional_description") or fallback["professional_description"],
            "scope": data.get("scope") or fallback["scope"],
            "terms": data.get("terms") or fallback["terms"],
            "customer_message": data.get("customer_message") or fallback["customer_message"],
        }

    except Exception:
        return fallback


# =========================================================
# PDF
# =========================================================

def pdf_styles():
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="OffertlyTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#111827"),
            spaceAfter=14,
        )
    )

    styles.add(
        ParagraphStyle(
            name="OffertlyH2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#111827"),
            spaceBefore=12,
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="OffertlyBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#111827"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="OffertlySmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#6B7280"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="OffertlyRight",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#111827"),
        )
    )

    return styles


def add_pdf_header(elements, styles, document_type: str, company: Optional[Dict[str, Any]], number: str):
    company_name = pdf_text(company.get("company_name") if company else "Offertly")
    org_number = pdf_text(company.get("org_number") if company else "")
    phone = pdf_text(company.get("phone") if company else "")
    email = pdf_text(company.get("email") if company else "")
    address = pdf_text(company.get("address") if company else "")
    website = pdf_text(company.get("website") if company else "")

    left = Paragraph(
        f"<b>{company_name}</b><br/>"
        f"{'Org.nr: ' + org_number + '<br/>' if org_number else ''}"
        f"{address + '<br/>' if address else ''}"
        f"{phone + '<br/>' if phone else ''}"
        f"{email + '<br/>' if email else ''}"
        f"{website if website else ''}",
        styles["OffertlyBody"],
    )

    right = Paragraph(
        f"<b>{pdf_text(document_type)}</b><br/>"
        f"Nr: {pdf_text(number)}<br/>"
        f"Datum: {today_iso()}",
        styles["OffertlyRight"],
    )

    table = Table([[left, right]], colWidths=[105 * mm, 65 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    elements.append(table)
    elements.append(Spacer(1, 12))


def add_company_description_to_pdf(elements, styles, company: Optional[Dict[str, Any]]):
    description = safe_text(company.get("company_description") if company else "").strip()

    if description:
        elements.append(Paragraph("Om företaget", styles["OffertlyH2"]))
        elements.append(Paragraph(pdf_text(description), styles["OffertlyBody"]))


def add_pdf_footer_note(elements, styles, text: str):
    elements.append(Spacer(1, 16))
    elements.append(Paragraph(pdf_text(text), styles["OffertlySmall"]))


def customer_table(offer: Dict[str, Any], styles):
    rows = [
        ["Kund", pdf_text(offer.get("customer_name"))],
        ["E-post", pdf_text(offer.get("customer_email"))],
        ["Telefon", pdf_text(offer.get("customer_phone"))],
        ["Adress", pdf_text(offer.get("customer_address"))],
    ]

    table = Table(rows, colWidths=[38 * mm, 132 * mm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    return table


def price_table(price_rows: List[Dict[str, Any]], styles):
    priced_rows = get_priced_rows(price_rows)
    data = [["Typ", "Beskrivning", "Antal", "Enhet", "À-pris", "Summa"]]

    if not priced_rows:
        data.append(["-", "Inga prissatta rader", "-", "-", "-", "-"])
    else:
        for row in priced_rows:
            qty = safe_float(row.get("qty", 1))
            unit_price = safe_float(row.get("unit_price", 0))
            total = qty * unit_price

            data.append(
                [
                    pdf_text(row.get("type", "Övrigt")),
                    pdf_text(row.get("description", "")),
                    f"{qty:g}",
                    pdf_text(row.get("unit", "st")),
                    money(unit_price),
                    money(total),
                ]
            )

    table = Table(data, colWidths=[23 * mm, 62 * mm, 17 * mm, 18 * mm, 25 * mm, 25 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ]
        )
    )

    return table


def totals_table(offer: Dict[str, Any], styles):
    subtotal = safe_float(offer.get("subtotal_ex_vat"))
    vat = safe_float(offer.get("vat_amount"))
    total = safe_float(offer.get("total_inc_vat"))
    labor_inc = safe_float(offer.get("labor_total_inc_vat"))
    rot = safe_float(offer.get("rot_deduction"))
    after_rot = safe_float(offer.get("total_after_rot"))

    rows = [
        ["Summa exkl. moms", money(subtotal)],
        ["Moms 25 %", money(vat)],
        ["Totalt inkl. moms", money(total)],
    ]

    if rot > 0:
        rows.extend(
            [
                ["Arbetskostnad inkl. moms", money(labor_inc)],
                [f"Preliminärt ROT-avdrag {int(ROT_RATE * 100)} %", f"-{money(rot)}"],
                ["Att betala efter ROT", money(after_rot)],
            ]
        )

    table = Table(rows, colWidths=[95 * mm, 55 * mm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    return table


def build_offer_pdf(offer: Dict[str, Any], company: Optional[Dict[str, Any]]) -> bytes:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = pdf_styles()
    elements = []

    offer_number = safe_text(offer.get("offer_number") or "OFFERT")
    add_pdf_header(elements, styles, "OFFERT", company, offer_number)

    elements.append(Paragraph(pdf_text(offer.get("project_title") or "Offert"), styles["OffertlyTitle"]))
    elements.append(Paragraph(f"Status: {pdf_text(status_label(safe_text(offer.get('status'))))}", styles["OffertlySmall"]))
    elements.append(Spacer(1, 10))

    add_company_description_to_pdf(elements, styles, company)

    elements.append(Paragraph("Kunduppgifter", styles["OffertlyH2"]))
    elements.append(customer_table(offer, styles))

    elements.append(Paragraph("Projektbeskrivning", styles["OffertlyH2"]))
    elements.append(Paragraph(pdf_text(offer.get("project_description")), styles["OffertlyBody"]))

    price_rows = normalize_price_rows(offer.get("price_rows"))
    scope_rows = get_scope_rows(price_rows)

    if scope_rows:
        elements.append(Paragraph("Arbetsomfattning", styles["OffertlyH2"]))
        for item in scope_rows:
            elements.append(Paragraph(f"• {pdf_text(item)}", styles["OffertlyBody"]))

    elements.append(Paragraph("Prisrader", styles["OffertlyH2"]))
    elements.append(price_table(price_rows, styles))

    elements.append(Paragraph("Prisöversikt", styles["OffertlyH2"]))
    elements.append(totals_table(offer, styles))

    terms = safe_text(offer.get("terms"))

    if terms:
        elements.append(Paragraph("Villkor", styles["OffertlyH2"]))
        for line in terms.splitlines():
            if line.strip():
                elements.append(Paragraph(f"• {pdf_text(line.strip())}", styles["OffertlyBody"]))

    public_token = safe_text(offer.get("public_token"))

    if public_token:
        elements.append(Paragraph("Kundgodkännande", styles["OffertlyH2"]))
        elements.append(
            Paragraph(
                "Kunden kan granska och godkänna offerten via följande länk:",
                styles["OffertlyBody"],
            )
        )
        elements.append(Paragraph(pdf_text(get_public_link(public_token)), styles["OffertlyBody"]))

    add_pdf_footer_note(
        elements,
        styles,
        "Offerten är framtagen i Offertly. Eventuella tillägg, ändringar eller arbeten utanför angiven omfattning ska godkännas separat.",
    )

    doc.build(elements)
    return buffer.getvalue()


def build_contract_pdf(offer: Dict[str, Any], company: Optional[Dict[str, Any]]) -> bytes:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = pdf_styles()
    elements = []

    contract_id = safe_text(offer.get("contract_id") or "AVTAL")
    add_pdf_header(elements, styles, "KONTRAKT / AVTAL", company, contract_id)

    elements.append(Paragraph(pdf_text(offer.get("project_title") or "Kontrakt"), styles["OffertlyTitle"]))

    add_company_description_to_pdf(elements, styles, company)

    meta = [
        ["Offertnummer", pdf_text(offer.get("offer_number"))],
        ["Kontraktsnummer", pdf_text(contract_id)],
        ["Godkänd datum", pdf_text(safe_text(offer.get("approved_at"))[:10])],
        ["Kontrakt skapat", pdf_text(safe_text(offer.get("contract_created_at"))[:10])],
    ]

    meta_table = Table(meta, colWidths=[50 * mm, 120 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    elements.append(meta_table)

    elements.append(Paragraph("Parter", styles["OffertlyH2"]))
    elements.append(customer_table(offer, styles))

    elements.append(Paragraph("Projekt och omfattning", styles["OffertlyH2"]))
    elements.append(Paragraph(pdf_text(offer.get("project_description")), styles["OffertlyBody"]))

    price_rows = normalize_price_rows(offer.get("price_rows"))
    scope_rows = get_scope_rows(price_rows)

    if scope_rows:
        for item in scope_rows:
            elements.append(Paragraph(f"• {pdf_text(item)}", styles["OffertlyBody"]))

    elements.append(Paragraph("Pris", styles["OffertlyH2"]))
    elements.append(price_table(price_rows, styles))
    elements.append(Spacer(1, 8))
    elements.append(totals_table(offer, styles))

    terms = safe_text(offer.get("terms"))

    if terms:
        elements.append(Paragraph("Avtalsvillkor", styles["OffertlyH2"]))
        for line in terms.splitlines():
            if line.strip():
                elements.append(Paragraph(f"• {pdf_text(line.strip())}", styles["OffertlyBody"]))

    payment_info = safe_text(company.get("payment_info") if company else "")

    if payment_info:
        elements.append(Paragraph("Betalningsinformation", styles["OffertlyH2"]))
        elements.append(Paragraph(pdf_text(payment_info), styles["OffertlyBody"]))

    elements.append(Paragraph("Signering", styles["OffertlyH2"]))
    elements.append(
        Paragraph(
            "Avtalet gäller enligt godkänd offert och angivna villkor. Om BankID-signering kopplas in senare kan detta avtal kompletteras med digital signeringsinformation.",
            styles["OffertlyBody"],
        )
    )

    elements.append(Spacer(1, 25))

    sign_table = Table(
        [
            ["Entreprenör", "Beställare"],
            ["\n\n______________________________", "\n\n______________________________"],
            ["Namnförtydligande", "Namnförtydligande"],
        ],
        colWidths=[80 * mm, 80 * mm],
    )

    sign_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("TOPPADDING", (0, 1), (-1, 1), 25),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
            ]
        )
    )

    elements.append(sign_table)

    add_pdf_footer_note(
        elements,
        styles,
        "Kontraktet är skapat från en godkänd offert i Offertly.",
    )

    doc.build(elements)
    return buffer.getvalue()


def build_invoice_pdf(offer: Dict[str, Any], company: Optional[Dict[str, Any]]) -> bytes:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = pdf_styles()
    elements = []

    invoice_id = safe_text(offer.get("invoice_id") or "FAKTURA")
    add_pdf_header(elements, styles, "FAKTURA", company, invoice_id)

    due_date = datetime.date.today() + datetime.timedelta(days=30)

    elements.append(Paragraph(pdf_text(offer.get("project_title") or "Faktura"), styles["OffertlyTitle"]))

    invoice_meta = [
        ["Fakturanummer", pdf_text(invoice_id)],
        ["Fakturadatum", today_iso()],
        ["Förfallodatum", due_date.isoformat()],
        ["Offertnummer", pdf_text(offer.get("offer_number"))],
        ["Kontraktsnummer", pdf_text(offer.get("contract_id"))],
        ["Status", pdf_text(status_label(safe_text(offer.get("status"))))],
    ]

    invoice_meta_table = Table(invoice_meta, colWidths=[50 * mm, 120 * mm])
    invoice_meta_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    elements.append(invoice_meta_table)

    elements.append(Paragraph("Kund / fakturamottagare", styles["OffertlyH2"]))
    elements.append(customer_table(offer, styles))

    elements.append(Paragraph("Projekt", styles["OffertlyH2"]))
    elements.append(Paragraph(pdf_text(offer.get("project_description")), styles["OffertlyBody"]))

    price_rows = normalize_price_rows(offer.get("price_rows"))
    scope_rows = get_scope_rows(price_rows)

    if scope_rows:
        elements.append(Paragraph("Utfört / avtalat arbete", styles["OffertlyH2"]))
        for item in scope_rows:
            elements.append(Paragraph(f"• {pdf_text(item)}", styles["OffertlyBody"]))

    elements.append(Paragraph("Fakturarader", styles["OffertlyH2"]))
    elements.append(price_table(price_rows, styles))

    elements.append(Paragraph("Belopp", styles["OffertlyH2"]))
    elements.append(totals_table(offer, styles))

    rot = safe_float(offer.get("rot_deduction"))

    if rot > 0:
        elements.append(Paragraph("ROT-information", styles["OffertlyH2"]))
        elements.append(
            Paragraph(
                pdf_text(
                    f"Fakturan visar preliminärt ROT-avdrag om {money(rot)}. "
                    f"ROT-avdraget baseras endast på arbetskostnad och förutsätter att kunden uppfyller Skatteverkets villkor."
                ),
                styles["OffertlyBody"],
            )
        )

    payment_info = safe_text(company.get("payment_info") if company else "")

    elements.append(Paragraph("Betalningsinformation", styles["OffertlyH2"]))

    if payment_info:
        elements.append(Paragraph(pdf_text(payment_info), styles["OffertlyBody"]))
    else:
        elements.append(
            Paragraph(
                "Betalningsinformation saknas i företagsprofilen. Lägg in bankgiro, plusgiro, Swish eller kontonummer i Offertly.",
                styles["OffertlyBody"],
            )
        )

    add_pdf_footer_note(
        elements,
        styles,
        "Fakturan är skapad från godkänd offert/kontrakt i Offertly.",
    )

    doc.build(elements)
    return buffer.getvalue()


# =========================================================
# PUBLIC CUSTOMER VIEW
# =========================================================

def render_public_offer(public_token: str):
    offer = fetch_public_offer(public_token)

    if not offer:
        st.error("Offerten kunde inte hittas.")
        return

    company = offer.get("_company_profile") if isinstance(offer.get("_company_profile"), dict) else None

    if not company:
        user_id = offer.get("user_id")

        if user_id:
            company = fetch_company_profile(user_id)

    price_rows = normalize_price_rows(offer.get("price_rows"))
    scope_rows = get_scope_rows(price_rows)

    st.markdown('<div class="public-wrapper">', unsafe_allow_html=True)

    company_name = safe_text(company.get("company_name") if company else "Offertly")
    company_description = safe_text(company.get("company_description") if company else "")

    st.markdown(
        f"""
        <div class="public-header">
            <h1>Offert från {escape(company_name)}</h1>
            <p>{escape(company_description)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="public-card">', unsafe_allow_html=True)
    st.markdown(f"## {safe_text(offer.get('project_title'))}")
    st.markdown(status_badge(safe_text(offer.get("status"))), unsafe_allow_html=True)
    st.markdown(status_progress_html(safe_text(offer.get("status"))), unsafe_allow_html=True)
    st.write("")
    st.write(safe_text(offer.get("project_description")))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="public-card">', unsafe_allow_html=True)
    st.markdown("### Kunduppgifter")

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**Namn:** {safe_text(offer.get('customer_name'))}")
        st.write(f"**E-post:** {safe_text(offer.get('customer_email'))}")

    with col2:
        st.write(f"**Telefon:** {safe_text(offer.get('customer_phone'))}")
        st.write(f"**Adress:** {safe_text(offer.get('customer_address'))}")

    st.markdown("</div>", unsafe_allow_html=True)

    if scope_rows:
        st.markdown('<div class="public-card">', unsafe_allow_html=True)
        st.markdown("### Omfattning")

        for item in scope_rows:
            st.write(f"• {item}")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="public-card">', unsafe_allow_html=True)
    st.markdown("### Pris")

    priced_rows = get_priced_rows(price_rows)

    if priced_rows:
        for row in priced_rows:
            st.write(
                f"**{safe_text(row.get('description'))}** – "
                f"{safe_float(row.get('qty')):g} {safe_text(row.get('unit'))} × {money(row.get('unit_price'))} "
                f"= **{money(row.get('total'))}**"
            )
    else:
        st.write("Prissatta rader saknas.")

    st.divider()
    st.write(f"Summa exkl. moms: **{money(offer.get('subtotal_ex_vat'))}**")
    st.write(f"Moms 25 %: **{money(offer.get('vat_amount'))}**")
    st.write(f"Totalt inkl. moms: **{money(offer.get('total_inc_vat'))}**")

    if safe_float(offer.get("rot_deduction")) > 0:
        st.write(f"Preliminärt ROT-avdrag: **-{money(offer.get('rot_deduction'))}**")
        st.success(f"Att betala efter ROT: {money(offer.get('total_after_rot'))}")

    st.markdown("</div>", unsafe_allow_html=True)

    terms = safe_text(offer.get("terms"))

    if terms:
        st.markdown('<div class="public-card">', unsafe_allow_html=True)
        st.markdown("### Villkor")

        for line in terms.splitlines():
            if line.strip():
                st.write(f"• {line.strip()}")

        st.markdown("</div>", unsafe_allow_html=True)

    payment_info = safe_text(company.get("payment_info") if company else "")

    if payment_info:
        st.markdown('<div class="public-card">', unsafe_allow_html=True)
        st.markdown("### Betalningsinformation")
        st.write(payment_info)
        st.markdown("</div>", unsafe_allow_html=True)

    status = safe_text(offer.get("status"))

    if status in ["approved", "signed_with_bankid", "contract_created", "invoiced"]:
        st.success("Offerten är redan godkänd.")
    else:
        st.markdown('<div class="public-card">', unsafe_allow_html=True)
        st.markdown("### Godkänn offert")
        st.write(
            "När du godkänner offerten bekräftar du att du har tagit del av omfattning, pris och villkor."
        )

        if st.button("Godkänn offert", type="primary", use_container_width=True):
            try:
                approve_public_offer(public_token)
                st.success("Tack! Offerten är godkänd.")
                st.rerun()
            except Exception as e:
                st.error(f"Kunde inte godkänna offerten: {e}")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# LOGIN
# =========================================================

def render_login():
    st.markdown(
        """
        <div class="offertly-hero">
            <h1>Offertly</h1>
            <p>Professionellt arbetsflöde för hantverkare: offert → kundgodkännande → kontrakt → faktura.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.1, 0.9])

    with left:
        st.markdown("### Skapa professionella offerter snabbare")
        st.write(
            "Offertly hjälper hantverkare att skapa tydliga offerter, skicka kundlänk, "
            "få kundgodkännande och omvandla arbetet vidare till kontrakt och faktura."
        )

        st.markdown(
            """
            **Det här ingår i arbetsflödet:**

            - AI-genererad offerttext
            - Prisrader med moms och ROT
            - Premium-PDF för offert
            - Unik kundlänk
            - Kundgodkännande
            - Kontrakt-PDF
            - Faktura-PDF
            """
        )

    with right:
        tab_login, tab_signup = st.tabs(["Logga in", "Skapa konto"])

        with tab_login:
            email = st.text_input("E-post", key="login_email")
            password = st.text_input("Lösenord", type="password", key="login_password")

            if st.button("Logga in", type="primary", use_container_width=True):
                try:
                    res = supabase.auth.sign_in_with_password(
                        {"email": email, "password": password}
                    )

                    st.session_state["access_token"] = res.session.access_token
                    st.session_state["refresh_token"] = res.session.refresh_token
                    st.session_state["user"] = {
                        "id": res.user.id,
                        "email": res.user.email,
                    }

                    st.rerun()

                except Exception as e:
                    st.error(f"Kunde inte logga in: {e}")

        with tab_signup:
            new_email = st.text_input("E-post", key="signup_email")
            new_password = st.text_input("Lösenord", type="password", key="signup_password")

            if st.button("Skapa konto", use_container_width=True):
                try:
                    supabase.auth.sign_up(
                        {"email": new_email, "password": new_password}
                    )

                    st.success("Konto skapat. Kontrollera din e-post och bekräfta kontot innan du loggar in.")

                except Exception as e:
                    st.error(f"Kunde inte skapa konto: {e}")


# =========================================================
# APP SECTIONS
# =========================================================

def render_overview(user: Dict[str, Any]):
    offers = fetch_offers(user["id"])
    profile = fetch_company_profile(user["id"])

    total_offers = len(offers)
    drafts = len([o for o in offers if o.get("status") == "draft"])
    sent = len([o for o in offers if o.get("status") == "sent"])
    approved = len([o for o in offers if o.get("status") == "approved"])
    contracts = len([o for o in offers if o.get("status") == "contract_created"])
    invoices = len([o for o in offers if o.get("status") == "invoiced"])

    total_value = sum(safe_float(o.get("total_inc_vat")) for o in offers)
    invoiced_value = sum(safe_float(o.get("total_inc_vat")) for o in offers if o.get("status") == "invoiced")

    st.markdown(
        """
        <div class="offertly-hero">
            <h1>Offertly</h1>
            <p>Skapa professionella offerter, låt kunden godkänna, skapa kontrakt och faktura – i ett sammanhållet arbetsflöde.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_profile_warning(profile)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f'<div class="metric-box"><h3>{total_offers}</h3><p>Totalt antal offerter</p></div>',
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f'<div class="metric-box"><h3>{approved}</h3><p>Godkända offerter</p></div>',
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f'<div class="metric-box"><h3>{contracts}</h3><p>Skapade kontrakt</p></div>',
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f'<div class="metric-box"><h3>{invoices}</h3><p>Skapade fakturor</p></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    col5, col6, col7 = st.columns(3)

    with col5:
        st.metric("Offererat värde inkl. moms", money(total_value))

    with col6:
        st.metric("Fakturerat värde inkl. moms", money(invoiced_value))

    with col7:
        st.metric("Företagsprofil färdig", f"{company_profile_score(profile)} %")

    st.write("")

    st.markdown("### Arbetsflöde")
    st.markdown(status_progress_html("draft"), unsafe_allow_html=True)
    st.caption("Utkast → skickad offert → kundgodkännande → kontrakt → faktura")

    st.write("")

    col_a, col_b = st.columns([1.1, 0.9])

    with col_a:
        st.markdown("### Statusöversikt")
        status_rows = [
            ["Utkast", drafts],
            ["Skickade", sent],
            ["Godkända", approved],
            ["Kontrakt skapade", contracts],
            ["Fakturerade", invoices],
        ]

        st.table(
            {
                "Status": [r[0] for r in status_rows],
                "Antal": [r[1] for r in status_rows],
            }
        )

    with col_b:
        st.markdown("### Inför online-deployment")

        checks = [
            ("Supabase Auth fungerar", True),
            ("AI-nyckel finns", bool(OPENAI_API_KEY)),
            ("APP_BASE_URL är satt", bool(APP_BASE_URL)),
            ("Företagsprofil är komplett", is_company_profile_ready(profile)),
            ("PDF-flöde finns", True),
            ("Kundlänk finns", True),
            ("Stripe kopplas senare", False),
        ]

        for label, ok in checks:
            if ok:
                st.success(f"✓ {label}")
            else:
                st.warning(f"Behöver ses över: {label}")

    if offers:
        st.markdown("### Senaste offerter")

        for offer in offers[:5]:
            c1, c2, c3 = st.columns([2.2, 1, 1])

            with c1:
                st.write(f"**{safe_text(offer.get('project_title') or 'Namnlös offert')}**")
                st.caption(f"{safe_text(offer.get('customer_name'))} · {safe_text(offer.get('offer_number'))}")

            with c2:
                st.markdown(status_badge(safe_text(offer.get("status"))), unsafe_allow_html=True)

            with c3:
                st.write(money(offer.get("total_inc_vat")))
    else:
        st.info("När du skapar din första offert kommer översikten börja visa status, värde och arbetsflöde.")


def render_create_offer(user: Dict[str, Any]):
    company = fetch_company_profile(user["id"])

    st.markdown("## Skapa offert")
    st.caption("Bygg en professionell offert med AI-text, prisrader, ROT och kundlänk.")

    render_profile_warning(company)

    with st.form("create_offer_form"):
        st.markdown("### 1. Kund")

        col1, col2 = st.columns(2)

        with col1:
            customer_name = st.text_input("Kundens namn")
            customer_email = st.text_input("Kundens e-post")

        with col2:
            customer_phone = st.text_input("Kundens telefon")
            customer_address = st.text_input("Kundens adress")

        st.markdown("### 2. Projekt")

        col3, col4 = st.columns(2)

        with col3:
            project_title = st.text_input("Projekttitel", placeholder="Ex: Badrumsrenovering i Malmö")

        with col4:
            project_type = st.selectbox(
                "Projekttyp",
                [
                    "Bygg",
                    "VVS",
                    "El",
                    "Snickeri",
                    "Målning",
                    "Plattsättning",
                    "Golv",
                    "Tak",
                    "Markarbete",
                    "Annat",
                ],
            )

        raw_project_description = st.text_area(
            "Kort projektinformation till AI",
            height=140,
            placeholder=(
                "Exempel: Kunden vill renovera badrum på ca 6 kvm. Rivning av befintligt ytskikt, "
                "ny tätskiktslösning, kakel/klinker, montering av kommod, duschvägg och WC. "
                "Material enligt överenskommelse."
            ),
        )

        use_ai = st.checkbox("Använd AI för att skapa professionell offerttext", value=True)

        st.markdown("### 3. Prisrader")
        st.caption("Arbete är ROT-grundande. Material och övrigt är inte ROT-grundande.")

        col_price_1, col_price_2 = st.columns(2)

        with col_price_1:
            labor_description = st.text_input("Arbete – beskrivning", value="Arbetskostnad enligt omfattning")
            material_description = st.text_input("Material – beskrivning", value="Material")
            other_description = st.text_input("Övrigt – beskrivning", value="Övriga kostnader")

        with col_price_2:
            labor_amount = st.number_input("Arbete exkl. moms", min_value=0.0, step=500.0, value=0.0)
            material_amount = st.number_input("Material exkl. moms", min_value=0.0, step=500.0, value=0.0)
            other_amount = st.number_input("Övrigt exkl. moms", min_value=0.0, step=250.0, value=0.0)

        include_rot = st.checkbox("Räkna med preliminärt ROT-avdrag på arbetskostnad", value=False)

        preview_rows = []

        if labor_amount > 0:
            preview_rows.append(
                {
                    "description": labor_description,
                    "type": "Arbete",
                    "qty": 1,
                    "unit": "st",
                    "unit_price": labor_amount,
                }
            )

        if material_amount > 0:
            preview_rows.append(
                {
                    "description": material_description,
                    "type": "Material",
                    "qty": 1,
                    "unit": "st",
                    "unit_price": material_amount,
                }
            )

        if other_amount > 0:
            preview_rows.append(
                {
                    "description": other_description,
                    "type": "Övrigt",
                    "qty": 1,
                    "unit": "st",
                    "unit_price": other_amount,
                }
            )

        preview_totals = calculate_totals(preview_rows, include_rot=include_rot)

        st.markdown("### 4. Prisöversikt")
        col_t1, col_t2, col_t3 = st.columns(3)

        with col_t1:
            st.metric("Summa exkl. moms", money(preview_totals["subtotal_ex_vat"]))

        with col_t2:
            st.metric("Moms 25 %", money(preview_totals["vat_amount"]))

        with col_t3:
            st.metric("Totalt inkl. moms", money(preview_totals["total_inc_vat"]))

        if include_rot:
            st.info(
                f"Preliminärt ROT-avdrag: {money(preview_totals['rot_deduction'])}. "
                f"Att betala efter ROT: {money(preview_totals['total_after_rot'])}."
            )

        submitted = st.form_submit_button("Skapa och spara offert", type="primary", use_container_width=True)

    if submitted:
        errors = build_offer_validation_errors(
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            project_title=project_title,
            raw_project_description=raw_project_description,
            labor_amount=labor_amount,
            material_amount=material_amount,
            other_amount=other_amount,
            include_rot=include_rot,
        )

        if errors:
            st.error("Offerten kan inte sparas ännu.")
            for error in errors:
                st.write(f"• {error}")
            return

        ai_data = {
            "professional_description": raw_project_description,
            "scope": [],
            "terms": [],
            "customer_message": "",
        }

        if use_ai:
            with st.spinner("AI skapar professionell offerttext..."):
                ai_data = generate_ai_offer_text(
                    project_type=project_type,
                    project_title=project_title,
                    project_description=raw_project_description,
                    customer_name=customer_name,
                    company_profile=company,
                )

        default_terms = safe_text(company.get("default_terms") if company else "")
        ai_terms = "\n".join(ai_data.get("terms", []))
        terms = ai_terms or default_terms

        if not terms:
            terms = (
                "Priset gäller enligt angiven omfattning.\n"
                "Eventuella tilläggsarbeten debiteras efter separat överenskommelse.\n"
                "Betalning sker enligt överenskommelse."
            )

        price_rows = []

        for scope_item in ai_data.get("scope", []):
            if safe_text(scope_item).strip():
                price_rows.append(
                    {
                        "description": safe_text(scope_item).strip(),
                        "type": "Omfattning",
                        "qty": 1,
                        "unit": "st",
                        "unit_price": 0,
                    }
                )

        if labor_amount > 0:
            price_rows.append(
                {
                    "description": labor_description,
                    "type": "Arbete",
                    "qty": 1,
                    "unit": "st",
                    "unit_price": labor_amount,
                }
            )

        if material_amount > 0:
            price_rows.append(
                {
                    "description": material_description,
                    "type": "Material",
                    "qty": 1,
                    "unit": "st",
                    "unit_price": material_amount,
                }
            )

        if other_amount > 0:
            price_rows.append(
                {
                    "description": other_description,
                    "type": "Övrigt",
                    "qty": 1,
                    "unit": "st",
                    "unit_price": other_amount,
                }
            )

        totals = calculate_totals(price_rows, include_rot=include_rot)

        payload = {
            "customer_name": customer_name.strip(),
            "customer_email": customer_email.strip(),
            "customer_phone": customer_phone.strip(),
            "customer_address": customer_address.strip(),
            "project_title": project_title.strip(),
            "project_type": project_type,
            "project_description": ai_data.get("professional_description") or raw_project_description,
            "price_rows": price_rows,
            "subtotal_ex_vat": totals["subtotal_ex_vat"],
            "vat_amount": totals["vat_amount"],
            "total_inc_vat": totals["total_inc_vat"],
            "labor_total_inc_vat": totals["labor_total_inc_vat"],
            "rot_deduction": totals["rot_deduction"],
            "total_after_rot": totals["total_after_rot"],
            "terms": terms,
            "status": "draft",
            "offer_number": generate_offer_number(),
        }

        try:
            created = create_offer(user["id"], payload)
            st.success("Offerten är sparad.")

            if created and created.get("public_token"):
                st.write("Kundlänk:")
                st.code(get_public_link(created["public_token"]))

            st.info("Nästa steg: gå till Sparade offerter, ladda ner offert-PDF eller kopiera kundlänken.")

        except Exception as e:
            st.error(f"Kunde inte spara offerten: {e}")


def render_company_profile(user: Dict[str, Any]):
    st.markdown("## Företagsprofil")
    st.caption("Denna information används i offert, kundvy, kontrakt och faktura.")

    profile = fetch_company_profile(user["id"]) or {}
    score = company_profile_score(profile)

    col_status_1, col_status_2 = st.columns([1, 2])

    with col_status_1:
        st.metric("Profil färdig", f"{score} %")

    with col_status_2:
        if is_company_profile_ready(profile):
            st.success("Företagsprofilen är redo för riktiga kunddokument.")
        else:
            st.warning("Fyll i alla viktiga uppgifter innan du använder Offertly med riktiga kunder.")

    with st.form("company_profile_form"):
        col1, col2 = st.columns(2)

        with col1:
            company_name = st.text_input("Företagsnamn", value=safe_text(profile.get("company_name")))
            org_number = st.text_input("Organisationsnummer", value=safe_text(profile.get("org_number")))
            contact_person = st.text_input("Kontaktperson", value=safe_text(profile.get("contact_person")))
            phone = st.text_input("Telefon", value=safe_text(profile.get("phone")))

        with col2:
            email = st.text_input("E-post", value=safe_text(profile.get("email")))
            address = st.text_input("Adress", value=safe_text(profile.get("address")))
            website = st.text_input("Webbplats", value=safe_text(profile.get("website")))
            logo_url = st.text_input("Logo URL", value=safe_text(profile.get("logo_url")))

        company_description = st.text_area(
            "Företagsbeskrivning",
            value=safe_text(profile.get("company_description")),
            height=130,
            placeholder=(
                "Skriv en kort professionell presentation av företaget. "
                "Den visas i kundvyn och stärker förtroendet i offerten."
            ),
        )

        default_terms = st.text_area(
            "Standardvillkor",
            value=safe_text(profile.get("default_terms")),
            height=150,
            placeholder=(
                "Exempel:\n"
                "Priset gäller enligt angiven omfattning.\n"
                "Tilläggsarbeten debiteras efter separat överenskommelse.\n"
                "Betalning sker enligt faktura med 30 dagars betalningsvillkor."
            ),
        )

        payment_info = st.text_area(
            "Betalningsinformation",
            value=safe_text(profile.get("payment_info")),
            height=130,
            placeholder="Ex: Bankgiro, Plusgiro, Swish, IBAN eller betalningsvillkor.",
        )

        submitted = st.form_submit_button("Spara företagsprofil", type="primary", use_container_width=True)

    if submitted:
        missing = []

        if not company_name.strip():
            missing.append("Företagsnamn saknas.")
        if not org_number.strip():
            missing.append("Organisationsnummer saknas.")
        if not contact_person.strip():
            missing.append("Kontaktperson saknas.")
        if not phone.strip():
            missing.append("Telefon saknas.")
        if not email.strip():
            missing.append("E-post saknas.")
        if not address.strip():
            missing.append("Adress saknas.")
        if not company_description.strip():
            missing.append("Företagsbeskrivning saknas.")
        if not default_terms.strip():
            missing.append("Standardvillkor saknas.")
        if not payment_info.strip():
            missing.append("Betalningsinformation saknas.")

        if missing:
            st.warning("Profilen sparas, men den är inte komplett ännu:")
            for item in missing:
                st.write(f"• {item}")

        payload = {
            "company_name": company_name.strip(),
            "org_number": org_number.strip(),
            "contact_person": contact_person.strip(),
            "phone": phone.strip(),
            "email": email.strip(),
            "address": address.strip(),
            "website": website.strip(),
            "company_description": company_description.strip(),
            "default_terms": default_terms.strip(),
            "payment_info": payment_info.strip(),
            "logo_url": logo_url.strip(),
        }

        try:
            upsert_company_profile(user["id"], payload)
            st.success("Företagsprofilen är sparad.")
            st.rerun()

        except Exception as e:
            st.error(f"Kunde inte spara företagsprofilen: {e}")


def render_offer_card(offer: Dict[str, Any], user: Dict[str, Any], company: Optional[Dict[str, Any]]):
    offer_id = safe_text(offer.get("id"))
    status = safe_text(offer.get("status") or "draft")
    public_token = safe_text(offer.get("public_token"))

    with st.container():
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)

        top1, top2 = st.columns([3, 1])

        with top1:
            st.markdown(f"### {safe_text(offer.get('project_title') or 'Namnlös offert')}")
            st.markdown(status_badge(status), unsafe_allow_html=True)
            st.markdown(status_progress_html(status), unsafe_allow_html=True)
            st.caption(f"Offertnummer: {safe_text(offer.get('offer_number'))}")

            if offer.get("contract_id"):
                st.caption(f"Kontraktsnummer: {safe_text(offer.get('contract_id'))}")

            if offer.get("invoice_id"):
                st.caption(f"Fakturanummer: {safe_text(offer.get('invoice_id'))}")

        with top2:
            st.metric("Totalt inkl. moms", money(offer.get("total_inc_vat")))

            if safe_float(offer.get("rot_deduction")) > 0:
                st.caption(f"Efter ROT: {money(offer.get('total_after_rot'))}")

        st.write(f"**Kund:** {safe_text(offer.get('customer_name'))}")
        st.write(f"**Projekt:** {safe_text(offer.get('project_description'))[:260]}")

        if not offer_has_valid_price(offer):
            st.warning("Den här offerten saknar giltigt pris. Kontrollera prisraderna innan den skickas till kund.")

        if public_token:
            with st.expander("Visa kundlänk"):
                st.code(get_public_link(public_token))

        tabs = st.tabs(["Offert", "Kontrakt", "Faktura", "Admin"])

        with tabs[0]:
            col_a, col_b = st.columns(2)

            with col_a:
                offer_pdf = build_offer_pdf(offer, company)

                st.download_button(
                    "Ladda ner offert-PDF",
                    data=offer_pdf,
                    file_name=f"{safe_text(offer.get('offer_number') or 'offert')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"download_offer_pdf_{offer_id}",
                )

            with col_b:
                if status == "draft":
                    if st.button("Markera som skickad", key=f"sent_{offer_id}", use_container_width=True):
                        try:
                            update_offer(
                                offer_id,
                                user["id"],
                                {
                                    "status": "sent",
                                    "sent_at": now_iso(),
                                },
                            )

                            st.success("Offerten markerades som skickad.")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Kunde inte uppdatera status: {e}")
                else:
                    st.info("Offerten är redan skickad eller längre fram i flödet.")

        with tabs[1]:
            allowed_for_contract = status in ["approved", "signed_with_bankid", "contract_created", "invoiced"]

            if not allowed_for_contract:
                st.info("Kontrakt kan skapas när kunden har godkänt offerten.")
            else:
                if not offer.get("contract_id"):
                    if st.button(
                        "Skapa kontrakt från godkänd offert",
                        key=f"contract_{offer_id}",
                        type="primary",
                        use_container_width=True,
                    ):
                        try:
                            contract_id = generate_contract_number()

                            update_offer(
                                offer_id,
                                user["id"],
                                {
                                    "contract_id": contract_id,
                                    "contract_created_at": now_iso(),
                                    "status": "contract_created",
                                },
                            )

                            st.success(f"Kontrakt skapat: {contract_id}")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Kunde inte skapa kontrakt: {e}")
                else:
                    st.success(f"Kontrakt är skapat: {safe_text(offer.get('contract_id'))}")

                    contract_pdf = build_contract_pdf(offer, company)

                    st.download_button(
                        "Ladda ner kontrakt-PDF",
                        data=contract_pdf,
                        file_name=f"{safe_text(offer.get('contract_id') or 'kontrakt')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"download_contract_pdf_{offer_id}",
                    )

        with tabs[2]:
            allowed_for_invoice = status in ["contract_created", "invoiced"]

            if not offer.get("contract_id"):
                st.info("Skapa kontrakt först innan faktura skapas.")
            elif not allowed_for_invoice:
                st.info("Faktura kan skapas när kontrakt är skapat.")
            else:
                if not offer.get("invoice_id"):
                    st.warning("Faktura är inte skapad ännu.")

                    if st.button(
                        "Skapa faktura från kontrakt",
                        key=f"invoice_{offer_id}",
                        type="primary",
                        use_container_width=True,
                    ):
                        try:
                            invoice_id = generate_invoice_number()

                            update_offer(
                                offer_id,
                                user["id"],
                                {
                                    "invoice_id": invoice_id,
                                    "invoiced_at": now_iso(),
                                    "status": "invoiced",
                                },
                            )

                            st.success(f"Faktura skapad: {invoice_id}")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Kunde inte skapa faktura: {e}")
                else:
                    st.success(f"Faktura är skapad: {safe_text(offer.get('invoice_id'))}")

                    if offer.get("invoiced_at"):
                        st.caption(f"Fakturadatum: {safe_text(offer.get('invoiced_at'))[:10]}")

                    invoice_pdf = build_invoice_pdf(offer, company)

                    st.download_button(
                        "Ladda ner faktura-PDF",
                        data=invoice_pdf,
                        file_name=f"{safe_text(offer.get('invoice_id') or 'faktura')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"download_invoice_pdf_{offer_id}",
                    )

        with tabs[3]:
            st.warning("Adminläget är till för intern hantering och testning. Använd det försiktigt.")

            statuses = ["draft", "sent", "approved", "signed_with_bankid", "contract_created", "invoiced"]

            index = statuses.index(status) if status in statuses else 0

            new_status = st.selectbox(
                "Status",
                statuses,
                index=index,
                key=f"status_select_{offer_id}",
            )

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Uppdatera status", key=f"update_status_{offer_id}", use_container_width=True):
                    try:
                        payload = {"status": new_status}

                        if new_status == "sent" and not offer.get("sent_at"):
                            payload["sent_at"] = now_iso()

                        if new_status == "approved" and not offer.get("approved_at"):
                            payload["approved_at"] = now_iso()

                        if new_status == "contract_created":
                            if not offer.get("contract_created_at"):
                                payload["contract_created_at"] = now_iso()

                            if not offer.get("contract_id"):
                                payload["contract_id"] = generate_contract_number()

                        if new_status == "invoiced":
                            if not offer.get("invoiced_at"):
                                payload["invoiced_at"] = now_iso()

                            if not offer.get("invoice_id"):
                                payload["invoice_id"] = generate_invoice_number()

                            if not offer.get("contract_id"):
                                payload["contract_id"] = generate_contract_number()

                            if not offer.get("contract_created_at"):
                                payload["contract_created_at"] = now_iso()

                        update_offer(offer_id, user["id"], payload)

                        st.success("Status uppdaterad.")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Kunde inte uppdatera status: {e}")

            with col2:
                confirm_delete = st.checkbox(
                    "Jag vill ta bort denna offert",
                    key=f"confirm_delete_{offer_id}",
                )

                if st.button(
                    "Ta bort offert",
                    key=f"delete_{offer_id}",
                    use_container_width=True,
                    disabled=not confirm_delete,
                ):
                    try:
                        delete_offer(offer_id, user["id"])

                        st.success("Offerten togs bort.")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Kunde inte ta bort offert: {e}")

        st.markdown("</div>", unsafe_allow_html=True)


def render_saved_offers(user: Dict[str, Any]):
    st.markdown("## Sparade offerter")
    st.caption("Här hanterar du offert, kundlänk, kontrakt och faktura.")

    company = fetch_company_profile(user["id"])
    offers = fetch_offers(user["id"])

    if not offers:
        st.info("Du har inga sparade offerter ännu. Skapa din första offert i fliken Skapa offert.")
        return

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        search = st.text_input(
            "Sök",
            placeholder="Sök på kund, projekt, offertnummer, kontraktsnummer eller fakturanummer",
        )

    with col2:
        status_filter = st.selectbox(
            "Statusfilter",
            ["Alla", "draft", "sent", "approved", "signed_with_bankid", "contract_created", "invoiced"],
        )

    with col3:
        sort_mode = st.selectbox(
            "Sortering",
            ["Nyast först", "Högst värde", "Lägst värde"],
        )

    filtered = []
    query = search.lower().strip()

    for offer in offers:
        haystack = " ".join(
            [
                safe_text(offer.get("customer_name")),
                safe_text(offer.get("project_title")),
                safe_text(offer.get("offer_number")),
                safe_text(offer.get("contract_id")),
                safe_text(offer.get("invoice_id")),
            ]
        ).lower()

        if query and query not in haystack:
            continue

        if status_filter != "Alla" and offer.get("status") != status_filter:
            continue

        filtered.append(offer)

    if sort_mode == "Högst värde":
        filtered.sort(key=lambda o: safe_float(o.get("total_inc_vat")), reverse=True)
    elif sort_mode == "Lägst värde":
        filtered.sort(key=lambda o: safe_float(o.get("total_inc_vat")))

    st.write(f"Visar {len(filtered)} av {len(offers)} offerter.")

    if not filtered:
        st.warning("Inga offerter matchar filtret.")
        return

    for offer in filtered:
        render_offer_card(offer, user, company)


# =========================================================
# MAIN APP
# =========================================================

def render_app():
    user = current_user()

    if not user:
        render_login()
        return

    with st.sidebar:
        st.markdown("## Offertly")
        st.caption(f"Inloggad som {user.get('email')}")

        st.divider()

        st.caption("Miljö")
        if APP_BASE_URL.startswith("http://localhost"):
            st.warning("Lokal utveckling")
        else:
            st.success("Online-läge")

        st.caption(f"APP_BASE_URL: {APP_BASE_URL}")

        st.divider()

        if st.button("Logga ut", use_container_width=True):
            sign_out()

    page = st.tabs(
        [
            "Översikt",
            "Skapa offert",
            "Sparade offerter",
            "Företagsprofil",
        ]
    )

    with page[0]:
        render_overview(user)

    with page[1]:
        render_create_offer(user)

    with page[2]:
        render_saved_offers(user)

    with page[3]:
        render_company_profile(user)


# =========================================================
# ROUTING
# =========================================================

params = st.query_params

if "offer" in params:
    token_value = params.get("offer")

    if isinstance(token_value, list):
        token_value = token_value[0]

    render_public_offer(token_value)
else:
    render_app()