# Cross-cutting tests

This directory is for tests that span modules or drive the system from outside:

- integration flows that touch more than one domain module
- permission-matrix tests once roles exist (Phase 2)
- end-to-end browser tests once there is a workflow to drive (Phase 4 onward)
- migration rehearsal checks before staging release (Phase 12)

Unit and per-module tests live beside the code in `backend/apps/<module>/tests/`.

Nothing exists here yet by design: Phase 1 has no business workflow to test end to end, and writing scenario tests before the workflows are signed off would test assumptions rather than behaviour.
