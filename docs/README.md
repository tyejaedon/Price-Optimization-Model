# Documentation: start here

Start with the [project overview](../README.md): what a mentor supplies, what a quote means, and what exists today. Then run the [pipeline walkthrough notebook](../notebooks/pipeline_walkthrough.ipynb) on the **ignored local** harmonized parquet and macro lookup. It uses fixed chronological windows for dated job-budget proxies, not verified mentor rates. Research artifacts are temporary; no Firebase credentials are needed, and missing local inputs fail explicitly. See the [#93 benchmark](M9_93_Inference_Safe_Benchmark.md) for the separately documented OOT research protocol.

## Reading path

| Read | Purpose |
| --- | --- |
| [Blueprint.md](Blueprint.md) | Historical M1-M8 engineering baseline; proposed objectives are not current readiness claims |
| [Canonical architecture](architecture_blueprint%20%281%29.md) | M9-M14 target and migration decisions; consult its scope updates before interpreting proposed gates |
| [Milestones and issues](Project_Milestones_and_Issues.md) | Roadmap and historical acceptance criteria; unchecked historical boxes are not live issue states |
| [Label provenance audit](Label_Provenance_Audit_91.md) | Why job budgets/profile asking rates cannot validate mentor earnings; deferred empirical/OOT work |
| [Experimental evidence index](experiments/README.md) | Current local research evidence, assumptions and reporting conventions |

## Implementation notes

| Follow the flow | Source and supporting notes |
| --- | --- |
| Source rows -> harmonized KES/hour corpus | `src/ingest_multisource.py`, `src/ingest_platform.py`; [platform ingestion](Platform_Dataset_Ingestion.md) |
| Text/country/market information -> 53 coordinates | `src/nlp_pipeline.py`, `src/macro_arbitrage.py`; `src/metadata_enrichment.py` is optional offline ablation support |
| Corpus -> fitted components -> peer estimate | `src/train_pipeline.py`, `src/spatial_engine.py`; [diagnostics](M9_Industry_Error_Diagnostics_92.md), [inference-safe research](M9_93_Inference_Safe_Benchmark.md) |
| Request -> ownership/readiness -> quote | `src/serve.py`, `src/deployment.py`; [container configuration and trust pins](M13.2_Container_and_CI.md), [API/schema alignment](Architecture/Firestore_API_Contract_Alignment.md) |
| Stored peers -> corridor -> fee -> audit | [listing provenance](M11.1_Firestore_Listing_Peers.md), [audit behavior](M11.2_Pricing_Audit.md), [tariff policy](M11.3_Mpesa_Tariff.md) |
| Local timings and operations | [protected in-process benchmark](M10.3_Protected_Pricing_Latency.md), [local stability](M8.2_Inference_Latency_and_Operational_Stability.md), [MLOps](M8.7_MLOps_UC8_UC11.md) |

Source docstrings describe current behavior. Historical blueprints preserve their proposals. An in-process test with injected authentication/storage is not a Firebase/cloud measurement, and neither it nor a proxy-model metric proves production readiness. Live authenticated 3G round-trip measurement remains tracked by #86.

## Plain-English glossary

| Term | Meaning here |
| --- | --- |
| KES/hour | Kenyan shillings per hour; all quote rates and corridor bounds use this unit. The configured one-transfer M-Pesa fee is added once to the hourly quote; no payment is executed. |
| Nearest peer / comparable | A stored record close to the request in fitted feature space, not necessarily a verified mentor transaction. Canonical comparables require proven root listing IDs; anonymous proxy rows do not acquire invented IDs. |
| Feature / coordinate | One numeric input used for distance comparisons. Current order is 50 text coordinates, then bilateral factor, market saturation and industry-relative density: 53 total. |
| TF-IDF | A fitted vocabulary that weights words/word pairs by their frequency in descriptions and rarity in the training corpus. |
| SVD | A fitted compression of that large word representation into latent numeric axes; the 50 text positions are not 50 named skills. |
| KD-tree | A search index that retrieves nearby feature vectors within an industry partition. Sparse industries may route to `general_tech`; a missing or too-small fallback fails explicitly. |
| IDW (inverse-distance weighting) | Averaging nearby rates with more weight for closer peers: weights are proportional to `1 / (distance^2 + epsilon)` and normalized to sum to one. |
| Bilateral factor | A country-pair number derived from purchasing-power-parity (PPP) and cost-of-living lookup values. It is not a learned accuracy score or proof of fair pricing. |
| Saturation / density | Separate market-frequency inputs. Live saturation comes from the request; live density comes from the trained partition mapping. Cost-of-living overrides affect the bilateral factor, not a fourth coordinate. |
| Base / corridor / final quote | Peer-weighted rate; fee-free negotiation bounds; base plus applicable fee. The floor constrains the lower bound, not the base, and the final quote may exceed the corridor ceiling. The corridor is not a calibrated statistical confidence interval. |
| Proxy label | A substitute target such as a job's posted hourly budget or a profile's advertised rate, not observed mentor earnings. A field named `verified_rate` alone does not verify payments. |
| Artifact / manifest / pin | Saved fitted components; a file describing their hashes/schema/provenance; an expected manifest hash from a separate trusted release record. Self-hashing an arbitrary downloaded joblib bundle does not make it safe to deserialize. |
| Training / inference | Learning transforms and storing peer rates offline; applying those same frozen transforms to a new request online. Fitting on holdout rows leaks information into evaluation. |
| Out-of-time (OOT) validation | Training on earlier genuine source observations and testing on strictly later ones using a predeclared cutoff. Random stratified splits are not OOT evidence; synthetic timestamps are not empirical evidence. |
| R-squared / MAE / RMSE | Fit relative to a mean predictor (can be negative); average absolute error; root mean squared error. The latter two are KES/hour here. Good proxy scores do not establish mentor-price accuracy. |
| Firestore / Firebase UID | Google's document database; the identity returned after token verification. A mentor document may have a different ID and must bind that UID through `auth_uid`. |
| Audit | An append-only record of a successful pricing calculation, not proof of payment. Background persistence can fail after the quote response. |
| RTT / SLA | Round-trip time from client through network/service and back; a promised service level. Local in-process timings measure neither live mobile RTT nor an HTTP SLA. |

For contribution policy, read [CONTRIBUTING.md](../CONTRIBUTING.md). Keep datasets, fitted binaries, generated reports and credentials outside version control.
