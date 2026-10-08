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

Le fichier `public/data/catalog.json` est pour l'instant un catalogue de démonstration. Il sera remplacé par un export vérifié de `compatigo_agent`. Les relations non vérifiées ne sont pas affichées comme compatibles. Les liens d'affiliation seront ajoutés séparément.
