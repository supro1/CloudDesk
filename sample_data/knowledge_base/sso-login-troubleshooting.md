---
title: Troubleshooting single sign-on
category: login_issue
tags: [sso, login, identity-provider, enterprise]
summary: Checks for diagnosing team-wide single sign-on failures.
---
# Troubleshooting single sign-on

Use these checks when a user or team cannot sign in through the configured identity provider. Ask for the affected workspace, approximate start time, and whether the issue affects one person or everyone. Never ask for a password, recovery code, or identity-provider secret.

## Check the scope

Confirm whether a direct sign-in or another workspace is affected. If the entire organization is blocked, check the service-status source and any active incident before changing account settings. Record the impact and escalate a confirmed broad outage to the appropriate support team.

## Verify the sign-in configuration

Ask the workspace administrator to confirm that the user is assigned to the CloudDesk application in the identity provider and that the expected sign-in method is selected. Compare the configured callback or entity details with the administrator's approved setup instructions. Do not request private keys or copy identity-provider credentials into a ticket.

## Collect safe diagnostics

Ask for the time of a failed attempt, the displayed error text, browser, and a request or correlation ID if one is shown. Do not request session cookies, access tokens, or a full network trace containing credentials. If the configuration appears correct and sign-in still fails, escalate with these safe details.
