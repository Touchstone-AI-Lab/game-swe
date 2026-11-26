# GameSWE website

Project page for GameSWE (Vite + TypeScript, no framework). This branch holds only the site. It is published at
https://touchstone-ai-lab.github.io/bench/game-swe/ by the workflow in
[Touchstone-AI-Lab.github.io](https://github.com/Touchstone-AI-Lab/Touchstone-AI-Lab.github.io), which rebuilds from this branch within
15 minutes of a push (`gh workflow run pages.yml -R Touchstone-AI-Lab/Touchstone-AI-Lab.github.io` publishes at once).

```bash
npm install
python tools/build_data.py <paper_dir>   # regenerate src/data.json (optional; the output is committed)
npm run dev                              # local preview
npm run build                            # static site in dist/
```

`<paper_dir>` is the paper checkout. `build_data.py` reads only aggregate numbers (`analysis/r30/data/e1-paper-stats.json`,
`source/table/main_results.tex`, `source/data/inventory_macros.tex`), maps internal model ids to public slugs, cross-checks the
stats file against Table 2, and refuses to write output that contains an internal id or a private link. Every number on the page
is read from `src/data.json` through `data-bind` attributes or the chart code, so regenerating it updates the whole page.

- `src/globe.ts`: the hero globe, a 2D canvas with one dot per task (repair filled, construction ringed) clustered by game.
- `src/results.ts`: leaderboard, per-game heatmap, stage bar and attempt funnel.
- `public/icons/`: model logos from LobeHub Icons (MIT), listed in `public/THIRD-PARTY-NOTICES.txt`.
- `public/og.png`: the social card, a capture of the hero in the dark theme.

The paper is under double-blind review, so the page names no authors and links neither the paper nor the code yet.
