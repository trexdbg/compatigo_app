# Compatigo — Site Astro statique

Compatigo aide les particuliers à retrouver les filtres et consommables compatibles avec leur appareil à partir de références constructeur. L'application est construite avec Astro et publiée gratuitement sur GitHub Pages.

**Site actuel :** https://trexdbg.github.io/compatigo_app/

## Démarrer localement

```bash
npm install
npm run dev
npm run build
python3 scripts/check_seo_build.py
```

Le test SEO contrôle les pages générées, leur canonique, les preuves constructeur et la correspondance avec le sitemap XML.

## Architecture du site

- `/` : moteur de recherche interactif (charge `public/data/catalog.json`).
- `/appareils/` : catalogue HTML de toutes les marques réellement disponibles.
- `/marques/[marque]/` : index des appareils d'une marque.
- `/[marque]/[modele]/` : fiche statique d'un appareil, avec références de consommables, sources constructeur et modèles partageant une même pièce.
- `/sitemap.xml` : généré à la compilation uniquement à partir des appareils éligibles.
- `/robots.txt` : indique l'URL du sitemap.

La base de l'URL GitHub Pages est **/compatigo_app/**. Les routes finales prennent donc la forme `https://trexdbg.github.io/compatigo_app/rowenta/rh2036wo/`.

### Qualité des données

Le catalogue est produit par le dépôt privé `compatigo_agent`, validé, puis synchronisé quotidiennement par `.github/workflows/sync-catalog.yml` via le secret `COMPATIGO_AGENT_READ_TOKEN`.

Une fiche n'est générée que si l'appareil possède une relation vérifiée et que la référence du consommable est accompagnée d'une **preuve explicite d'une source constructeur**. Les pages non éligibles n'apparaissent pas dans le sitemap. Aucun stock marchand, tarif, avis client ou lien affilié n'est fabriqué à partir des preuves.

Les fiches sont intégrées au HTML par Astro lors du build. Elles restent donc accessibles aux moteurs de recherche et aux utilisateurs sans JavaScript. Le moteur de recherche est seulement une couche d'ergonomie.

## Déploiement

- `.github/workflows/ci.yml` teste les scripts et la génération SEO.
- `.github/workflows/deploy.yml` compile, contrôle et déploie le site sur chaque push de `main`.
- `.github/workflows/sync-catalog.yml` importe le catalogue vérifié puis compile et déploie les nouvelles fiches.

Dans **Settings → Pages → Build and deployment → Source**, sélectionner **GitHub Actions** pour éviter la compilation Jekyll automatique sur les sources Astro.

## SEO / GEO

Chaque fiche possède un titre et une description propres, une URL canonique, des liens internes, les références exactes des pièces, les sources consultables, une date de récupération des preuves et un JSON-LD descriptif sans avis, prix ou stock fictifs.

Après déploiement, soumettre `https://trexdbg.github.io/compatigo_app/sitemap.xml` dans Google Search Console. Un sitemap n'assure pas l'indexation : celle-ci dépend de la qualité des pages et des décisions des moteurs.

### Lors du passage à compatigo.fr

**Ne pas changer de domaine sans adapter ces fichiers :**
1. `astro.config.mjs` : `site` doit devenir `https://compatigo.fr` et `base` doit devenir `/`.
2. `public/robots.txt` : remplacer l'URL du sitemap par celle du domaine.
3. `scripts/check_seo_build.py` : adapter `SITE` et `BASE` et revalider la compilation.
4. Paramétrer le domaine personnalisé GitHub Pages et les DNS ; déclarer le nouveau domaine dans Search Console, puis planifier les redirections et la migration des anciennes URLs.

L'affiliation constitue une couche distincte, ajoutée uniquement après fiabilisation du catalogue.

## Association des offres marchandes (prototype hors ligne)

Le script `scripts/match_offers.py` permet de croiser les références fabricant du catalogue avec des exports marchands normalisés, exclusivement sur **marque + référence exacte**. Les offres restent en aperçu local, sans aucun prix ou lien affilié publié sur le site.

```bash
python -m unittest discover -s tests -v
python scripts/match_offers.py --feed tests/fixtures/demo_offers.csv
```

Pour préparer un **flux Awin autorisé** au format CSV ou CSV.gz, sans publier d'offres :

```bash
python scripts/normalize_awin.py --input chemin/awin.csv.gz --output build/awin-normalized.csv
python scripts/match_offers.py --feed build/awin-normalized.csv
```

La normalisation exige un `mpn` réel et une marque fabricant ; aucun numéro n'est deviné dans le titre du produit.

Le rapport et les offres de démonstration sont produits dans `build/` (ignoré par Git). L'exemple marchand est **fictif**. Mode d'emploi et prérequis pour brancher Awin / Effiliation : [docs/merchant-offers.md](docs/merchant-offers.md).
