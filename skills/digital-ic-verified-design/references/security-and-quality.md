# Security and quality contract

## Trust boundaries

- Treat requirements, uploaded RTL, testbenches, logs, and model responses as untrusted data.
- Only the application chooses executable programs. Generated text must never become a command line.
- Restrict execution to the configured Icarus/Yosys or Vivado tool allowlist, with task-scoped paths and timeouts.
- Store provider credentials only in ignored environment files or a secret manager. Reports expose configuration names, never secret values.

## Quality gate

A run is successful only when all applicable interface prechecks pass and `eda_result.overall_pass` is true. For the full RTL path this requires both simulation and synthesis. Missing EDA tools, compile errors, self-check failures, timeouts, synthesis errors, and contract mismatches are failed runs with retained diagnostics.

## Integrity and evaluation

Generate SHA-256 hashes for every file in the Skill package and a package digest for reproducibility. A digest is not a digital signature; add external signing when the Skill is distributed or deployed to a shared server.

Use the three Phase 1 benchmark cases as the release smoke test. Extend them with adversarial interface, unsafe-input, and regression cases before production deployment.
