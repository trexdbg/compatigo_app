# Compatigo — rapprochement des offres marchandes (phase 1)

Ce module est un **prototype hors ligne** : il ne fait pas de scraping, ne contacte aucun marchand, et **n'ajoute aucun prix ni lien affilié au site public**. Les résultats sont produits sous `build/`, exclu de Git.

## Commandes

Prérequis : Python 3.12 ou supérieur, aucune dépendance externe.

```bash
python -m unittest discover -s tests -v
python scripts/match_offers.py
python scripts/match_offers.py --feed tests/fixtures/demo_offers.csv
# Après accord des plateformes d'affiliation, avec des exports normalisés :
python scripts/normalize_awin.py --input chemin/awin_autorise.csv.gz --output build/awin-normalized.csv
python scripts/match_offers.py --feed build/awin-normalized.csv --feed chemin/effiliation_normalized.csv
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

## Import Awin CSV (préparé, sans compte marchand connecté)

Le script `scripts/normalize_awin.py` accepte un export **CSV ou CSV.gz obtenu légalement depuis un programme accepté**. Le script ne télécharge rien et ne contient aucune clé API. Il ne normalise que les produits dotés de :

- `brand_name` (marque fabricant de la pièce), `mpn` (référence constructeur réelle), `merchant_name` (ou `--merchant` fourni explicitement) ;
- `merchant_deep_link` (lien HTTPS de la fiche produit), `aw_deep_link` facultatif (suivi affilié, seulement si fourni par Awin) ;
- `search_price` / `store_price`, `currency`, `in_stock` / `stock_status`, `last_updated` (facultatifs).

**Jamais de correspondance par `product_name`, `model_number` ou EAN** : ils ne remplacent pas le MPN constructeur. Un prix n'est conservé que si `currency=EUR` ; sans date de dernière mise à jour ISO 8601 avec fuseau horaire, le matcher cache prix et disponibilité. Les URL non HTTPS, locales ou avec identifiants sont rejetées. Les flux et aperçus restent dans des répertoires privés ou `build/` exclus de Git.

La structure des colonnes suit les [documents officiels Awin sur les flux](https://help.awin.com/developers/docs/product-feed-list-download) ; selon les partenaires, les colonnes effectivement fournies peuvent varier. L'import Effiliation demandera une adaptation après vérification du schéma autorisé.

## Règles de sécurité et de qualité

1. Rapprochement strict sur **marque + référence constructeur**, avec seulement une normalisation de ponctuation et de casse. Jamais de recherche floue, d'inférence depuis le titre ni de rapprochement par référence tronquée.
2. L'appareil et la pièce doivent être marqués `verified` et contenir une preuve **explicite** issue d'une source fabricant de type reconnu avec une URL HTTPS. Ce script ne réanalyse pas le contenu distant au moment du rapprochement.
3. Rejet des références invalides, marques non concordantes, URL dangereuses, autres devises, prix invalides et doublons.
4. Sans horodatage valide et récent (maximum 7 jours par défaut), prix masqué et disponibilité inconnue. Les contraintes de fraîcheur propres aux partenaires pourront exiger un délai plus court.
5. Les fichiers de flux privés et les résultats hors ligne ne doivent jamais être committés. Secrets API uniquement dans GitHub Actions Secrets.
6. Les offres commerciales n'établissent **jamais** une compatibilité appareil/pièce ; nettoyer d'abord les faux appareils dans `compatigo_agent`.

## Étapes suivantes (après l'inscription aux programmes)

- Confirmer l'acceptation éditeur et l'éligibilité réelle des **consommables** à commission.
- Vérifier conditions d'utilisation des flux, prix, images, taux, fréquence de mise à jour et restrictions de tracking.
- Utiliser le normaliseur Awin avec un flux autorisé, tester un échantillon, puis planifier une synchronisation privée ; adapter Effiliation seulement après accès à un export documenté.
- Vérifier sur échantillon les offres rapprochées, les ruptures et substitutions.
- Seulement ensuite, publier des offres fiables dans `compatigo_app`, avec transparence de l'affiliation, liens `rel="sponsored noopener noreferrer"` et prise en compte des règles de consentement applicables.

**Important :** les faux modèles Rowenta ont été écartés par les garde-fous de l'agent. Les autres marques restent candidates tant qu'elles n'ont pas de preuve fabricant suffisante. La couverture commerciale doit être mesurée sur les seules pièces publiées.
