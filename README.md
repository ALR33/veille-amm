# veille-amm

Veille automatique de la base publique du médicament (BDPM), pour repérer les AMM qui changent de mains ou qui s'arrêtent.

## Fonctionnement

Chaque lundi, GitHub télécharge les fichiers publics de la BDPM, les compare à la semaine précédente et publie un rapport.

- `data/latest` contient le dernier instantané des fichiers BDPM, tels que publiés.
- `reports/LATEST.md` est le dernier rapport, lisible sur téléphone.
- `reports/AAAA-MM-JJ/` contient le détail en CSV.

Le rapport liste les changements de titulaire, les présentations passées en arrêt de commercialisation, les changements de statut d'AMM, les ruptures et tensions signalées, les mouvements sur la liste des MITM, les baisses de prix et les spécialités retirées ou ajoutées. Les MITM apparaissent en tête de chaque liste.

Le job peut aussi être lancé à la main depuis l'onglet Actions, avec « Run workflow ».

## Ce qui n'est jamais dans ce dépôt

Ce dépôt est public. Il ne contient que des données publiques. La liste de cibles, le scoring et les notes d'appels restent hors de GitHub.
