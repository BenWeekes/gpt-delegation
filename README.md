# gpt-delegation

A working recipe for a voice agent that **stays responsive while a second model thinks**.

Five things at once:

1. **Full-duplex speech** — the front model talks and listens at the same time, so it can
   backchannel ("mm-hm") while you are still speaking.
2. **Delegated reasoning** — the front model hands the hard thinking to a separate backend
   model. They are prompted separately. The voice loop never blocks.
3. **A genuinely slow tool over MCP** — several real API calls, taking seconds.
4. **A verifiable action** — the agent writes your choice to disk, so you can check it
   actually happened rather than trusting the transcript.
5. **A talking avatar** — a face that keeps animating through the slow tool call instead of
   freezing. An avatar is the harshest test of the whole idea: it consumes the audio stream
   continuously, so any gap or premature end-of-turn is immediately visible.

Built on [Agora convoAI](https://docs.agora.io/en/conversational-ai/overview/product-overview)
with OpenAI's GPT Live. The front model runs full-duplex; a Responses model does the reasoning
and drives the tools; the tools are served over MCP by the small server in this repo.

For the architecture, how the agent stays responsive, how each claim was verified, and what the
latency looks like, see the **[walkthrough](docs/walkthrough.md)**. This README is the setup
guide.

## The scenario

> "I want to go somewhere sunny this weekend."

| Step | What happens |
| ---- | ------------ |
| you ask | the front model converses and backchannels |
| the backend model picks candidate cities and calls `get_forecast` for each | several real API calls, a few seconds |
| it compares them and recommends one | actual reasoning, not a lookup |
| "book Lisbon" — then "actually, Seville" | a correction mid-task |
| `save_trip` writes `output/<id>.json` | a file you can `cat` |

Then the same conversation again with an avatar attached, which is where premature turn
endings and audio gaps become obvious.

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
  spoken before the tool actually returns. The agent says a short filler while `get_forecast`
  runs and speaks the numbers only once they are back.
- **It does not re-delegate to repeat itself.** Ask "what did you say again?" and there are
  zero new tool calls — it repeats from memory.
- **A correction leaves one file, not two.** After "actually, Seville" there is exactly one
  file in `output/`, containing Seville. `save_trip` reuses the trip id.
- **The conversation stays live during the wait.** You hear something while the tool runs, not
  silence.
- **With an avatar, the face does not stop and restart** part-way through an answer, and no
  audio is dropped.

## Layout

```
mcp-server/
  server.py         the MCP server: get_forecast + save_trip
  requirements.txt
output/             where save_trip writes; gitignored, created on first run
```

## Run the MCP server

Python 3.10+.

```bash
cd mcp-server
pip install -r requirements.txt
python server.py            # binds 0.0.0.0:8787, MCP endpoint at /mcp
```

Environment:

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `PORT` | `8787` | Listen port. |
| `OUTPUT_DIR` | `../output` | Where `save_trip` writes. |

The convoAI agent connects to this server over the network, so run it on a host the agent can
reach, bind it to `0.0.0.0` (the default here), and use that host's address in the join request
below. `save_trip` writes to `output/` next to the server, so you can inspect what the agent
actually did.

The two tools:

- **`get_forecast(cities)`** — pass all candidate cities in one call. Returns Saturday's and
  Sunday's sky, max temperature, rain chance and sunshine hours for each, from Open-Meteo. It
  makes two live requests per city, so it takes a few seconds. That delay is the point of the
  recipe, not a bug to hide.
- **`save_trip(city, country, reason, trip_id)`** — records the chosen destination as
  `output/<trip_id>.json`. Call it again with the same `trip_id` to replace an earlier choice,
  so a correction leaves exactly one file.

## The join request

POST this to the convoAI agent endpoint. **Every credential and endpoint is a placeholder** —
replace the `<…>` and `OBFUSCATED` values with your own. `save_trip` and delegation need no
extra credentials; the only keys are your OpenAI key (GPT Live and the backend model are on the
same key) and, if you attach one, the avatar vendor's.

```
POST https://api.agora.io/api/conversational-ai-agent/v2/projects/<app-id>/join
Header: Authorization: agora token=<token>
```

```json
{
  "name": "agent-<channel>",
  "properties": {
    "channel": "<channel>",
    "token": "<rtc-token>",
    "agent_rtc_uid": "12345",
    "remote_rtc_uids": ["*"],
    "enable_string_uid": false,
    "idle_timeout": 120,
    "silence_timeout": 60,
    "parameters": { "data_channel": "rtm" },
    "advanced_features": {
      "enable_mllm": true,
      "enable_rtm": true,
      "enable_tools": true
    },
    "agent_rtm_uid": "agent_rtm",
    "rtm_token": "<rtm-token>",
    "mllm": {
      "enable": true,
      "vendor": "openai_gpt_live",
      "api_key": "sk-...OBFUSCATED...",
      "url": "wss://api.openai.com/v1/live/sessions",
      "greeting_message": "Hi! I'm GPT Live, running on Agora. Tell me what kind of weather you're after this weekend and I'll pick your getaway.",
      "params": {
        "voice": "cedar",
        "prompt": "<front-model instructions>",
        "delegation": "responses",
        "responses_model": "gpt-6-astra",
        "responses_params": {
          "instructions": "<backend-model instructions>"
        },
        "output_idle_end_ms": 1500,
        "output_buffer_ms": -1,
        "mcp_servers": [
          {
            "name": "trip-planner",
            "endpoint": "http://<MCP_HOST>:8787/mcp",
            "transport": "streamable_http",
            "timeout_ms": 30000
          }
        ]
      }
    },
    "avatar": {
      "enable": true,
      "vendor": "generic",
      "params": {
        "agora_appid": "<agora-app-id>",
        "agora_channel": "<channel>",
        "agora_token": "<avatar-rtc-token>",
        "agora_uid": "102",
        "api_base_url": "https://lemonslice.com/api/liveai/agora",
        "api_key": "<lemonslice-api-key>",
        "avatar_id": "<lemonslice-avatar-id>",
        "aspect_ratio": "1x1",
        "quality": "high",
        "version": "v1",
        "video_encoding": "H264"
      }
    }
  }
}
```

What the fields do:

- **`mllm.vendor: "openai_gpt_live"`** selects the full-duplex GPT Live front model. There is
  no `asr`, `llm` or `tts` node: the model does speech-to-speech itself.
- **`delegation: "responses"` + `responses_model`** send the reasoning and tool work to a
  separate Responses model. Prompt it through `responses_params.instructions`, separately from
  the front model's `prompt`. The front model keeps the conversation alive while it thinks.
- **`mcp_servers`** points at the server you started above. The transport spelling is
  `streamable_http` (underscore). `enable_tools` must be on, or the delegate has no tools.
- **`output_idle_end_ms`** ends the assistant's turn after 1.5 s of output silence, which keeps
  an avatar animating smoothly instead of stopping and restarting between clauses.
  **`output_buffer_ms`** is an arrival cushion: `-1` (the default here) disables it for the lowest first-audio latency, at the cost of occasional crackle if the provider's delivery jitters; raise it (for example to `1500`) for the smoothest avatar at higher latency.
- **`avatar`** is optional — drop the whole block for a voice-only agent. This one is LemonSlice
  through the generic avatar vendor, which wants the 24 kHz audio GPT Live emits by default.

### Checking that reasoning is really delegated

It is easy to build something that looks delegated but silently answers from the front model.
To prove it, set `responses_model` to a name that does not exist. If delegation is truly wired,
the agent visibly fails to answer instead of quietly falling back. Put the real model back and
the behaviour returns.

## Licence

TBD
