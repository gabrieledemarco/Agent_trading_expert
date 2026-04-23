# Phase 0 — Stabilizzazione (baseline contratti)

Obiettivo: creare una baseline verificabile prima delle modifiche strutturali V2.

## Scope

- Congelare i contratti documentali V2 (README, PRD, ARCHITECTURE_V2, deploy docs).
- Congelare i contratti minimi di configurazione runtime (Render + `.env.example`).
- Congelare i contratti statici della migration SQL V2 (tabelle/eventi/trigger attesi).

## Deliverable fase 0

1. Test contratti documentazione V2
2. Test contratti config runtime
3. Test contratti statici migration SQL V2

## Criteri di uscita fase 0

- I test `tests/contracts/test_phase0_*.py` passano in locale.
- Nessuna modifica runtime funzionale richiesta in questa fase.
- Le fasi successive possono evolvere codice/DB mantenendo una baseline di regressione.
