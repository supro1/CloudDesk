---
title: Troubleshooting API rate limits
category: api_failure
tags: [api, "429", rate-limit, retry]
summary: Diagnose HTTP 429 responses and make API clients retry safely.
---
# Troubleshooting API rate limits

An HTTP 429 response means the request was rate-limited. Identify the affected API operation, approximate request rate, time window, and whether retries are multiplying the traffic. Do not include an API key or bearer token in a support ticket.

## Reduce repeated requests

Use exponential backoff with jitter and respect a `Retry-After` header when the response provides one. Avoid immediate retry loops, synchronize scheduled jobs where possible, and cache data that does not need to be fetched repeatedly. Check whether several workers share the same integration credential and therefore the same limit.

## Investigate a continuing issue

Compare the request IDs and timestamps for successful and limited calls. Confirm the applicable plan and documented API limits before advising a change. If a normal workload is unexpectedly throttled, provide safe request details to API support for review; do not claim a higher limit is available unless confirmed.
