# Oldbase Implementation Map

## Preserve / Repair / Add

| Area | Action | Current Direction |
|---|---|---|
| Visual identity | Preserve | Keep oldbase colors, layout density, cards, panels, modal/review feel, and workbench flow. |
| Vehicle builder | Repair | Preserve vehicle-first selection, configuration state, required parts, summary, and review behavior. |
| Trunk/bag/bundle builders | Repair | The audited oldbase has generic quick-build/child nesting but no explicit trunk, bag, or bundle state model. Add these by extending—not bypassing—the oldbase workbench interaction. |
| Item selection | Preserve and adapt | Use oldbase item-card and nested catalog interaction patterns as the shared frontend language. |
| Trader | Add | Build inside oldbase styling and interaction patterns; do not create a separate dashboard aesthetic. |
| Admin/server control | Preserve and connect | Keep equal priority with Trader/builder flows; gate mutations on the server. |
| Simplified Flask/Jinja UI | Retire later | Keep until oldbase-based replacements exist, work, and meet route/behavior parity. |
| Wallet language | Refit later | Explore bank/cash terminology while preserving immutable ledger behavior underneath. |

## Backend Attachment Map

| Backend area | Confirmed support | Intended attachment | Audit needed |
|---|---|---|---|
| Item database | `shared/catalog/service.py` exposes search, category, and item lookup functions. | Feed oldbase item pickers and Trader through a stable catalog adapter. | Verify canonical IDs, categories, quantities, nested-item rules, and API shape. |
| Thumbnails/images | `shared/catalog/thumbnails.py` and the vehicle resolver/builder services provide mapped images and fallbacks. | Resolve oldbase card, picker, and review images with a controlled fallback. | Inventory oldbase image references and current resolver coverage. |
| Trader/catalog data | Catalog routes and `AutoTraderOrderService` product/order preview methods exist; intended Trader UI is absent from oldbase. | Add an oldbase-style Trader using trunk/bundle catalog behavior patterns. | Separate browse data, admin availability/pricing, order preview, and real delivery states. |
| Admin role/auth | `web/local_auth.py` provides role checks; catalog mutation/admin routes use `admin_or_higher`. | Authorize oldbase admin controls server-side; hiding controls is not authorization. | Map every mutation to its existing or required guarded endpoint. |
| Economy/bank/cash | `WalletLedgerService` and the Auto-Trader wallet bridge exist. | Attach balances, holds, debits, refunds, and history without exposing ledger jargon to players. | Define bank/cash terminology and whether carried cash is presentation-only or a distinct domain concept. |
| Discord integration | Trader UI/cog plus local wallet and Auto-Trader cogs exist. | Reuse backend services and link Discord actions to the same authoritative workflows. | Verify active commands, identity mapping, permissions, and web handoff behavior. |

## Implementation Order After Audit

1. Freeze oldbase visual and interaction parity criteria.
2. Repair vehicle builder state and review flow.
3. Repair trunk, bag, bundle, and nested item builders.
4. Add a read-only catalog adapter and thumbnail resolver.
5. Add oldbase-style Trader browse, inspect, and review.
6. Attach guarded admin catalog controls.
7. Attach truthful order/economy previews, then verified transaction paths.
8. Attach Discord entry and notification points.
9. Replace simplified routes only after parity and acceptance checks pass.

## Open Questions

- Whether oldbase should remain one document during repair or be split only after behavior parity is captured.
- Which current endpoints already provide the exact data required by oldbase.
- Which oldbase controls are prototypes and must stay disabled until backend support is real.

## First Repair Boundary

Before backend attachment, consolidate oldbase onto one builder state/controller:

- one `quick`, `builds`, selected vehicle/color, and child-nesting state;
- one delegated action path for catalog cards, attachments, removal, and workbench movement;
- event-driven rendering without the 1.5-second rerender loop;
- persisted chance edits and explicit restricted-item rejection;
- truthful UI that does not claim quantity, capacity, bag, bundle, or trunk enforcement until those rules exist.
