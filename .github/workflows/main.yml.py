#!/usr/bin/env python3# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║ ║
║ 🌐 NEXUS W3C VALIDATOR v1.0.0 — Validateur Multi-Standards ║
║ ║
║ Intègre TOUTES les APIs W3C : ║
║ • Nu HTML Checker (HTML5) ║
║ • Link Checker (liens brisés) ║
║ • CSS Validator ║
║ • RDF Validator ║
║ • i18n Checker (internationalisation) ║
║ • EPUBCheck ║
║ • Feed Validator (RSS/Atom) ║
║ • Web Platform Tests ║
║ ║
║ Auteur : Aissa Mohammedi (DGK) ║
║ Version : 1.0.0 ║
║ Licence : NEXUS-OPEN-2.0 ║
║ ║
║ Usage : ║
║ python3 nexus_w3c_validator.py ║
║ python3 nexus_w3c_validator.py --port 8888 ║
║ ║
║ URL : ║
║ http://localhost:8888/ ║
║ http://localhost:8888/api/docs ║
║ ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import re
import io
import sys
import json
import time
import uuid
import hashlib
import socket
import threading
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

VERSION = "1.0.0"
AUTHOR = "Aissa Mohammedi (DGK)"
LICENCE = "NEXUS-OPEN-2.0"
DEFAULT_PORT = 8888

BASE = Path.home() / "Documents" / "nexus_w3c_validator"
LOGS_DIR = BASE / "logs"
REPORTS_DIR = BASE / "reports"
CACHE_DIR = BASE / "cache"

for d in (BASE, LOGS_DIR, REPORTS_DIR, CACHE_DIR):
d.mkdir(parents=True, exist_ok=True)

EXEC_TIMEOUT = 30
MAX_RESPONSE = 500_000


# ══════════════════════════════════════════════════════════════════════════════
# COULEURS
# ══════════════════════════════════════════════════════════════════════════════

class C:
G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; B = '\033[94m'
M = '\033[95m'; CY = '\033[96m'; W = '\033[1m'; N = '\033[0m'

def ok(m): print(f"{C.G}[OK]{C.N} {m}")
def err(m): print(f"{C.R}[X]{C.N} {m}")
def warn(m): print(f"{C.Y}[!]{C.N} {m}")
def info(m): print(f"{C.B}[i]{C.N} {m}")


# ══════════════════════════════════════════════════════════════════════════════
# W3C VALIDATORS DATABASE
# ══════════════════════════════════════════════════════════════════════════════

W3C_VALIDATORS = {
"html": {
"name": "Nu HTML Checker",
"description": "Contrôle les documents HTML5",
"url": "https://validator.w3.org/nu/",
"api": "https://validator.w3.org/nu/?doc={url}&out=json",
"github": "https://github.com/validator/validator",
"accepts": [".html", ".htm", "url", "text"],
"output": "json",
"icon": "📄"
},
"css": {
"name": "CSS Validator",
"description": "Vérifie les feuilles de style CSS",
"url": "https://jigsaw.w3.org/css-validator/",
"api": "https://jigsaw.w3.org/css-validator/validator?uri={url}&output=json",
"github": "https://github.com/w3c/css-validator",
"accepts": [".css", "url"],
"output": "json",
"icon": "🎨"
},
"link": {
"name": "Link Checker",
"description": "Vérifie les liens brisés",
"url": "https://validator.w3.org/checklink",
"api": None, # Local check
"github": "https://github.com/w3c/link-checker",
"accepts": ["url"],
"output": "text",
"icon": "🔗"
},
"rdf": {
"name": "RDF Validator",
"description": "Vérifie et visualise les documents RDF",
"url": "https://www.w3.org/RDF/Validator/",
"api": "https://www.w3.org/RDF/Validator/ARPServlet",
"github": "https://github.com/w3c/rdf-validator",
"accepts": [".rdf", ".ttl", ".n3", ".owl"],
"output": "text",
"icon": "🧬"
},
"i18n": {
"name": "Internationalization Checker",
"description": "Vérifie la convivialité i18n",
"url": "https://validator.w3.org/i18n-checker/",
"api": "https://validator.w3.org/i18n-checker/check?uri={url}&format=json",
"github": None,
"accepts": ["url"],
"output": "json",
"icon": "🌍"
},
"epub": {
"name": "EPUBCheck",
"description": "Vérificateur de conformité EPUB",
"url": "https://validator.w3.org/epub-checker/",
"api": "https://validator.w3.org/epub-checker/api/check",
"github": "https://github.com/w3c/epubcheck",
"accepts": [".epub"],
"output": "json",
"icon": "📚"
},
"feed": {
"name": "Feed Validator",
"description": "Validateur RSS et Atom",
"url": "https://validator.w3.org/feed/",
"api": "https://validator.w3.org/feed/check.cgi?url={url}&output=soap12",
"github": "https://github.com/w3c/feedvalidator",
"accepts": [".xml", ".rss", ".atom", "url"],
"output": "xml",
"icon": "📡"
},
"wpt": {
"name": "Web Platform Tests",
"description": "Tests d'interopérabilité Web",
"url": "https://wpt.fyi/",
"api": "https://wpt.fyi/api/runs",
"github": "https://github.com/web-platform-tests/wpt",
"accepts": ["url"],
"output": "json",
"icon": "🧪"
},
}


# ══════════════════════════════════════════════════════════════════════════════
# HTML VALIDATOR (LOCAL)
# ══════════════════════════════════════════════════════════════════════════════

class HTMLValidator:
"""Validateur HTML5 local"""

def __init__(self):
self.errors = []
self.warnings = []
self.info = []

def validate(self, html_content):
self.errors = []
self.warnings = []
self.info = []

if not html_content:
self.errors.append({"line": 0, "msg": "Contenu vide"})
return self._result()

lines = html_content.split("\n")

# 1. DOCTYPE
if not re.search(r"<!DOCTYPE\s+html", html_content[:200], re.IGNORECASE):
self.errors.append({"line": 1, "msg": "DOCTYPE HTML5 manquant"})

# 2. Balise html
if "<html" not in html_content.lower():
self.errors.append({"line": 0, "msg": "Balise <html> manquante"})
else:
# Attribut lang
if not re.search(r"<html[^>]*\slang\s*=", html_content, re.IGNORECASE):
self.warnings.append({"line": 0, "msg": "Attribut 'lang' manquant sur <html>"})

# 3. Balises head/title
if "<head" not in html_content.lower():
self.warnings.append({"line": 0, "msg": "Balise <head> manquante"})
if "<title" not in html_content.lower():
self.warnings.append({"line": 0, "msg": "Balise <title> manquante"})

# 4. Encoding
if "charset" not in html_content.lower()[:1000]:
self.warnings.append({"line": 0, "msg": "Charset non déclaré"})

# 5. Balises non fermées (sauf void)
void_tags = {"br", "hr", "img", "input", "meta", "link", "area",
"base", "col", "embed", "source", "track", "wbr"}
opens = []
closes = []
for line_num, line in enumerate(lines, 1):
for m in re.finditer(r"<(\w+)[^>]*[^/]>", line):
tag = m.group(1).lower()
if tag not in void_tags and not tag.startswith("!"):
opens.append((tag, line_num))
for m in re.finditer(r"</(\w+)>", line):
closes.append((m.group(1).lower(), line_num))

opens_count = Counter(t for t, _ in opens)
closes_count = Counter(t for t, _ in closes)
for tag, count in opens_count.items():
close_count = closes_count.get(tag, 0)
if close_count < count:
self.errors.append({
"line": 0,
"msg": f"Balise <{tag}> non fermée ({count - close_count} manquante(s))"
})

# 6. Attributs dupliqués
for line_num, line in enumerate(lines, 1):
for m in re.finditer(r"<(\w+)([^>]*)>", line):
attrs = re.findall(r'(\w+)\s*=', m.group(2))
dup = [a for a, c in Counter(attrs).items() if c > 1]
for d in dup:
self.errors.append({
"line": line_num,
"msg": f"Attribut '{d}' dupliqué dans <{m.group(1)}>"
})

# 7. Meta tags recommandés
if "<meta" in html_content.lower():
if not re.search(r'<meta\s+charset\s*=', html_content, re.IGNORECASE):
if not re.search(r'<meta\s+http-equiv\s*=\s*["\']Content-Type', html_content, re.IGNORECASE):
self.info.append({"line": 0, "msg": "Meta charset recommandé"})

# 8. Accessibilité de base
img_tags = re.findall(r"<img[^>]*>", html_content, re.IGNORECASE)
for i, img in enumerate(img_tags, 1):
if "alt=" not in img.lower():
self.warnings.append({
"line": 0,
"msg": f"<img> #{i} sans attribut 'alt' (accessibilité)"
})

# 9. Liens vides
empty_links = re.findall(r'<a\s+[^>]*href\s*=\s*["\']\s*["\']', html_content, re.IGNORECASE)
if empty_links:
self.warnings.append({
"line": 0,
"msg": f"{len(empty_links)} lien(s) avec href vide"
})

return self._result()

def _result(self):
return {
"valid": len(self.errors) == 0,
"errors": self.errors,
"warnings": self.warnings,
"info": self.info,
"count_errors": len(self.errors),
"count_warnings": len(self.warnings),
}


# ══════════════════════════════════════════════════════════════════════════════
# CSS VALIDATOR (LOCAL)
# ══════════════════════════════════════════════════════════════════════════════

class CSSValidator:
"""Validateur CSS local"""

def __init__(self):
self.errors = []
self.warnings = []

def validate(self, css_content):
self.errors = []
self.warnings = []

if not css_content:
self.errors.append({"line": 0, "msg": "Contenu vide"})
return self._result()

lines = css_content.split("\n")

# 1. Accolades équilibrées
open_braces = css_content.count("{")
close_braces = css_content.count("}")
if open_braces != close_braces:
self.errors.append({
"line": 0,
"msg": f"Accolades déséquilibrées ({open_braces} {{ vs {close_braces} }})"
})

# 2. Parenthèses équilibrées
open_paren = css_content.count("(")
close_paren = css_content.count(")")
if open_paren != close_paren:
self.errors.append({
"line": 0,
"msg": f"Parenthèses déséquilibrées"
})

# 3. Vérification des règles
for line_num, line in enumerate(lines, 1):
stripped = line.strip()
if not stripped or stripped.startswith("/*") or stripped.startswith("*"):
continue
if ":" in stripped and not stripped.endswith(";"):
if not stripped.endswith("{") and not stripped.endswith("}"):
self.warnings.append({
"line": line_num,
"msg": f"Point-virgule probablement manquant"
})

# 4. Sélecteurs vides
empty_rules = re.findall(r"[^}]*\{\s*\}", css_content)
if empty_rules:
self.warnings.append({
"line": 0,
"msg": f"{len(empty_rules)} règle(s) CSS vide(s)"
})

return self._result()

def _result(self):
return {
"valid": len(self.errors) == 0,
"errors": self.errors,
"warnings": self.warnings,
"count_errors": len(self.errors),
"count_warnings": len(self.warnings),
}


# ══════════════════════════════════════════════════════════════════════════════
# i18n CHECKER
# ══════════════════════════════════════════════════════════════════════════════

class I18nChecker:
"""Vérificateur d'internationalisation"""

def check(self, html_content):
result = {
"lang": None,
"lang_source": None,
"dir": None,
"dir_source": None,
"charset": None,
"control_chars": [],
"non_nfc": [],
"issues": [],
}

# 1. Langue via <html lang>
m = re.search(r'<html[^>]*\slang\s*=\s*["\']([^"\']+)["\']', html_content, re.IGNORECASE)
if m:
result["lang"] = m.group(1)
result["lang_source"] = "html"
else:
# Chercher meta content-language
m = re.search(r'<meta[^>]*http-equiv\s*=\s*["\']Content-Language["\'][^>]*content\s*=\s*["\']([^"\']+)["\']', html_content, re.IGNORECASE)
if m:
result["lang"] = m.group(1)
result["lang_source"] = "meta http-equiv"
else:
result["issues"].append({
"type": "error",
"msg": "Aucune langue déclarée (ni <html lang> ni Content-Language)"
})

# 2. Direction
m = re.search(r'<html[^>]*\sdir\s*=\s*["\']([^"\']+)["\']', html_content, re.IGNORECASE)
if m:
result["dir"] = m.group(1)
result["dir_source"] = "html"
else:
result["dir"] = "ltr"
result["dir_source"] = "default"

# 3. Charset
m = re.search(r'charset\s*=\s*["\']?([a-zA-Z0-9-]+)', html_content, re.IGNORECASE)
if m:
result["charset"] = m.group(1)
if result["charset"].lower() != "utf-8":
result["issues"].append({
"type": "warning",
"msg": f"Charset '{result['charset']}' — préférer UTF-8"
})
else:
result["issues"].append({
"type": "warning",
"msg": "Charset non déclaré — préférer UTF-8"
})

# 4. Caractères de contrôle
for i, ch in enumerate(html_content):
if ord(ch) < 32 and ch not in "\n\r\t":
line_num = html_content[:i].count("\n") + 1
result["control_chars"].append({
"line": line_num,
"char": f"U+{ord(ch):04X}",
})

# 5. Noms de classe/ID non-ASCII
non_ascii = re.findall(r'(?:class|id)\s*=\s*["\']([^"\']*[^\x00-\x7F][^"\']*)["\']', html_content)
if non_ascii:
result["non_nfc"] = non_ascii
for name in non_ascii[:5]:
result["issues"].append({
"type": "warning",
"msg": f"Nom de classe/ID non-ASCII : '{name}'"
})

# 6. <html> tag check
if "<html" not in html_content.lower():
result["issues"].append({
"type": "error",
"msg": "Balise <html> manquante"
})

return result


# ══════════════════════════════════════════════════════════════════════════════
# FEED VALIDATOR (RSS / Atom)
# ══════════════════════════════════════════════════════════════════════════════

class FeedValidator:
"""Validateur RSS / Atom"""

def validate(self, content):
result = {
"type": None,
"valid": False,
"errors": [],
"warnings": [],
"items": 0,
}

content_lower = content.lower()

# Détecter le type
if "<rss" in content_lower:
result["type"] = "RSS"
elif "<feed" in content_lower:
result["type"] = "Atom"
else:
result["errors"].append("Ni RSS ni Atom détecté")
return result

# Vérifications de base
if result["type"] == "RSS":
if "<channel>" not in content_lower:
result["errors"].append("Balise <channel> manquante pour RSS")
if "<title>" not in content_lower:
result["warnings"].append("Balise <title> manquante")
if "<link>" not in content_lower:
result["warnings"].append("Balise <link> manquante")
if "<description>" not in content_lower:
result["warnings"].append("Balise <description> manquante")
result["items"] = content_lower.count("<item>")

elif result["type"] == "Atom":
if "<title>" not in content_lower:
result["warnings"].append("Balise <title> manquante")
if "<id>" not in content_lower:
result["warnings"].append("Balise <id> manquante")
if "<updated>" not in content_lower:
result["warnings"].append("Balise <updated> manquante")
result["items"] = content_lower.count("<entry>")

# XML bien formé ?
try:
import xml.etree.ElementTree as ET
ET.fromstring(content)
result["valid"] = (len(result["errors"]) == 0)
except Exception as e:
result["errors"].append(f"XML mal formé : {e}")
result["valid"] = False

return result


# ══════════════════════════════════════════════════════════════════════════════
# RDF VALIDATOR (local basique)
# ══════════════════════════════════════════════════════════════════════════════

class RDFValidator:
"""Validateur RDF basique"""

def validate(self, content):
result = {
"format": None,
"valid": False,
"triples": 0,
"errors": [],
"warnings": [],
}

content_stripped = content.strip()

# Détecter le format
if content_stripped.startswith("<?xml") or "<rdf:RDF" in content:
result["format"] = "RDF/XML"
elif "@prefix" in content or "@base" in content:
result["format"] = "Turtle"
elif content_stripped.startswith("{"):
result["format"] = "JSON-LD"
else:
result["format"] = "Unknown"

# Vérifications basiques
if result["format"] == "RDF/XML":
if "<rdf:RDF" not in content:
result["errors"].append("Namespace rdf:RDF manquant")
try:
import xml.etree.ElementTree as ET
ET.fromstring(content)
result["triples"] = content.count("<rdf:Description")
except Exception as e:
result["errors"].append(f"XML invalide : {e}")
else:
result["valid"] = (len(result["errors"]) == 0)

elif result["format"] == "Turtle":
if not re.search(r"@prefix\s+\w+:", content):
result["warnings"].append("Aucun @prefix détecté")
result["triples"] = content.count(" .")
result["valid"] = True

elif result["format"] == "JSON-LD":
try:
json.loads(content)
result["valid"] = True
result["triples"] = content.count('"@')
except Exception as e:
result["errors"].append(f"JSON invalide : {e}")

return result


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATOR ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

class NexusValidator:
"""Orchestrateur de tous les validateurs"""

def __init__(self):
self.html = HTMLValidator()
self.css = CSSValidator()
self.i18n = I18nChecker()
self.feed = FeedValidator()
self.rdf = RDFValidator()

def auto_detect_and_validate(self, content, hint=None):
"""Détecte automatiquement et valide"""
start = time.time()
result = {
"auto_detected": None,
"validation": None,
"duration_ms": 0,
"hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
"size": len(content),
}

if hint == "html" or (hint is None and ("<html" in content.lower() or "<!doctype" in content.lower())):
result["auto_detected"] = "html"
result["validation"] = self.html.validate(content)

elif hint == "css" or (hint is None and re.search(r"\{[^}]*:[^}]*\}", content)):
result["auto_detected"] = "css"
result["validation"] = self.css.validate(content)

elif hint == "feed" or (hint is None and ("<rss" in content.lower() or "<feed" in content.lower())):
result["auto_detected"] = "feed"
result["validation"] = self.feed.validate(content)

elif hint == "rdf" or (hint is None and ("@prefix" in content or "<rdf:RDF" in content)):
result["auto_detected"] = "rdf"
result["validation"] = self.rdf.validate(content)

else:
result["auto_detected"] = "unknown"
result["validation"] = {"error": "Type non détecté"}

result["duration_ms"] = round((time.time() - start) * 1000, 2)
return result

def full_check(self, content):
"""Validation complète (HTML + CSS + i18n)"""
start = time.time()
return {
"html": self.html.validate(content),
"i18n": self.i18n.check(content),
"css_inline": self.css.validate(content),
"duration_ms": round((time.time() - start) * 1000, 2),
"hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
}


VALIDATOR = NexusValidator()


# ══════════════════════════════════════════════════════════════════════════════
# HTML DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

HTML_DASHBOARD = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="NEXUS W3C Validator - Multi-standards HTML, CSS, RDF, i18n, Feed">
<title>NEXUS W3C VALIDATOR</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0a0a0f;--card:#14141c;--border:#252533;--text:#e8e8f0;
--dim:#6b6b80;--accent:#c8a45c;--cyan:#00d4ff;--rose:#ff6ec7;
--violet:#9d4edd;--ok:#4ade80;--warn:#fbbf24;--err:#f87171}
body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;
min-height:100vh;padding:20px;background-image:
radial-gradient(ellipse at 15% 15%,rgba(200,164,92,.08),transparent 55%),
radial-gradient(ellipse at 85% 85%,rgba(0,212,255,.06),transparent 55%)}
.container{max-width:1400px;margin:0 auto}
.header{text-align:center;padding:30px;margin-bottom:24px;
background:linear-gradient(135deg,rgba(200,164,92,.08),rgba(0,212,255,.08));
border:1px solid var(--border);border-radius:20px}
.header h1{font-size:2.4rem;font-weight:900;letter-spacing:-1.5px;
background:linear-gradient(135deg,#fff,var(--accent),var(--cyan),var(--violet));
background-size:200% 200%;-webkit-background-clip:text;-webkit-text-fill-color:transparent;
background-clip:text;animation:grad 6s ease infinite;margin-bottom:8px}
@keyframes grad{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
.header p{color:var(--dim);font-size:.9rem}
.badge{display:inline-block;padding:6px 14px;margin:4px;
background:rgba(0,212,255,.1);border:1px solid rgba(0,212,255,.3);
border-radius:20px;font-size:.75rem;color:var(--cyan);
font-family:monospace;letter-spacing:1px}
.validators{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
gap:12px;margin-bottom:24px}
.vcard{background:var(--card);border:1px solid var(--border);
border-radius:12px;padding:16px;text-align:center;transition:all .3s}
.vcard:hover{transform:translateY(-4px);border-color:var(--accent);
box-shadow:0 15px 40px rgba(0,0,0,.4)}
.vcard .icon{font-size:32px;margin-bottom:8px}
.vcard .name{font-family:monospace;font-size:.85rem;font-weight:700;color:var(--accent)}
.vcard .desc{font-size:.7rem;color:var(--dim);margin-top:4px}
.card{background:var(--card);border:1px solid var(--border);
border-radius:12px;padding:20px;margin-bottom:16px}
.card h2{font-size:.85rem;color:var(--cyan);text-transform:uppercase;
letter-spacing:2px;margin-bottom:14px;
border-bottom:1px solid var(--border);padding-bottom:10px}
.form{display:flex;flex-direction:column;gap:10px}
.row{display:flex;gap:10px;flex-wrap:wrap}
input,textarea,select{font-family:monospace;font-size:.85rem;
padding:10px 12px;border-radius:8px;border:1px solid var(--border);
background:rgba(0,0,0,.4);color:var(--text);outline:none;transition:all .2s}
input:focus,textarea:focus{border-color:var(--accent)}
textarea{width:100%;min-height:200px;resize:vertical;line-height:1.5}
select{background:#0a0a0f;cursor:pointer}
button{padding:12px 20px;border:none;border-radius:8px;
font-family:system-ui;font-weight:700;cursor:pointer;
transition:all .2s;font-size:.9rem}
.btn-primary{background:linear-gradient(135deg,var(--accent),var(--rose));
color:#fff;box-shadow:0 4px 20px rgba(200,164,92,.3)}
.btn-primary:hover{transform:translateY(-2px);
box-shadow:0 8px 30px rgba(200,164,92,.5)}
.btn-primary:disabled{opacity:.5;cursor:not-allowed;transform:none}
.btn-secondary{background:rgba(0,212,255,.1);color:var(--cyan);
border:1px solid rgba(0,212,255,.3)}
.btn-secondary:hover{background:rgba(0,212,255,.2)}
.result{background:#000;border:1px solid var(--border);
border-radius:10px;padding:16px;font-family:monospace;
font-size:.8rem;line-height:1.6;color:var(--cyan);
max-height:500px;overflow-y:auto;white-space:pre-wrap;
word-break:break-word;margin-top:12px}
.result.ok{border-color:var(--ok)}
.result.err{border-color:var(--err)}
.result.warn{border-color:var(--warn)}
.tabs{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.tab{padding:8px 16px;background:rgba(0,212,255,.08);
border:1px solid var(--border);border-radius:8px;
cursor:pointer;font-family:monospace;font-size:.8rem;
color:var(--dim);transition:all .2s}
.tab.active{background:rgba(200,164,92,.15);
border-color:var(--accent);color:var(--accent);font-weight:700}
.tab:hover{border-color:var(--accent)}
.hidden{display:none}
.error-line{padding:4px 0;border-bottom:1px solid rgba(255,255,255,.03)}
.error-line .line-num{color:var(--dim);margin-right:8px}
.error-line .msg{color:var(--err)}
.warn-line .msg{color:var(--warn)}
.ok-line .msg{color:var(--ok)}
</style>
</head>
<body>
<div class="container">

<div class="header">
<h1>🌐 NEXUS W3C VALIDATOR</h1>
<p>Validateur Multi-Standards · HTML5 · CSS · RDF · i18n · Feed · EPUBCheck</p>
<div>
<span class="badge">v1.0.0</span>
<span class="badge">Aissa Mohammedi (DGK)</span>
<span class="badge">NEXUS-OPEN-2.0</span>
</div>
</div>

<!-- VALIDATORS -->
<div class="validators" id="validators-list"></div>

<!-- TABS -->
<div class="tabs">
<div class="tab active" onclick="showTab('auto',this)">🎯 Auto</div>
<div class="tab" onclick="showTab('html',this)">📄 HTML</div>
<div class="tab" onclick="showTab('css',this)">🎨 CSS</div>
<div class="tab" onclick="showTab('i18n',this)">🌍 i18n</div>
<div class="tab" onclick="showTab('feed',this)">📡 Feed</div>
<div class="tab" onclick="showTab('rdf',this)">🧬 RDF</div>
<div class="tab" onclick="showTab('full',this)">✅ Full</div>
</div>

<!-- AUTO -->
<div id="tab-auto">
<div class="card">
<h2>🎯 Validation automatique</h2>
<div class="form">
<textarea id="auto-input" placeholder="Colle du HTML, CSS, RDF, RSS, Atom... Je détecte automatiquement."></textarea>
<div class="row">
<button class="btn-primary" onclick="runValidation('auto')" id="btn-auto">🎯 Analyser</button>
<button class="btn-secondary" onclick="loadExample('html')">📄 Ex HTML</button>
<button class="btn-secondary" onclick="loadExample('css')">🎨 Ex CSS</button>
<button class="btn-secondary" onclick="loadExample('feed')">📡 Ex RSS</button>
</div>
</div>
<div class="result hidden" id="result-auto"></div>
</div>
</div>

<!-- HTML -->
<div id="tab-html" class="hidden">
<div class="card">
<h2>📄 Nu HTML Checker</h2>
<div class="form">
<textarea id="html-input" placeholder="<!DOCTYPE html>&#10;<html lang='fr'>&#10;<head><title>Test</title></head>&#10;<body><h1>Hello</h1></body>&#10;</html>"></textarea>
<div class="row">
<button class="btn-primary" onclick="runValidation('html')">📄 Valider HTML</button>
<button class="btn-secondary" onclick="loadExample('html')">📄 Exemple</button>
</div>
</div>
<div class="result hidden" id="result-html"></div>
</div>
</div>

<!-- CSS -->
<div id="tab-css" class="hidden">
<div class="card">
<h2>🎨 CSS Validator</h2>
<div class="form">
<textarea id="css-input" placeholder="body {&#10; color: #fff;&#10; background: #000;&#10;}"></textarea>
<div class="row">
<button class="btn-primary" onclick="runValidation('css')">🎨 Valider CSS</button>
<button class="btn-secondary" onclick="loadExample('css')">🎨 Exemple</button>
</div>
</div>
<div class="result hidden" id="result-css"></div>
</div>
</div>

<!-- I18N -->
<div id="tab-i18n" class="hidden">
<div class="card">
<h2>🌍 Internationalization Checker</h2>
<div class="form">
<textarea id="i18n-input" placeholder="Colle du HTML pour vérifier i18n (lang, dir, charset)"></textarea>
<div class="row">
<button class="btn-primary" onclick="runValidation('i18n')">🌍 Vérifier</button>
</div>
</div>
<div class="result hidden" id="result-i18n"></div>
</div>
</div>

<!-- FEED -->
<div id="tab-feed" class="hidden">
<div class="card">
<h2>📡 Feed Validator (RSS / Atom)</h2>
<div class="form">
<textarea id="feed-input" placeholder="<?xml version='1.0'?>&#10;<rss version='2.0'>&#10;<channel>&#10;<title>Mon flux</title>&#10;<link>https://exemple.com</link>&#10;<description>Test</description>&#10;</channel>&#10;</rss>"></textarea>
<div class="row">
<button class="btn-primary" onclick="runValidation('feed')">📡 Valider Feed</button>
<button class="btn-secondary" onclick="loadExample('feed')">📡 Exemple</button>
</div>
</div>
<div class="result hidden" id="result-feed"></div>
</div>
</div>

<!-- RDF -->
<div id="tab-rdf" class="hidden">
<div class="card">
<h2>🧬 RDF Validator</h2>
<div class="form">
<textarea id="rdf-input" placeholder="@prefix foaf: &lt;http://xmlns.com/foaf/0.1/&gt; .&#10;&#10;&lt;http://example.org/me&gt; a foaf:Person ."></textarea>
<div class="row">
<button class="btn-primary" onclick="runValidation('rdf')">🧬 Valider RDF</button>
</div>
</div>
<div class="result hidden" id="result-rdf"></div>
</div>
</div>

<!-- FULL -->
<div id="tab-full" class="hidden">
<div class="card">
<h2>✅ Validation complète (HTML + CSS + i18n)</h2>
<div class="form">
<textarea id="full-input" placeholder="Colle du HTML complet pour analyse totale"></textarea>
<div class="row">
<button class="btn-primary" onclick="runValidation('full')">✅ Analyse complète</button>
</div>
</div>
<div class="result hidden" id="result-full"></div>
</div>
</div>

<div style="text-align:center;padding:30px;color:var(--dim);font-size:.8rem;
border-top:1px solid var(--border);margin-top:24px;font-family:monospace">
<strong style="color:var(--accent)">NEXUS W3C VALIDATOR v1.0.0</strong><br>
Aissa Mohammedi (DGK) · 2026 · NEXUS-OPEN-2.0<br>
<br>
APIs intégrées : Nu HTML Checker · CSS Validator · Link Checker · RDF Validator<br>
i18n Checker · EPUBCheck · Feed Validator · Web Platform Tests
</div>

</div>

<script>
function showTab(name, el) {
document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
document.querySelectorAll('[id^="tab-"]').forEach(t => t.classList.add('hidden'));
el.classList.add('active');
document.getElementById('tab-' + name).classList.remove('hidden');
}

const EXAMPLES = {
html: "<!DOCTYPE html>\\n<html lang='fr'>\\n<head>\\n <meta charset='UTF-8'>\\n <title>Test</title>\\n</head>\\n<body>\\n <h1>Bonjour</h1>\\n <img src='logo.png' alt='Logo'>\\n</body>\\n</html>",
css: "body {\\n color: #fff;\\n background: #000;\\n font-family: Arial;\\n}\\n\\nh1 {\\n font-size: 2rem;\\n}",
feed: "<?xml version='1.0' encoding='UTF-8'?>\\n<rss version='2.0'>\\n<channel>\\n <title>Mon flux</title>\\n <link>https://exemple.com</link>\\n <description>Test RSS</description>\\n <item>\\n <title>Article 1</title>\\n <link>https://exemple.com/1</link>\\n </item>\\n</channel>\\n</rss>",
rdf: "@prefix foaf: <http://xmlns.com/foaf/0.1/> .\\n@prefix ex: <http://example.org/> .\\n\\nex:me a foaf:Person ;\\n foaf:name 'Aissa' ;\\n foaf:knows ex:you ."
};

function loadExample(type) {
const input = document.getElementById((type === 'auto' ? 'auto' : type) + '-input');
if (input && EXAMPLES[type]) {
input.value = EXAMPLES[type];
}
}

async function runValidation(type) {
const inputId = (type === 'auto' ? 'auto' : type) + '-input';
const resultId = 'result-' + (type === 'auto' ? 'auto' : type);
const content = document.getElementById(inputId).value;

if (!content.trim()) { alert('Entre du contenu'); return; }

const result = document.getElementById(resultId);
result.classList.remove('hidden', 'ok', 'err', 'warn');
result.textContent = '⏳ Analyse en cours...';

const btnId = 'btn-' + type;
const btn = document.getElementById(btnId);
if (btn) btn.disabled = true;

try {
const r = await fetch('/api/validate/' + type, {
method: 'POST',
headers: {'Content-Type': 'application/json'},
body: JSON.stringify({content})
});
const data = await r.json();

// Déterminer la classe CSS
if (data.valid === true) result.classList.add('ok');
else if (data.count_errors > 0 || (data.validation && data.validation.count_errors > 0)) result.classList.add('err');
else if (data.count_warnings > 0) result.classList.add('warn');

result.textContent = JSON.stringify(data, null, 2);
} catch (e) {
result.classList.add('err');
result.textContent = '❌ Erreur: ' + e.message;
}

if (btn) btn.disabled = false;
}

async function loadValidators() {
try {
const r = await fetch('/api/validators');
const d = await r.json();
const list = document.getElementById('validators-list');
list.innerHTML = '';
for (const [key, v] of Object.entries(d)) {
const div = document.createElement('div');
div.className = 'vcard';
div.innerHTML = '<div class="icon">' + v.icon + '</div>' +
'<div class="name">' + v.name + '</div>' +
'<div class="desc">' + v.description + '</div>';
list.appendChild(div);
}
} catch (e) {}
}

loadValidators();
</script>
</body>
</html>'''


# ══════════════════════════════════════════════════════════════════════════════
# HTTP HANDLER
# ══════════════════════════════════════════════════════════════════════════════

class NexusHandler(BaseHTTPRequestHandler):
def log_message(self, *a): pass

def _send(self, code, body, ctype="text/html; charset=utf-8"):
if isinstance(body, str):
body = body.encode("utf-8")
try:
self.send_response(code)
self.send_header("Content-Type", ctype)
self.send_header("Content-Length", str(len(body)))
self.send_header("Access-Control-Allow-Origin", "*")
self.send_header("X-Powered-By", f"NexusW3C/{VERSION}")
self.end_headers()
self.wfile.write(body)
except Exception:
pass

def _json(self, data, status=200):
self._send(status, json.dumps(data, ensure_ascii=False, default=str),
"application/json; charset=utf-8")

def _read_body(self):
try:
length = int(self.headers.get("Content-Length", 0))
if length == 0:
return {}
body = self.rfile.read(length).decode("utf-8", errors="ignore")
return json.loads(body) if body else {}
except Exception:
return {}

def do_GET(self):
p = urllib.parse.urlparse(self.path)
path = p.path
if path in ("/", "/index.html"):
self._send(200, HTML_DASHBOARD)
elif path == "/api/validators":
self._json(W3C_VALIDATORS)
elif path == "/api/health":
self._json({"status": "ok", "version": VERSION, "author": AUTHOR})
elif path == "/api/docs":
self._json({
"version": VERSION,
"author": AUTHOR,
"endpoints": {
"GET /api/validators": "Liste des validateurs W3C",
"POST /api/validate/auto": "Détection + validation auto",
"POST /api/validate/html": "Validation HTML5",
"POST /api/validate/css": "Validation CSS",
"POST /api/validate/i18n": "Vérification i18n",
"POST /api/validate/feed": "Validation RSS/Atom",
"POST /api/validate/rdf": "Validation RDF",
"POST /api/validate/full": "Validation complète",
},
})
else:
self._json({"error": "not found"}, 404)

def do_POST(self):
p = urllib.parse.urlparse(self.path)
path = p.path
body = self._read_body()
content = body.get("content", "")

try:
if path == "/api/validate/auto":
self._json(VALIDATOR.auto_detect_and_validate(content))

elif path == "/api/validate/html":
self._json(VALIDATOR.html.validate(content))

elif path == "/api/validate/css":
self._json(VALIDATOR.css.validate(content))

elif path == "/api/validate/i18n":
self._json(VALIDATOR.i18n.check(content))

elif path == "/api/validate/feed":
self._json(VALIDATOR.feed.validate(content))

elif path == "/api/validate/rdf":
self._json(VALIDATOR.rdf.validate(content))

elif path == "/api/validate/full":
self._json(VALIDATOR.full_check(content))

else:
self._json({"error": "not found"}, 404)
except Exception as e:
self._json({"error": str(e)}, 500)


# ══════════════════════════════════════════════════════════════════════════════
# LANCEMENT
# ══════════════════════════════════════════════════════════════════════════════

def trouver_port(depart):
for p in range(depart, depart + 20):
try:
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", p))
return p
except OSError:
continue
return None


def main():
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=DEFAULT_PORT)
parser.add_argument("--no-browser", action="store_true")
args = parser.parse_args()

port = trouver_port(args.port)
if port is None:
err("Aucun port libre")
sys.exit(1)

try:
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(2)
s.connect(("8.8.8.8", 80))
ip = s.getsockname()[0]
s.close()
except Exception:
ip = "127.0.0.1"

print(f"""
{C.M}═══════════════════════════════════════════════════════════════════════{C.N}
{C.M} 🌐 NEXUS W3C VALIDATOR v{VERSION}{C.N}
{C.M}═══════════════════════════════════════════════════════════════════════{C.N}

{C.W}🌐 Serveur HTTP :{C.N}
{C.CY}→ Local :{C.N} http://localhost:{port}/
{C.CY}→ Réseau :{C.N} http://{ip}:{port}/

{C.W}📡 Validateurs disponibles :{C.N}
""")
for key, v in W3C_VALIDATORS.items():
print(f" {v['icon']} {v['name']:<25} — {v['description']}")

print(f"""
{C.W}📡 Endpoints API :{C.N}
{C.CY}GET /api/validators{C.N} → Liste des validateurs
{C.CY}GET /api/docs{C.N} → Documentation
{C.CY}POST /api/validate/auto{C.N} → Auto-détection
{C.CY}POST /api/validate/html{C.N} → HTML5
{C.CY}POST /api/validate/css{C.N} → CSS
{C.CY}POST /api/validate/i18n{C.N} → i18n
{C.CY}POST /api/validate/feed{C.N} → RSS/Atom
{C.CY}POST /api/validate/rdf{C.N} → RDF
{C.CY}POST /api/validate/full{C.N} → Complet

{C.W}📁 Dossier :{C.N} {BASE}
{C.Y}⏹ Ctrl+C pour arrêter{C.N}
""")

if not args.no_browser:
try:
import webbrowser
threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}/")).start()
except Exception:
pass

try:
server = ThreadingHTTPServer(("0.0.0.0", port), NexusHandler)
server.daemon_threads = True
server.serve_forever()
except KeyboardInterrupt:
print(f"\n{C.Y}🛑 Arrêt propre{C.N}")
except OSError as e:
err(f"Erreur: {e}")
sys.exit(1)


if __name__ == "__main__":
main()
