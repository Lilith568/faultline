# Meta model backends

Faultline uses Meta models at runtime. It sends HTTP requests with `httpx`; it does not depend on the OpenAI SDK and does not call the OpenAI API. "Chat Completions compatible" describes the request format, not the model provider.

## Hosted Meta Model API

The default is unchanged:

```dotenv
FAULTLINE_MODEL_BACKEND=meta
MODEL_API_KEY=your-private-meta-key
META_BASE_URL=https://api.meta.ai/v1
META_MODEL=muse-spark-1.3
META_REASONING_EFFORT=medium
```

`muse-wonder-1.0` is the other accepted hosted model. The hosted backend requires Meta's API host. Environment variables override `.env`. Never commit `.env` or paste a real key into a report.

## Optional Meta open weights

The adapter accepts an existing HTTP deployment of Muse Glimmer or Muse Spark Open. Provisioning a model server or a hosted inference account is a separate step. No weights, credentials or paid services are bundled.

For a local Glimmer deployment exposing the compatible endpoint, use:

```dotenv
FAULTLINE_MODEL_BACKEND=open_weights
META_OPEN_BASE_URL=http://127.0.0.1:11434/v1
META_OPEN_MODEL=muse-glimmer
META_OPEN_API_KEY=
META_OPEN_REASONING_EFFORT=
META_OPEN_VISION=0
META_OPEN_JSON_MODE=json_schema
```

For another deployment, set its actual base URL, model ID and key. Remote deployments require HTTPS and their own `META_OPEN_API_KEY`. The hosted Meta key is never reused for them. An unauthenticated endpoint is permitted only for a local development address. Use a trusted deployment that actually serves the named Meta checkpoint: an advertised model name alone is not independent proof of the loaded weights.

Accepted open-weight IDs:

- `muse-glimmer`
- `meta-models/Muse-Glimmer-30B`
- `meta-models/Muse-Spark-Open-816B-A42B`
- `meta-models/Muse-Spark-Open-816B-A42B-NVFP4`
- `meta/muse-spark-open`
- `meta-models/muse-spark-open-1026`

The participant guide supplied by the author specifies `meta-models/muse-spark-open-1026` for Baseten during this hackathon, replacing the general documentation's `meta-models/muse-spark-open` alias. Set `META_OPEN_MODEL` to the exact hackathon ID when using that partner deployment. Its acceptance is covered by a mocked request test only: no live Baseten request has been made, and supporting this alias alone does not establish prize qualification.

Use `json_schema` when the serving runtime supports it. For a runtime that supports JSON objects but not schemas, explicitly select `META_OPEN_JSON_MODE=json_object`; Faultline includes the schema in the request. Experiment plans still pass the same independent vocabulary and grounding validator. Unsupported or malformed output is reported and can trigger the existing rules-only fallback. Evaluation output must not count that fallback as a successful Muse run.

Image input is disabled for this backend by default because deployment capabilities vary. The diagnosis still receives the verified text evidence. Enable `META_OPEN_VISION=1` only after checking that the endpoint accepts images. The same selected Meta backend also produces optional source-based patch proposals.

Start Faultline as usual after configuring the server:

```bash
python -m faultline serve
python scripts/evaluate.py --planner meta
```

The planner name `meta` covers either selected Meta backend. Keep results from different backend/model configurations separate when comparing them.

## What is and is not verified

Automated mocked-endpoint tests cover request construction, model restrictions, credential separation, structured-output modes, image gating and failure accounting. No live open-weight endpoint or hosted Meta key was available during this revision. Do not describe this adapter as a completed live-model evaluation or proof of eligibility for an Open Weights prize. Record an actual run, its deployment and checkpoint provenance before making those claims.

Each `meta_calls` entry represents an attempted HTTP request, including failures and schema retries. `success` means the endpoint returned a parseable JSON object; the experiment validator separately determines whether its plan is accepted. Only usage values actually returned by the endpoint are recorded; unknown usage remains `null`. Call records omit request contents, keys, raw error bodies and transport exception text. Redirects are not followed.

If a response reports a model ID different from the requested ID, it is rejected instead of silently attributing the result to the requested model. Configure the exact model ID exposed by your deployment.

## Primary documentation

- [Meta: Muse Spark Open inference](https://dev.meta.ai/docs/muse-spark-open/deploy)
- [Meta: Muse Glimmer inference](https://dev.meta.ai/docs/muse-glimmer/deploy)
- [Meta: Glimmer on Together AI](https://github.com/meta-models/meta-oss-cookbook/blob/main/hosted/together-ai.md)
- [Cloudflare: Muse Spark Open model](https://developers.cloudflare.com/ai/models/meta/muse-spark-open/)

Consult the current deployment documentation for runtime versions, hardware and model-server configuration. The adapter neither provisions hardware nor substitutes another model.
