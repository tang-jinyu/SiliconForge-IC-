Learned FPGA failure memory for prompt injection.
Updated at: 2026-09-29T10:05:39.002359+00:00
Tracked failure observations: 14

Top recurring failure tags:
- runtime_exception: 5
- interface_contract_mismatch: 4
- unknown_fpga_failure: 4
- simulation_self_check_failure: 1

Top skill categories needing reinforcement:
- Repair Root-Cause Locality: 11
- Interface Contract and Handshake Discipline: 8
- Arithmetic Width and Signedness Discipline: 5
- External Stimulus and Self-Checking Testbench: 4
- Resource Inference and Local Helper Templates: 4

Top semantic fingerprints:
- handshake_contract_surface: 6
- error_path_determinism: 4
- public_serial_stimulus: 4
- ram_fifo_inference: 4
- carry_borrow_path: 3

Recent corrective guardrails:
- Stabilize the first runtime exception and preserve partial artifacts for diagnosis before widening the repair scope.
- Define and preserve cycle-level handshake meaning before adjusting local control logic.
- Make byte ordering explicit across interface packing, storage layout, and visible result buses.
- Stimulate serial ingress through the exposed pins and timing model rather than invented helper wires in the testbench.
- Keep storage logic inference-friendly and local instead of hiding it behind undefined wrappers or ambiguous read-write behavior.
