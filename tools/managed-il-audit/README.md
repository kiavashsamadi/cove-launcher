# Managed IL audit

Read assembly identity, module MVID and each managed method body's digest without
loading or executing the inspected assembly.

Requires the .NET 6 SDK/runtime:

```sh
dotnet run --project tools/managed-il-audit -- stock-managed.dll old-cache.ni.dll new-cache.ni.dll
```

The output reports identity, machine, native-header size, body-read failures and
method-token/name/signature-to-IL-digest mappings. Compare identities, MVID and
all method mappings, and require zero body-read failures for an IL-equivalence
assessment. Generated native machine code can differ even when managed IL matches.
This tool does not authenticate a package, validate compiled machine code or prove
that a device's installer will accept it. Establish source provenance separately.
Keep original binaries and generated output local; only this generic tool is shared.
