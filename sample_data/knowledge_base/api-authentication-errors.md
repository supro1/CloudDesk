---
title: Troubleshooting API authentication failures
category: api_failure
tags: [api, authentication, token, credentials]
summary: Diagnose API authorization errors without exposing credentials.
---
# Troubleshooting API authentication failures

First distinguish an authentication failure from an authorization failure. Confirm the endpoint, HTTP method, response code, time of the request, and request ID. Never ask the customer to paste an API key, bearer token, or secret into a ticket.

## Check the client configuration

Ask the customer to confirm that the integration is using the intended credential, that it has not been revoked or rotated, and that it is sent using the documented authorization header. Check for whitespace, environment mix-ups, and a token that has expired. The customer should rotate credentials through the secure settings interface if they may have been exposed.

## Check access scope

If authentication succeeds but the operation is denied, verify that the credential's permissions cover the requested resource and action. Ask an authorized workspace administrator to make any access change. If a correctly configured credential continues to fail, escalate with a redacted request and its request ID.
