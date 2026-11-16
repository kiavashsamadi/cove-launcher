# Preparing network privacy controls

The next useful boundary is control of the TV's outbound traffic. Removing more
packages is not a substitute: shared data, account and push services may have
other consumers, and a process name does not establish what it transmits.

## Choose the scope

| Option | Benefit | Required qualification |
| --- | --- | --- |
| TV-only Internet block, local access retained | Covers outbound traffic regardless of hostname | IPv4 and IPv6 rules, alternate interfaces, local control and a scoped undo |
| TV-only DNS filtering on an existing reliable LAN resolver | Reduces access to reviewed domains with less TV modification | Client identity, both address families, explicit upstream, resolver availability and compatibility |
| Resolver on the TV | Could filter without another host | Exact native behavior, privilege separation, loop prevention, independent recovery, firewall isolation and startup qualification |

The first option also removes Internet-dependent TV features. DNS filtering is
selective, but cannot guarantee coverage of cached or hard-coded addresses,
unknown hosts, alternate resolvers or encrypted DNS. A host that sleeps is not a
reliable default resolver. Per-client groups can separate a TV policy from other
clients; see the [Pi-hole group examples](https://docs.pi-hole.net/group_management/example/).

Start with independently reviewed ACR and advertising domains. Keep update
delivery, reporting and remote assistance in separate trials: those can affect
security maintenance, connectivity detection and support. Never block a shared
service parent merely because one of its subdomains is a candidate.

## Generate an offline review

Create a private UTF-8 JSON catalog using explicit groups. This synthetic example
contains no production blocklist:

```json
{
  "schema": 1,
  "groups": {
    "acr": ["measurement.example"],
    "advertising": ["advertising.example"]
  }
}
```

```text
python scripts/prepare_network_policy.py --catalog /absolute/private/catalog.json --groups acr advertising --output /absolute/checkout/.local/network-review
```

Supported group names are `acr`, `advertising`, `update_offers`,
`update_downloads`, `reporting` and `remote_assistance`. Selection is explicit;
there is no fallback list or implicit external DNS provider. Input is bounded,
domains are normalized, and malformed names, resolver-option injection,
duplicate JSON keys and known shared service parents are rejected. This is a
syntax and scope guard, not a complete public-suffix database or a determination
that every accepted domain is safe to block.

The output contains a hash manifest, review checklist and **lab-only** dnsmasq
configuration. It listens on loopback at a high port and refers only to a
separate synthetic loopback upstream. The tool does not start either server,
send queries, change DNS settings, install firewall rules or write startup files.
An output directory must be new and inside `.local`; an invalid candidate never
replaces a previous review. An interrupted output without its final manifest is
incomplete. Do not turn this lab file into a production configuration without
qualifying the missing deployment steps.

The generated `address` and `local` rules are paired to cover query types beyond
A/AAAA. The installed dnsmasq version must be tested: its documented `--test`
checks syntax and exits without starting a resolver, so a passing syntax result
does not prove response behavior. See the [dnsmasq manual](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html).

## Runtime trial and recovery

An isolated on-device trial passed 233 response checks using synthetic upstream
answers: exact names, subdomains, lookalikes, case handling, A/AAAA/TXT, UDP/TCP
and IPv4/IPv6 loopback. Upstream outage/recovery, resolver termination/restart
and the supervised worker deadline passed. The worker ran without effective,
permitted, inherited or ambient capabilities. Native DNS settings and both
firewall rule sets stayed unchanged; no real client traffic was redirected.

**Automatic supervisor-loss recovery did not pass.** The worker outlived its
supervisor, and a separate diagnostic guard had to terminate the exact owned
process. Linux clears the parent-death signal when executing a file with
capabilities; configuring that signal before execution is therefore insufficient
for the tested stock executable. See the
[Linux parent-death signal documentation](https://man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html).
A byte-identical temporary copy without capability attributes was also refused
by the TV's executable-signature enforcement. The original binary, its attributes
and security policies were preserved; the copy and other trial files were removed.

A separate [manager-owned recovery design](dns-recovery.md) passed ten isolated
lifecycle cases, including frozen-worker and launch-client loss, plus 239 DNS
response assertions. It avoids reliance on the earlier parent-death signal.
Supplementary-group minimization remains unresolved, and restoration of real
DNS routing is modeled rather than qualified on the TV. This qualifies isolated
containment, **not an unattended on-TV resolver**. Keep a reliable external LAN
resolver as an alternative. No trial resolver or filtering policy remains installed.

Private receipts can be assessed offline:

```text
python scripts/verify_dns_trial.py --functional /absolute/private/response-result.json --recovery /absolute/private/recovery-result.json --copy-attempt /absolute/private/copy-result.json
```

The copy-attempt argument is optional. A zero exit status means the records are
internally consistent, including a recognized, safely recovered failure; read
`automatic_parent_loss_recovery_passed` separately. The checker never reports
production DNS qualification or complete tracking prevention. It does not prove
receipt authenticity or freshness, and prints no private paths or raw records.

Before changing any resolver setting, test the isolated resolver with synthetic
upstream responses. Cover exact blocked names and subdomains, permitted names,
similar-looking suffixes, A/AAAA/other query types, UDP/TCP, upstream timeout,
process loss and restart. Confirm that blocked requests never reach the
upstream. Keep payloads and query logs private; production query logging should
not be enabled as an incidental default.

Record the current DNS values, existing rules and reachable recovery channel.
Prove recovery while the candidate resolver is unavailable. On-TV enforcement
needs owned rules for both IP families that preserve Samsung's existing rules
and exclude the resolver's own upstream traffic. Do not flush a firewall, set
global policy, replace a shared resolver or silently fall back to an unfiltered
provider. Clock synchronization and required local functions also need checks.

Deployment, persistence and reversal are separate qualifications. Reversal must
restore the recorded native DNS values and remove only owned redirection rules
before terminating a resolver that existing clients still depend on. Verify both
address families and local control afterward. Retain a recovery path independent
of the service being tested.
