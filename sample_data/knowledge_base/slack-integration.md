---
title: Troubleshooting the Slack integration
category: integration
tags: [slack, integration, notifications, workspace]
summary: Diagnose a disconnected Slack integration or missing notifications.
---
# Troubleshooting the Slack integration

Confirm which CloudDesk workspace is connected, which Slack workspace is expected, and whether the integration reports as connected. Ask when notifications last worked and whether all events or only a particular channel are affected.

## Check connection and permissions

An authorized administrator can review the integration status and its requested permissions in the connected-workspace settings. Confirm that the app remains installed and that the target channel is available to it. Do not ask for a Slack token or attempt to reconnect using credentials shared in a ticket.

## Check notification settings

Verify that the relevant event is enabled and directed to the expected channel. Send a test notification only if the product provides an approved test action. If the integration was unexpectedly removed or permissions changed, escalate rather than broadening access.

## Collect diagnostics

Record the event type, approximate time, affected channel name, and any request ID. Redact message contents and secrets. If the connection and settings look correct but delivery still fails, send these details to integration support.
