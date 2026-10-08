# Compatigo — rapprochement des offres marchandes (phase 1)

Ce module est un **prototype hors ligne** : il ne fait pas de scraping, ne contacte aucun marchand, et **n'ajoute aucun prix ni lien affilié au site public**. Les résultats sont produits sous `build/`, exclu de Git.

## Commandes

Prérequis : Python 3.12 ou supérieur, aucune dépendance externe.

```bash
python -m unittest discover -s tests -v
python scripts/match_offers.py
python scripts/match_offers.py --feed tests/fixtures/demo_offers.csv
# Après accord des plateformes d'affiliation, avec des exports normalisés :
python scripts/match_offers.py --feed chemin/awin_normalized.csv --feed chemin/effiliation_normalized.csv
```

Sorties : `build/offers-preview.json` (interne, à ne **pas** publier), et `build/offers-report.json` (nombre de pièces couvertes, d'offres et motifs de rejet). Sans flux fourni, zéro offre est **normal**. La boutique `merchant.example` dans le fichier de démonstration est fictive ; il n'y a ni lien affilié réel ni prix actuel.

## Contrat CSV (UTF-8) ou JSON

Une ligne représente **une offre pour une référence constructeur explicite**. Champs CSV :

| Champ | Obligatoire | Usage |
| --- | --- | --- |
| `network` | oui | `awin`, `effiliation` ou autre source autorisée |
| `merchant` | oui | Nom du marchand |
| `brand` | oui | Marque de la pièce (ex. Rowenta) |
| `manufacturer_part_number` | oui | Référence fabricant explicite (ex. ZR903701) |
| `title` | non | Libellé de l'offre (jamais utilisé pour faire une correspondance) |
| `product_url` | oui | URL HTTPS vers le produit exact |
| `affiliate_url` | non | URL HTTPS fournie par le programme accepté |
| `price_eur` | non | Nombre positif en euros, ex. `19.90` |
| `currency` | non | `EUR` ou vide |
| `availability` | non | `in_stock`, `out_of_stock`, `unknown` |
| `checked_at` | non | Date ISO 8601 **avec fuseau horaire** |

JSON : liste d'objets de même structure ou objet `{"offers":[...]}`. L'option `--feed` peut être répétée. Chaque plateforme utilisant ses propres noms de colonnes, il faudra écrire un **adaptateur d'import** pour ses flux autorisés après acceptation du programme ; aucun accès API Awin/Effiliation n'est encore branché.

## Règles de sécurité et de qualité

1. Rapprochement strict sur **marque + référence constructeur**, avec seulement une normalisation de ponctuation et de casse. Jamais de recherche floue, d'inférence depuis le titre ni de rapprochement par référence tronquée.
2. Une pièce candidate doit déjà être déclarée `verified` dans le catalogue agent et contenir une URL de preuve HTTPS. **Ce script ne recontrôle pas la réalité de la preuve constructeur.**
3. Rejet des références invalides, marques non concordantes, URL dangereuses, autres devises, prix invalides et doublons.
4. Sans horodatage valide et récent (maximum 7 jours par défaut), prix masqué et disponibilité inconnue. Les contraintes de fraîcheur propres aux partenaires pourront exiger un délai plus court.
5. Les fichiers de flux privés et les résultats hors ligne ne doivent jamais être committés. Secrets API uniquement dans GitHub Actions Secrets.
6. Les offres commerciales n'établissent **jamais** une compatibilité appareil/pièce ; nettoyer d'abord les faux appareils dans `compatigo_agent`.

## Étapes suivantes (après l'inscription aux programmes)

- Confirmer l'acceptation éditeur et l'éligibilité réelle des **consommables** à commission.
- Vérifier conditions d'utilisation des flux, prix, images, taux, fréquence de mise à jour et restrictions de tracking.
- Construire l'import depuis les flux approuvés et exécuter une synchronisation automatique.
- Vérifier sur échantillon les offres rapprochées, les ruptures et substitutions.
- Seulement ensuite, publier des offres fiables dans `compatigo_app`, avec transparence de l'affiliation, liens `rel="sponsored noopener noreferrer"` et prise en compte des règles de consentement applicables.

**Important :** la base actuelle contient encore des faux modèles (ex. ROBINET / MOUSSE). L'indicateur d'appareils « couverts » ne sera crédible qu'après correction dans l'agent.
