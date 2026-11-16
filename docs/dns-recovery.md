# Isolated DNS recovery

The restricted resolver, native routing inverse and automatic recovery after loss of the rule-installing controller have passed isolated TV tests. Native DNS lookups and a temporary resolver using the TV's existing upstreams also passed a limited compatibility replay. **Permanent DNS filtering remains unqualified.** Routing mutations occur only inside a separately verified, loopback-only network namespace. The TV's live DNS and firewall are unchanged.

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

The test redirects IPv4 UDP/TCP port 53 to a restricted resolver. An owned cgroup exemption prevents the resolver's own upstream query from looping. IPv6 NAT is unavailable on the tested firmware, so the alternative explicitly rejects IPv6 port-53 DNS. It does **not** claim IPv6 redirection or successful native-application fallback. Here UDP rejection returns access-denied and TCP rejection returns connection-refused; queries succeed before and after the rule.

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

This proves loss of the on-TV rule controller. It does **not** simulate termination of the entire diagnostic session, physical PC/network disconnection, manager/kernel failure or power loss. The diagnostic observer remains available to read evidence, and SDK upload cleanup still occurs afterward.

A combined fault test then interrupted the primary inverse after its IPv6 work, leaving IPv4 filtering active in the isolated network. The independent backup finished recovery with 28 DNS assertions, both tables restored and automatic native cleanup. The primary failure is recorded explicitly; it is not relabeled as a successful primary inverse.

## Existing connections and real DNS compatibility

Restoring rules is not enough to claim seamless connection recovery. Two successive queries on the same TCP connection succeeded before the inverse, both against the original resolver and the active candidate. After recovery, an existing UDP socket reached the original resolver, but the held TCP connection was reset. New UDP/TCP queries succeeded. These results do not prove that every native DNS client retries correctly, or that connection tracking on the live network behaves identically.

Netfilter applies a connection's NAT decision to subsequent packets; see the [NAT documentation](https://www.netfilter.org/documentation/HOWTO/NAT-HOWTO-5.html). DNS clients should retry unanswered queries after a TCP close, but that recommendation is not evidence of a particular application's behavior; see [RFC 7766, teardown](https://www.rfc-editor.org/rfc/rfc7766.html#section-6.2.4). No global connection-state flush, timeout change or module loading was used. Ordinary-client interception is withheld until reconnect or drain behavior is qualified.

Two bounded receive-only samples, lasting four and six seconds, observed real requests from the native resolver lookup probe and their replies. Both samples contained two IPv4 queries and two replies, with **zero background-app queries observed**. Each replayed A and AAAA queries over UDP and TCP through the restricted temporary resolver using the existing configured upstreams. All four replay checks and eight separate blocking checks passed in each run; native lookups before and after also succeeded.

This is native resolver traffic, not simulated upstream data, but it is a narrow probe. It does not establish background-app compatibility, IPv6 upstream use, native IPv6 rejection fallback, connection-state recovery or compatibility with all native functions. No ordinary client was redirected. Packet contents and query names were not retained in the report; private per-name hashes are not published. No new upstream provider was selected.

Production still needs complete diagnostic-session-loss qualification, existing-flow recovery, authenticated root-owned recovery material, serialization against concurrent network changes, an explicit upstream and failure policy, native-function compatibility, and separately supervised standby/cold-boot/AC-loss tests. An availability-first inverse restores original DNS access and therefore stops filtering. A privacy-first outage policy is a different choice. Do not silently select an external fallback resolver.

Encrypted DNS, hard-coded addresses, alternate DNS ports and unknown telemetry endpoints remain outside this port-53 trial. A working DNS filter is not proof that every tracking path is blocked. A reliable external LAN resolver or suitable router remains an alternative.

## Offline evidence checks

```text
python scripts/verify_dns_confinement.py --deadline /absolute/private/deadline-result.json --recovery /absolute/private/recovery-result.json --routing /absolute/private/routing-result.json
python scripts/verify_dns_confinement.py --deadline /absolute/private/deadline-result.json --recovery /absolute/private/recovery-result.json --independent-crash /absolute/private/crash-result.json --independent-frozen-client /absolute/private/frozen-client-result.json
python scripts/verify_dns_controller_loss.py --controller /absolute/private/controller-result.json --partial-primary /absolute/private/partial-result.json --flows /absolute/private/flow-result.json --compatibility /absolute/private/replay-result.json --compatibility-version 2
python scripts/simulate_dns_recovery.py
```

These tools never contact a TV. The checker requires complete native/controller outcomes, exact case/query coverage, effective worker restrictions, owned process identities, network preservation and cleanup. It prints aggregates only and keeps production qualification false. It checks consistency, not authenticity, freshness or arbitrary logs. Operational payloads, raw receipts and firmware binaries stay private.

The earlier [manager checker](../scripts/verify_dns_manager.py) retains the original debug-mode matrix's explicit group limitation. The earlier [trial checker](../scripts/verify_dns_trial.py) retains its parent-death-signal failure and signature-admission refusal. Those separate failures are not rewritten as passes by the stronger design.
