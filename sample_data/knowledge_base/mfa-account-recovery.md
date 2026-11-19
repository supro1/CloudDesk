---
title: Recovering access after multi-factor authentication problems
category: login_issue
tags: [mfa, login, recovery, account]
summary: Safe troubleshooting for users locked out by multi-factor authentication.
---
# Recovering access after multi-factor authentication problems

Start by confirming the account email and workspace through the established support verification process. Never ask the user to send a password, one-time code, recovery code, or authenticator seed in a ticket.

## Check the sign-in method

Confirm that the user is signing in with the method configured for their workspace. Ask them to verify the device clock, network connection, and whether their authenticator app is available. If they recently changed devices, use the workspace's documented recovery process rather than bypassing MFA.

## Locked accounts

If repeated attempts caused a temporary lock, stop repeated retries and follow the account recovery procedure available to authorized support staff. Verify account ownership before making any account-level change. Escalate when ownership cannot be verified or the recovery path is unavailable.

## Suspected compromise

If the user did not initiate the sign-in attempts, treat the report as a security concern. Do not reset MFA or disclose account details before verification. Escalate the case to the security team and include only the verified account, approximate times, and safe error details.
