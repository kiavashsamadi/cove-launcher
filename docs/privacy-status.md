# Privacy scope

Cove's renderer performs local control and does not send network requests.
Samsung's remaining operating system and applications are separate. Installing
Cove alone does not disable them or prove that telemetry is absent.

## Qualified component controls

A tested configuration uses these nine cold-boot-verified global
app-registration disables:

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

The native ad player (`com.samsung.tv.adplayer`) is separate from the web
application `adplatform.ADPlayer` in package `adplatform`. The web player's
global registration flag is now disabled as a separate tenth control. Its
native disable/enable round trip and recovery after a controlled post-disable
validation failure passed before deployment. Both tests restored the original
flag and preserved the full global, owner, web-app and picture tables.

Deployment received the matching successful native completion callback and a
disabled readback. Fresh full-database comparisons found exactly that one
global flag change: all other registry rows, all six picture tables and the
launcher, update, network and identity checks were preserved.
The package and its data remain installed, with a scoped
native enable inverse retained. Restart persistence, all possible activation
paths and a reduction in transmitted data are not established for this new
control. It does not disable the shared advertising framework.

The offline [package inventory comparison](../scripts/compare_package_inventory.py)
keeps package IDs, application IDs and sibling flags separate; recorded flags
alone do not establish runtime blocking or qualify another removal.

## Automatic-update policies

Four native settings were separately tested: the two firmware auto-update
policies, app auto-updates, and server upgrades of built-in apps. All four were
set to their typed off values and independently read back. Each write had a
recorded inverse and a full policy readback; pending-upgrade flags, firmware
files and updater services were left unchanged. A subsequent cold boot was
confirmed by a new boot identity; fresh reads verified that all four policies
remained off. The existing component controls and all six picture-setting tables
also passed their post-restart checks.

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

DNS filtering has not been deployed. Its qualification is separate from the
TV-side component controls above.

Keeping local access while blocking TV Internet access requires a suitable
network rule covering both IPv4 and IPv6 and verification of alternate routes.
A wireless MAC filter usually controls association and can remove local access;
it is not equivalent to a TV-only Internet block. A DNS list alone cannot cover
hard-coded addresses or alternate resolvers.

Read-only checks found IPv6 DNS activity as well as IPv4 connections. The
restricted-worker design passed eight isolated lifecycle/failure cases and 237
detailed DNS assertions plus readiness checks. A separate private-network trial passed 60 native routing and
rollback assertions, including partial activation, interruptions and conflicts.
Independent deadline recovery then passed resolver-crash and frozen-worker/client-loss
cases, with 28 DNS assertions each and no controller-issued inverse.
Complete diagnostic-agent loss and an interrupted primary inverse also passed
independent backup recovery and automatic native cleanup. Native libc TCP retry
and 12 NSS IPv4/IPv6 fallback cases passed. Real native lookup/replay checks used
existing upstreams; the bounded samples observed no background-app queries. A
raw retained TCP connection still reset, and ordinary-client interception remains
unqualified.
Worker supplementary groups and active capabilities are empty after startup.
Eight real-upstream lookup cases also passed using restricted test clients with
private resolver views and empty supplementary groups. Live TV DNS/firewall
settings remain unchanged; ordinary applications were not redirected.
Client-scoped routing also passed isolated complete-controller-loss and
interrupted-primary recovery, with an independent restricted witness and
separate host-network readback. Nonmember DNS remained unaffected. This is a
prerequisite for a separate live-network trial. That trial also verified
owned-client recovery after complete controller loss and a partial primary
inverse, with outside-group DNS unaffected and later DNS/firewall preservation
confirmed. Ordinary apps were not redirected; no filtering remains installed.
An unattended on-TV resolver remains unqualified. See the
[recovery evidence and deployment gates](dns-recovery.md).

A longer receive-only sample observed two background DNS questions and their
replies, neither matching the reviewed blocklist. A separate bounded replay
sample observed no questions and therefore provides no background-replay
coverage. Names and packet contents are not retained or published. These samples
cannot establish absent telemetry or ordinary-app compatibility. An offline
boot-recovery model now covers interrupted preparation/restoration and stale
workers; native durable startup and power-loss recovery remain unqualified.

App synchronization is another candidate because it participates in app
restoration. Its native metadata and registry baseline were read successfully,
but its system package advertises no disable support. Native disable acceptance,
re-enablement and restoration behavior remain unproven. Empty dependency rows
and process absence in a short sample are insufficient to qualify removal. Do
not replace this uncertainty with direct registry edits or package-manager
restarts. Dormant app removal likewise has no demonstrated speed benefit here.

Native server inspection also found that deactivation can terminate its target
before changing the registration flag. App-sync can perform installation and
restoration work, so its disable needs more than a prior idle-process sample and
a reversible flag. No app-sync mutation was performed during this review. The
[native operation boundaries](privacy-preparation.md#native-operation-boundaries)
describe the completion and recovery requirements.

No network policy is installed by Cove. Separately connected HDMI players and
consoles have their own network behavior. See [recovery](recovery.md),
[offline review tools](privacy-preparation.md) and [external references](resource-review.md).
