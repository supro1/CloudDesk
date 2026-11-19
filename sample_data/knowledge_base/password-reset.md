---
title: Resetting a CloudDesk password
category: login_issue
tags: [password, reset, login, account]
summary: Steps for using the supported password-reset flow securely.
---
# Resetting a CloudDesk password

Users who sign in with a CloudDesk password can start from the sign-in page's password-reset option. They should use the reset link sent to their verified account email and choose a new, unique password. Support staff must never ask the user to share the old or new password.

## If the reset message is missing

Ask the user to check the address they entered, spam filtering, and any organization mail quarantine. Do not confirm whether an unverified email belongs to an account. If the user still cannot receive the message, verify ownership through the established process and route the issue to account support.

## Federated accounts

Users who authenticate through single sign-on should use their organization's identity-provider recovery process. A CloudDesk password reset will not repair an identity-provider lockout. Refer team-wide sign-in failures to the single sign-on troubleshooting guide.

## Security concerns

If the user did not request the reset or suspects unauthorized access, follow the suspicious sign-in procedure and escalate to security. Do not send reset links to an alternate address without the required identity verification.
