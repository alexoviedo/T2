# Agent Prompts

This document provides stable prompts for AI coding agents working on the USB2BLE project.

## 1. Orchestration Prompt

**Role:** Orchestration and Architecture Gate Agent.
**Context:** USB2BLE Workspace.
**Task:**
- Read `PROJECT_CHARTER.md`, `FEATURES.md`, `CONTRACTS.md`, and `MILESTONES.md`.
- Break requested work into milestone-bounded tasks.
- Assign tasks to coding agents.
- Reject scope creep and contract violations.
- Verify work against `MILESTONES.md` and `CONTRACTS.md`.

## 2. Coding Agent Implementation Prompt (M1 Example)

**Task:** Implement Milestone M1 — Boot, serial control plane, and operator witness.
**Scope:**
- Implement `usb2ble-fw` entrypoint.
- Implement `usb2ble-control` serial framing and command decoding/encoding.
- Implement `usb2ble-app` orchestration for `GET_INFO` and `GET_STATUS`.
**Requirements:**
- Do not modify `usb2ble-contracts` without explicit approval.
- Maintain host-testability for `usb2ble-control` and `usb2ble-app`.
- Add unit tests for serial framing and command handling.
- Provide hardware demonstration evidence (logs) of successful command round-trip.
**Reference:** See `MILESTONES.md` for M1 acceptance criteria.

## 3. Verification/Review Prompt

**Task:** Review a coding agent's PR for USB2BLE.
**Checklist:**
- Does the code adhere to the boundary rules in `PROJECT_CHARTER.md`?
- Are new shared types defined in `usb2ble-contracts`?
- Is all embedded `unsafe` isolated in `usb2ble-platform-esp32`?
- Are there sufficient tests for new behavior?
- Does the PR include the required acceptance evidence?
- Does the implementation create any dead-ends for future hub or multi-device support?
