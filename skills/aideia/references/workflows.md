# Aideia workflow examples

Use these examples when they match the user's request. Tool availability depends on the connected account and its permissions. Discover the applicable tools and use their current descriptions and schemas; the examples do not promise that a particular capability is exposed.

## Read recent sleep or activity

Example request: “How did I sleep last night?”

Find the sleep capability appropriate to the requested day. Check the returned date and freshness before describing it as the most recent night. A current snapshot can still contain an older record if a provider has not supplied a new one.

Explain the available observations in ordinary language, including their dates and units where useful. If a metric is missing, say so. Do not infer a zero value or a diagnosis. For an activity question, likewise distinguish recorded activity from a complete account of everything the user did.

Example response shape:

> The latest sleep record covers [returned period]. It reports [supported observations]. [Relevant measure or newer period] is unavailable, so I cannot assess that part.

The bracketed text describes how to use a real result; it is not sample user data to send to a tool.

## Compare several days

Example request: “Compare my sleep over the past three nights with my activity.”

Resolve the relevant days from user-local dates. Use closed-day daily records for historical comparisons and current state for any still-open day. If only a broader summary is available, explain that it cannot support the requested daily detail.

Align records by their documented date conventions, particularly sleep that crosses midnight. Compare only metrics that are present and meaningfully comparable. Keep missing days visible instead of excluding them silently or treating them as zero.

A compact date-by-date comparison is often useful. Follow it with the observations the data supports. If discussing a possible relationship between activity and sleep, distinguish that interpretation from measured facts and avoid assigning a cause from a few correlated records.

## Ask about the schedule

Example request: “Am I free this afternoon?”

Check the tool's supported date range, timezone, coverage, and availability indicators. A tool limited to today's timed commitments cannot answer tomorrow's schedule or prove that unreported commitments do not exist.

Distinguish “no commitments returned for this interval” from “reliable coverage establishes a free interval.” If the source is stale or availability is unknown, describe the limitation rather than promising free time.

## Save a journal entry

Example request: “Save this as my journal entry: [the user's text].”

Use the journal-writing operation only if permitted. Preserve the supplied journal text exactly and keep operational explanations outside the entry. Use an explicit date if the user supplies one; otherwise follow the tool's documented local-day default.

If the request does not clearly identify which text to save, or a required sensitive-content confirmation has not been supplied, clarify the relevant point. Do not turn a request to discuss a feeling into permission to save the conversation as a journal entry.

After a successful result, confirm the saved entry and day only to the extent established by that result. If the response is lost, check through an appropriate permitted read if available instead of automatically submitting the entry twice.

## Record an activity or manage a reminder

Example requests: “Record the walk I just finished” or “Remind me to call the dentist tomorrow morning.”

Inspect the relevant operation's required fields and defaults. For an activity, obtain the real timing or duration when needed. For a reminder, use the user's local date context and a documented default if one actually resolves the requested time; otherwise ask what time they mean. Do not invent an exact time solely to make the call valid.

For changes or cancellation, identify the intended existing record. If several records could match, ask which one before changing any. Report the action the tool accepted, rather than promising a notification has already been delivered.

## When part of a request is unavailable

Example request: “Review my recent sleep and save a journal reflection.”

Read access and write access are separate. Complete independent authorized parts where useful, while clearly identifying what is unavailable. Do not claim a journal entry was saved because a read succeeded, and do not rewrite the user's journal text as an inferred reflection without their request.

If a tool returns a partial outcome, preserve that distinction. In particular, accepted storage, downstream synchronization, and delivery or playback are different results. Report only what the returned evidence establishes.
