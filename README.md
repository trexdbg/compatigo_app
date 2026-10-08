# Compatigo — Frontend

Application web Astro statique, pensée pour Cloudflare Pages. Recherche par référence d'appareil, preuves constructeur et statut de vérification.

## Démarrage

```bash
npm install
npm run dev
npm run build
```

## Déploiement Cloudflare Pages

Framework preset : **Astro** ; build command : `npm run build` ; output directory : `dist` ; Node.js 22 ou supérieur.

## Catalogue

`public/data/catalog.json` est le contrat provisoire entre `compatigo_agent` et le frontend. Les exemples inclus sont des **entrées de démonstration, non validées**. L'interface affiche seulement les consommables portant `status: "verified"` avec preuve source ; elle n'invente jamais de compatibilité ou de prix. Intégrer plus tard un export agent validé en CI.

Structure d'une entrée :

```json
{
  "brand": "Rowenta",
  "model": "RO7649EA",
  "type": "Aspirateur",
  "verified": true,
  "parts": [{
    "manufacturer_part_number": "REFERENCE",
    "consumable_type": "filter",
    "status": "verified",
    "evidence": [{"source_url": "https://constructeur.example/source"}]
  }]
}
```

La compatibilité et l'affiliation doivent rester indépendantes. Pas d'affichage d'offres commerciales non vérifiées.
