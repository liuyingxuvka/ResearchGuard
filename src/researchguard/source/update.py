"""
Purpose: Apply SourceGuard observations to a belief state without converting candidates into final evidence.
Repository: https://github.com/liuyingxuvka/ResearchGuard
Skill: SourceGuard
Math boundary: Expected utility ranks search value, not factual truth or calibrated probability.
CLI: researchguard source add-observation <model.yaml> --observation observation.yaml --output updated.yaml
Boundary: Source candidates and evidence anchors require downstream TraceGuard/LogicGuard review before final claims.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import date
import ipaddress
import re
import unicodedata
from urllib.parse import urlparse

from .root_zone import TOP_LEVEL_DOMAINS
from .schema import (
    BeliefState,
    EvidenceAnchor,
    Gap,
    GapClosureBasis,
    GapQualification,
    Lead,
    Observation,
    SchemaError,
    SourceRecord,
    unit_score,
    utc_now,
)


DEFAULT_QUALIFICATION_THRESHOLDS = {
    "source_reliability": 0.5,
    "extraction_confidence": 0.5,
    "specificity": 0.5,
}


def _upsert_by_id(items, new_item, attr: str):
    output = []
    replaced = False
    new_id = getattr(new_item, attr)
    for item in items:
        if getattr(item, attr) == new_id:
            output.append(new_item)
            replaced = True
        else:
            output.append(item)
    if not replaced:
        output.append(new_item)
    return output


def add_source(belief_state: BeliefState, source: SourceRecord) -> BeliefState:
    source = replace(source, source_status=source.source_status or "candidate")
    return replace(belief_state, sources=_upsert_by_id(belief_state.sources, source, "source_id"))


def add_anchor(belief_state: BeliefState, anchor: EvidenceAnchor, *, source: SourceRecord | None = None,
               create_only: bool = False) -> BeliefState:
    """Keep anchors source-owned; explicit creation rejects an existing identity."""
    if create_only and any(row.anchor_id == anchor.anchor_id for row in belief_state.anchors):
        raise ValueError(f"duplicate anchor id: {anchor.anchor_id}")
    if source is not None and source.source_id != anchor.source_id:
        raise ValueError(f"anchor {anchor.anchor_id} belongs to {anchor.source_id}, not {source.source_id}")
    if not any(row.source_id == anchor.source_id for row in belief_state.sources):
        new_source = source or SourceRecord(source_id=anchor.source_id)
        require_document(new_source, "this anchor would create")
        belief_state = add_source(belief_state, new_source)
    if anchor.locator.strip() and not names_place(anchor.locator):
        raise ValueError(
            f"anchor_locator_names_no_place:{anchor.anchor_id}: locator {anchor.locator!r} names no place in "
            f"{anchor.source_id}; it names a person, a kind of message, or nothing. A quote belongs to the document "
            "it is printed in, at the place it is printed. Nothing was written.")
    return replace(belief_state, anchors=_upsert_by_id(belief_state.anchors, anchor, "anchor_id"))


_DOI = re.compile(r"^(?:doi:\s*)?10\.\d{4,9}/\S+$", re.IGNORECASE)
_ISBN = re.compile(r"^(?:urn:)?isbn(?:-1[03])?(?::\s*|\s+)([0-9][0-9 -]{8,15}[0-9X])$", re.IGNORECASE)
_ARXIV = re.compile(r"^arxiv:\s*(?:\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}|[a-z]+(?:-[a-z]+)*(?:\.[a-z]{2})?/\d{2}(?:0[1-9]|1[0-2])\d{3})"
                    r"(?:v\d+)?$", re.IGNORECASE)
_HOST_LABEL = re.compile(r"^[^\W_](?:[^\W_]|-){0,62}$")
_AUTHORITY = re.compile(r"https?://([^/?#]*)", re.IGNORECASE)
_PORT = re.compile(r"\d{0,5}", re.ASCII)
_HEXTET = re.compile(r"[0-9a-f]{1,4}", re.ASCII | re.IGNORECASE)
_IPV4 = re.compile(r"(?:0|[1-9]\d{0,2})(?:\.(?:0|[1-9]\d{0,2})){3}", re.ASCII)
# Host names that exist only for examples or tests, and the top-level domains that name no public host.
_EXAMPLE_HOSTS = ("example.com", "example.net", "example.org")
_NO_PUBLIC_HOST = frozenset({"arpa", "onion"})
_DATE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
_NO_OUTSIDE_LOCATOR = "no link, DOI, ISBN or arXiv id"


# Words that, on their own, name no document: placeholders, words for a person or a kind of message,
# small connecting words, and (for a title) words for a kind of document. A title or locator made only of
# these, or of single Latin letters, or with no letter or digit at all, names nothing another reader can find.
_PLACEHOLDER_WORDS = frozenset(
    "unknown unk none null nil na tbd tba todo untitled unnamed anonymous anon placeholder missing empty blank "
    "xxx xx test misc various same ibid see above below".split())
_PERSONAL_WORDS = frozenset(
    "note notes memo memos email emails mail message messages msg chat chats call calls phone conversation "
    "conversations discussion meeting comment comments remark remarks colleague colleagues coworker coworkers "
    "worker workers friend friends boss manager someone somebody person people expert insider contact personal "
    "communication private internal verbal oral informal unpublished own my our his her their me we you they "
    "told said says heard mentioned".split())
_CONNECTING_WORDS = frozenset("the of from by with to and or on in about at for an this that".split())
_DOCUMENT_KIND_WORDS = frozenset(
    "title source sources document documents doc docs file item entry reference ref citation quote quotation "
    "excerpt passage text record article report paper page website site web online link book".split())
_PLACEHOLDER_PHRASES = frozenset("未知 不详 无 无标题 同事 同事的笔记 同事笔记 笔记 备注 来源 资料 聊天记录 邮件 个人通信".split())
_TITLE_WORDS = _PLACEHOLDER_WORDS | _PERSONAL_WORDS | _CONNECTING_WORDS | _DOCUMENT_KIND_WORDS
_LOCATOR_WORDS = _PLACEHOLDER_WORDS | _PERSONAL_WORDS | _CONNECTING_WORDS


def visible_text(text: str) -> str:
    """``text`` as a reader sees it: invisible characters such as a zero-width space removed, spaces collapsed."""
    shown = "".join(char for char in unicodedata.normalize("NFKC", text) if unicodedata.category(char) not in {"Cf", "Cc", "Co", "Cn"})
    return " ".join(shown.split())


def _names_nothing(text: str, generic: frozenset[str]) -> bool:
    words = re.findall(r"[^\W_]+", visible_text(text).casefold())
    return all(word in generic or word in _PLACEHOLDER_PHRASES or (len(word) == 1 and word.isascii() and word.isalpha())
               for word in words)


def names_place(locator: str) -> bool:
    """Whether a locator can point into a document: it is not only a person, a kind of message or a placeholder."""
    return not _names_nothing(locator, _LOCATOR_WORDS)


@dataclass(frozen=True)
class SourceIdentity:
    """What a source record says about its document, checked by the tool.

    A title names a document unless it has no letter or digit, or is made only of placeholders, words for
    a person or a kind of message or document, and small connecting words ("colleague's note", "n/a").
    That is all a tool can check about a title: an invented title passes. A link must be an http or https
    URL with a dotted host name or an IP address and, if it has one, a port from 0 to 65535, or a DOI, an
    ISBN or an arXiv id. A date must be a calendar date that is not in the
    future. A source names its document when it has a title that names one or a link; a date alone names
    none. A source is unverifiable unless its link is an outside locator (see ``outside_locator``): then
    ``unverifiable`` says why, whatever the title says.
    """

    title: str
    title_names_document: bool
    link: str
    date: str
    problems: tuple[str, ...]
    unverifiable: str

    @property
    def names_document(self) -> bool:
        return self.title_names_document or bool(self.link)

    def title_summary(self) -> str:
        if not self.title:
            return "no title"
        return f'title "{self.title}"' + ("" if self.title_names_document else " names no document")

    def summary(self) -> str:
        return "; ".join((self.title_summary(), f"link {self.link}" if self.link else "no link",
                          f"date {self.date}" if self.date else "no date"))


def source_identity(source: SourceRecord) -> SourceIdentity:
    url, when, title = source.url.strip(), source.source_date.strip(), visible_text(source.title)
    problems = []
    if url and not _is_link(url):
        problems.append(f"url {url!r} is not a link: http or https with a host name, a DOI, an ISBN or an arXiv id")
    if when and not _is_date(when):
        problems.append(f"date {when!r} is not a calendar date: YYYY, YYYY-MM or YYYY-MM-DD, not in the future")
    return SourceIdentity(title=title, title_names_document=bool(title) and not _names_nothing(title, _TITLE_WORDS),
                          link=url if url and _is_link(url) else "", date=when if when and _is_date(when) else "",
                          problems=tuple(problems), unverifiable=outside_locator(url)[1])


def outside_locator(url: str) -> tuple[str, str]:
    """What a reader outside this folder can look the document up by, read from a source's url field only.

    Returns ``(kind, "")`` with kind ``"link"`` (an http or https URL whose host name ends in a top-level
    domain of the root zone and is not an example, onion or .arpa name), ``"DOI"``, ``"ISBN"`` (with a
    correct check digit) or ``"arXiv id"``, and ``("", reason)`` for anything else. No title, locator or
    date is read, and nothing is looked up on the network: an invented link, DOI or ISBN passes, and the
    owner sees it in the candidate comparison.
    """
    url = url.strip()
    if not url:
        return "", _NO_OUTSIDE_LOCATOR
    if _DOI.match(url):
        return "DOI", ""
    isbn = _ISBN.match(url)
    if isbn:
        return ("ISBN", "") if _isbn_checks(isbn[1]) else ("", f"the ISBN in {url!r} has a wrong check digit")
    if _ARXIV.match(url):
        return "arXiv id", ""
    host, port = _url_host(url)
    if not host:
        return "", f"{url!r} is not an http or https link, a DOI, an ISBN or an arXiv id"
    if not _port_checks(port):
        return "", f"the port {port!r} of {url} is not a number from 0 to 65535"
    address = _ip_address(host)
    if address is not None:
        return "", f"the host {host} of {url} is {'a loopback' if address.is_loopback else 'an'} IP address, not a public host name"
    if not _public_host(host):
        return "", f"the host {host} of {url} is not a public host name"
    return "link", ""


def _isbn_checks(text: str) -> bool:
    digits = text.replace("-", "").replace(" ", "").upper()
    if len(digits) == 10 and digits[:9].isdigit() and (digits[9].isdigit() or digits[9] == "X"):
        values = [int(char) for char in digits[:9]] + [10 if digits[9] == "X" else int(digits[9])]
        return sum((10 - index) * value for index, value in enumerate(values)) % 11 == 0
    if len(digits) == 13 and digits.isdigit() and digits[:3] in {"978", "979"}:
        return sum((1 if index % 2 == 0 else 3) * int(char) for index, char in enumerate(digits)) % 10 == 0
    return False


def _url_host(url: str) -> tuple[str, str]:
    """The host and the port text of an http or https URL, or ``("", "")`` for anything else.

    A host is a name or an IPv6 address in brackets; any other bracket, or a space, makes no URL. The port
    text is returned unchecked (see ``_port_checks``). The URL parser is never given input it rejects: it
    raises on a bracketed host that is not an IPv6 address, and on a port that is not a number.
    """
    url = unicodedata.normalize("NFKC", url)
    authority = _AUTHORITY.match(url)
    if authority is None or any(char.isspace() for char in url):
        return "", ""
    hostport = authority[1].rpartition("@")[2]
    start = authority.end(1) - len(hostport)
    if hostport.startswith("["):
        literal, closed, after = hostport[1:].partition("]")
        rest = url[:start] + url[start + len(literal) + 2:]
        if not closed or not _ipv6_literal(literal) or (after and not after.startswith(":")) or "[" in rest or "]" in rest:
            return "", ""
        return literal.casefold(), after[1:]
    if "[" in url or "]" in url:
        return "", ""
    return urlparse(url).hostname or "", hostport.partition(":")[2]


def _port_checks(port: str) -> bool:
    """Whether the port text of a URL is empty or a number from 0 to 65535."""
    number = port.lstrip("0")
    return bool(_PORT.fullmatch(number)) and (not number or int(number) <= 65535)


def _ipv6_literal(text: str) -> bool:
    """Whether ``text`` is an IPv6 address the URL parser accepts in brackets (no zone id), checked without it."""
    if "%" in text:
        return False
    head, double, tail = text.partition("::")
    if "::" in tail:
        return False
    groups = [group for part in (head, tail) if part for group in part.split(":")]
    if groups and "." in groups[-1]:
        if not _IPV4.fullmatch(groups[-1]) or any(int(octet) > 255 for octet in groups[-1].split(".")) \
                or (not tail and double):
            return False
        groups[-1:] = ["0", "0"]
    if not all(_HEXTET.fullmatch(group) for group in groups):
        return False
    return len(groups) < 8 if double else len(groups) == 8


def _ip_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """The IP address a URL host is, or None for a host name; only text checked first is given to ipaddress."""
    if _ipv6_literal(host):
        return ipaddress.IPv6Address(host)
    if _IPV4.fullmatch(host) and all(int(octet) <= 255 for octet in host.split(".")):
        return ipaddress.IPv4Address(host)
    return None


def _public_host(host: str) -> bool:
    """Whether a host name could be a public one: labels of letters, digits and hyphens under a top-level
    domain of the root zone, and not a name kept for examples. An IP address is not a host name."""
    name = host.casefold().rstrip(".")
    labels = name.split(".")
    return (len(labels) >= 2 and all(_HOST_LABEL.match(label) and not label.endswith("-") for label in labels)
            and labels[-1] in TOP_LEVEL_DOMAINS and labels[-1] not in _NO_PUBLIC_HOST
            and not any(name == example or name.endswith("." + example) for example in _EXAMPLE_HOSTS))


_MONTHS = {name: number for number, names in enumerate(
    (("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"), ("may",), ("june", "jun"),
     ("july", "jul"), ("august", "aug"), ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
     ("december", "dec")), start=1) for name in names}
_NAMED_TIME = re.compile(
    r"\b(?:(\d{1,2})\s+)?(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?(?:\s+(\d{1,2}),?)?\s+(\d{4})\b"
    r"|\b(\d{4})-(\d{2})(?:-(\d{2}))?\b", re.IGNORECASE)


def times_named(text: str) -> list[tuple[str, date]]:
    """Each day or month a text names (``29 March 2021``, ``April 2021``, ``2021-04``) with the day it starts on.

    A bare year is not read: in a quote it is as often an amount as a time.
    """
    named = []
    for match in _NAMED_TIME.finditer(text):
        if match[4]:
            year, month, day = int(match[4]), _MONTHS[match[2].lower()], int(match[1] or match[3] or 1)
        else:
            year, month, day = int(match[5]), int(match[6]), int(match[7] or 1)
        if 1 <= year and 1 <= month <= 12 and 1 <= day <= monthrange(year, month)[1]:
            named.append((match[0], date(year, month, day)))
    return named


def date_period_end(text: str) -> date:
    """The last day a well-formed source date (YYYY, YYYY-MM or YYYY-MM-DD) covers."""
    match = _DATE.match(text)
    if match is None:
        raise ValueError(f"not a source date: {text!r}")
    year = int(match[1])
    month = int(match[2] or 12)
    return date(year, month, int(match[3] or monthrange(year, month)[1]))


def _is_link(url: str) -> bool:
    """Whether a url field is well formed: an outside locator, or an http or https URL whose host is dotted
    or an IP address and whose port, if any, is a number from 0 to 65535."""
    if outside_locator(url)[0]:
        return True
    host, port = _url_host(url)
    return _port_checks(port) and ("." in host.strip(".") or _ip_address(host) is not None)


def _is_date(text: str) -> bool:
    match = _DATE.match(text)
    if not match:
        return False
    year, month, day = int(match[1]), int(match[2] or 1), int(match[3] or 1)
    if not (1 <= year and 1 <= month <= 12 and 1 <= day <= monthrange(year, month)[1]):
        return False
    return date(year, month, day) <= date.today()


def require_document(source: SourceRecord, action: str) -> SourceIdentity:
    """Refuse to write a source record that names no document or whose link or date is malformed."""
    identity = source_identity(source)
    if identity.problems:
        problems = '; '.join(identity.problems)
        if source.url and not _is_link(source.url):
            problems += '; ' + outside_locator(source.url)[1]
        raise ValueError(f"new_source_identity_invalid:{source.source_id}: {problems}. "
                         "Nothing was written.")
    if not identity.names_document:
        raise ValueError(
            f"new_source_without_identity:{source.source_id}: {action} a source that names no document "
            f"({identity.summary()}). A source is a document that another reader can find; a date alone does "
            "not name one, and a colleague's remark or your own summary is not one. Nothing was written. Leave "
            "the passage out of the argument and keep its missing document as an open source gap until you "
            "have the document itself.")
    return identity


def add_gap(belief_state: BeliefState, gap: Gap) -> BeliefState:
    return replace(belief_state, gaps=_upsert_by_id(belief_state.gaps, gap, "gap_id"))


def add_lead(belief_state: BeliefState, lead: Lead) -> BeliefState:
    return replace(belief_state, leads=_upsert_by_id(belief_state.leads, lead, "lead_id"))


def mark_action_executed(belief_state: BeliefState, action_id: str) -> BeliefState:
    actions = []
    for action in belief_state.actions:
        if action.action_id == action_id:
            actions.append(replace(action, status="executed"))
        else:
            actions.append(action)
    return replace(belief_state, actions=actions)


def _source_is_accessible_candidate(belief_state: BeliefState, source_id: str) -> bool:
    source = belief_state.source_by_id().get(source_id)
    if source is None:
        return False
    return source.access_status not in {"permission_gated", "unavailable"} and source.source_status not in {
        "permission_gated",
        "inaccessible",
        "rejected",
    }


def _qualification_thresholds(belief_state: BeliefState) -> dict[str, float]:
    configured = belief_state.metadata.get("qualification_thresholds")
    if configured is None:
        configured = {}
    if not isinstance(configured, dict):
        raise SchemaError(f"metadata.qualification_thresholds must be a mapping, got {configured!r}")
    return {
        name: unit_score(configured.get(name), default, f"metadata.qualification_thresholds.{name}")
        for name, default in DEFAULT_QUALIFICATION_THRESHOLDS.items()
    }


def qualify_gap_from_anchor(
    belief_state: BeliefState,
    anchor: EvidenceAnchor,
    *,
    observation_id: str = "",
) -> BeliefState:
    """Advance matching gaps only when semantic qualification is explicit.

    A locator is one input, not a closure decision. Closure additionally needs
    an accessible source, reliability/extraction/specificity floors, explicit
    target fit, and claim usability when the gap requests claim closure.
    """

    source = belief_state.source_by_id().get(anchor.source_id)
    accessible = _source_is_accessible_candidate(belief_state, anchor.source_id)
    thresholds = _qualification_thresholds(belief_state)
    gaps = []
    for gap in belief_state.gaps:
        if gap.gap_id not in set(anchor.supports) or gap.gap_type == "permission_gap":
            gaps.append(gap)
            continue

        role_match = bool(source) and (
            not gap.suggested_source_roles or source.source_role in gap.suggested_source_roles
        )
        modality_match = not gap.suggested_modalities or anchor.modality in gap.suggested_modalities
        target_match = role_match and modality_match
        reliability = source.source_reliability if source else 0.0
        reasons: list[str] = []
        checks = {
            "locator present": bool(anchor.locator),
            "source accessible": accessible,
            "source reliability threshold": reliability >= thresholds["source_reliability"],
            "extraction confidence threshold": anchor.extraction_confidence
            >= thresholds["extraction_confidence"],
            "specificity threshold": anchor.specificity >= thresholds["specificity"],
            "target role and modality match": target_match,
            "observation id recorded": bool(observation_id),
        }
        for label, passed in checks.items():
            if not passed:
                reasons.append(f"failed: {label}")
        if gap.requires_claim_usability and not anchor.usable_for_claim:
            reasons.append("failed: anchor is not usable for claim closure")

        evidence_qualified = all(checks.values())
        claim_use_ok = not gap.requires_claim_usability or anchor.usable_for_claim
        closure_qualified = evidence_qualified and claim_use_ok
        if (
            not closure_qualified
            and gap.semantic_state == "closed"
            and gap.closure_basis.is_complete()
        ):
            # A later portfolio, limiting, or independent anchor may be linked
            # to an already closed gap without matching the primary closure
            # role.  It must not erase the earlier qualified closure.
            gaps.append(gap)
            continue
        if closure_qualified:
            decision = "claim_usable" if gap.requires_claim_usability else "qualified_non_claim_closure"
            semantic_state = "closed"
        elif not accessible:
            decision = "blocked"
            semantic_state = "blocked"
        elif evidence_qualified and gap.requires_claim_usability:
            decision = "qualified_not_claim_usable"
            semantic_state = "qualified"
        else:
            decision = "observed_not_qualified"
            semantic_state = "observed"

        qualification = GapQualification(
            anchor_id=anchor.anchor_id,
            source_id=anchor.source_id,
            observation_id=observation_id,
            locator_present=bool(anchor.locator),
            source_accessible=accessible,
            source_reliability=reliability,
            extraction_confidence=anchor.extraction_confidence,
            specificity=anchor.specificity,
            supports_gap=True,
            role_match=role_match,
            modality_match=modality_match,
            target_match=target_match,
            usable_for_claim=anchor.usable_for_claim,
            decision=decision,
            reasons=reasons,
        )
        closure_basis = gap.closure_basis
        if closure_qualified:
            closure_basis = GapClosureBasis(
                anchor_ids=[anchor.anchor_id],
                source_ids=[anchor.source_id],
                observation_ids=[observation_id],
                thresholds=thresholds,
                target_match="source role, anchor modality, and explicit gap support matched",
                claim_use_decision=decision,
                qualified=True,
            )
        note = "Semantically qualified and closed." if closure_qualified else "Anchor observed; semantic closure not licensed."
        gaps.append(
            replace(
                gap,
                semantic_state=semantic_state,
                qualification=qualification,
                closure_basis=closure_basis,
                review_required=not closure_qualified,
                notes=f"{gap.notes} {note}".strip(),
            )
        )
    return replace(belief_state, gaps=gaps)


def detect_basic_contradiction(belief_state: BeliefState, observation: Observation) -> list[Gap]:
    gaps: list[Gap] = []
    for index, contradiction in enumerate(observation.contradictions, start=1):
        gaps.append(
            Gap(
                gap_id=f"contradiction-{observation.observation_id}-{index}",
                lead_id="",
                gap_type="contradiction",
                description=contradiction,
                importance=0.7,
                blocking=True,
                suggested_source_roles=["counter_evidence", "limiting_evidence"],
                semantic_state="contradicted",
                notes="Observation reported a contradiction; existing support is preserved.",
            )
        )
    for source in observation.observed_sources:
        if source.source_role == "counter_evidence":
            answered_gap_ids = {
                gap_id for anchor in observation.observed_anchors
                if anchor.source_id == source.source_id for gap_id in anchor.supports
            }
            if any(
                gap.gap_id in answered_gap_ids
                and (gap.gap_type == "missing_counterevidence" or "counter_evidence" in gap.suggested_source_roles)
                for gap in belief_state.gaps
            ):
                continue
            gaps.append(
                Gap(
                    gap_id=f"counter-source-{source.source_id}",
                    gap_type="contradiction",
                    description=f"Counterevidence candidate observed: {source.title or source.source_id}",
                    importance=0.7,
                    blocking=False,
                    suggested_source_roles=["counter_evidence", "limiting_evidence"],
                    semantic_state="contradicted",
                    notes="Counterevidence should be modeled downstream rather than overwriting prior support.",
                )
            )
    return gaps


def update_frontier(belief_state: BeliefState) -> BeliefState:
    metadata = dict(belief_state.metadata)
    metadata["updated_at"] = utc_now()
    metadata["frontier_boundary"] = "Updated frontier preserves candidates and anchors; it does not validate final claims."
    return replace(belief_state, metadata=metadata)


def apply_observation(belief_state: BeliefState, observation: Observation) -> BeliefState:
    state = belief_state
    warnings = list(state.metadata.get("warnings", []))
    for source in observation.observed_sources:
        require_document(source, "this observation would write")
        state = add_source(state, source)
        if source.access_status in {"permission_gated", "unavailable"} or source.source_status == "permission_gated":
            warnings.append(f"Source {source.source_id} is permission-gated or unavailable and remains an access gap.")
    for anchor in observation.observed_anchors:
        anchor_warnings = list(anchor.warnings)
        if not anchor.locator:
            anchor_warnings.append("Anchor has no locator and cannot safely close a specific evidence gap.")
            warnings.append(f"Anchor {anchor.anchor_id} has no locator.")
        safe_anchor = replace(anchor, warnings=anchor_warnings)
        state = add_anchor(state, safe_anchor)
        state = qualify_gap_from_anchor(state, safe_anchor, observation_id=observation.observation_id)
        for gap in state.gaps:
            if gap.qualification.anchor_id == safe_anchor.anchor_id and gap.semantic_state != "closed":
                warnings.append(
                    f"Anchor {safe_anchor.anchor_id} observed for {gap.gap_id} but did not satisfy semantic closure: "
                    + "; ".join(gap.qualification.reasons)
                )
    for lead in observation.new_leads:
        state = add_lead(state, lead)
    for gap in observation.new_gaps:
        state = add_gap(state, gap)
    for gap in detect_basic_contradiction(state, observation):
        state = add_gap(state, gap)
    if observation.action_id:
        state = mark_action_executed(state, observation.action_id)
    state = replace(state, observations=_upsert_by_id(state.observations, observation, "observation_id"))
    metadata = dict(state.metadata)
    metadata["warnings"] = warnings
    return update_frontier(replace(state, metadata=metadata))
