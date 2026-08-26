# Foreman — the numbers, straight from the deployment

> **Generated, never typed.** `python scripts/verify_live_numbers.py`
> Source: `https://foreman-yi3t.onrender.com` · captured 2026-08-26 18:41 UTC

Any figure that appears in a slide, a README or a message must be copied
from this file. If a number is not here, it is not claimed.

## Instance

- graph store: **neo4j** (26 nodes)
- language model reachable: **True**
- materials tracked: **8**

## Schedule risk (Monte-Carlo)

- simulations: **3000**
- vendor correlation applied: **0.0**
- baseline handover: **2026-11-04**
- P(handover slips): **0.15**
- mean slip: **0.43 days** · P50 **0.0** · P90 **2.0**

Top risk drivers:

| material | risk contribution |
| --- | --- |
| 2MVA diesel generators (x4) | 0.612 |
| 4000A LV switchgear lineup | 0.028 |
| Busway / busbar trunking | 0.023 |
| CRAC cooling units (x8) | 0.005 |
| Fire suppression system (NOVEC skids) | 0.005 |

## Cascade — the two headline scenarios

| scenario | handover | slip | slipped | absorbed | confidence |
| --- | --- | --- | --- | --- | --- |
| Structural steel +21d | 2026-11-04 → 2026-11-22 | **18d** | 11 | 0 | 0.92 |
| LV switchgear +14d | 2026-11-04 → 2026-11-04 | **0d** | 0 | 5 | 0.7 |

## Commercials

- $2,611 — Late-handover penalty (assumed)
- $888 — Extra site running cost (assumed)

