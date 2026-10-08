# Compatigo — Frontend GitHub Pages

Site Astro statique hébergé gratuitement sur GitHub Pages.

**URL prévue : https://trexdbg.github.io/compatigo_app/**

## Développement local

```bash
npm install
npm run dev
npm run build
```

## Publication

Le workflow `.github/workflows/deploy.yml` compile et publie automatiquement sur chaque push de `main`.

Dans **Settings → Pages → Build and deployment → Source**, sélectionner **GitHub Actions**. Le dépôt doit autoriser GitHub Pages.

## Données

Le fichier `public/data/catalog.json` est synchronisé depuis l'agent Compatigo. Les relations non vérifiées ne doivent pas être affichées comme compatibles. La qualité des références extraites reste à auditer dans `compatigo_agent`.

### Rapprochement marchand : expérimentation hors ligne

Un premier moteur d'analyse des offres existe dans `scripts/match_offers.py`. Il rapproche uniquement les références explicites fabricant **et marque** avec des exports marchands normalisés. Aucun lien affilié ni prix n'est intégré au frontend pour le moment.

```bash
python -m unittest discover -s tests -v
python scripts/match_offers.py --feed tests/fixtures/demo_offers.csv
```

Les résultats et rapports sont écrits dans le dossier local `build/` ignoré par Git. **Exemple fictif, aucune offre commerciale réelle.**

Guide complet : [docs/merchant-offers.md](docs/merchant-offers.md).
