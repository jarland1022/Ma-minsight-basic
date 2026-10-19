# Reddit value posts — MA-MinSight

Read each sub’s rules. Lead with experience; soft-disclose your project once.

## r/sysadmin or r/netsec — value angle

**Title:** How do you keep Wazuh (or any SIEM) queues from eating the week?

**Body (template):**

```text
Curious how other teams handle this:

We run Wazuh-class detection. Volume is fine for “coverage,” awful for “who looks at this.”
Same host/rule loops, juniors can’t decode rule IDs, seniors eyeball until burnout.

Things that didn’t work for us long-term:
• piling more correlation rules
• dumping alerts into ChatGPT with no audit trail
• hiring “one analyst” who becomes a ticket black hole

What helped more: a digestion layer — ingest, triage, aggregate into fewer events, then decide.

We’ve open-sourced a Community edition of that approach (self-hosted). Happy to share the repo if useful; mostly interested in how you structure ownership of the queue.

(Disclosure: I work on MA-MinSight.)
```

If asked for the link:

```text
https://github.com/jarland1022/Ma-minsight-basic
```

## r/Wazuh

**Title:** Alert triage / aggregation on top of Wazuh — what’s your stack?

Keep it conversational; offer Community only when asked.

## Don’t

- Title with price or “hire me”  
- Multi-sub spam the same day  
- Argue in comment wars  
