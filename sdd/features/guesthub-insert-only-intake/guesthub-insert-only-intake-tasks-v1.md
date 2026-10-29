# GuestHub insert-only intake — Tasks v1

- [x] Trace the production 500 to the post-insert `access_requests` update.
- [x] Confirm production `service_role` has only `SELECT` and `INSERT` on `access_requests`.
- [x] Confirm request `d7431a55-ea12-4e3d-a4cb-ee94b07ec0df` is persisted as pending and has no review task.
- [x] Persist final status and review metadata with the initial insert.
- [x] Keep review-task creation best-effort; confirm production `service_role` has no `tasks` grants.
- [x] Run focused GuestHub service tests and inspect the diff.
- [x] Toni validates the change in development.
- [x] Commit and push the validated change to `development`.
- [ ] Review Preview and promote the exact reviewed SHA with `PROMOTE=FULL`.
- [ ] Retry the existing GuestHub request and confirm successful response plus one pending review task.
