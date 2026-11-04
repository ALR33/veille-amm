"""Télécharge les fichiers de la base publique du médicament (BDPM).

Usage : python scripts/snapshot.py DOSSIER_DE_SORTIE

Le script lit la page de téléchargement, repère les liens vers les fichiers
texte et les enregistre tels quels. Si la page ne donne aucun lien, il essaie
l'ancienne adresse de téléchargement pour une liste de fichiers connus.
"""

import datetime
import html
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://base-donnees-publique.medicaments.gouv.fr"
PAGE = BASE + "/telechargement"
OLD_PATTERN = BASE + "/telechargement.php?fichier={name}"
KNOWN_FILES = [
    "CIS_bdpm.txt",
    "CIS_CIP_bdpm.txt",
    "CIS_COMPO_bdpm.txt",
    "CIS_HAS_SMR_bdpm.txt",
    "CIS_HAS_ASMR_bdpm.txt",
    "HAS_LiensPageCT_bdpm.txt",
    "CIS_GENER_bdpm.txt",
    "CIS_CPD_bdpm.txt",
    "CIS_InfoImportantes.txt",
    "CIS_MITM.txt",
]
REQUIRED = {"CIS_bdpm.txt", "CIS_CIP_bdpm.txt"}
HEADERS = {"User-Agent": "veille-amm/1.0 (GitHub Actions; donnees publiques BDPM)"}


def fetch(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (i + 1))
    raise last


def links_from_page():
    raw = fetch(PAGE).decode("utf-8", errors="replace")
    found = {}
    for href in re.findall(r'href=["\']([^"\']+)["\']', raw, flags=re.I):
        href = html.unescape(href)
        url = urllib.parse.urljoin(PAGE + "/", href)
        m = re.search(r"([A-Za-z0-9_]+\.txt)", url)
        if m:
            found.setdefault(m.group(1), url)
    return found


def main():
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    log = []
    try:
        links = links_from_page()
        log.append(f"Page de téléchargement lue, {len(links)} liens .txt trouvés")
    except Exception as e:  # noqa: BLE001
        links = {}
        log.append(f"Page de téléchargement illisible ({e!r})")
    for name in KNOWN_FILES:
        links.setdefault(name, OLD_PATTERN.format(name=name))

    ok = set()
    for name, url in sorted(links.items()):
        try:
            data = fetch(url)
        except Exception as e:  # noqa: BLE001
            log.append(f"ECHEC {name} {url} ({e!r})")
            continue
        head = data[:400].lower()
        if b"<html" in head or b"<!doctype" in head or len(data) < 50:
            log.append(f"ECHEC {name} {url} (réponse HTML ou vide, {len(data)} octets)")
            continue
        (out / name).write_bytes(data)
        ok.add(name)
        log.append(f"OK {name} {len(data)} octets {url}")

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (out / "SOURCES.txt").write_text(
        f"Instantané du {stamp}\n" + "\n".join(log) + "\n", encoding="utf-8"
    )
    print("\n".join(log))
    missing = REQUIRED - ok
    if missing:
        print(f"Fichiers indispensables manquants : {sorted(missing)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
