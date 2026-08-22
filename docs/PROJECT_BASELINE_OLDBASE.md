# Oldbase Frontend Baseline

## Confirmed Current State

- `local_console_reference/ScreeniestoUSE/oldbase.html` is the primary frontend baseline.
- Its design language, colors, layout feel, and builder/workbench workflow define the target product identity.
- The vehicle builder and trunk, bag, bundle, and nested-item builders are important product behavior and must be preserved and repaired.
- Oldbase does not contain the intended Trader system.
- The current Flask/Jinja interface is a support/test interface, not the target frontend identity.
- Existing catalog, vehicle, wallet/ledger, admin, database, and Discord code may provide support layers. Each connection must be verified before use.
- The current simplified interface must remain available until working oldbase-based replacements cover its required paths.

## Planned Refactor Direction

- Restore oldbase behavior before changing its information architecture.
- Repair builders in place rather than replacing them with weaker selector flows.
- Add Trader in oldbase style, reusing the item-card and nested item-selection patterns used by trunk and bundle workflows.
- Connect backend systems through narrow adapters while keeping oldbase presentation and interaction patterns intact.
- Keep player and admin/server-control workflows equally important and visually coherent.
- Revisit player-facing wallet/economy wording later, likely around bank and cash concepts, without weakening ledger safety.

## Open Questions

- Which oldbase builder sections are fully functional, partially functional, or mock-only?
- Which oldbase data structures can consume the current catalog and thumbnail data without reshaping the UI?
- Which admin actions need server-side authorization before oldbase controls can become active?
- How should bank, carried cash, holds, and transaction history map onto the current immutable wallet ledger?
- Which Discord actions should open, mirror, or complete web workflows?

## Next Steps

1. Index oldbase sections, state, event handlers, and data dependencies without a full linear reread.
2. Audit vehicle and nested item builders first.
3. Map verified backend attachment points.
4. Define parity tests before replacing any current simplified route.

