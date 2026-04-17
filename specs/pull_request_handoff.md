# Pull Request Handoff

- Branch locale: `feat/implement-dashboard-dynamicization`
- Commit baseline dynamicization: `434db61`
- Commit hardening anti-regressione: `e7843ee`
- Commit merge-conflict resolution (resize + hydration): `5d09047`
- Commit restore container Backtest: `dfec936`

## Stato attuale PR
Questa PR include:
1. Data layer condiviso `dashboards/dashboard_data.js`.
2. Hydration API per dashboard/chat/agents con fallback statico.
3. Resize sections persistenti (`localStorage`) su pagine dashboard principali.
4. Ripristino e fallback dei container Backtest per evitare tabelle vuote.

## Nota ambiente
In questo ambiente non è configurato alcun remote git (`git remote -v` è vuoto), quindi non posso fare `git push` verso GitHub/GitLab.
Per questo motivo la PR viene preparata tramite tool `make_pr`.
