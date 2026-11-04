"""Compare deux instantanés de la base publique du médicament.

Usage : python scripts/compare_bdpm.py ANCIEN NOUVEAU DOSSIER_RAPPORTS

Produit un rapport lisible (Markdown, sans tableau) et des fichiers CSV
avec le détail des mouvements utiles à la veille AMM :
changements de titulaire, arrêts de commercialisation, changements de statut,
spécialités retirées ou ajoutées, baisses de prix.
"""

import csv
import datetime
import pathlib
import shutil
import sys

# Colonnes du fichier CIS_bdpm.txt (index à partir de 0)
CIS, DENOM, FORME, VOIES, STATUT_AMM, PROCEDURE, ETAT_COM, DATE_AMM, STATUT_BDM, NUM_EU, TITULAIRE = range(11)
# Colonnes du fichier CIS_CIP_bdpm.txt
P_CIS, P_CIP7, P_LIB, P_STATUT, P_ETAT, P_DATE, P_CIP13, P_AGREMENT, P_TAUX, P_PRIX = range(10)

MAX_LIST = 40


def read_table(path):
    if not path.exists():
        return None
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        rows.append([c.strip() for c in line.split("\t")])
    return rows


def col(row, i):
    return row[i] if len(row) > i else ""


def by_key(rows, key_cols):
    out = {}
    for r in rows or []:
        out[tuple(col(r, i) for i in key_cols)] = r
    return out


def price(value):
    v = value.replace(" ", "").replace(" ", "")
    if not v:
        return None
    # Formats possibles « 1 234,56 » ou « 1,234,56 » selon les versions
    if v.count(",") > 1:
        head, _, tail = v.rpartition(",")
        v = head.replace(",", "") + "." + tail
    else:
        v = v.replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def year(date_str):
    parts = date_str.split("/")
    if len(parts) == 3 and parts[2].isdigit():
        return int(parts[2])
    return None


def tag(r):
    """Étiquette rapide pour repérer les produits proches de notre cible."""
    tags = []
    if "nationale" in col(r, PROCEDURE).lower():
        tags.append("procédure nationale")
    y = year(col(r, DATE_AMM))
    if y and y <= 2005:
        tags.append(f"AMM {y}")
    return ", ".join(tags)


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        w.writerows(rows)


def bullet_list(lines, total):
    out = [f"- {l}" for l in lines[:MAX_LIST]]
    if total > MAX_LIST:
        out.append(f"- … et {total - MAX_LIST} autres, voir le fichier CSV")
    return out


def main():
    old_dir, new_dir, rep_root = (pathlib.Path(a) for a in sys.argv[1:4])
    today = datetime.date.today().isoformat()
    rep_dir = rep_root / today
    rep_dir.mkdir(parents=True, exist_ok=True)

    new_spec = read_table(new_dir / "CIS_bdpm.txt")
    new_pres = read_table(new_dir / "CIS_CIP_bdpm.txt")
    old_spec = read_table(old_dir / "CIS_bdpm.txt")
    old_pres = read_table(old_dir / "CIS_CIP_bdpm.txt")

    md = [f"# Veille BDPM du {today}", ""]

    if old_spec is None:
        md += [
            "Premier instantané enregistré. La comparaison commencera au prochain passage.",
            "",
            f"- Spécialités dans la base, {len(new_spec)}",
            f"- Présentations dans la base, {len(new_pres)}",
        ]
        (rep_dir / "rapport.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        shutil.copy(rep_dir / "rapport.md", rep_root / "LATEST.md")
        print("\n".join(md))
        return

    o_spec, n_spec = by_key(old_spec, [CIS]), by_key(new_spec, [CIS])
    o_pres, n_pres = by_key(old_pres, [P_CIS, P_CIP7]), by_key(new_pres, [P_CIS, P_CIP7])

    titulaires, commercialisation, statuts = [], [], []
    for k in sorted(set(o_spec) & set(n_spec)):
        o, n = o_spec[k], n_spec[k]
        base = [col(n, CIS), col(n, DENOM), col(n, PROCEDURE), col(n, DATE_AMM), tag(n)]
        if col(o, TITULAIRE) != col(n, TITULAIRE):
            titulaires.append(base + [col(o, TITULAIRE), col(n, TITULAIRE)])
        if col(o, ETAT_COM) != col(n, ETAT_COM):
            commercialisation.append(base + [col(o, ETAT_COM), col(n, ETAT_COM), col(n, TITULAIRE)])
        if col(o, STATUT_AMM) != col(n, STATUT_AMM):
            statuts.append(base + [col(o, STATUT_AMM), col(n, STATUT_AMM), col(n, TITULAIRE)])

    retirees = [
        [col(o_spec[k], CIS), col(o_spec[k], DENOM), col(o_spec[k], TITULAIRE)]
        for k in sorted(set(o_spec) - set(n_spec))
    ]
    nouvelles = [
        [col(n_spec[k], CIS), col(n_spec[k], DENOM), col(n_spec[k], TITULAIRE)]
        for k in sorted(set(n_spec) - set(o_spec))
    ]

    arrets, baisses = [], []
    for k in sorted(set(o_pres) & set(n_pres)):
        o, n = o_pres[k], n_pres[k]
        spec = n_spec.get((col(n, P_CIS),), [])
        if col(o, P_ETAT) != col(n, P_ETAT) and "arr" in col(n, P_ETAT).lower():
            arrets.append([
                col(n, P_CIS), col(spec, DENOM), col(n, P_LIB), col(n, P_ETAT),
                col(n, P_DATE), col(spec, TITULAIRE), tag(spec) if spec else "",
            ])
        po, pn = price(col(o, P_PRIX)), price(col(n, P_PRIX))
        if po and pn and pn < po:
            baisses.append([
                col(n, P_CIS), col(spec, DENOM), col(n, P_LIB),
                f"{po:.2f}", f"{pn:.2f}", f"{(pn / po - 1) * 100:.1f}", col(spec, TITULAIRE),
            ])

    write_csv(rep_dir / "changements_titulaire.csv",
              ["CIS", "Dénomination", "Procédure", "Date AMM", "Repère", "Ancien titulaire", "Nouveau titulaire"],
              titulaires)
    write_csv(rep_dir / "changements_commercialisation.csv",
              ["CIS", "Dénomination", "Procédure", "Date AMM", "Repère", "Avant", "Après", "Titulaire"],
              commercialisation)
    write_csv(rep_dir / "changements_statut_amm.csv",
              ["CIS", "Dénomination", "Procédure", "Date AMM", "Repère", "Avant", "Après", "Titulaire"],
              statuts)
    write_csv(rep_dir / "presentations_arret.csv",
              ["CIS", "Dénomination", "Présentation", "État", "Date", "Titulaire", "Repère"], arrets)
    write_csv(rep_dir / "baisses_prix.csv",
              ["CIS", "Dénomination", "Présentation", "Prix avant", "Prix après", "Variation %", "Titulaire"],
              baisses)
    write_csv(rep_dir / "specialites_retirees.csv", ["CIS", "Dénomination", "Titulaire"], retirees)
    write_csv(rep_dir / "specialites_nouvelles.csv", ["CIS", "Dénomination", "Titulaire"], nouvelles)

    md += [
        "## En bref", "",
        f"- Changements de titulaire, {len(titulaires)}",
        f"- Présentations passées en arrêt de commercialisation, {len(arrets)}",
        f"- Spécialités dont l'état de commercialisation a changé, {len(commercialisation)}",
        f"- Changements de statut d'AMM, {len(statuts)}",
        f"- Baisses de prix, {len(baisses)}",
        f"- Spécialités retirées de la base, {len(retirees)}",
        f"- Nouvelles spécialités, {len(nouvelles)}",
        "",
        "## Changements de titulaire", "",
        "Chaque ligne est une AMM qui a changé de mains. Le vendeur et l'acheteur sont des contacts à qualifier.", "",
    ]
    md += bullet_list(
        [f"**{r[1]}** (CIS {r[0]}{', ' + r[4] if r[4] else ''}). {r[5]} vers {r[6]}." for r in titulaires],
        len(titulaires))
    md += ["", "## Arrêts de commercialisation de présentations", ""]
    md += bullet_list(
        [f"**{r[1] or r[0]}**, {r[2]}. {r[3]}{' le ' + r[4] if r[4] else ''}. Titulaire {r[5]}{'. Repère, ' + r[6] if r[6] else ''}."
         for r in arrets],
        len(arrets))
    md += ["", "## Changements de statut d'AMM", ""]
    md += bullet_list(
        [f"**{r[1]}** (CIS {r[0]}). {r[5]} vers {r[6]}. Titulaire {r[7]}." for r in statuts], len(statuts))
    md += ["", "## Spécialités retirées de la base", ""]
    md += bullet_list([f"**{r[1]}** (CIS {r[0]}). Titulaire {r[2]}." for r in retirees], len(retirees))
    md += ["", f"Le détail complet est dans le dossier reports/{today}."]

    (rep_dir / "rapport.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    shutil.copy(rep_dir / "rapport.md", rep_root / "LATEST.md")
    print("\n".join(md[:12]))


if __name__ == "__main__":
    main()
