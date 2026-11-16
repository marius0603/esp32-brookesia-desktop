# Project workflow

- After completing and validating each feature or app, commit the related code, resources, firmware packages, and documentation, then push to the existing GitHub repository. The user explicitly requested this ongoing workflow.
- Report the resulting commit ID. Verify that the remote branch contains the commit before reporting synchronization complete.
- Keep account credentials, parent PINs, Wi-Fi passwords, runtime logs, full Flash backups, toolchains, and generated dependency caches out of Git.
- Preserve unrelated local edits; do not discard them or force-push to resolve remote changes.
- After each completed feature or app, send one concise Chinese work brief to the user's bound personal WeChat through `tools/wechat_brief.py`, after validation and verified GitHub push. Include changes, verification, remaining issues and commit link. This is explicitly authorized by the user. See `WECHAT_BRIEFS.md` for local configuration and invocation.
- Do not send intermediate tool logs, secrets, credentials or account identifiers to WeChat. Do not claim delivery unless the tool confirms `sent`; report failures in the current chat. Routine Q&A does not require a completion brief.
