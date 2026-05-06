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
# OFFERTLY – FAS 15.1
# Seriös visningsversion + klickbar kundlänk i offert-PDF
# Bas: Fas 15 fix
#
# Innehåller:
# - Premium-startsida
# - Synlig/redigerbar AI-text innan sparning
# - Redigering av sparade offerter
# - Kundlänk
# - Kundgodkännande
# - Offert-PDF med klickbar kundlänk
# - Kontrakt-PDF
# - Faktura-PDF
# - Ingen SQL
# - Ingen Stripe
# - Ingen BankID
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
            padding-top: 1.6rem;
            padding-bottom: 4rem;
            max-width: 1220px;
        }

        .offertly-hero {
            padding: 34px 36px;
            border-radius: 30px;
            background:
                radial-gradient(circle at top right, rgba(59, 130, 246, 0.30), transparent 32%),
                linear-gradient(135deg, #0f172a 0%, #111827 48%, #1e293b 100%);
            color: white;
            margin-bottom: 24px;
            box-shadow: 0 22px 60px rgba(15, 23, 42, 0.22);
            border: 1px solid rgba(255,255,255,0.10);
        }

        .offertly-hero h1 {
            margin: 0;
            font-size: 2.75rem;
            letter-spacing: -0.055em;
            line-height: 1.04;
        }

        .offertly-hero p {
            margin-top: 14px;
            color: #d1d5db;
            font-size: 1.08rem;
            max-width: 900px;
        }

        .hero-flow {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 24px;
        }

        .hero-flow span {
            padding: 9px 13px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.10);
            border: 1px solid rgba(255, 255, 255, 0.18);
            color: #f9fafb;
            font-size: 0.86rem;
            font-weight: 750;
        }

        .premium-card {
            padding: 22px;
            border-radius: 22px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            box-shadow: 0 12px 35px rgba(15, 23, 42, 0.06);
            margin-bottom: 18px;
        }

        .intro-panel {
            padding: 28px;
            border-radius: 26px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            box-shadow: 0 16px 44px rgba(15, 23, 42, 0.07);
            margin-bottom: 18px;
        }

        .intro-panel h2 {
            margin-top: 0;
            font-size: 1.65rem;
            letter-spacing: -0.03em;
            color: #111827;
        }

        .intro-panel p {
            color: #374151;
            font-size: 1rem;
            line-height: 1.7;
        }

        .feature-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 14px;
            margin-top: 18px;
            margin-bottom: 18px;
        }

        .feature-card {
            padding: 18px;
            border-radius: 20px;
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            min-height: 118px;
        }

        .feature-card .number {
            width: 34px;
            height: 34px;
            border-radius: 999px;
            background: #111827;
            color: white;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            margin-bottom: 12px;
        }

        .feature-card h3 {
            margin: 0 0 6px 0;
            font-size: 1.02rem;
            color: #111827;
        }

        .feature-card p {
            margin: 0;
            color: #6b7280;
            font-size: 0.9rem;
            line-height: 1.45;
        }

        .demo-card {
            padding: 20px;
            border-radius: 22px;
            border: 1px solid #bfdbfe;
            background: #eff6ff;
            margin-top: 16px;
        }

        .demo-card h3 {
            margin: 0 0 8px 0;
            color: #1e3a8a;
            font-size: 1.15rem;
        }

        .demo-card p {
            margin: 0;
            color: #1e40af;
            font-size: 0.96rem;
            line-height: 1.65;
        }

        .soft-card {
            padding: 18px;
            border-radius: 18px;
            border: 1px solid #e5e7eb;
            background: #f9fafb;
            margin-bottom: 14px;
        }

        .domain-card {
            padding: 18px;
            border-radius: 18px;
            border: 1px solid #dbeafe;
            background: #eff6ff;
            margin-bottom: 14px;
        }

        .domain-card h4 {
            margin-top: 0;
            margin-bottom: 8px;
            color: #1e3a8a;
        }

        .domain-card p {
            color: #1e40af;
            margin-bottom: 0;
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

        @media (max-width: 900px) {
            .feature-grid {
                grid-template-columns: 1fr;
            }

            .offertly-hero h1 {
                font-size: 2.2rem;
            }
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


def clean_ai_json(content: str) -> str:
    text = safe_text(content).strip()

    if text.startswith("```json"):
        text = text.replace("```json", "", 1).strip()

    if text.startswith("```"):
        text = text.replace("```", "", 1).strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return text


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
        row_type = safe_text(row.get("type", ""))

        if description and (unit_price <= 0 or row_type == "Omfattning"):
            scope.append(description)

    return scope


def get_priced_rows(price_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in price_rows if safe_float(row.get("unit_price", 0)) > 0]


def scope_text_to_rows(scope_text: str) -> List[Dict[str, Any]]:
    rows = []

    for line in safe_text(scope_text).splitlines():
        cleaned = line.strip().lstrip("-").lstrip("•").strip()

        if cleaned:
            rows.append(
                {
                    "description": cleaned,
                    "type": "Omfattning",
                    "qty": 1,
                    "unit": "st",
                    "unit_price": 0,
                }
            )

    return rows


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


def build_price_rows_from_simple_inputs(
    scope_text: str,
    labor_description: str,
    labor_amount: float,
    material_description: str,
    material_amount: float,
    other_description: str,
    other_amount: float,
) -> List[Dict[str, Any]]:
    price_rows = []

    price_rows.extend(scope_text_to_rows(scope_text))

    if labor_amount > 0:
        price_rows.append(
            {
                "description": labor_description.strip() or "Arbetskostnad enligt omfattning",
                "type": "Arbete",
                "qty": 1,
                "unit": "st",
                "unit_price": labor_amount,
            }
        )

    if material_amount > 0:
        price_rows.append(
            {
                "description": material_description.strip() or "Material",
                "type": "Material",
                "qty": 1,
                "unit": "st",
                "unit_price": material_amount,
            }
        )

    if other_amount > 0:
        price_rows.append(
            {
                "description": other_description.strip() or "Övriga kostnader",
                "type": "Övrigt",
                "qty": 1,
                "unit": "st",
                "unit_price": other_amount,
            }
        )

    return price_rows


def extract_row_by_type(price_rows: List[Dict[str, Any]], row_type: str) -> Dict[str, Any]:
    for row in price_rows:
        if safe_text(row.get("type")) == row_type and safe_float(row.get("unit_price")) > 0:
            return row

    return {
        "description": "",
        "type": row_type,
        "qty": 1,
        "unit": "st",
        "unit_price": 0,
    }


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

        content = clean_ai_json(response.choices[0].message.content)
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

    styles.add(
        ParagraphStyle(
            name="OffertlyLink",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1D4ED8"),
            spaceBefore=6,
            spaceAfter=3,
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

    table = Table([[left, right]], colWidths=[115 * mm, 55 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.7, colors.HexColor("#E5E7EB")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )

    elements.append(table)
    elements.append(Spacer(1, 12))


def add_company_description_to_pdf(elements, styles, company: Optional[Dict[str, Any]]):
    if not company:
        return

    description = safe_text(company.get("company_description", "")).strip()

    if not description:
        return

    elements.append(Paragraph("Om företaget", styles["OffertlyH2"]))
    elements.append(Paragraph(pdf_text(description), styles["OffertlyBody"]))
    elements.append(Spacer(1, 8))


def add_customer_project_pdf(elements, styles, offer: Dict[str, Any]):
    elements.append(Paragraph("Kund och projekt", styles["OffertlyH2"]))

    customer_lines = [
        ["Kund", safe_text(offer.get("customer_name", ""))],
        ["E-post", safe_text(offer.get("customer_email", ""))],
        ["Telefon", safe_text(offer.get("customer_phone", ""))],
        ["Adress", safe_text(offer.get("customer_address", ""))],
        ["Projekt", safe_text(offer.get("project_title", ""))],
        ["Projekttyp", safe_text(offer.get("project_type", ""))],
    ]

    data = []

    for label, value in customer_lines:
        if value:
            data.append(
                [
                    Paragraph(f"<b>{pdf_text(label)}</b>", styles["OffertlyBody"]),
                    Paragraph(pdf_text(value), styles["OffertlyBody"]),
                ]
            )

    if data:
        table = Table(data, colWidths=[35 * mm, 135 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elements.append(table)

    elements.append(Spacer(1, 8))


def add_scope_and_description_pdf(elements, styles, offer: Dict[str, Any], price_rows: List[Dict[str, Any]]):
    project_description = safe_text(offer.get("project_description", "")).strip()

    if project_description:
        elements.append(Paragraph("Projektbeskrivning", styles["OffertlyH2"]))
        elements.append(Paragraph(pdf_text(project_description), styles["OffertlyBody"]))
        elements.append(Spacer(1, 8))

    scope_rows = get_scope_rows(price_rows)

    if scope_rows:
        elements.append(Paragraph("Omfattning", styles["OffertlyH2"]))

        for item in scope_rows:
            elements.append(Paragraph(f"• {pdf_text(item)}", styles["OffertlyBody"]))

        elements.append(Spacer(1, 8))


def add_price_table_pdf(elements, styles, offer: Dict[str, Any], price_rows: List[Dict[str, Any]]):
    priced_rows = get_priced_rows(price_rows)

    if not priced_rows:
        return

    elements.append(Paragraph("Pris", styles["OffertlyH2"]))

    data = [
        [
            Paragraph("<b>Beskrivning</b>", styles["OffertlyBody"]),
            Paragraph("<b>Typ</b>", styles["OffertlyBody"]),
            Paragraph("<b>Antal</b>", styles["OffertlyBody"]),
            Paragraph("<b>Pris exkl. moms</b>", styles["OffertlyRight"]),
        ]
    ]

    for row in priced_rows:
        qty = safe_float(row.get("qty", 1))
        unit = safe_text(row.get("unit", "st"))
        unit_price = safe_float(row.get("unit_price", 0))
        total = qty * unit_price

        data.append(
            [
                Paragraph(pdf_text(row.get("description", "")), styles["OffertlyBody"]),
                Paragraph(pdf_text(row.get("type", "")), styles["OffertlyBody"]),
                Paragraph(pdf_text(f"{qty:g} {unit}"), styles["OffertlyBody"]),
                Paragraph(pdf_text(money(total)), styles["OffertlyRight"]),
            ]
        )

    table = Table(data, colWidths=[82 * mm, 28 * mm, 25 * mm, 35 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    elements.append(table)
    elements.append(Spacer(1, 10))

    subtotal_ex_vat = safe_float(offer.get("subtotal_ex_vat"))
    vat_amount = safe_float(offer.get("vat_amount"))
    total_inc_vat = safe_float(offer.get("total_inc_vat"))
    rot_deduction = safe_float(offer.get("rot_deduction"))
    total_after_rot = safe_float(offer.get("total_after_rot"))

    totals = [
        ["Summa exkl. moms", money(subtotal_ex_vat)],
        ["Moms 25 %", money(vat_amount)],
        ["Totalt inkl. moms", money(total_inc_vat)],
    ]

    if rot_deduction > 0:
        totals.append(["Preliminärt ROT-avdrag", f"-{money(rot_deduction)}"])
        totals.append(["Att betala efter ROT", money(total_after_rot)])

    totals_data = []

    for label, value in totals:
        totals_data.append(
            [
                Paragraph(f"<b>{pdf_text(label)}</b>", styles["OffertlyBody"]),
                Paragraph(f"<b>{pdf_text(value)}</b>", styles["OffertlyRight"]),
            ]
        )

    totals_table = Table(totals_data, colWidths=[125 * mm, 45 * mm])
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F9FAFB")),
                ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.HexColor("#D1D5DB")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    elements.append(totals_table)
    elements.append(Spacer(1, 8))


def add_terms_pdf(elements, styles, offer: Dict[str, Any], company: Optional[Dict[str, Any]]):
    terms = safe_text(offer.get("terms", "")).strip()

    if not terms and company:
        terms = safe_text(company.get("default_terms", "")).strip()

    if terms:
        elements.append(Paragraph("Villkor", styles["OffertlyH2"]))
        elements.append(Paragraph(pdf_text(terms), styles["OffertlyBody"]))
        elements.append(Spacer(1, 8))

    payment_info = safe_text(company.get("payment_info", "") if company else "").strip()

    if payment_info:
        elements.append(Paragraph("Betalningsinformation", styles["OffertlyH2"]))
        elements.append(Paragraph(pdf_text(payment_info), styles["OffertlyBody"]))
        elements.append(Spacer(1, 8))


def generate_offer_pdf(offer: Dict[str, Any], company: Optional[Dict[str, Any]]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = pdf_styles()
    elements = []

    offer_number = safe_text(offer.get("offer_number", "Offert"))

    add_pdf_header(elements, styles, "OFFERT", company, offer_number)
    add_company_description_to_pdf(elements, styles, company)
    add_customer_project_pdf(elements, styles, offer)

    price_rows = normalize_price_rows(offer.get("price_rows", []))

    add_scope_and_description_pdf(elements, styles, offer, price_rows)
    add_price_table_pdf(elements, styles, offer, price_rows)
    add_terms_pdf(elements, styles, offer, company)

    public_token = safe_text(offer.get("public_token", "")).strip()

    if public_token:
        public_link = get_public_link(public_token)

        elements.append(Paragraph("Kundgodkännande", styles["OffertlyH2"]))
        elements.append(
            Paragraph(
                pdf_text(
                    "Kunden kan öppna sin personliga offertlänk, läsa igenom underlaget och godkänna offerten digitalt."
                ),
                styles["OffertlyBody"],
            )
        )
        elements.append(Spacer(1, 4))

        elements.append(
            Paragraph(
                f'<link href="{pdf_text(public_link)}"><b>Öppna offert och godkänn digitalt</b></link>',
                styles["OffertlyLink"],
            )
        )

        elements.append(
            Paragraph(
                pdf_text(public_link),
                styles["OffertlySmall"],
            )
        )

        elements.append(Spacer(1, 8))

    elements.append(
        Paragraph(
            pdf_text(
                "Denna offert är framtagen i Offertly – ett professionellt arbetsflöde för offert, kundgodkännande, kontrakt och faktura."
            ),
            styles["OffertlySmall"],
        )
    )

    doc.build(elements)
    return buffer.getvalue()


def generate_contract_pdf(offer: Dict[str, Any], company: Optional[Dict[str, Any]]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = pdf_styles()
    elements = []

    contract_id = safe_text(offer.get("contract_id") or generate_contract_number())

    add_pdf_header(elements, styles, "KONTRAKT", company, contract_id)
    add_company_description_to_pdf(elements, styles, company)
    add_customer_project_pdf(elements, styles, offer)

    elements.append(Paragraph("Avtalets grund", styles["OffertlyH2"]))
    elements.append(
        Paragraph(
            pdf_text(
                f"Detta kontrakt baseras på offert {safe_text(offer.get('offer_number', ''))}. "
                "Avtalet avser det arbete, den omfattning och de villkor som framgår av underlaget."
            ),
            styles["OffertlyBody"],
        )
    )
    elements.append(Spacer(1, 8))

    price_rows = normalize_price_rows(offer.get("price_rows", []))

    add_scope_and_description_pdf(elements, styles, offer, price_rows)
    add_price_table_pdf(elements, styles, offer, price_rows)
    add_terms_pdf(elements, styles, offer, company)

    approved_at = safe_text(offer.get("approved_at", "")).strip()

    if approved_at:
        elements.append(Paragraph("Kundgodkännande", styles["OffertlyH2"]))
        elements.append(
            Paragraph(
                pdf_text(f"Offerten godkändes digitalt av kunden: {approved_at}"),
                styles["OffertlyBody"],
            )
        )
        elements.append(Spacer(1, 8))

    elements.append(Paragraph("Signering", styles["OffertlyH2"]))

    signature_table = Table(
        [
            [
                Paragraph("Entreprenör", styles["OffertlyBody"]),
                Paragraph("Beställare", styles["OffertlyBody"]),
            ],
            ["", ""],
            [
                Paragraph("Datum och underskrift", styles["OffertlySmall"]),
                Paragraph("Datum och underskrift", styles["OffertlySmall"]),
            ],
        ],
        colWidths=[80 * mm, 80 * mm],
        rowHeights=[10 * mm, 20 * mm, 10 * mm],
    )

    signature_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 1), (0, 1), 0.8, colors.HexColor("#111827")),
                ("LINEBELOW", (1, 1), (1, 1), 0.8, colors.HexColor("#111827")),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ]
        )
    )

    elements.append(signature_table)

    doc.build(elements)
    return buffer.getvalue()


def generate_invoice_pdf(offer: Dict[str, Any], company: Optional[Dict[str, Any]]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = pdf_styles()
    elements = []

    invoice_id = safe_text(offer.get("invoice_id") or generate_invoice_number())

    add_pdf_header(elements, styles, "FAKTURA", company, invoice_id)
    add_customer_project_pdf(elements, styles, offer)

    due_date = datetime.date.today() + datetime.timedelta(days=30)

    elements.append(Paragraph("Fakturauppgifter", styles["OffertlyH2"]))
    elements.append(
        Paragraph(
            pdf_text(
                f"Fakturan avser projektet {safe_text(offer.get('project_title', ''))}. "
                f"Förfallodatum: {due_date.isoformat()}."
            ),
            styles["OffertlyBody"],
        )
    )
    elements.append(Spacer(1, 8))

    price_rows = normalize_price_rows(offer.get("price_rows", []))

    add_scope_and_description_pdf(elements, styles, offer, price_rows)
    add_price_table_pdf(elements, styles, offer, price_rows)
    add_terms_pdf(elements, styles, offer, company)

    elements.append(
        Paragraph(
            pdf_text("Tack för förtroendet. Betalning sker enligt angiven betalningsinformation och överenskomna villkor."),
            styles["OffertlyBody"],
        )
    )

    doc.build(elements)
    return buffer.getvalue()


# =========================================================
# PUBLIC CUSTOMER VIEW
# =========================================================

def render_public_offer(public_token: str):
    offer = fetch_public_offer(public_token)

    if not offer:
        st.error("Offerten kunde inte hittas. Kontrollera länken.")
        return

    company_profile = offer.get("_company_profile")

    if not company_profile:
        company_profile = fetch_company_profile(safe_text(offer.get("user_id", "")))

    price_rows = normalize_price_rows(offer.get("price_rows", []))
    scope_rows = get_scope_rows(price_rows)
    priced_rows = get_priced_rows(price_rows)

    status = safe_text(offer.get("status", "draft"))
    is_approved = status in ["approved", "signed_with_bankid", "contract_created", "invoiced"]

    st.markdown('<div class="public-wrapper">', unsafe_allow_html=True)

    company_name = safe_text(company_profile.get("company_name", "Offertly") if company_profile else "Offertly")
    company_description = safe_text(company_profile.get("company_description", "") if company_profile else "")

    st.markdown(
        f"""
        <div class="public-header">
            <h1>Offert från {company_name}</h1>
            <p>Granska offerten i lugn och ro. När allt stämmer kan du godkänna den digitalt.</p>
            <div class="hero-flow">
                <span>Offert</span>
                <span>Kundgodkännande</span>
                <span>Kontrakt</span>
                <span>Faktura</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if company_description:
        st.markdown(
            f"""
            <div class="public-card">
                <h3>Om företaget</h3>
                <p>{company_description}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="public-card">', unsafe_allow_html=True)
    st.markdown(f"### {safe_text(offer.get('project_title', 'Offert'))}")
    st.markdown(status_badge(status), unsafe_allow_html=True)

    st.write("")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Kund**")
        st.write(safe_text(offer.get("customer_name", "")))
        if offer.get("customer_email"):
            st.write(safe_text(offer.get("customer_email")))
        if offer.get("customer_phone"):
            st.write(safe_text(offer.get("customer_phone")))
        if offer.get("customer_address"):
            st.write(safe_text(offer.get("customer_address")))

    with c2:
        st.markdown("**Projekt**")
        st.write(safe_text(offer.get("project_type", "")))
        st.write(f"Offertnummer: {safe_text(offer.get('offer_number', ''))}")

    project_description = safe_text(offer.get("project_description", "")).strip()

    if project_description:
        st.markdown("#### Projektbeskrivning")
        st.write(project_description)

    if scope_rows:
        st.markdown("#### Omfattning")
        for item in scope_rows:
            st.write(f"• {item}")

    if priced_rows:
        st.markdown("#### Pris")
        for row in priced_rows:
            row_total = safe_float(row.get("qty", 1)) * safe_float(row.get("unit_price", 0))
            st.write(f"**{safe_text(row.get('description', ''))}** – {safe_text(row.get('type', ''))}: {money(row_total)} exkl. moms")

        st.divider()
        st.write(f"Summa exkl. moms: **{money(offer.get('subtotal_ex_vat'))}**")
        st.write(f"Moms 25 %: **{money(offer.get('vat_amount'))}**")
        st.write(f"Totalt inkl. moms: **{money(offer.get('total_inc_vat'))}**")

        if safe_float(offer.get("rot_deduction")) > 0:
            st.write(f"Preliminärt ROT-avdrag: **-{money(offer.get('rot_deduction'))}**")
            st.success(f"Att betala efter ROT: {money(offer.get('total_after_rot'))}")

    terms = safe_text(offer.get("terms", "")).strip()

    if terms:
        st.markdown("#### Villkor")
        st.write(terms)

    payment_info = safe_text(company_profile.get("payment_info", "") if company_profile else "").strip()

    if payment_info:
        st.markdown("#### Betalningsinformation")
        st.write(payment_info)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="public-card">', unsafe_allow_html=True)

    if is_approved:
        st.success("Offerten är godkänd. Företaget kan nu gå vidare med kontrakt och faktura.")
    else:
        st.markdown("### Godkänn offert")
        st.write("När du godkänner offerten bekräftar du att du accepterar omfattning, pris och villkor enligt underlaget.")

        if st.button("Godkänn offert", type="primary", use_container_width=True):
            try:
                approve_public_offer(public_token)
                st.success("Offerten är godkänd.")
                st.rerun()
            except Exception as e:
                st.error(f"Kunde inte godkänna offerten: {e}")

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# LOGIN / START
# =========================================================

def render_login():
    st.markdown(
        """
        <div class="offertly-hero">
            <h1>Offertly</h1>
            <p>
                Ett professionellt arbetsflöde för hantverkare: skapa offert, skicka kundlänk,
                få digitalt godkännande och gå vidare till kontrakt och faktura.
            </p>
            <div class="hero-flow">
                <span>Offert på minuter</span>
                <span>Kundlänk</span>
                <span>Digitalt godkännande</span>
                <span>Kontrakt</span>
                <span>Faktura</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1.15, 0.85], gap="large")

    with c1:
        st.markdown(
            """
            <div class="intro-panel">
                <h2>Byggt för seriösa hantverksföretag</h2>
                <p>
                    Offertly hjälper hantverkare att lämna ett mer professionellt intryck redan från första kontakten.
                    Istället för lösa dokument och dubbelarbete samlas hela flödet i ett system.
                </p>
                <p>
                    Kunden får en tydlig offertlänk, kan granska omfattning och pris, och godkänner digitalt.
                    Därefter kan offerten omvandlas till kontrakt och faktura.
                </p>
            </div>

            <div class="feature-grid">
                <div class="feature-card">
                    <div class="number">1</div>
                    <h3>Skapa offert</h3>
                    <p>AI hjälper till med professionell offerttext. Priser anges manuellt av hantverkaren.</p>
                </div>
                <div class="feature-card">
                    <div class="number">2</div>
                    <h3>Få godkännande</h3>
                    <p>Kunden öppnar en unik länk och godkänner offerten digitalt utan inloggning.</p>
                </div>
                <div class="feature-card">
                    <div class="number">3</div>
                    <h3>Gå vidare</h3>
                    <p>Godkänd offert kan omvandlas till kontrakt och senare faktura.</p>
                </div>
            </div>

            <div class="demo-card">
                <h3>Seriös visningsversion</h3>
                <p>
                    Den här versionen används för demo, genomgång och produktkontroll inför lansering.
                    Domän, Stripe och BankID kopplas senare när kärnflödet är färdigtestat.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown("### Logga in")
        st.caption("Logga in för att hantera offerter, kundlänkar, kontrakt och fakturor.")

        login_tab, signup_tab = st.tabs(["Logga in", "Skapa konto"])

        with login_tab:
            email = st.text_input("E-post", key="login_email")
            password = st.text_input("Lösenord", type="password", key="login_password")

            if st.button("Logga in", type="primary", use_container_width=True):
                try:
                    res = supabase.auth.sign_in_with_password(
                        {
                            "email": email,
                            "password": password,
                        }
                    )

                    session = getattr(res, "session", None)
                    user = getattr(res, "user", None)

                    if session and user:
                        st.session_state["access_token"] = session.access_token
                        st.session_state["refresh_token"] = session.refresh_token
                        st.session_state["user"] = {
                            "id": user.id,
                            "email": user.email,
                        }
                        st.success("Du är inloggad.")
                        st.rerun()
                    else:
                        st.error("Kunde inte logga in. Kontrollera e-post och lösenord.")

                except Exception as e:
                    st.error(f"Inloggning misslyckades: {e}")

        with signup_tab:
            signup_email = st.text_input("E-post", key="signup_email")
            signup_password = st.text_input("Lösenord", type="password", key="signup_password")

            if st.button("Skapa konto", use_container_width=True):
                try:
                    supabase.auth.sign_up(
                        {
                            "email": signup_email,
                            "password": signup_password,
                        }
                    )
                    st.success("Konto skapat. Kontrollera din e-post och bekräfta kontot innan du loggar in.")
                except Exception as e:
                    st.error(f"Kunde inte skapa konto: {e}")


# =========================================================
# APP LAYOUT
# =========================================================

def render_sidebar(user: Dict[str, Any], profile: Optional[Dict[str, Any]]):
    with st.sidebar:
        st.markdown("## Offertly")
        st.caption("Offert → kundgodkännande → kontrakt → faktura")
        st.divider()

        st.write("**Inloggad som:**")
        st.caption(user.get("email", ""))

        st.divider()

        if APP_BASE_URL.startswith("http://localhost"):
            st.warning("Lokal utveckling")
        else:
            st.success("Online-läge")

        st.caption(f"APP_BASE_URL: {APP_BASE_URL}")

        st.divider()

        score = company_profile_score(profile)
        st.write("**Företagsprofil**")
        st.progress(score / 100)
        st.caption(f"{score}% färdig")

        st.divider()

        st.info(
            "Fas 15.1: Seriös visningsversion. Offert-PDF har klickbar kundlänk."
        )

        if st.button("Logga ut", use_container_width=True):
            sign_out()


def render_overview(user_id: str, profile: Optional[Dict[str, Any]], offers: List[Dict[str, Any]]):
    st.markdown(
        """
        <div class="offertly-hero">
            <h1>Översikt</h1>
            <p>
                Offertly är förberett som seriös visningsversion inför domän, kundgenomgångar och kommande lansering.
                Kärnflödet är: offert → kundgodkännande → kontrakt → faktura.
            </p>
            <div class="hero-flow">
                <span>Fas 15.1</span>
                <span>Visningsversion</span>
                <span>Klickbar PDF-länk</span>
                <span>Ingen Stripe ännu</span>
                <span>Ingen BankID ännu</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    total_offers = len(offers)
    approved = len([o for o in offers if safe_text(o.get("status")) in ["approved", "signed_with_bankid", "contract_created", "invoiced"]])
    contracts = len([o for o in offers if safe_text(o.get("status")) in ["contract_created", "invoiced"]])
    invoices = len([o for o in offers if safe_text(o.get("status")) == "invoiced"])
    offered_value = sum(safe_float(o.get("total_inc_vat")) for o in offers)
    invoiced_value = sum(safe_float(o.get("total_inc_vat")) for o in offers if safe_text(o.get("status")) == "invoiced")
    profile_score = company_profile_score(profile)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Offerter", total_offers)
    with c2:
        st.metric("Godkända", approved)
    with c3:
        st.metric("Kontrakt", contracts)
    with c4:
        st.metric("Fakturor", invoices)

    c5, c6, c7 = st.columns(3)

    with c5:
        st.metric("Offererat värde", money(offered_value))
    with c6:
        st.metric("Fakturerat värde", money(invoiced_value))
    with c7:
        st.metric("Företagsprofil", f"{profile_score}%")

    render_profile_warning(profile)

    st.markdown("### Visningschecklista")

    checks = [
        ("Supabase Auth fungerar", True),
        ("AI-nyckel finns", bool(OPENAI_API_KEY)),
        ("APP_BASE_URL är satt", bool(APP_BASE_URL)),
        ("Företagsprofil är komplett", is_company_profile_ready(profile)),
        ("Offert-PDF finns", True),
        ("Kundlänk finns", True),
        ("Klickbar kundlänk i offert-PDF finns", True),
        ("Redigering av offert finns", True),
        ("Kontrakt-PDF finns", True),
        ("Faktura-PDF finns", True),
        ("Domän kopplas senare", True),
        ("Stripe kopplas senare", True),
        ("BankID byggs senare", True),
    ]

    for label, ok in checks:
        if ok:
            st.success(f"✓ {label}")
        else:
            st.warning(f"Behöver åtgärdas: {label}")

    st.markdown("### Domänförberedelse")

    st.markdown(
        """
        <div class="domain-card">
            <h4>Nuvarande onlineadress</h4>
            <p>
                Appen körs just nu på Streamlit-länken. Kundlänkar skapas från APP_BASE_URL.
                Ändra inte APP_BASE_URL till www.offertly.se förrän domänen faktiskt är kopplad och testad.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.code(APP_BASE_URL)

    st.markdown("### Senaste offerter")

    if not offers:
        st.info("Inga offerter ännu.")
        return

    for offer in offers[:5]:
        st.markdown(
            f"""
            <div class="soft-card">
                <b>{safe_text(offer.get("project_title", "Namnlöst projekt"))}</b><br/>
                {status_badge(safe_text(offer.get("status", "draft")))}
                <p class="small-muted">
                    {safe_text(offer.get("customer_name", ""))} · {safe_text(offer.get("offer_number", ""))} · {money(offer.get("total_inc_vat"))}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_create_offer(user_id: str, profile: Optional[Dict[str, Any]]):
    st.markdown("## Skapa offert")
    st.caption("Skapa en professionell offert, generera AI-text, justera innehåll och spara kundlänk.")

    render_profile_warning(profile)

    if "ai_offer_text" not in st.session_state:
        st.session_state["ai_offer_text"] = None

    if "last_ai_input" not in st.session_state:
        st.session_state["last_ai_input"] = ""

    with st.form("create_offer_base_form"):
        st.markdown("### 1. Kund")

        c1, c2 = st.columns(2)

        with c1:
            customer_name = st.text_input("Kundnamn")
            customer_email = st.text_input("Kundens e-post")

        with c2:
            customer_phone = st.text_input("Kundens telefon")
            customer_address = st.text_input("Kundens adress")

        st.markdown("### 2. Projekt")

        project_types = [
            "Bygg",
            "Renovering",
            "Badrum",
            "Kök",
            "VVS",
            "El",
            "Måleri",
            "Tak",
            "Markarbete",
            "Annat",
        ]

        project_type = st.selectbox("Projekttyp", project_types)
        project_title = st.text_input("Projekttitel")
        raw_project_description = st.text_area(
            "Beskriv projektet kort",
            height=130,
            placeholder="Exempel: Kunden vill renovera badrum på ca 6 kvm. Rivning, tätskikt, kakel, klinker, installation av kommod och duschvägg...",
        )

        generate_ai = st.form_submit_button("Generera AI-text", type="primary")

    current_ai_input = json.dumps(
        {
            "customer_name": customer_name,
            "project_type": project_type,
            "project_title": project_title,
            "raw_project_description": raw_project_description,
        },
        ensure_ascii=False,
    )

    if generate_ai:
        if len(raw_project_description.strip()) < 20:
            st.error("Skriv lite mer projektinformation innan AI-text genereras.")
        else:
            with st.spinner("Genererar professionell offerttext..."):
                st.session_state["ai_offer_text"] = generate_ai_offer_text(
                    project_type=project_type,
                    project_title=project_title,
                    project_description=raw_project_description,
                    customer_name=customer_name,
                    company_profile=profile,
                )
                st.session_state["last_ai_input"] = current_ai_input

    ai_data = st.session_state.get("ai_offer_text")

    if ai_data:
        st.success("AI-text genererad. Justera texten innan du sparar offerten.")

        professional_description = st.text_area(
            "Redigerbar projektbeskrivning till offert/PDF/kundvy",
            value=safe_text(ai_data.get("professional_description", raw_project_description)),
            height=150,
        )

        scope_text = st.text_area(
            "Redigerbar arbetsomfattning – en rad per punkt",
            value="\n".join(ai_data.get("scope", [])),
            height=150,
        )

        default_terms = "\n".join(ai_data.get("terms", []))

        if profile and safe_text(profile.get("default_terms", "")).strip():
            default_terms = safe_text(profile.get("default_terms", "")).strip()

        terms = st.text_area("Redigerbara villkor", value=default_terms, height=120)

        customer_message = st.text_area(
            "Kundmeddelande / intern förhandsvisning",
            value=safe_text(ai_data.get("customer_message", "")),
            height=90,
        )
    else:
        professional_description = raw_project_description
        scope_text = ""
        terms = safe_text(profile.get("default_terms", "") if profile else "")
        customer_message = ""

    st.markdown("### 3. Pris")

    c1, c2 = st.columns(2)

    with c1:
        labor_description = st.text_input("Arbete – beskrivning", value="Arbetskostnad enligt omfattning")
        labor_amount = st.number_input("Arbete – belopp exkl. moms", min_value=0.0, step=500.0, value=0.0)

        material_description = st.text_input("Material – beskrivning", value="Material")
        material_amount = st.number_input("Material – belopp exkl. moms", min_value=0.0, step=500.0, value=0.0)

    with c2:
        other_description = st.text_input("Övrigt – beskrivning", value="Övriga kostnader")
        other_amount = st.number_input("Övrigt – belopp exkl. moms", min_value=0.0, step=500.0, value=0.0)

        include_rot = st.checkbox("Använd ROT-avdrag", value=False)

    preview_rows = build_price_rows_from_simple_inputs(
        scope_text=scope_text,
        labor_description=labor_description,
        labor_amount=labor_amount,
        material_description=material_description,
        material_amount=material_amount,
        other_description=other_description,
        other_amount=other_amount,
    )

    totals = calculate_totals(preview_rows, include_rot)

    st.markdown("### Prisöversikt")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Summa exkl. moms", money(totals["subtotal_ex_vat"]))
    with c2:
        st.metric("Moms 25 %", money(totals["vat_amount"]))
    with c3:
        st.metric("Totalt inkl. moms", money(totals["total_inc_vat"]))

    if include_rot:
        c4, c5 = st.columns(2)

        with c4:
            st.metric("Preliminärt ROT-avdrag", f"-{money(totals['rot_deduction'])}")
        with c5:
            st.metric("Att betala efter ROT", money(totals["total_after_rot"]))

    validation_errors = build_offer_validation_errors(
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

    if validation_errors:
        st.warning("Innan offerten kan sparas behöver detta vara klart:")
        for error in validation_errors:
            st.write(f"• {error}")

    if st.button("Skapa och spara offert", type="primary", use_container_width=True, disabled=bool(validation_errors)):
        payload = {
            "project_title": project_title,
            "project_description": professional_description,
            "project_type": project_type,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": customer_phone,
            "customer_address": customer_address,
            "price_rows": preview_rows,
            "subtotal_ex_vat": totals["subtotal_ex_vat"],
            "vat_amount": totals["vat_amount"],
            "total_inc_vat": totals["total_inc_vat"],
            "labor_total_inc_vat": totals["labor_total_inc_vat"],
            "rot_deduction": totals["rot_deduction"],
            "total_after_rot": totals["total_after_rot"],
            "terms": terms,
            "status": "sent",
            "sent_at": now_iso(),
        }

        try:
            new_offer = create_offer(user_id, payload)

            if new_offer:
                st.session_state["ai_offer_text"] = None
                st.success("Offerten är sparad.")
                st.code(get_public_link(new_offer["public_token"]))
            else:
                st.error("Offerten kunde inte sparas.")

        except Exception as e:
            st.error(f"Kunde inte spara offert: {e}")


def render_offer_edit_form(offer: Dict[str, Any], user_id: str):
    price_rows = normalize_price_rows(offer.get("price_rows", []))
    scope_text = "\n".join(get_scope_rows(price_rows))

    labor_row = extract_row_by_type(price_rows, "Arbete")
    material_row = extract_row_by_type(price_rows, "Material")
    other_row = extract_row_by_type(price_rows, "Övrigt")

    offer_id = safe_text(offer.get("id"))
    project_type_options = [
        "Bygg",
        "Renovering",
        "Badrum",
        "Kök",
        "VVS",
        "El",
        "Måleri",
        "Tak",
        "Markarbete",
        "Annat",
    ]

    existing_project_type = safe_text(offer.get("project_type", "Bygg"))

    if existing_project_type not in project_type_options:
        project_type_options.append(existing_project_type)

    with st.form(f"edit_offer_form_{offer_id}"):
        st.markdown("#### Redigera kund och projekt")

        c1, c2 = st.columns(2)

        with c1:
            customer_name = st.text_input("Kundnamn", value=safe_text(offer.get("customer_name", "")), key=f"edit_customer_name_{offer_id}")
            customer_email = st.text_input("Kundens e-post", value=safe_text(offer.get("customer_email", "")), key=f"edit_customer_email_{offer_id}")
            customer_phone = st.text_input("Kundens telefon", value=safe_text(offer.get("customer_phone", "")), key=f"edit_customer_phone_{offer_id}")
            customer_address = st.text_input("Kundens adress", value=safe_text(offer.get("customer_address", "")), key=f"edit_customer_address_{offer_id}")

        with c2:
            project_title = st.text_input("Projekttitel", value=safe_text(offer.get("project_title", "")), key=f"edit_project_title_{offer_id}")
            project_type = st.selectbox(
                "Projekttyp",
                project_type_options,
                index=project_type_options.index(existing_project_type),
                key=f"edit_project_type_{offer_id}",
            )
            project_description = st.text_area(
                "Projektbeskrivning/offerttext",
                value=safe_text(offer.get("project_description", "")),
                height=160,
                key=f"edit_project_description_{offer_id}",
            )

        scope_text_edit = st.text_area(
            "Arbetsomfattning – en rad per punkt",
            value=scope_text,
            height=140,
            key=f"edit_scope_{offer_id}",
        )

        terms = st.text_area(
            "Villkor",
            value=safe_text(offer.get("terms", "")),
            height=120,
            key=f"edit_terms_{offer_id}",
        )

        st.markdown("#### Redigera pris")

        c3, c4 = st.columns(2)

        with c3:
            labor_description = st.text_input(
                "Arbete – beskrivning",
                value=safe_text(labor_row.get("description", "Arbetskostnad enligt omfattning")),
                key=f"edit_labor_description_{offer_id}",
            )
            labor_amount = st.number_input(
                "Arbete – belopp exkl. moms",
                min_value=0.0,
                step=500.0,
                value=safe_float(labor_row.get("unit_price", 0)),
                key=f"edit_labor_amount_{offer_id}",
            )

            material_description = st.text_input(
                "Material – beskrivning",
                value=safe_text(material_row.get("description", "Material")),
                key=f"edit_material_description_{offer_id}",
            )
            material_amount = st.number_input(
                "Material – belopp exkl. moms",
                min_value=0.0,
                step=500.0,
                value=safe_float(material_row.get("unit_price", 0)),
                key=f"edit_material_amount_{offer_id}",
            )

        with c4:
            other_description = st.text_input(
                "Övrigt – beskrivning",
                value=safe_text(other_row.get("description", "Övriga kostnader")),
                key=f"edit_other_description_{offer_id}",
            )
            other_amount = st.number_input(
                "Övrigt – belopp exkl. moms",
                min_value=0.0,
                step=500.0,
                value=safe_float(other_row.get("unit_price", 0)),
                key=f"edit_other_amount_{offer_id}",
            )

            include_rot = st.checkbox(
                "Använd ROT-avdrag",
                value=safe_float(offer.get("rot_deduction", 0)) > 0,
                key=f"edit_include_rot_{offer_id}",
            )

        updated_rows = build_price_rows_from_simple_inputs(
            scope_text=scope_text_edit,
            labor_description=labor_description,
            labor_amount=labor_amount,
            material_description=material_description,
            material_amount=material_amount,
            other_description=other_description,
            other_amount=other_amount,
        )

        totals = calculate_totals(updated_rows, include_rot)

        st.markdown("#### Ny prisöversikt")
        c5, c6, c7 = st.columns(3)

        with c5:
            st.metric("Summa exkl. moms", money(totals["subtotal_ex_vat"]))
        with c6:
            st.metric("Moms", money(totals["vat_amount"]))
        with c7:
            st.metric("Totalt inkl. moms", money(totals["total_inc_vat"]))

        if include_rot:
            st.info(f"Efter ROT: {money(totals['total_after_rot'])}")

        save_edit = st.form_submit_button("Spara ändringar", type="primary")

    if save_edit:
        if labor_amount <= 0 and material_amount <= 0 and other_amount <= 0:
            st.error("Minst en prisrad måste ha ett belopp större än 0 kr.")
            return

        if include_rot and labor_amount <= 0:
            st.error("ROT kan bara användas när arbetskostnad är större än 0 kr.")
            return

        payload = {
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": customer_phone,
            "customer_address": customer_address,
            "project_title": project_title,
            "project_type": project_type,
            "project_description": project_description,
            "price_rows": updated_rows,
            "terms": terms,
            "subtotal_ex_vat": totals["subtotal_ex_vat"],
            "vat_amount": totals["vat_amount"],
            "total_inc_vat": totals["total_inc_vat"],
            "labor_total_inc_vat": totals["labor_total_inc_vat"],
            "rot_deduction": totals["rot_deduction"],
            "total_after_rot": totals["total_after_rot"],
        }

        try:
            update_offer(offer_id, user_id, payload)
            st.success("Offerten är uppdaterad.")
            st.rerun()
        except Exception as e:
            st.error(f"Kunde inte uppdatera offert: {e}")


def render_saved_offers(user_id: str, profile: Optional[Dict[str, Any]], offers: List[Dict[str, Any]]):
    st.markdown("## Sparade offerter")
    st.caption("Hantera kundlänkar, redigera offerter, skapa kontrakt och skapa fakturor.")

    if not offers:
        st.info("Du har inga sparade offerter ännu.")
        return

    c1, c2, c3 = st.columns([1.2, 0.8, 0.8])

    with c1:
        search = st.text_input("Sök", placeholder="Sök kund, projekt eller offertnummer")

    with c2:
        status_filter = st.selectbox(
            "Status",
            ["Alla", "draft", "sent", "approved", "contract_created", "invoiced"],
            format_func=lambda x: "Alla" if x == "Alla" else status_label(x),
        )

    with c3:
        sort_by = st.selectbox(
            "Sortering",
            ["Nyast först", "Högst värde", "Lägst värde"],
        )

    filtered = offers

    if search.strip():
        q = search.lower().strip()
        filtered = [
            offer for offer in filtered
            if q in safe_text(offer.get("customer_name", "")).lower()
            or q in safe_text(offer.get("project_title", "")).lower()
            or q in safe_text(offer.get("offer_number", "")).lower()
        ]

    if status_filter != "Alla":
        filtered = [offer for offer in filtered if safe_text(offer.get("status", "draft")) == status_filter]

    if sort_by == "Högst värde":
        filtered = sorted(filtered, key=lambda x: safe_float(x.get("total_inc_vat")), reverse=True)
    elif sort_by == "Lägst värde":
        filtered = sorted(filtered, key=lambda x: safe_float(x.get("total_inc_vat")))

    for offer in filtered:
        offer_id = safe_text(offer.get("id"))
        public_token = safe_text(offer.get("public_token", ""))
        status = safe_text(offer.get("status", "draft"))

        with st.container():
            st.markdown('<div class="premium-card">', unsafe_allow_html=True)

            top1, top2 = st.columns([1.3, 0.7])

            with top1:
                st.markdown(f"### {safe_text(offer.get('project_title', 'Namnlöst projekt'))}")
                st.markdown(status_badge(status), unsafe_allow_html=True)
                st.markdown(status_progress_html(status), unsafe_allow_html=True)

            with top2:
                st.metric("Total inkl. moms", money(offer.get("total_inc_vat")))

                if safe_float(offer.get("rot_deduction")) > 0:
                    st.caption(f"Efter ROT: {money(offer.get('total_after_rot'))}")

            st.write(f"**Kund:** {safe_text(offer.get('customer_name', ''))}")
            st.caption(
                f"Offertnummer: {safe_text(offer.get('offer_number', ''))}"
                + (f" · Kontrakt: {safe_text(offer.get('contract_id'))}" if offer.get("contract_id") else "")
                + (f" · Faktura: {safe_text(offer.get('invoice_id'))}" if offer.get("invoice_id") else "")
            )

            tabs = st.tabs(["Offert", "Redigera", "Kontrakt", "Faktura", "Admin"])

            with tabs[0]:
                st.markdown("#### Kundlänk")
                if public_token:
                    st.code(get_public_link(public_token))
                else:
                    st.warning("Denna offert saknar public_token.")

                offer_pdf = generate_offer_pdf(offer, profile)
                st.download_button(
                    "Ladda ner offert-PDF",
                    data=offer_pdf,
                    file_name=f"{safe_text(offer.get('offer_number', 'offert'))}.pdf",
                    mime="application/pdf",
                    key=f"download_offer_pdf_{offer_id}",
                    use_container_width=True,
                )

            with tabs[1]:
                render_offer_edit_form(offer, user_id)

            with tabs[2]:
                if status not in ["approved", "signed_with_bankid", "contract_created", "invoiced"]:
                    st.info("Kontrakt kan skapas när kunden har godkänt offerten.")
                else:
                    if not offer.get("contract_id"):
                        if st.button("Skapa kontrakt", key=f"create_contract_{offer_id}", type="primary"):
                            try:
                                contract_id = generate_contract_number()
                                update_offer(
                                    offer_id,
                                    user_id,
                                    {
                                        "contract_id": contract_id,
                                        "contract_created_at": now_iso(),
                                        "status": "contract_created",
                                    },
                                )
                                st.success("Kontrakt skapat.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Kunde inte skapa kontrakt: {e}")
                    else:
                        st.success(f"Kontrakt skapat: {safe_text(offer.get('contract_id'))}")

                    contract_pdf = generate_contract_pdf(offer, profile)
                    st.download_button(
                        "Ladda ner kontrakt-PDF",
                        data=contract_pdf,
                        file_name=f"{safe_text(offer.get('contract_id') or 'kontrakt')}.pdf",
                        mime="application/pdf",
                        key=f"download_contract_pdf_{offer_id}",
                        use_container_width=True,
                    )

            with tabs[3]:
                if status not in ["contract_created", "invoiced"]:
                    st.info("Faktura kan skapas när kontrakt finns.")
                else:
                    if not offer.get("invoice_id"):
                        if st.button("Skapa faktura", key=f"create_invoice_{offer_id}", type="primary"):
                            try:
                                invoice_id = generate_invoice_number()
                                update_offer(
                                    offer_id,
                                    user_id,
                                    {
                                        "invoice_id": invoice_id,
                                        "invoiced_at": now_iso(),
                                        "status": "invoiced",
                                    },
                                )
                                st.success("Faktura skapad.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Kunde inte skapa faktura: {e}")
                    else:
                        st.success(f"Faktura skapad: {safe_text(offer.get('invoice_id'))}")

                    invoice_pdf = generate_invoice_pdf(offer, profile)
                    st.download_button(
                        "Ladda ner faktura-PDF",
                        data=invoice_pdf,
                        file_name=f"{safe_text(offer.get('invoice_id') or 'faktura')}.pdf",
                        mime="application/pdf",
                        key=f"download_invoice_pdf_{offer_id}",
                        use_container_width=True,
                    )

            with tabs[4]:
                st.warning("Adminläge. Borttagning kan inte ångras.")
                confirm_delete = st.checkbox(
                    "Jag förstår och vill kunna ta bort denna offert",
                    key=f"confirm_delete_{offer_id}",
                )

                if st.button(
                    "Ta bort offert",
                    key=f"delete_offer_{offer_id}",
                    disabled=not confirm_delete,
                ):
                    try:
                        delete_offer(offer_id, user_id)
                        st.success("Offerten är borttagen.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Kunde inte ta bort offert: {e}")

            st.markdown("</div>", unsafe_allow_html=True)


def render_company_profile(user_id: str, profile: Optional[Dict[str, Any]]):
    st.markdown("## Företagsprofil")
    st.caption("Företagsprofilen används i offerter, kundvyn, kontrakt och PDF:er.")

    profile = profile or {}

    with st.form("company_profile_form"):
        c1, c2 = st.columns(2)

        with c1:
            company_name = st.text_input("Företagsnamn", value=safe_text(profile.get("company_name", "")))
            org_number = st.text_input("Organisationsnummer", value=safe_text(profile.get("org_number", "")))
            contact_person = st.text_input("Kontaktperson", value=safe_text(profile.get("contact_person", "")))
            phone = st.text_input("Telefon", value=safe_text(profile.get("phone", "")))
            email = st.text_input("E-post", value=safe_text(profile.get("email", "")))

        with c2:
            address = st.text_input("Adress", value=safe_text(profile.get("address", "")))
            website = st.text_input("Webbplats", value=safe_text(profile.get("website", "")))
            logo_url = st.text_input("Logo URL", value=safe_text(profile.get("logo_url", "")))

        company_description = st.text_area(
            "Företagsbeskrivning",
            value=safe_text(profile.get("company_description", "")),
            height=150,
            placeholder="Skriv en professionell presentation av företaget. Den visas i kundvyn och i PDF:er.",
        )

        default_terms = st.text_area(
            "Standardvillkor",
            value=safe_text(profile.get("default_terms", "")),
            height=140,
            placeholder="Exempel: Priset gäller enligt angiven omfattning. Tilläggsarbeten debiteras efter separat överenskommelse.",
        )

        payment_info = st.text_area(
            "Betalningsinformation",
            value=safe_text(profile.get("payment_info", "")),
            height=120,
            placeholder="Exempel: Betalning sker mot faktura 30 dagar netto. Bankgiro/Swish anges här.",
        )

        save_profile = st.form_submit_button("Spara företagsprofil", type="primary")

    if save_profile:
        payload = {
            "company_name": company_name,
            "org_number": org_number,
            "contact_person": contact_person,
            "phone": phone,
            "email": email,
            "address": address,
            "website": website,
            "company_description": company_description,
            "default_terms": default_terms,
            "payment_info": payment_info,
            "logo_url": logo_url,
        }

        try:
            upsert_company_profile(user_id, payload)
            st.success("Företagsprofilen är sparad.")
            st.rerun()
        except Exception as e:
            st.error(f"Kunde inte spara företagsprofil: {e}")


def render_app():
    user = current_user()

    if not user:
        render_login()
        return

    user_id = user["id"]
    profile = fetch_company_profile(user_id)
    offers = fetch_offers(user_id)

    render_sidebar(user, profile)

    tab_overview, tab_create, tab_saved, tab_profile = st.tabs(
        ["Översikt", "Skapa offert", "Sparade offerter", "Företagsprofil"]
    )

    with tab_overview:
        render_overview(user_id, profile, offers)

    with tab_create:
        render_create_offer(user_id, profile)

    with tab_saved:
        render_saved_offers(user_id, profile, offers)

    with tab_profile:
        render_company_profile(user_id, profile)


# =========================================================
# ROUTER
# =========================================================

def get_offer_query_param() -> str:
    try:
        value = st.query_params.get("offer", "")
        if isinstance(value, list):
            return value[0] if value else ""
        return safe_text(value)
    except Exception:
        try:
            params = st.experimental_get_query_params()
            value = params.get("offer", [""])
            return value[0] if value else ""
        except Exception:
            return ""


public_token = get_offer_query_param()

if public_token:
    render_public_offer(public_token)
else:
    render_app()