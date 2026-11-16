# Isolated DNS recovery

The restricted resolver, native routing inverse and independent recovery after complete diagnostic-agent loss have passed isolated TV tests, including an interrupted primary inverse. Native TCP reconnection, IPv4/IPv6 lookup fallback and limited replay through existing upstreams also passed. **Permanent DNS filtering remains unqualified.** Routing mutations occur only inside a separately verified, loopback-only network namespace. The TV's live DNS and firewall are unchanged.

## Worker permissions

Use dnsmasq's normal foreground mode, `--keep-in-foreground`, with its native user/group drop. Its debug mode, `--no-daemon`, skips that drop. This distinction is documented in the [dnsmasq manual](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html) and was verified against the stock binary's actual process credentials.

The tested worker has an unprivileged identity, no supplementary groups, no-new-privileges, and empty permitted, effective, inheritable and ambient capability sets. The bounding set retains SETUID/SETGID for startup; **it is not empty and is not an active grant**. The original synthetic port-53 resolver also needs NET_BIND_SERVICE during startup. Neither worker retains active capabilities after its native drop. No signatures, file capabilities or platform security policies are changed.

The existing systemd 244 manager enforces a three-second lifetime, bounded startup/stop, full control-group termination, no restart and collection after failure. The strict worker batch also verifies ProtectSystem=strict, ProtectHome, private devices, kernel/control-group protections and restrictive umask. Read-only root and selected system mounts are checked in the worker's actual mount table. No syscall-filter claim is made: this manager build lacks seccomp support. See the version-matched [execution controls](https://github.com/systemd/systemd/blob/v244/man/systemd.exec.xml) and [service lifetime](https://github.com/systemd/systemd/blob/v244/man/systemd.service.xml).

| Restricted-worker case | Native result |
| --- | --- |
| Manager deadline | Worker and resources removed without controller fallback |
| Frozen worker | Removed at the manager's deadline |
| Waiting launch client killed | Worker survived the client, then expired independently |
| Resolver killed | Service, group and listeners removed |
| Fresh launch after crash | DNS replies and scoped shutdown passed |
| Invalid configuration | Startup refused and resources collected |
| Explicit scoped shutdown | Only the owned service stopped |
| Functional queries | Filtering, forwarding and upstream outage/recovery passed |

The first batch records readiness in each case; the second includes 237 detailed DNS assertions covering exact names, subdomains, lookalikes, case handling, A/AAAA/TXT, UDP/TCP and IPv4/IPv6 loopback. These are synthetic checks, not a capture or classification of all TV traffic. The launch-client test does not simulate a physical PC/network disconnection.

## Real routing inverse, isolated network

A pinned namespace must differ from the diagnostic thread and PID 1, contain only loopback and have no default route. Every native firewall command checks that identity again inside the target namespace. Queries run on a dedicated thread that must restore its original namespace. A deliberately wrong identity is refused before mutation. [Linux network namespaces](https://man7.org/linux/man-pages/man7/network_namespaces.7.html) separate the relevant interfaces, routes, firewall state and sockets.

The test redirects IPv4 UDP/TCP port 53 to a restricted resolver. An owned cgroup exemption prevents the resolver's own upstream query from looping. IPv6 NAT is unavailable on the tested firmware, so the alternative explicitly rejects IPv6 port-53 DNS. It does **not** claim IPv6 redirection. The separate native NSS matrix below establishes fallback for its lookup clients, not for every application. Here UDP rejection returns access-denied and TCP rejection returns connection-refused; queries succeed before and after the rule.

The supervised inverse passed 60 DNS assertions across direct-worker, baseline, partial activation, active filtering, restored DNS and fault-recovery phases. Native checks also passed:

- Empty/partly populated chain recovery and repeated inverse.
- Preservation of an unrelated chain, including a similar name.
- Refusal of an unexpected owned-chain rule without changing it.
- Recovery after each of four inverse interruption points.
- Exact original IPv4/IPv6 table listings and DNS replies after recovery.

Recovery deletes only exact owned hooks/rules and then empty owned chains. It never flushes a table or chain. Discarding a failed test namespace is cleanup, **not** a passing native inverse. The old DNS-setting transaction model remains available, but the preferred design leaves Samsung's DNS configuration intact: removing interception returns requests to its existing resolver policy without overwriting a later legitimate DNS change.

## Independent recovery and deployment gates

A separate manager-owned inverse is armed before interception. Its three-second deadline runs a post-stop recovery command in the isolated namespace. The helper has only NET_ADMIN and NET_RAW capabilities, no-new-privileges and the same read-only system protections. The stock legacy firewall tool opens a raw control socket, which requires NET_RAW; see its [version-matched source](https://www.netfilter.org/projects/iptables/files/iptables-1.6.1.tar.bz2) and [raw-socket capability requirement](https://man7.org/linux/man-pages/man7/raw.7.html). The resolver itself retains no active capabilities.

The inverse is supplied through the manager's standard-input data, avoiding access to staging files or extra filesystem capabilities. Recovery results use an owned, root-only runtime directory. The only additional writable path is the existing firewall lock file; its content must remain unchanged. Namespace and exact rule ownership checks run before mutation.

An owned parent slice keeps the cgroup exemption valid until recovery completes. This matters on the tested legacy firewall: when a rule names a worker cgroup that has disappeared, even deleting another rule can fail because the whole table is revalidated. The candidate resolver, recovery helpers and rule-installing controller belong to this temporary slice. It is removed after its members have ended and its rules are gone.

| Independent fault | Native result |
| --- | --- |
| Resolver killed after interception | Deadline inverse restored both table listings and original DNS responses |
| Resolver frozen and waiting launch client killed | Deadline inverse restored DNS while the worker remained frozen |

Each case passed 28 DNS assertions across baseline, interception and recovery, without the controller calling the inverse. The generated shell inverse also passed 29 local synthetic cases, including all ten command interruptions and retries, unknown/duplicate/foreign rules, namespace mismatch, unrelated-rule preservation, and failed or empty rule listings. A successful script exit alone is insufficient: stderr, exact table restoration and working DNS must also pass.

The original cases above needed observer cleanup of the empty slice and receipt directory. A separate test now creates the slice with `StopWhenUnneeded=yes` and uses automatically removed runtime directories. The slice and service are submitted together through the manager's transient-unit API; no persistent unit file is created. See the version-matched [unit controls](https://github.com/systemd/systemd/blob/v244/man/systemd.unit.xml) and [transient-unit implementation](https://github.com/systemd/systemd/blob/v244/src/core/dbus-manager.c).

The on-TV rule-installing controller is then killed after activation. It has no inverse trap. An enforced read-only observer watches the primary recovery deadline restore DNS, then a separately armed backup repeats the inverse. The case passed 36 DNS assertions, exact table restoration, both helper results and automatic native artifact cleanup. The primary and backup deadlines are three and five seconds; resolver workers have eight-second lifetimes. The result does not depend on the observer stopping services or deleting native receipt directories.

That case establishes rule-controller loss while a diagnostic observer remains. The separate complete-agent-loss test below removes the observer too. Neither case simulates physical PC/network disconnection, manager/kernel failure or power loss.

A combined fault test then interrupted the primary inverse after its IPv6 work, leaving IPv4 filtering active in the isolated network. The independent backup finished recovery with 28 DNS assertions, both tables restored and automatic native cleanup. The primary failure is recorded explicitly; it is not relabeled as a successful primary inverse.

## Complete diagnostic-agent loss

The diagnostic root agent arms independent helpers, returns an authenticated
pending receipt, then kills its own pinned process with SIGKILL. Its callback
closes; no agent finalizer or observer inverse runs. A manager-owned witness has
already dropped its supplementary groups, UID/GID and active capabilities. It
observes the original agent's death through a pinned process descriptor and
checks DNS at independently established monotonic deadlines.

In the combined fault case, the primary inverse deliberately exits with status
75 after restoring IPv6. The witness verifies that IPv4 remains filtered, then
verifies both families after the backup completes. Its 24 UDP/TCP assertions,
exact table receipts, signal exit and process ledger passed. Services, cgroups,
slice and runtime directories disappear independently; later SDK reconciliation
removes only the owned upload. A separate root read confirms unchanged host DNS,
firewall and protected-file state across the loss.

The witness can perform fixed queries and observe process death; it cannot
alter firewall rules or control services. Its startup bounding set retains only
SETUID/SETGID, with no active capabilities after the drop. Existing security
labels are selected without changing platform policy or stock file attributes.
Known paired runtime GC trailers are validated separately from query evidence;
unexpected, interleaved or incomplete logs fail verification.

This proves agent/callback loss and backup completion in an isolated network.
It does not establish recovery from PID 1, kernel, physical network or power
failure, or qualify interception of ordinary TV applications.

## Client-scoped recovery

A further isolated trial matches only a newly created client cgroup at the
OUTPUT hook. The resolver and nonmember clients remain outside that match.
Sixteen baseline/nonmember DNS assertions pass. After complete diagnostic-agent
loss, a restricted witness passes 24 assertions covering active filtering,
partial primary recovery and full backup recovery. Both helpers hold the client
group through their inverse; temporary groups, services and files are removed
automatically. A separate readback confirms host DNS/firewall preservation.

The exact generated scripts also pass 48 synthetic activation/inverse cases,
including every mutation interruption, duplicate/foreign rules, unrelated
concurrent rules, quoted paths and wrong-namespace refusal. The
[kernel cgroup matcher](https://github.com/torvalds/linux/blob/v5.4/net/netfilter/xt_cgroup.c)
matches descendant socket groups, so no ordinary application is moved into the
test group. These results qualify scoped recovery only in the isolated network;
live-host interception, ordinary-app compatibility and persistent deployment
remain unqualified.

## Existing connections and real DNS compatibility

Restoring rules is not enough to claim seamless connection recovery. Two successive queries on the same TCP connection succeeded before the inverse, both against the original resolver and the active candidate. After recovery, an existing UDP socket reached the original resolver, but the held TCP connection was reset. New UDP/TCP queries succeeded. These results do not prove that every native DNS client retries correctly, or that connection tracking on the live network behaves identically.

Netfilter applies a connection's NAT decision to subsequent packets; see the [NAT documentation](https://www.netfilter.org/documentation/HOWTO/NAT-HOWTO-5.html). DNS clients should retry unanswered queries after a TCP close, but that recommendation is not evidence of a particular application's behavior; see [RFC 7766, teardown](https://www.rfc-editor.org/rfc/rfc7766.html#section-6.2.4). No global connection-state flush, timeout change or module loading was used. Ordinary-client interception remains withheld while compatibility beyond the tested native resolver paths is unresolved.

A separate test exercises the stock native libc resolver with a retained TCP
connection. Eight native calls pass: baseline reuse, filtered reuse, then the
first call after each inverse and a repeat. The first post-inverse call succeeds
and uses a new socket; later calls reuse it. This establishes native reconnect
for that exact resolver path. The diagnostic process is privileged, and the raw
managed TCP reset remains an explicit result. This is not universal client or
live-network recovery qualification. See the version-matched
[glibc resolver source](https://github.com/bminor/glibc/blob/glibc-2.30/resolv/res_send.c).

A 12-case native NSS matrix also passes UDP/TCP lookups with IPv6-first
resolution, unavailable IPv6 followed by IPv4, unavailable IPv4 followed by
IPv6, active IPv6 rejection with IPv4 fallback, blocked names, and restored
resolution. Each stock lookup client has its own read-only resolver-file bind
inside the isolated test network. Host resolver settings remain intact. These
clients have no active capabilities but retain 20 stock supplementary groups;
they establish functional coverage, not production-client confinement. The
separate explicit-drop managed witness has empty groups.

Two bounded receive-only samples, lasting four and six seconds, observed real requests from the native resolver lookup probe and their replies. Both samples contained two IPv4 queries and two replies, with **zero background-app queries observed**. Each replayed A and AAAA queries over UDP and TCP through the restricted temporary resolver using the existing configured upstreams. All four replay checks and eight separate blocking checks passed in each run; native lookups before and after also succeeded.

This is native resolver traffic, not simulated upstream data, but it is a narrow probe. The replay does not establish background-app compatibility, IPv6 upstream use, connection-state recovery or compatibility with all native functions. Native fallback and reconnect coverage come from the separate tests above. No ordinary client was redirected. Packet contents and query names were not retained in the report; private per-name hashes are not published. No new upstream provider was selected.

Production still needs ordinary-client and live-network compatibility, authenticated root-owned persistent recovery material, serialization against concurrent network changes, an explicit upstream and failure policy, a qualified startup mechanism, and separately supervised standby/cold-boot/AC-loss tests. Isolated controller loss and the tested native retry paths no longer count as untested, but they do not satisfy those broader gates. An availability-first inverse restores original DNS access and therefore stops filtering. A privacy-first outage policy is a different choice. Do not silently select an external fallback resolver.

Eight further cases use the stock native lookup program through the temporary
filter with the existing upstreams in their configured order. Allowed and
blocked names pass over both IPv4 and IPv6 DNS transport, using UDP and TCP.
Each client has a private read-only resolver-file view. A restricted entry
process explicitly clears supplementary groups and active capabilities before
executing the stock lookup program; the clients have no firewall operation.
The loopback-only resolver expires independently after 12 seconds and each
client after 1.5 seconds. Host DNS/firewall preservation and automatic cleanup
passed. This advances real native-function compatibility without redirecting
ordinary Samsung apps or proving that the upstream leg used IPv6.

Encrypted DNS, hard-coded addresses, alternate DNS ports and unknown telemetry endpoints remain outside this port-53 trial. A working DNS filter is not proof that every tracking path is blocked. A reliable external LAN resolver or suitable router remains an alternative.

## Offline evidence checks

```text
python scripts/verify_dns_confinement.py --deadline /absolute/private/deadline-result.json --recovery /absolute/private/recovery-result.json --routing /absolute/private/routing-result.json
python scripts/verify_dns_confinement.py --deadline /absolute/private/deadline-result.json --recovery /absolute/private/recovery-result.json --independent-crash /absolute/private/crash-result.json --independent-frozen-client /absolute/private/frozen-client-result.json
python scripts/verify_dns_controller_loss.py --controller /absolute/private/controller-result.json --partial-primary /absolute/private/partial-result.json --flows /absolute/private/flow-result.json --compatibility /absolute/private/replay-result.json --compatibility-version 2
python scripts/verify_dns_native_retry.py /absolute/private/native-retry-result.json
python scripts/verify_dns_nss.py /absolute/private/native-nss-result.json
python scripts/verify_dns_native_live.py /absolute/private/native-live-result.json
python scripts/verify_dns_session_loss.py --loss /absolute/private/loss-result.json --after /absolute/private/later-network-read.json --launcher-log /absolute/private/launcher.log --agent-status /absolute/private/root-agent.status
python scripts/verify_dns_session_loss.py --owned-clients --loss /absolute/private/scoped-loss-result.json --after /absolute/private/later-network-read.json --launcher-log /absolute/private/launcher.log --agent-status /absolute/private/root-agent.status
python scripts/simulate_dns_recovery.py
```

These tools never contact a TV. The checker requires complete native/controller outcomes, exact case/query coverage, effective worker restrictions, owned process identities, network preservation and cleanup. It prints aggregates only and keeps production qualification false. It checks consistency, not authenticity, freshness or arbitrary logs. Operational payloads, raw receipts and firmware binaries stay private.

The earlier [manager checker](../scripts/verify_dns_manager.py) retains the original debug-mode matrix's explicit group limitation. The earlier [trial checker](../scripts/verify_dns_trial.py) retains its parent-death-signal failure and signature-admission refusal. Those separate failures are not rewritten as passes by the stronger design.
