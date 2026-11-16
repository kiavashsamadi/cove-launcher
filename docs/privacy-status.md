# Privacy scope

Cove's renderer performs local control and does not send network requests.
Samsung's remaining operating system and applications are separate. Installing
Cove alone does not disable them or prove that telemetry is absent.

## Qualified component controls

A tested configuration uses nine native global app-registration disables:

| Component group | Count |
| --- | ---: |
| Dedicated ACR service | 1 |
| Samsung Analytics | 1 |
| Targeted-ad service and native ad player | 2 |
| Samsung Health components | 3 |
| SmartThings Find components | 2 |

Those flags and the existing PISA/adagent negative-path startup conditions were
verified after a cold boot. The latter left unit files unchanged and reported
inactive processes with failed startup conditions. Later readbacks confirmed
the controls remained in place. This does not establish that every direct or
shared-host activation path is blocked.

Each change needs exact-device validation and a field-specific inverse. The
repository's review tools do not install this configuration. Preserve Settings,
Device Care, the Cove carrier, display/panel care, HDMI/CEC/eARC, audio, networking,
Bluetooth, accessibility and security components.

## Automatic-update policies

Four native settings were separately tested: the two firmware auto-update
policies, app auto-updates, and server upgrades of built-in apps. All four were
set to their typed off values and independently read back. Each write had a
recorded inverse and a full policy readback; pending-upgrade flags, firmware
files and updater services were left unchanged. Persistence across a subsequent
cold boot is still pending.

These policies reduce automatic changes; they do not block every manual update,
store/server restoration path or network request. Deferring updates also defers
security fixes, so retain a deliberate maintenance and requalification route.
The launcher does not apply this configuration. The
[offline receipt checker](privacy-preparation.md) verifies only the recorded
values, not complete update or telemetry prevention.

## Unresolved paths

Short socket samples and private binary inspection identified shared data/KPI,
push, recognition and diagnostic paths. Socket ownership does not establish
what was sent, and an absent socket does not establish permanent inactivity.
Configured event names do not prove collection or transmission.

The shared data service has multiple consumers. SP-KPI references broad display,
power, network and HDMI diagnostics; media analytics contains both consent and
policy logic. No isolated persistent control with a complete consumer-impact
review and reliable inverse was established for these paths. Broad service
disables, guessed policy edits, firmware remounts and watchdogs are not qualified
privacy fixes.

Native consent options can reduce collection, but they are not a packet-level
audit. Complete telemetry prevention, decrypted traffic coverage and measured
before/after transmission rates are not established.

## Network boundary

Keeping local access while blocking TV Internet access requires a suitable
network rule covering both IPv4 and IPv6 and verification of alternate routes.
A wireless MAC filter usually controls association and can remove local access;
it is not equivalent to a TV-only Internet block. A DNS list alone cannot cover
hard-coded addresses or alternate resolvers.

No network policy is installed by Cove. Separately connected HDMI players and
consoles have their own network behavior. See [recovery](recovery.md),
[offline review tools](privacy-preparation.md) and [external references](resource-review.md).
