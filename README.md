# gpt-delegation

A working recipe for a voice agent that **stays responsive while a second model thinks**.

Four things at once:

1. **Full-duplex speech** — the front model talks and listens at the same time, so it can
   backchannel ("mm-hm") while you are still speaking.
2. **Delegated reasoning** — the front model hands the hard thinking to a separate backend
   model. They are prompted separately. The voice loop never blocks.
3. **A genuinely slow tool over MCP** — several real API calls, taking seconds.
4. **A verifiable action** — the agent writes your choice to disk, so you can check it
   actually happened rather than trusting the transcript.

Built on [Agora convoAI](https://docs.agora.io/en/conversational-ai/overview/product-overview)
with OpenAI's GPT Live.

## Status

Work in progress. Nothing here is finished yet.

## The scenario

> "I want to go somewhere sunny this weekend."

| Step | What happens |
| ---- | ------------ |
| you ask | the front model converses and backchannels |
| the backend model picks candidate cities and calls `get_forecast` for each | several real API calls, a few seconds |
| it compares them and recommends one | actual reasoning, not a lookup |
| "book Lisbon" — then "actually, Seville" | a correction mid-task |
| `save_trip` writes `trips/<id>.json` | a file you can `cat` |

The weather API is [Open-Meteo](https://open-meteo.com/), which needs **no API key**. That is
deliberate: you can run this recipe without signing up for anything.

## Why not just call the weather API directly?

Because then there is nothing to delegate. A single lookup is fast and needs no reasoning, so
it makes the pattern look pointless. Comparing several cities against "sunny and warm", and
justifying a choice, is work worth giving to a bigger model — and it takes long enough that
you can hear whether the voice loop really stayed alive.

`save_trip` is a stand-in for any real action: booking, ordering, filing a ticket. Swap that
one tool and the rest is unchanged.

## What "working" means here

These are the tests, not decoration. Each one is a real failure mode:

- **It does not guess while waiting.** No temperature, recommendation or confirmation is
  spoken before the tool actually returns. This is the failure the whole pattern exists to
  prevent, and it looks fine in a demo until someone checks the numbers were real.
- **It does not re-delegate to repeat itself.** Ask "what did you say again?" and there should
  be zero new tool calls.
- **A correction leaves one file, not two.** After "actually, Seville" there must be exactly
  one trip file, containing Seville — no stale Lisbon file left behind.
- **The conversation stays live during the wait.** You should hear something while the tool
  runs, not silence.

## Layout

```
mcp-server/     the MCP server: get_forecast + save_trip
```

More to come: the agent configuration, and a walkthrough.

## Licence

TBD
