"""Model-free candidate pairing by topic, scope and polarity.

The extraction model invents `subject_key`, and its wording changes between runs
("refunds" vs "approval-threshold", "sampletrack-beta" vs "sampletrack-ga").
Requiring an exact key loses real pairs, so the matcher combines independent
topic signals instead: canonical key tokens, subject words, distinctive values
and the message text. Scope is checked first, so a shared word never pairs two
different customers.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from rapidfuzz import fuzz

from .models import Claim, ClaimKind, ClaimStatus
from .store import pair_id

SUBJECT_SIMILARITY = 80

_STOP = frozenset(
    """
a an the and or but if then than so as at by for in on of to with without within about
over under above below from into onto upon between among through during before after
until since while when where which who whom whose what why how this that these those
there here their them they we our us you your he she it its his her i me my mine ours
yours is are was were be been being am have has had do does did will would can could
may might must should shall not no nor yes all any both each every few more most less
least many much some such only also just very too now today tomorrow yesterday soon
later again once twice ever never always often sometimes usually already still yet even
well back out up down off away forward together apart etc
el la los las un una unos unas de del al a y o pero si entonces que como para por con
sin en sobre entre durante antes despues hasta desde cuando donde quien quienes cuyo
cuya este esta estos estas ese esa esos esas aquel aquella su sus mi mis tu tus nuestro
nuestra nuestros nuestras es son ser esta estan estaba estaban fue fueron era eran ha
han habia hay tiene tienen tenia tenian puede pueden podria podrian debe deben sera
seran ni todo toda todos todas cada algun alguna algunos algunas ningun ninguna mas
menos muy tambien solo ahora hoy manana ayer ya aun siempre nunca
""".split()
)

# Words that describe the shape of a claim (phase, meta, units, generic business
# nouns) rather than the topic. They still count as weak evidence, but a pair of
# claims that only shares one of them is not the same subject.
_GENERIC = frozenset(
    """
data api support service services platform system tool tools trial trials hour hours time
times fee fees price prices pricing cost costs rate rates usd eur gbp mxn cop clp ars kg lb
lbs km mi cm mm hr hrs min mins minute minutes rph rpm route routes storage waiver
waivers extension extensions window windows sale sales policy policies commitment
commitments decision decisions status state approval approvals approved approve exception
exceptions threshold thresholds limit limits value values requirement requirements rule
rules term terms condition conditions clause clauses exclusion exclusions exclude
excluded include included inclusion change changes update updates date dates schedule
scheduled deadline deadlines timeline milestone milestones phase phases stage stages
version versions launch launches release releases rollout rollouts ship ships shipping
beta betas preview pilot pilots ga general availability available early access limited
full public private alpha new next current upcoming plan plans planned proposal
proposed announce announced announcement notice note correction correct corrected
replace replaced supersede superseded cancel cancelled canceled remove removed move
moved delay delayed postpone postponed extend extended reduce reduced increase
increased raise raised lower lowered cap capped waive waived mandatory optional option
request requested signed sign contract contracts agreement agreements addendum addenda
customer customers client clients account accounts user users company companies team
teams business businesses product products feature features tier tiers segment segments
region regions area areas site sites location locations unit units item items thing
things part parts group groups people person member members vendor vendors supplier
suppliers partner partners agency agencies all every each per from starting effective
applies apply applied remain remains stay stays keep keeps kept get gets got give
gives make makes take takes come comes go goes use uses used need needs want wants
know see say says said tell told show shows provide provides provided offer offers
offered start starts started begin begins began end ends ended continue continues run
runs running work works working happen happens require requires required expect
expects expected allow allows allowed add adds added extra additional base standard
default currently politica politicas compromiso compromisos decision decisiones estado
aprobacion aprobado aprobar excepcion excepciones umbral umbrales limite limites valor
valores requisito requisitos regla reglas termino terminos condicion condiciones
clausula clausulas exclusion exclusiones excluir excluido incluir incluido cambio
cambios actualizacion actualizaciones fecha fechas calendario programado plazo hito
fase fases etapa version lanzamiento lanzamientos liberacion despliegue envio vista
previa piloto disponibilidad disponible temprano acceso limitado completo publico
privado nuevo nueva proximo proxima actual plan planes planificado propuesta anuncio
aviso nota correccion corregido reemplazar reemplazado cancelar cancelado eliminar
eliminado mover movido retrasar retrasado posponer pospuesto extender extendido
reducir reducido aumentar aumentado subir subido bajar bajado exencion obligatorio
opcional opcion solicitud firmado contrato contratos acuerdo acuerdos cliente clientes
cuenta cuentas usuario usuarios empresa empresas equipo equipos negocio negocios
producto productos servicio servicios funcion funciones nivel niveles segmento segmentos
region regiones area areas sitio sitios ubicacion ubicaciones unidad unidades elemento
elementos cosa cosas parte partes grupo grupos persona personas miembro miembros
proveedor proveedores socio socios agencia agencias efectivo aplica aplicar permanecer
mantener obtener dar hacer tomar venir ir usar necesitar querer saber ver decir
mostrar proporcionar ofrecer comenzar empezar terminar continuar ejecutar trabajar
suceder requerir esperar permitir agregar adicional estandar predeterminado actualmente
todavia
""".split()
)

# Time words are values, not topics: two claims that both mention Q4 or January
# are not necessarily about the same thing.
_TEMPORAL = frozenset(
    """
monday tuesday wednesday thursday friday saturday sunday mon tue tues wed thu thur
thurs fri sat sun lunes martes miercoles jueves viernes sabado domingo january
february march april may june july august september october november december jan feb
mar apr jun jul aug sep sept oct nov dec enero febrero marzo abril mayo junio julio
agosto septiembre octubre noviembre diciembre ene abr ago dic q1 q2 q3 q4 quarter
quarters day days week weeks month months year years today tomorrow yesterday weekday
weekend spring summer autumn winter end start beginning mid early late next last this
current upcoming
""".split()
)

# A scope prefix is the same customer at a finer granularity (a site, a clinic, a
# marketplace). A different region or segment is not: those are different scopes.
_SEGMENT = frozenset(
    """
eu us usa uk apac latam emea americas asia europe africa global worldwide enterprise
smb sme midmarket mid-market region regions
""".split()
)

_SPELLING = {
    "centre": "center",
    "centres": "center",
    "centers": "center",
    "colour": "color",
    "colours": "color",
    "organisation": "organization",
    "organisations": "organization",
    "authorise": "authorize",
    "authorised": "authorize",
    "cancelled": "canceled",
    "cancelling": "canceling",
    "labelling": "labeling",
    "labelled": "labeled",
    "modelling": "modeling",
    "travelling": "traveling",
    "travelled": "traveled",
    "analyse": "analysis",
    "licence": "license",
    "defence": "defense",
    "practise": "practice",
    "programme": "program",
}

# Singular words that end in "s"; stripping it would turn them into a different
# word ("status" -> "statu", "campus" -> "campu").
_KEEP_S = frozenset(
    """
status campus business analysis basis series news means species alias atlas canvas
chaos cosmos gas lens plus focus bonus virus census consensus corpus genius radius
surplus syllabus thesis crisis diagnosis emphasis hypothesis synthesis axis
headquarters premises logistics
""".split()
)

# Distinctive values: exact dates, percentages, money and measurements. Quarters
# and bare years are deliberately absent; they are too common to identify a topic.
_NUMBER_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|"
    r"\b\d+(?:[.,]\d+)?\s*%|"
    r"[$€£]\s*\d+(?:[.,]\d+)?|"
    r"\b(?:usd|eur|gbp|mxn|cop|clp|ars)\s*\d+(?:[.,]\d+)?|"
    r"\b\d+(?:[.,]\d+)?\s*(?:usd|eur|gbp|mxn|cop|clp|ars)\b|"
    r"\b\d+(?:[.,]\d+)?[\s-]*(?:kg|lb|lbs|km|mi|m|cm|mm|h|hr|hrs|hour|hours|min|mins|"
    r"minute|minutes|day|days|week|weeks|month|months|year|years|seat|seats|kit|kits|"
    r"van|vans|route|routes|request|requests|rph|rpm)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class MatchReport:
    matches: list[Claim]
    skip_reasons: tuple[str, ...]


def _words(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9]+", ascii_text.casefold())


def _canon(token: str) -> str:
    token = _SPELLING.get(token, token)
    if token in _KEEP_S:
        return token
    if token.endswith("ies") and len(token) > 4:
        return _SPELLING.get(token[:-3] + "y", token[:-3] + "y")
    if token.endswith("es") and len(token) > 4:
        # "statuses", "classes", "boxes" drop "es"; "dates", "phases" drop "s".
        stripped = (
            token[:-2]
            if token.endswith(("uses", "sses", "xes", "zes", "ches", "shes"))
            else token[:-1]
        )
        return _SPELLING.get(stripped, stripped)
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        stripped = token[:-1]
        return _SPELLING.get(stripped, stripped)
    return token


def _tokens(text: str) -> set[str]:
    return {_canon(word) for word in _words(text) if word not in _STOP}


def _key_order(subject_key: str) -> list[str]:
    return [_canon(part) for part in subject_key.split("-") if part and part not in _STOP]


def _subject_order(subject: str) -> list[str]:
    return [_canon(word) for word in _words(subject) if word not in _STOP]


def _specific(tokens: set[str]) -> set[str]:
    return {
        token
        for token in tokens
        if token not in _GENERIC and token not in _TEMPORAL and not token.isdigit()
    }


def _head(ordered: list[str]) -> str | None:
    useful = [token for token in ordered if token not in _GENERIC and token not in _TEMPORAL]
    if useful:
        return useful[-1]
    return ordered[-1] if ordered else None


def _numbers(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return {
        " ".join(match.group(0).casefold().split()) for match in _NUMBER_RE.finditer(ascii_text)
    }


def _name_tokens(claim: Claim) -> set[str]:
    """Proper names, acronyms and camelCase products in the model's own fields."""
    names: set[str] = set()
    for text in (claim.subject, claim.value):
        raw_words = re.findall(r"[A-Za-z][A-Za-z0-9]*", text)
        for index, raw in enumerate(raw_words):
            token = _canon(raw.casefold())
            if token in _STOP or token in _GENERIC or token in _TEMPORAL:
                continue
            if raw.isupper() and len(raw) >= 2:
                names.add(token)
            elif any(char.isupper() for char in raw[1:]):
                names.add(token)
            elif index > 0 and raw[0].isupper():
                names.add(token)
    return names


def _scope_tokens(scope_key: str) -> set[str]:
    return {_canon(part) for part in scope_key.split("-") if part and part != "*"}


def _compatible_scope(new: Claim, stored: Claim) -> bool:
    if new.scope_key == stored.scope_key or "*" in (new.scope_key, stored.scope_key):
        return True
    new_tokens = _scope_tokens(new.scope_key)
    stored_tokens = _scope_tokens(stored.scope_key)
    if not (new_tokens < stored_tokens or stored_tokens < new_tokens):
        return False
    extra = (
        (stored_tokens - new_tokens) if new_tokens < stored_tokens else (new_tokens - stored_tokens)
    )
    return not bool(extra & _SEGMENT)


def _same_topic(new: Claim, stored: Claim) -> bool:
    if new.subject_key == stored.subject_key:
        return True

    new_key = set(_key_order(new.subject_key))
    stored_key = set(_key_order(stored.subject_key))
    new_subject = set(_subject_order(new.subject))
    stored_subject = set(_subject_order(stored.subject))

    shared_scope = _scope_tokens(new.scope_key) & _scope_tokens(stored.scope_key)
    new_value = _tokens(new.value) - shared_scope
    stored_value = _tokens(stored.value) - shared_scope
    new_text = _tokens(new.text) - shared_scope
    stored_text = _tokens(stored.text) - shared_scope
    exact_scope = new.scope_key == stored.scope_key or "*" in (new.scope_key, stored.scope_key)

    shared_key = _specific(new_key) & _specific(stored_key)
    if len(shared_key) >= 2:
        return True
    if shared_key and _head(_key_order(new.subject_key)) in shared_key:
        if _head(_key_order(stored.subject_key)) in shared_key:
            return True
    if shared_key & _name_tokens(new) & _name_tokens(stored):
        return True

    shared_subject = _specific(new_subject) & _specific(stored_subject)
    if len(shared_subject) >= 2:
        return True
    if shared_subject and _head(_subject_order(new.subject)) in shared_subject:
        if _head(_subject_order(stored.subject)) in shared_subject:
            return True
    if shared_subject & _name_tokens(new) & _name_tokens(stored):
        return True

    if _numbers(new.value) & _numbers(stored.value):
        return True

    shared_any = _specific(new_key | new_subject | new_value | new_text) & _specific(
        stored_key | stored_subject | stored_value | stored_text
    )
    if shared_any:
        if exact_scope:
            return True
        # A finer scope (one site of a customer) is weak evidence on its own:
        # require the shared word to name the subject, not just to appear in prose.
        if _specific(new_key | new_subject) & _specific(stored_key | stored_subject):
            return True

    if _numbers(new.text) & _numbers(stored.text):
        return True

    return fuzz.token_set_ratio(new.subject, stored.subject) >= SUBJECT_SIMILARITY


def match_report(
    new: Claim,
    stored: Sequence[Claim],
    *,
    pairs_seen: Iterable[str] = (),
) -> MatchReport:
    """Find active claims in a different room that could conflict with `new`."""
    seen = set(pairs_seen)
    matches: list[Claim] = []
    reasons: list[str] = []
    for other in stored:
        if other.status != ClaimStatus.ACTIVE:
            continue
        if other.room_id == new.room_id:
            reasons.append("same room")
            continue
        if pair_id(new, other) in seen:
            reasons.append("pair already seen")
            continue
        if other.kind != ClaimKind.DECISION and other.author.casefold() == new.author.casefold():
            reasons.append("same author")
            continue
        if not _compatible_scope(new, other):
            reasons.append("different scope")
            continue
        if not _same_topic(new, other):
            reasons.append("different subject")
            continue
        matches.append(other)
    # Recorded decisions first, then the most recent claim, then id for a stable
    # order across SQLite row orderings.
    matches.sort(
        key=lambda item: (
            0 if item.kind == ClaimKind.DECISION else 1,
            -item.ts,
            item.id,
        )
    )
    return MatchReport(matches=matches, skip_reasons=tuple(sorted(set(reasons))))


def find_matches(
    new: Claim,
    stored: Sequence[Claim],
    *,
    pairs_seen: Iterable[str] = (),
) -> list[Claim]:
    return match_report(new, stored, pairs_seen=pairs_seen).matches
