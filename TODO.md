# Modal Portal Fix TODO

- [x] Inspect and update `frontend/src/app/layout.tsx` to include `#modal-root` directly under `<body>`.
- [x] Refactor `InsightModal` in `frontend/src/components/analytics/PremiumDashboard.tsx` to use React portal rendering to `#modal-root`.
- [x] Apply hardened modal overlay/modal box/modal body fixed-position styles and internal scrolling behavior.
- [x] Add body scroll lock when modal is open and restore on close.
- [x] Add temporary debug border (`2px solid red`) to validate true fullscreen overlay behavior.
- [ ] Mark completed tasks and run frontend lint/build validation.
