 #!/usr/bin/env python3# -*- coding: utf-8 -*-
"""
NEXUS CODE VALIDATOR MEGA v2.0.0
==================================
Validateur multi-langages + validateur HTML/CSS/RDF/RSS/EPUB/i18n
Reproduit les API W3C (Nu HTML Checker, CSS Validator, RDF Validator,
RSS Validator, EPUBCheck, i18n Checker, Link Checker, Web Platform Tests)

Auteur : Aissa Mohammedi (DGK)
Licence : MPL 2.0 (compatible W3C/Mozilla)
Port : 9996
Protocole : Nametron 3 Lara / ZTMESH v1.5.15

⚠️ Validateur d'audit — aucune modification du code analysé.

Usage :
python3 nexus_code_validator_mega.py
python3 nexus_code_validator_mega.py --test
python3 nexus_code_validator_mega.py --file mon_fichier.html
"""

import os
import sys
import re
import json
import time
import ssl
import socket
import threading
import urllib.request
import urllib.error
import urllib.parse
import hashlib
import html
import unicodedata
import base64
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict, OrderedDict
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════
# COUCHE 0 — CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class Config:
VERSION = "1.0.0"
BUILD = "2026.10.15"
AUTEUR = "Aissa Mohammedi (DGK)"
LICENCE = "MPL 2.0"
PROTOCOLE = "Nametron 3 Lara / ZTMESH v1.5.15"
PORT = int(os.environ.get("PORT", 9996))
HOST = "0.0.0.0"

HOME = Path(os.path.expanduser("~"))
BASE = HOME / "Documents" / "nexus_code_validator"
DATA = BASE / "data"
LOGS = BASE / "logs"
REPORTS = BASE / "reports"

LOG_FILE = LOGS / "validator.log"
MAX_BODY = 5_000_000

@classmethod
def init(cls):
for d in (cls.BASE, cls.DATA, cls.LOGS, cls.REPORTS):
d.mkdir(parents=True, exist_ok=True)


Config.init()


# ═══════════════════════════════════════════════════════════════════════════
# COUCHE 1 — LOGGING
# ═══════════════════════════════════════════════════════════════════════════

def log(msg: str, level: str = "INFO"):
ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
line = f"[{ts}] [{level}] {msg}"
print(line, flush=True)
try:
with open(Config.LOG_FILE, "a", encoding="utf-8") as f:
f.write(line + "\n")
except OSError:
pass


# ═══════════════════════════════════════════════════════════════════════════
# COUCHE 2 — STRUCTURES DE DONNÉES
# ═══════════════════════════════════════════════════════════════════════════

class Severity(str, Enum):
ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass
class ValidationMessage:
type: str
severity: str
message: str
line: int = 0
column: int = 0
code: str = ""
context: str = ""
help_url: str = ""

def to_dict(self) -> Dict:
return asdict(self)


@dataclass
class ValidationReport:
validator: str
target: str
messages: List[ValidationMessage] = field(default_factory=list)
metadata: Dict[str, Any] = field(default_factory=dict)
start_time: float = 0.0
end_time: float = 0.0

def duration_ms(self) -> float:
return (self.end_time - self.start_time) * 1000 if self.end_time else 0.0

def counts(self) -> Dict[str, int]:
c = Counter(m.severity for m in self.messages)
return {
"errors": c.get(Severity.ERROR.value, 0),
"warnings": c.get(Severity.WARNING.value, 0),
"info": c.get(Severity.INFO.value, 0),
"total": len(self.messages),
}

def to_dict(self) -> Dict:
return {
"validator": self.validator,
"target": self.target,
"messages": [m.to_dict() for m in self.messages],
"metadata": self.metadata,
"duration_ms": round(self.duration_ms(), 2),
"counts": self.counts(),
"success": self.counts()["errors"] == 0,
}


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATEUR 1 — NU HTML CHECKER (W3C)
# ═══════════════════════════════════════════════════════════════════════════

class NuHtmlChecker:
"""Reproduit le W3C Nu HTML Checker."""

# Tags HTML5 valides
HTML5_TAGS = {
"html", "head", "body", "title", "meta", "link", "script", "style",
"base", "noscript",
"div", "span", "p", "a", "img", "br", "hr", "strong", "em", "b", "i",
"u", "s", "small", "sub", "sup", "mark", "q", "cite", "code", "pre",
"kbd", "samp", "var", "abbr", "dfn", "time", "data", "bdi", "bdo",
"ruby", "rt", "rp", "wbr",
"header", "footer", "nav", "main", "article", "section", "aside",
"figure", "figcaption", "address", "details", "summary", "dialog",
"h1", "h2", "h3", "h4", "h5", "h6", "hgroup",
"ul", "ol", "li", "dl", "dt", "dd", "menu",
"table", "caption", "colgroup", "col", "thead", "tbody", "tfoot",
"tr", "th", "td",
"form", "label", "input", "button", "select", "datalist", "optgroup",
"option", "textarea", "output", "progress", "meter", "fieldset",
"legend",
"video", "audio", "source", "track", "canvas", "map", "area", "svg",
"math", "iframe", "embed", "object", "param", "picture",
"template", "slot", "portal",
}

# Attributs valides par tag (simplifié)
GLOBAL_ATTRS = {
"id", "class", "style", "title", "lang", "dir", "hidden", "tabindex",
"accesskey", "contenteditable", "draggable", "spellcheck", "translate",
"data-", "aria-", "role",
}

VOID_TAGS = {
"area", "base", "br", "col", "embed", "hr", "img", "input",
"link", "meta", "param", "source", "track", "wbr",
}

@classmethod
def validate(cls, html_content: str, target: str = "inline") -> ValidationReport:
start = time.time()
report = ValidationReport(validator="NuHtmlChecker", target=target)
report.start_time = start

try:
lines = html_content.split("\n")

# 1. Vérifier DOCTYPE
if not re.search(r"<!DOCTYPE\s+html>", html_content, re.IGNORECASE):
report.messages.append(ValidationMessage(
type="document",
severity=Severity.ERROR.value,
message="DOCTYPE HTML5 manquant",
code="W3C-DOCTYPE",
))

# 2. Vérifier balise lang sur html
html_tag = re.search(r"<html([^>]*)>", html_content, re.IGNORECASE)
if html_tag:
attrs = html_tag.group(1)
if 'lang=' not in attrs:
report.messages.append(ValidationMessage(
type="i18n",
severity=Severity.WARNING.value,
message="Attribut 'lang' manquant sur <html>",
code="W3C-LANG",
))

# 3. Balises valides + équilibre
stack = []
for i, line in enumerate(lines, 1):
# Tags ouverts
for m in re.finditer(r"<(\w+)([^>/]*)(/?)>", line):
tag = m.group(1).lower()
self_close = m.group(3) == "/"

if tag not in cls.HTML5_TAGS and not tag.startswith("!"):
report.messages.append(ValidationMessage(
type="element",
severity=Severity.ERROR.value,
message=f"Élément inconnu : <{tag}>",
line=i,
code="W3C-UNKNOWN-ELEMENT",
))

if not self_close and tag not in cls.VOID_TAGS:
stack.append((tag, i))

# Tags fermés
for m in re.finditer(r"</(\w+)>", line):
tag = m.group(1).lower()
if stack and stack[-1][0] == tag:
stack.pop()
else:
report.messages.append(ValidationMessage(
type="structure",
severity=Severity.ERROR.value,
message=f"Balise fermante orpheline : </{tag}>",
line=i,
code="W3C-ORPHAN-CLOSE",
))

# 4. Balises non fermées
for tag, line in stack:
report.messages.append(ValidationMessage(
type="structure",
severity=Severity.ERROR.value,
message=f"Balise <{tag}> non fermée",
line=line,
code="W3C-UNCLOSED",
))

# 5. Attributs dupliqués
for i, line in enumerate(lines, 1):
for m in re.finditer(r"<(\w+)([^>]*)>", line):
attrs_str = m.group(2)
attrs = re.findall(r"(\w[\w-]*)=", attrs_str)
dups = [a for a, c in Counter(attrs).items() if c > 1]
for d in dups:
report.messages.append(ValidationMessage(
type="attribute",
severity=Severity.ERROR.value,
message=f"Attribut dupliqué : '{d}'",
line=i,
code="W3C-DUP-ATTR",
))

# 6. Images sans alt
for i, line in enumerate(lines, 1):
for m in re.finditer(r"<img([^>]*)>", line, re.IGNORECASE):
if 'alt=' not in m.group(1):
report.messages.append(ValidationMessage(
type="accessibility",
severity=Severity.WARNING.value,
message="<img> sans attribut 'alt'",
line=i,
code="W3C-IMG-ALT",
))

# 7. Encodage
if not re.search(r'<meta\s+charset=', html_content, re.IGNORECASE):
report.messages.append(ValidationMessage(
type="i18n",
severity=Severity.WARNING.value,
message="<meta charset> manquant",
code="W3C-CHARSET",
))

# 8. Viewport
if not re.search(r'<meta\s+name="viewport"', html_content, re.IGNORECASE):
report.messages.append(ValidationMessage(
type="mobile",
severity=Severity.INFO.value,
message="<meta name='viewport'> manquant",
code="W3C-VIEWPORT",
))

except Exception as e:
report.messages.append(ValidationMessage(
type="internal",
severity=Severity.ERROR.value,
message=f"Erreur interne : {e}",
))

report.end_time = time.time()
return report


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATEUR 2 — CSS VALIDATOR (W3C)
# ═══════════════════════════════════════════════════════════════════════════

class CssValidator:
"""Reproduit le W3C CSS Validator."""

VALID_PROPERTIES = {
"color", "background", "background-color", "background-image",
"background-repeat", "background-position", "background-size",
"font", "font-family", "font-size", "font-weight", "font-style",
"margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
"padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
"border", "border-radius", "border-color", "border-width", "border-style",
"width", "height", "min-width", "max-width", "min-height", "max-height",
"display", "position", "top", "right", "bottom", "left",
"flex", "flex-direction", "justify-content", "align-items", "gap",
"grid", "grid-template-columns", "grid-template-rows",
"text-align", "text-decoration", "text-transform", "line-height",
"letter-spacing", "word-spacing", "white-space",
"overflow", "opacity", "z-index", "cursor", "transition",
"transform", "animation", "box-shadow", "box-sizing",
}

@classmethod
def validate(cls, css_content: str, target: str = "inline") -> ValidationReport:
start = time.time()
report = ValidationReport(validator="CssValidator", target=target)
report.start_time = start

try:
# 1. Équilibre des accolades
open_count = css_content.count("{")
close_count = css_content.count("}")
if open_count != close_count:
report.messages.append(ValidationMessage(
type="structure",
severity=Severity.ERROR.value,
message=f"Accolades déséquilibrées : {open_count} ouvertes vs {close_count} fermées",
code="CSS-UNBALANCED",
))

# 2. Propriétés invalides
props = re.findall(r"([\w-]+)\s*:", css_content)
for i, prop in enumerate(props, 1):
if prop not in cls.VALID_PROPERTIES and not prop.startswith("--"):
report.messages.append(ValidationMessage(
type="property",
severity=Severity.WARNING.value,
message=f"Propriété CSS inconnue : '{prop}'",
line=i,
code="CSS-UNKNOWN-PROP",
))

# 3. Points-virgules manquants
lines = css_content.split("\n")
for i, line in enumerate(lines, 1):
stripped = line.strip()
if ":" in stripped and not stripped.endswith((";", "{", "}", ",")):
if not stripped.startswith("//") and not stripped.startswith("/*"):
report.messages.append(ValidationMessage(
type="syntax",
severity=Severity.INFO.value,
message="Point-virgule potentiellement manquant",
line=i,
code="CSS-SEMICOLON",
))

# 4. URLs sans guillemets
for i, m in enumerate(re.finditer(r"url\(([^)]+)\)", css_content), 1):
inner = m.group(1).strip()
if not (inner.startswith('"') or inner.startswith("'")):
report.messages.append(ValidationMessage(
type="syntax",
severity=Severity.INFO.value,
message="URL sans guillemets dans url()",
line=i,
code="CSS-URL-QUOTES",
))

# 5. Pas de z-index négatif ?
if re.search(r"z-index\s*:\s*-\d+", css_content):
report.messages.append(ValidationMessage(
type="quality",
severity=Severity.WARNING.value,
message="z-index négatif détecté",
code="CSS-NEG-Z-INDEX",
))

except Exception as e:
report.messages.append(ValidationMessage(
type="internal",
severity=Severity.ERROR.value,
message=f"Erreur interne : {e}",
))

report.end_time = time.time()
return report


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATEUR 3 — RSS / ATOM VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

class RssValidator:
"""Reproduit le RSS/Atom Validator."""

REQUIRED_RSS_TAGS = ["channel", "title", "link", "description"]
REQUIRED_ATOM_TAGS = ["feed", "title", "id", "updated"]

@classmethod
def validate(cls, content: str, target: str = "inline") -> ValidationReport:
start = time.time()
report = ValidationReport(validator="RssValidator", target=target)
report.start_time = start

try:
content_low = content.lower()
is_rss = "<rss" in content_low
is_atom = "<feed" in content_low

if not is_rss and not is_atom:
report.messages.append(ValidationMessage(
type="format",
severity=Severity.ERROR.value,
message="Ni RSS ni Atom détecté",
code="FEED-FORMAT",
))
report.end_time = time.time()
return report

# Version
if is_rss:
m = re.search(r'<rss[^>]+version=["\']([^"\']+)', content_low)
version = m.group(1) if m else "inconnue"
report.metadata["format"] = "RSS"
report.metadata["version"] = version
if version not in ("2.0", "0.92", "0.91"):
report.messages.append(ValidationMessage(
type="version",
severity=Severity.WARNING.value,
message=f"Version RSS : {version} (recommandé : 2.0)",
code="RSS-VERSION",
))

# Tags requis
for tag in cls.REQUIRED_RSS_TAGS:
if f"<{tag}" not in content_low:
report.messages.append(ValidationMessage(
type="required",
severity=Severity.ERROR.value,
message=f"Tag requis manquant : <{tag}>",
code="RSS-REQUIRED",
))
elif is_atom:
report.metadata["format"] = "Atom"
for tag in cls.REQUIRED_ATOM_TAGS:
if f"<{tag}" not in content_low:
report.messages.append(ValidationMessage(
type="required",
severity=Severity.ERROR.value,
message=f"Tag requis manquant : <{tag}>",
code="ATOM-REQUIRED",
))

# Éléments <item> ou <entry>
items = len(re.findall(r"<item[ >]", content_low)) if is_rss else len(re.findall(r"<entry[ >]", content_low))
report.metadata["items"] = items
if items == 0:
report.messages.append(ValidationMessage(
type="content",
severity=Severity.WARNING.value,
message="Aucun item/entry trouvé",
code="FEED-EMPTY",
))

except Exception as e:
report.messages.append(ValidationMessage(
type="internal",
severity=Severity.ERROR.value,
message=f"Erreur interne : {e}",
))

report.end_time = time.time()
return report


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATEUR 4 — RDF VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

class RdfValidator:
"""Reproduit le RDF Validator (basique)."""

@classmethod
def validate(cls, content: str, target: str = "inline") -> ValidationReport:
start = time.time()
report = ValidationReport(validator="RdfValidator", target=target)
report.start_time = start

try:
content_low = content.lower()
# Détection format
if content_low.strip().startswith("{") or '"@context"' in content_low:
fmt = "JSON-LD"
elif content_low.strip().startswith("<"):
fmt = "RDF/XML"
elif "@prefix" in content_low or "@base" in content_low:
fmt = "Turtle"
else:
fmt = "inconnu"

report.metadata["format"] = fmt

# Vérifier namespaces RDF
if fmt == "RDF/XML":
if "rdf:about" not in content_low and "rdf:resource" not in content_low:
report.messages.append(ValidationMessage(
type="semantic",
severity=Severity.WARNING.value,
message="Aucun attribut rdf:about ou rdf:resource",
code="RDF-NO-SUBJECT",
))

if fmt == "Turtle":
if "@prefix" not in content_low:
report.messages.append(ValidationMessage(
type="syntax",
severity=Severity.INFO.value,
message="Aucun @prefix trouvé",
code="TURTLE-NO-PREFIX",
))

if fmt == "JSON-LD":
if "@context" not in content_low:
report.messages.append(ValidationMessage(
type="semantic",
severity=Severity.ERROR.value,
message="@context manquant en JSON-LD",
code="JSONLD-NO-CONTEXT",
))
try:
json.loads(content)
except json.JSONDecodeError as e:
report.messages.append(ValidationMessage(
type="syntax",
severity=Severity.ERROR.value,
message=f"JSON-LD invalide : {e}",
code="JSONLD-SYNTAX",
))

except Exception as e:
report.messages.append(ValidationMessage(
type="internal",
severity=Severity.ERROR.value,
message=f"Erreur interne : {e}",
))

report.end_time = time.time()
return report


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATEUR 5 — INTERNATIONALIZATION CHECKER (i18n)
# ═══════════════════════════════════════════════════════════════════════════

class I18nChecker:
"""Reproduit le W3C Internationalization Checker."""

@classmethod
def validate(cls, content: str, target: str = "inline") -> ValidationReport:
start = time.time()
report = ValidationReport(validator="I18nChecker", target=target)
report.start_time = start

try:
# 1. Content-Type HTTP charset
if re.search(r'<meta\s+http-equiv=["\']content-type["\']', content, re.IGNORECASE):
report.messages.append(ValidationMessage(
type="i18n",
severity=Severity.WARNING.value,
message="Utilise <meta http-equiv='Content-Type'> au lieu de <meta charset>",
code="I18N-HTTP-EQUIV",
))

# 2. BOM
if content.startswith("\ufeff"):
report.messages.append(ValidationMessage(
type="i18n",
severity=Severity.INFO.value,
message="Byte Order Mark (BOM) détecté",
code="I18N-BOM",
))

# 3. Meta charset
m = re.search(r'<meta\s+charset=["\']?([\w-]+)', content, re.IGNORECASE)
if m:
charset = m.group(1).lower()
if charset != "utf-8":
report.messages.append(ValidationMessage(
type="i18n",
severity=Severity.WARNING.value,
message=f"Charset : {charset} (recommandé : utf-8)",
code="I18N-CHARSET",
))
report.metadata["charset"] = charset
else:
report.messages.append(ValidationMessage(
type="i18n",
severity=Severity.WARNING.value,
message="<meta charset> manquant",
code="I18N-NO-CHARSET",
))

# 4. Langue HTML
m = re.search(r'<html[^>]+lang=["\']([^"\']+)', content, re.IGNORECASE)
if m:
lang = m.group(1)
report.metadata["html_lang"] = lang
if "-" in lang and not re.match(r"^[a-z]{2}-[A-Z]{2}$", lang):
report.messages.append(ValidationMessage(
type="i18n",
severity=Severity.INFO.value,
message=f"Format de langue inhabituel : {lang}",
code="I18N-LANG-FORMAT",
))
else:
report.messages.append(ValidationMessage(
type="i18n",
severity=Severity.WARNING.value,
message="Attribut 'lang' manquant sur <html>",
code="I18N-NO-LANG",
))

# 5. Direction du texte
m = re.search(r'<html[^>]+dir=["\']([^"\']+)', content, re.IGNORECASE)
if m:
report.metadata["dir"] = m.group(1)
else:
report.metadata["dir"] = "LTR (par défaut)"

# 6. Content-Language
m = re.search(r'<meta\s+http-equiv=["\']Content-Language["\'][^>]+content=["\']([^"\']+)', content, re.IGNORECASE)
if m:
report.metadata["http_content_language"] = m.group(1)

# 7. Codes de contrôle Unicode
control_chars = []
for i, ch in enumerate(content):
if unicodedata.category(ch) == "Cc" and ch not in "\n\r\t":
control_chars.append((i, hex(ord(ch))))
if control_chars:
report.messages.append(ValidationMessage(
type="i18n",
severity=Severity.ERROR.value,
message=f"{len(control_chars)} caractères de contrôle Unicode trouvés",
code="I18N-CONTROL-CHARS",
))

# 8. Noms de classe/ID non-ASCII
for m in re.finditer(r'(class|id)=["\']([^"\']+)["\']', content):
val = m.group(2)
if any(ord(ch) > 127 for ch in val):
report.messages.append(ValidationMessage(
type="i18n",
severity=Severity.INFO.value,
message=f"Identifiant non-ASCII : {val[:50]}",
code="I18N-NON-ASCII-ID",
))

# 9. Noms non-NFC
for i, ch in enumerate(content):
if ord(ch) > 127:
nfc = unicodedata.normalize("NFC", ch)
if nfc != ch:
report.messages.append(ValidationMessage(
type="i18n",
severity=Severity.INFO.value,
message=f"Caractère non-NFC détecté à la position {i}",
code="I18N-NON-NFC",
))
break

# 10. Accept-Language (si présent)
m = re.search(r'<meta\s+http-equiv=["\']Accept-Language["\'][^>]+content=["\']([^"\']+)', content, re.IGNORECASE)
if m:
report.metadata["accept_language"] = m.group(1)

except Exception as e:
report.messages.append(ValidationMessage(
type="internal",
severity=Severity.ERROR.value,
message=f"Erreur interne : {e}",
))

report.end_time = time.time()
return report


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATEUR 6 — LINK CHECKER
# ═══════════════════════════════════════════════════════════════════════════

class LinkChecker:
"""Reproduit le W3C Link Checker."""

@classmethod
def extract_links(cls, content: str, base_url: str = "") -> List[Dict]:
"""Extrait tous les liens d'un HTML."""
links = []
for m in re.finditer(r'href=["\']([^"\']+)["\']', content, re.IGNORECASE):
raw = m.group(1)
if raw.startswith(("#", "mailto:", "tel:", "javascript:")):
continue
url = urllib.parse.urljoin(base_url, raw) if base_url else raw
links.append({"raw": raw, "url": url, "type": "href"})
for m in re.finditer(r'src=["\']([^"\']+)["\']', content, re.IGNORECASE):
raw = m.group(1)
url = urllib.parse.urljoin(base_url, raw) if base_url else raw
links.append({"raw": raw, "url": url, "type": "src"})
return links

@classmethod
def validate_link(cls, url: str, timeout: float = 8.0) -> Dict:
"""Vérifie qu'un lien répond correctement."""
try:
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(url, method="HEAD",
headers={"User-Agent": "NexusLinkChecker/1.0"})
with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
return {"url": url, "ok": True, "status": r.status}
except urllib.error.HTTPError as e:
return {"url": url, "ok": False, "status": e.code, "error": f"HTTP {e.code}"}
except Exception as e:
return {"url": url, "ok": False, "status": None, "error": str(e)[:100]}

@classmethod
def validate(cls, content: str, target: str = "inline",
max_workers: int = 20) -> ValidationReport:
start = time.time()
report = ValidationReport(validator="LinkChecker", target=target)
report.start_time = start

try:
links = cls.extract_links(content, target if target.startswith("http") else "")
report.metadata["links_found"] = len(links)

# Vérifier en parallèle
with ThreadPoolExecutor(max_workers=max_workers) as ex:
futures = {ex.submit(cls.validate_link, l["url"]): l for l in links[:50]}
for fut in as_completed(futures):
link = futures[fut]
r = fut.result()
if not r["ok"]:
report.messages.append(ValidationMessage(
type="link",
severity=Severity.WARNING.value,
message=f"Lien cassé : {r['url'][:100]}",
context=link.get("raw", "")[:100],
code="LINK-BROKEN",
))

except Exception as e:
report.messages.append(ValidationMessage(
type="internal",
severity=Severity.ERROR.value,
message=f"Erreur interne : {e}",
))

report.end_time = time.time()
return report


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATEUR 7 — EPUBCheck (basique)
# ═══════════════════════════════════════════════════════════════════════════

class EpubChecker:
"""Reproduit EPUBCheck (basique)."""

@classmethod
def validate(cls, content: str, target: str = "inline") -> ValidationReport:
start = time.time()
report = ValidationReport(validator="EpubChecker", target=target)
report.start_time = start

try:
# Vérifier container.xml
if "container.xml" not in content and "META-INF" not in content:
report.messages.append(ValidationMessage(
type="structure",
severity=Severity.ERROR.value,
message="META-INF/container.xml non trouvé",
code="EPUB-NO-CONTAINER",
))

# Vérifier OPF
if ".opf" not in content and "package" not in content.lower():
report.messages.append(ValidationMessage(
type="structure",
severity=Severity.ERROR.value,
message="Fichier OPF (package) non trouvé",
code="EPUB-NO-OPF",
))

# Vérifier mimetype
if "application/epub+zip" not in content:
report.messages.append(ValidationMessage(
type="structure",
severity=Severity.WARNING.value,
message="Mimetype 'application/epub+zip' non détecté",
code="EPUB-MIMETYPE",
))

except Exception as e:
report.messages.append(ValidationMessage(
type="internal",
severity=Severity.ERROR.value,
message=f"Erreur interne : {e}",
))

report.end_time = time.time()
return report


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATEUR 8 — WEB PLATFORM TESTS
# ═══════════════════════════════════════════════════════════════════════════

class WebPlatformTests:
"""Reproduit les Web Platform Tests (basique)."""

@classmethod
def validate(cls, content: str, target: str = "inline") -> ValidationReport:
start = time.time()
report = ValidationReport(validator="WebPlatformTests", target=target)
report.start_time = start

try:
# Test : HTTP Content-Type
if '<meta' in content and 'http-equiv' in content:
report.messages.append(ValidationMessage(
type="http",
severity=Severity.INFO.value,
message="Utilise http-equiv au lieu de Content-Type HTTP",
code="WPT-HTTP-CONTENT-TYPE",
))

# Test : BOM
if content.startswith("\ufeff"):
report.messages.append(ValidationMessage(
type="encoding",
severity=Severity.INFO.value,
message="BOM présent (à éviter en HTML5)",
code="WPT-BOM",
))

# Test : meta charset
m = re.search(r'<meta\s+charset=["\']?([\w-]+)', content, re.IGNORECASE)
if m:
report.metadata["charset"] = m.group(1).lower()

# Test : langue
m = re.search(r'<html[^>]+lang=["\']([^"\']+)', content, re.IGNORECASE)
if m:
report.metadata["lang"] = m.group(1)

# Test : direction
m = re.search(r'<html[^>]+dir=["\']([^"\']+)', content, re.IGNORECASE)
if m:
report.metadata["dir"] = m.group(1)
else:
report.metadata["dir"] = "LTR (par défaut)"

except Exception as e:
report.messages.append(ValidationMessage(
type="internal",
severity=Severity.ERROR.value,
message=f"Erreur interne : {e}",
))

report.end_time = time.time()
return report


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATEUR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

class ValidatorOrchestrator:
"""Coordonne les 8 validateurs."""

VALIDATORS = {
"html": NuHtmlChecker,
"css": CssValidator,
"rss": RssValidator,
"rdf": RdfValidator,
"i18n": I18nChecker,
"link": LinkChecker,
"epub": EpubChecker,
"wpt": WebPlatformTests,
}

@classmethod
def validate_all(cls, content: str, target: str = "inline",
validators: Optional[List[str]] = None) -> Dict:
"""Lance tous les validateurs en parallèle."""
if validators is None:
validators = list(cls.VALIDATORS.keys())

results = {}
with ThreadPoolExecutor(max_workers=len(validators)) as ex:
futures = {
ex.submit(cls.VALIDATORS[v].validate, content, target): v
for v in validators if v in cls.VALIDATORS
}
for fut in as_completed(futures):
name = futures[fut]
try:
results[name] = fut.result().to_dict()
except Exception as e:
results[name] = {"error": str(e)[:200]}

# Résumé global
total_errors = sum(r.get("counts", {}).get("errors", 0) for r in results.values())
total_warnings = sum(r.get("counts", {}).get("warnings", 0) for r in results.values())
total_info = sum(r.get("counts", {}).get("info", 0) for r in results.values())

return {
"target": target,
"validators_run": list(results.keys()),
"results": results,
"summary": {
"errors": total_errors,
"warnings": total_warnings,
"info": total_info,
"success": total_errors == 0,
},
"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
}


# ═══════════════════════════════════════════════════════════════════════════
# HTML UI
# ═══════════════════════════════════════════════════════════════════════════

HTML_UI = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nexus Code Validator Mega</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:#0a0e1a;color:#c8e0f8;padding:24px;min-height:100vh;background-image:radial-gradient(ellipse at top,rgba(80,150,255,0.08),transparent 60%)}
.container{max-width:1300px;margin:0 auto}
h1{font-size:clamp(22px,4vw,36px);font-weight:800;letter-spacing:-1.5px;background:linear-gradient(135deg,#5096ff,#b366ff,#00ff88);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}
.subtitle{color:#607090;font-size:13px;font-family:ui-monospace,monospace;margin-bottom:20px}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}
.badge{padding:5px 12px;border-radius:999px;font-size:10px;font-family:ui-monospace,monospace;font-weight:700}
.badge.html{background:rgba(227,79,38,0.15);border:1px solid #e34f26;color:#e34f26}
.badge.css{background:rgba(21,114,182,0.15);border:1px solid #1572b6;color:#1572b6}
.badge.rss{background:rgba(255,166,0,0.15);border:1px solid #ffa600;color:#ffa600}
.badge.rdf{background:rgba(0,255,136,0.15);border:1px solid #00ff88;color:#00ff88}
.badge.i18n{background:rgba(179,102,255,0.15);border:1px solid #b366ff;color:#b366ff}
.badge.link{background:rgba(0,212,255,0.15);border:1px solid #00d4ff;color:#00d4ff}
.badge.epub{background:rgba(255,51,102,0.15);border:1px solid #ff3366;color:#ff3366}
.badge.wpt{background:rgba(255,255,255,0.1);border:1px solid #607090;color:#607090}
.panel{background:#131825;border:1px solid #253050;border-radius:14px;padding:20px;margin-bottom:16px}
.panel h2{color:#5096ff;font-size:12px;letter-spacing:2px;text-transform:uppercase;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #253050}
textarea,input[type=text]{width:100%;padding:14px;background:#000;border:1px solid #253050;border-radius:10px;color:#a0f0d0;font-family:ui-monospace,monospace;font-size:13px;outline:none;resize:vertical;line-height:1.6}
textarea{min-height:200px}
textarea:focus,input[type=text]:focus{border-color:#5096ff;box-shadow:0 0 20px rgba(80,150,255,0.2)}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.btn{background:linear-gradient(135deg,#5096ff,#b366ff);color:#fff;border:none;padding:12px 22px;border-radius:10px;font-weight:700;cursor:pointer;font-family:ui-monospace,monospace;font-size:12px;letter-spacing:1px;text-transform:uppercase;transition:all 0.3s}
.btn:hover{transform:translateY(-2px);box-shadow:0 5px 20px rgba(80,150,255,0.4)}
.btn.green{background:linear-gradient(135deg,#00ff88,#00d4ff);color:#000}
.btn.red{background:linear-gradient(135deg,#ff3366,#ff6b35);color:#fff}
.validators-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-bottom:16px}
.v-check{display:flex;align-items:center;gap:6px;padding:8px 12px;background:#0a0f1a;border:1px solid #253050;border-radius:8px;font-size:11px;font-family:ui-monospace,monospace;cursor:pointer}
.v-check input{width:auto}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px}
.stat{background:#0a0f1a;border:1px solid #253050;border-radius:10px;padding:14px;text-align:center}
.stat .l{color:#607090;font-size:10px;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px}
.stat .v{color:#5096ff;font-size:24px;font-weight:800;font-family:ui-monospace,monospace}
.stat .v.ok{color:#00ff88}
.stat .v.warn{color:#ffaa00}
.stat .v.danger{color:#ff3366}
.result{background:#000;border:1px solid #253050;border-radius:10px;padding:18px;font-family:ui-monospace,monospace;font-size:12px;color:#a0f0d0;white-space:pre-wrap;overflow:auto;line-height:1.7;margin-top:12px;max-height:700px}
.msg{padding:10px 14px;border-left:3px solid #5096ff;background:rgba(80,150,255,0.05);margin-bottom:6px;font-size:12px;font-family:ui-monospace,monospace}
.msg.error{border-left-color:#ff3366;background:rgba(255,51,102,0.08)}
.msg.warning{border-left-color:#ffaa00;background:rgba(255,170,0,0.05)}
.msg.info{border-left-color:#00d4ff;background:rgba(0,212,255,0.05)}
.msg .type{color:#5096ff;font-weight:700}
.msg .sev{font-weight:800;text-transform:uppercase}
.msg.error .sev{color:#ff3366}
.msg.warning .sev{color:#ffaa00}
.msg.info .sev{color:#00d4ff}
.footer{text-align:center;color:#303040;font-size:11px;margin-top:40px;padding-top:20px;border-top:1px solid #253050;font-family:ui-monospace,monospace}
</style>
</head>
<body>
<div class="container">
<h1>🧬 Nexus Code Validator Mega</h1>
<p class="subtitle">8 validateurs W3C · HTML · CSS · RSS · RDF · i18n · Links · EPUB · WPT · Port 9996</p>

<div class="badges">
<div class="badge html">HTML</div>
<div class="badge css">CSS</div>
<div class="badge rss">RSS/Atom</div>
<div class="badge rdf">RDF</div>
<div class="badge i18n">i18n</div>
<div class="badge link">Links</div>
<div class="badge epub">EPUB</div>
<div class="badge wpt">WPT</div>
</div>

<div class="panel">
<h2>📝 Code à valider</h2>
<textarea id="content" placeholder="Colle ton HTML/CSS/RSS/RDF ici..."><!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Test</title>
</head>
<body>
<h1>Bonjour</h1>
<img src="test.png">
<a href="https://example.com/page">Lien</a>
<a href="https://example.com/broken-404">Lien cassé</a>
</body>
</html></textarea>
</div>

<div class="panel">
<h2>⚙️ Validateurs à lancer</h2>
<div class="validators-grid">
<label class="v-check"><input type="checkbox" value="html" checked>HTML</label>
<label class="v-check"><input type="checkbox" value="css" checked>CSS</label>
<label class="v-check"><input type="checkbox" value="rss" checked>RSS/Atom</label>
<label class="v-check"><input type="checkbox" value="rdf" checked>RDF</label>
<label class="v-check"><input type="checkbox" value="i18n" checked>i18n</label>
<label class="v-check"><input type="checkbox" value="link" checked>Links</label>
<label class="v-check"><input type="checkbox" value="epub" checked>EPUB</label>
<label class="v-check"><input type="checkbox" value="wpt" checked>WPT</label>
</div>
<div class="actions">
<button class="btn" onclick="valider()">🔍 VALIDER</button>
<button class="btn green" onclick="validerTout()">⚡ TOUT VALIDER</button>
<button class="btn red" onclick="document.getElementById('content').value=''">🗑️ VIDER</button>
</div>
</div>

<div class="panel">
<h2>🌐 Analyser une URL</h2>
<input type="text" id="url" placeholder="https://example.com">
<div class="actions">
<button class="btn" onclick="validerURL()">🌐 ANALYSER</button>
</div>
</div>

<div class="panel" id="result-panel" style="display:none">
<h2>📊 Résultats</h2>
<div class="stats" id="stats"></div>
<div id="messages"></div>
<div class="result" id="raw-json"></div>
</div>

<div class="footer">Nexus Code Validator Mega v1.0.0 · MPL 2.0 · Aissa Mohammedi (DGK) · 8 validateurs W3C</div>
</div>

<script>
function esc(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

function getSelectedValidators(){
return Array.from(document.querySelectorAll('.v-check input:checked')).map(i => i.value);
}

function showLoader(msg){
document.getElementById('result-panel').style.display = 'block';
document.getElementById('stats').innerHTML = '<div class="stat"><div class="l">Statut</div><div class="v">'+esc(msg)+'</div></div>';
document.getElementById('messages').innerHTML = '';
document.getElementById('raw-json').textContent = '';
}

async function valider(){
const content = document.getElementById('content').value;
const validators = getSelectedValidators();
if(!content.trim() || validators.length === 0) return;
showLoader('Validation...');
try{
const r = await fetch('/api/validate', {
method:'POST',
headers:{'Content-Type':'application/json'},
body: JSON.stringify({content, validators})
});
const d = await r.json();
render(d);
}catch(e){ document.getElementById('raw-json').textContent = 'Erreur: ' + e.message; }
}

async function validerTout(){
document.querySelectorAll('.v-check input').forEach(i => i.checked = true);
await valider();
}

async function validerURL(){
const url = document.getElementById('url').value.trim();
if(!url) return;
const validators = getSelectedValidators();
showLoader('Analyse URL...');
try{
const r = await fetch('/api/validate-url', {
method:'POST',
headers:{'Content-Type':'application/json'},
body: JSON.stringify({url, validators})
});
const d = await r.json();
render(d);
}catch(e){ document.getElementById('raw-json').textContent = 'Erreur: ' + e.message; }
}

function render(d){
const s = d.summary || {};
const statsHtml =
'<div class="stat"><div class="l">Erreurs</div><div class="v '+(s.errors>0?'danger':'ok')+'">'+(s.errors||0)+'</div></div>' +
'<div class="stat"><div class="l">Warnings</div><div class="v '+(s.warnings>0?'warn':'ok')+'">'+(s.warnings||0)+'</div></div>' +
'<div class="stat"><div class="l">Info</div><div class="v">'+(s.info||0)+'</div></div>' +
'<div class="stat"><div class="l">Validateurs</div><div class="v">'+((d.validators_run||[]).length)+'</div></div>' +
'<div class="stat"><div class="l">Statut</div><div class="v '+(s.success?'ok':'danger')+'">'+(s.success?'OK':'ÉCHEC')+'</div></div>';
document.getElementById('stats').innerHTML = statsHtml;

let msgsHtml = '';
Object.entries(d.results || {}).forEach(([validator, result]) => {
if (result.error){
msgsHtml += '<div class="msg error"><span class="type">['+esc(validator)+']</span> <span class="sev">error</span> '+esc(result.error)+'</div>';
return;
}
if (result.messages && result.messages.length){
result.messages.forEach(m => {
msgsHtml += '<div class="msg '+esc(m.severity)+'">' +
'<span class="type">['+esc(validator)+']</span> ' +
'<span class="sev">'+esc(m.severity)+'</span> ' +
esc(m.message) +
(m.line ? ' <span style="color:#607090">(ligne '+m.line+')</span>' : '') +
'</div>';
});
}
});
if (!msgsHtml) msgsHtml = '<div class="msg info">✓ Aucun problème détecté</div>';
document.getElementById('messages').innerHTML = msgsHtml;

document.getElementById('raw-json').textContent = JSON.stringify(d, null, 2);
}
</script>
</body>
</html>
"""


# ═══════════════════════════════════════════════════════════════════════════
# HANDLER HTTP
# ═══════════════════════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):
def log_message(self, *a): pass

def _send(self, code, body, ctype="application/json"):
try:
if isinstance(body, str):
body = body.encode("utf-8")
self.send_response(code)
self.send_header("Content-Type", ctype + "; charset=utf-8")
self.send_header("Access-Control-Allow-Origin", "*")
self.send_header("Content-Length", str(len(body)))
self.end_headers()
self.wfile.write(body)
except (BrokenPipeError, ConnectionResetError):
pass

def _read_json(self) -> Dict:
try:
n = int(self.headers.get("Content-Length", "0"))
if n > Config.MAX_BODY:
return {}
return json.loads(self.rfile.read(n).decode("utf-8"))
except Exception:
return {}

def do_GET(self):
path = self.path.split("?")[0]
if path in ("/", "/index.html"):
return self._send(200, HTML_UI, "text/html")
if path == "/api/health":
return self._send(200, json.dumps({
"ok": True,
"version": Config.VERSION,
"validators": list(ValidatorOrchestrator.VALIDATORS.keys()),
"author": Config.AUTEUR,
"license": Config.LICENCE,
}))
return self._send(404, json.dumps({"error": "not found"}))

def do_POST(self):
path = self.path.split("?")[0]
data = self._read_json()

if path == "/api/validate":
content = data.get("content", "")
validators = data.get("validators", None)
if not content:
return self._send(400, json.dumps({"error": "content missing"}))
result = ValidatorOrchestrator.validate_all(content, "inline", validators)
return self._send(200, json.dumps(result, ensure_ascii=False, default=str))

if path == "/api/validate-url":
url = data.get("url", "")
validators = data.get("validators", None)
if not url:
return self._send(400, json.dumps({"error": "url missing"}))
try:
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(url, headers={"User-Agent": "NexusValidator/1.0"})
with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
content = resp.read(Config.MAX_BODY).decode("utf-8", errors="ignore")
result = ValidatorOrchestrator.validate_all(content, url, validators)
return self._send(200, json.dumps(result, ensure_ascii=False, default=str))
except Exception as e:
return self._send(500, json.dumps({"error": str(e)[:200]}))

return self._send(404, json.dumps({"error": "not found"}))


class Server(ThreadingMixIn, HTTPServer):
daemon_threads = True
allow_reuse_address = True


# ═══════════════════════════════════════════════════════════════════════════
# MAIN + CLI
# ═══════════════════════════════════════════════════════════════════════════

def cmd_test():
"""Test rapide avec HTML de démo."""
html_test = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Test</title>
</head>
<body>
<h1>Bonjour</h1>
<img src="test.png">
<a href="https://example.com/broken">Cassé</a>
</body>
</html>"""
print("=" * 70)
print(f" 🧬 TEST NEXUS CODE VALIDATOR v{Config.VERSION}")
print("=" * 70)
result = ValidatorOrchestrator.validate_all(html_test, "inline")
print(f"\n Erreurs : {result['summary']['errors']}")
print(f" Warnings : {result['summary']['warnings']}")
print(f" Info : {result['summary']['info']}")
print(f"\n Détails :")
for v, r in result["results"].items():
if "messages" in r:
for m in r["messages"]:
print(f" [{v}] [{m['severity']}] {m['message']}")


def cmd_file(filepath: str):
"""Valide un fichier."""
p = Path(filepath)
if not p.exists():
print(f"Fichier introuvable : {filepath}")
return
content = p.read_text(encoding="utf-8", errors="ignore")
result = ValidatorOrchestrator.validate_all(content, str(p))
print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def ip_locale() -> str:
try:
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
ip = s.getsockname()[0]
s.close()
return ip
except Exception:
return "localhost"


def main():
import argparse
parser = argparse.ArgumentParser(description="Nexus Code Validator Mega")
parser.add_argument("--test", action="store_true", help="Test rapide")
parser.add_argument("--file", type=str, help="Valider un fichier")
parser.add_argument("--port", type=int, default=Config.PORT)
args = parser.parse_args()

if args.test:
cmd_test()
return

if args.file:
cmd_file(args.file)
return

print("=" * 74)
print(f" 🧬 NEXUS CODE VALIDATOR MEGA v{Config.VERSION}")
print(f" {Config.LICENCE} · {Config.AUTEUR}")
print(f" {Config.PROTOCOLE}")
print("=" * 74)
print()
print(f" Port : {args.port}")
print(f" Validateurs: {len(ValidatorOrchestrator.VALIDATORS)}")
for v in ValidatorOrchestrator.VALIDATORS.keys():
print(f" · {v}")
print()
print(f" Local : http://localhost:{args.port}/")
print(f" Réseau : http://{ip_locale()}:{args.port}/")
print()
print(" Endpoints :")
print(" POST /api/validate → valide du contenu")
print(" POST /api/validate-url → valide une URL")
print(" GET /api/health → état du serveur")
print()
print(" Ctrl+C pour arrêter")
print()

try:
with Server((Config.HOST, args.port), Handler) as httpd:
httpd.serve_forever()
except KeyboardInterrupt:
print("\n Arrêté.")
except OSError as e:
print(f" ❌ Erreur port {args.port} : {e}")
sys.exit(1)


if __name__ == "__main__":
try:
main()
except Exception as e:
print(f"Fatal : {e}", file=sys.stderr)
import traceback
traceback.print_exc()
sys.exit(1)
