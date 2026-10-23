# Research — Reel: Automatic Cricket Highlight Generator

> Project #227 from the BTech AI project compendium ("AI-Powered Highlight Reel Generator from Sports Broadcasts"), narrowed to **T20 cricket**.

## The problem
A T20 broadcast runs about 3.5 hours, but only 40–60 deliveries in it (boundaries, wickets, near-misses) matter to a fan catching up. Turning a full match into a 3–10 minute highlight package is still mostly manual work: an editor scrubs the footage, marks in/out points around each four, six and wicket, and exports clips. Large broadcasters now automate this with proprietary AI systems. Everyone else (domestic and state T20 leagues, smaller rights-holders, university and club streams, independent content creators) either pays for a commercial tool or edits by hand, so highlights arrive late or never.

## Who has this problem
- **Digital/social team at a small rights-holder or state league** (e.g. a state premier league T20, or a regional streaming platform): they have the full broadcast but no editor free to produce highlights within minutes of the final ball.
- **Independent cricket content creators**: they make recap videos for YouTube and Instagram and spend hours per match finding and trimming moments.
- **Fans** who missed a match and want "every wicket and boundary" or "the best 5 minutes", not the 3-hour replay.

For this project the user we design for is the first one: someone who has a full match video file and wants a watchable highlight reel plus a list of key events, without manual editing.

## Why now / why us
- **Pretrained models now run on a laptop CPU.** CLIP (image–text) can recognise broadcast camera shots without training. PANNs (trained on AudioSet) recognises crowd cheering and applause. PaddleOCR/EasyOCR read on-screen score graphics. Two years ago each of these would have needed a GPU and our own training data.
- **Free ground truth exists.** [Cricsheet](https://cricsheet.org/matches/) publishes ball-by-ball data for 23,000+ matches (IPL, T20Is and most major T20 leagues) under an open licence. Every four, six and wicket is recorded per delivery, so we can measure accuracy without labelling what happened ourselves. We only add video timestamps.
- **The industry has shown it matters.** JioStar auto-generated full-match IPL 2025 highlights within minutes of each match ending, and that system reportedly won an Asia-Pacific broadcast award. WSC Sports and Magnifi sell the same capability to cricket broadcasters. The capability is valuable but locked inside proprietary products.

## What exists already

### Commercial systems (closed, proprietary)
| System | What it does for cricket | Gap for us |
|---|---|---|
| **WSC Sports** | Automated highlights for FanCode (India T20 tournaments), TVNZ and Cricket Australia (best wickets, boundaries) ([WSC/TVNZ](https://wsc-sports.com/blog/customer-spotlight/qa-how-tvnz-transformed-cricket-coverage-with-real-time-content-automation/), [FanCode](https://tech.sportbusiness.com/news/wsc-sports-adds-fancode-to-clients-using-its-ai-highlights-technology/)) | Enterprise product; no published method or accuracy |
| **Magnifi (VideoVerse)** | Auto-produced key moments for a cricket franchise; uses ball tracking to reframe clips to 9:16 ([SVG Europe](https://www.svgeurope.org/blog/headlines/magnifi-helps-cricket-game-franchise-boost-fan-engagement-with-auto-production-model-for-google-web-stories/)) | Enterprise product; closed |
| **JioStar (in-house)** | IPL 2025: full-match highlights auto-generated within minutes; follows the match delivery by delivery ([JioStar IPL 2025 report](https://cdn.jiostar.com/jiostar/wp-content/uploads/2025/08/From-Stadiums-to-Screens_-JioStars-%E2%80%98TATA-IPL-2025_-A-Year-of-Firsts-Report-Highlights-how-a-Billion-Viewers-Came.pdf), [Indian Television](https://indiantelevision.com/television/jiostar-clean-bowls-the-asia-pacific-broadcast-awards-with-a-two-trophy-haul/)) | No technical details published; confirms that delivery-by-delivery is the right unit |
| **Videograph AI** | Detected sixes and wickets and made vertical clips for YuppTV's Asia Cup coverage ([Videograph](https://www.videograph.ai/how-yupptv-used-videograph-ai-to-deliver-real-time-asia-cup-highlights-across-social-media/)) | Closed |
| **IBM Watson (Wimbledon, tennis)** | Rates each point's excitement from crowd noise, player gestures and match context (e.g. match point); human editor reviews ([The Batch](https://www.deeplearning.ai/the-batch/excitement-recognition)) | Not cricket, but it is the clearest description of the "event + excitement + context" scoring we use |

### Research
| Work | Approach | What we take / where we differ |
|---|---|---|
| **Shukla et al., CVPR Workshops 2018** — *Automatic Cricket Highlight Generation Using Event-Driven and Excitement-Based Features* ([CVF](https://openaccess.thecvf.com/content_cvpr_2018_workshops/w34/html/Shukla_Automatic_Cricket_Highlight_CVPR_2018_paper.html)) | Event cues (replays, scoreboard OCR, playfield scenes) + excitement cues (audio intensity, player celebrations). Evaluated by a user study and by overlap with official broadcaster highlights | **Closest prior work and our evaluation template.** We reuse the "event + excitement" split and the official-highlights comparison. We differ by: analysing per delivery, using modern pretrained models (CLIP, PANNs) instead of hand-crafted features, running on CPU only, evaluating against Cricsheet, and shipping a usable app |
| **Shingrakhia & Patel, ELCVIA 2022** — *Cricket Video Highlight Generation Methods: A Review* ([ELCVIA](https://raco.cat/index.php/ELCVIA/article/view/980000001010)) | Survey: methods split into event-driven and excitement-driven; recommends deep features over hand-crafted ones | Confirms the design space; our system combines both families |
| **Guntuboina et al., ELCVIA 2021** — *Deep Learning Based Automated Sports Video Summarization Using YOLO* ([ELCVIA](https://raco.cat/index.php/ELCVIA/article/view/v20-n1-guntuboina)) | Finds the scoreboard with YOLO, reads it with OCR, uses rules to time key events; soccer, cricket, kabaddi; average F1 0.979 | Shows score-graphic OCR alone is a very strong event signal. We add timing from audio and video, clip boundaries, and excitement ranking |
| **Ferdous et al., arXiv 2025** — *Automated Wicket-Taking Delivery Segmentation…Using OCR-Guided YOLOv8* ([arXiv 2510.18405](https://arxiv.org/abs/2510.18405v1)) | OCR on the scorecard finds wicket moments; YOLOv8 detects pitch and ball for trajectory analysis | Same "OCR tells us what happened" idea, but aimed at coaching analysis, not highlights. Ball tracking is out of our scope |
| **Amazon Science 2026** — *Automated cricket scene classification using vision-language model* ([Amazon Science](https://www.amazon.science/publications/automated-cricket-scene-classification-using-vision-language-model)) | Large vision-language models (zero-shot, few-shot, LoRA fine-tuned) on 30k frames from 25 matches: 90% event-marker accuracy, 98% scoreboard parsing, 95% delivery-start precision. Motivation: the existing workflow needs 45–50 min of human work per match | Independently confirms our two core sub-tasks (find delivery starts, parse the scoreboard) are the right ones. We do them with lightweight CPU models instead of large VLMs |
| **Abbas et al., IEEE DataPort 2025** — *Front Pitch View Shot Extraction…* ([DataPort](https://ieee-dataport.org/documents/front-pitch-view-shot-extraction-and-ball-tracking-cricket-using-deep-learning), [GitHub](https://github.com/KumailAbb/FPVShotDetection)) | 10,000 frames labelled "front pitch view" (bowler running in) vs other | Possible extra training/validation data for our delivery-start classifier. Licence not stated, so check before use |
| **Ramlogan et al., IConETech 2020** — *Semi-automated cricket broadcast highlight generation* ([UWI](https://uwispace.sta.uwi.edu/items/e5ed54db-4c57-4516-a23f-3bdf48c8eb98/full)) | Semi-automated cricket highlights (human in the loop) | Supports our optional review/remove-clip step |
| **Multimodal-LLM highlight work, 2024–2026** (e.g. YAMNet audio filter + Gemini for basketball, [JSAI 2026](https://pub.confit.atlas.jp/en/event/jsai2026/presentation/1Yin-A-10); commentary transcripts + LLM labels, [UNIST 2024](https://scholarworks.unist.ac.kr/handle/201301/84184)) | Pattern: a cheap filter (audio, commentary) finds candidates, then a large multimodal model judges them. Authors note large models struggle with long videos | Outside our compute budget. We follow the same "cheap filter, then judge" shape but judge with rules |

### Open-source and hobby projects
- Audio-energy highlight tutorials (e.g. [Analytics Vidhya](https://www.analyticsvidhya.com/blog/2019/09/guide-automatic-highlight-generation-python-without-machine-learning/)): loud moments are cut out. Simple, but they confuse loud commentary with real events and produce no event types.
- Commentary-keyword prototypes ([Sportlight](https://github.com/1407arjun/sportlight)) and general scoreboard-OCR tools ([ScoreSight](https://obsproject.com/forum/resources/scoresight-ocr-tool-for-scoreboards.1884)).
- We found **no open-source end-to-end cricket highlight pipeline** that combines score reading, audio and video cues with a proper evaluation.

### Datasets
- **Cricsheet**: ball-by-ball JSON/CSV for IPL, T20Is and 20+ T20 leagues; Open Data Commons Attribution licence. This is our ground truth for what happened on each ball.
- **FPV dataset** (Abbas et al.): bowler-run-up frames vs other frames.
- **No public cricket video benchmark with event timestamps exists.** We build a small one: video timestamps for each boundary and wicket in 3–5 matches. We release only the annotations, never the video.

### What existing work gets wrong or leaves out
1. **Closed.** The systems that work well are proprietary, with no published method or accuracy.
2. **Research prototypes stop at the paper.** They use older hand-crafted features, rarely release code, report narrow metrics, and don't produce a usable tool.
3. **Modern approaches need GPUs.** Vision-language models and multimodal LLMs give strong results but can't run on a student laptop.
4. **Highlights are not explained.** No tool shows why a clip was chosen.

## What we are doing differently
None of our individual components is new. What's new is the combination, the CPU-only constraint and the evaluation:
1. **The delivery as the unit of analysis.** The match is split into balls using the bowler-run-up camera shot and checked against the overs counter. Each ball is then rated.
2. **The score graphic, found automatically and read as a state machine.** The app locates the score box itself: it reads the text on a sample of frames and keeps the text that looks like a cricket score (`145/3`, `16.2`) and stays in the same place across the match. No user input and no training are needed. OCR readings become a validated match-state timeline: runs never decrease, wickets rise by at most 1, a new reading must repeat before it's accepted, DRS reversals and the innings change are detected. This tells us what happened on each ball. Audio and video tell us when it happened and how exciting it was.
3. **Cheap replay detection.** On many broadcasts the score graphic is hidden during replays. A run-up shot with the graphic hidden is a replay, not a new ball, and the number of replays after a ball measures its importance. To be checked on our footage, with logo-template matching as a fallback.
4. **CPU-only pretrained models.** CLIP to recognise camera shots (with a small classifier trained on CLIP features if needed), PANNs for crowd excitement, PaddleOCR for the score.
5. **Explainable selection.** Each clip carries its reasons (score change, crowd excitement, number of replays, match situation), shown in the UI.
6. **Rigorous, reproducible evaluation.** Event accuracy against Cricsheet, timestamp accuracy against our annotations, a test removing one signal at a time, agreement with the broadcaster's official highlights, and a small viewer survey.
7. **A usable product.** Upload a match in a web app, wait, and get the reel, an event list, an excitement chart and downloads. No settings and no manual steps.

## Rough shape of the solution
A local web app (Next.js frontend, Python FastAPI backend) where the user uploads a T20 match video and waits. A CPU pipeline finds the on-screen score box automatically, splits the match into deliveries, reads the result of each ball from the score graphic, rates each ball's excitement from crowd audio and replays, and cuts the top moments into a captioned highlight reel. The reel is shown alongside a clickable event list and an excitement-over-time chart.

## Locked decisions (from brainstorming)
| Decision | Choice |
|---|---|
| Sport / format | Cricket, **T20**, English commentary, one broadcaster's graphics for development (IPL on Star Sports by default) |
| ML approach | Pretrained models + rules. Light training is allowed where it clearly helps, e.g. a small classifier on CLIP features for the bowler-run-up view (trains in seconds on a CPU or Colab) |
| Compute | Laptop CPU + Google Colab, no dedicated GPU |
| Interface | Local web app: **Next.js** frontend + **FastAPI** backend. Upload → progress → results (reel player, event list, chart, downloads). No user input beyond the file |
| Score graphic | **Found automatically**: no manual box. If it can't be found, the reel is made from audio and video only, and drawing the box manually is a should-have fallback |
| Deployment | None. Runs locally for the demo |
| Footage | Real match videos kept locally (`data/`, gitignored); never committed or published |
| Commentary speech-to-text | **Stretch goal**, scheduled late: faster-whisper run only around candidate moments (cheap on CPU) to add commentary keywords ("six!", "gone!") as an extra excitement signal |
| Team / timeline | 2 people, 15 weeks |

## Key risks (carry into Architecture)
- **Score graphics differ between broadcasters and hide during replays and ads.** Mitigation: automatic detection based on score-like text in a fixed position, which doesn't depend on the broadcaster's style; readings are validated over time; development uses one broadcaster, tested on clips from others; audio+video-only fallback if no score box is found.
- **Automatic score-box detection fails or picks the wrong text** (e.g. a run-rate or partnership graphic). Mitigation: require the text to look like a score, stay in the same place, and change plausibly over time (runs only go up, overs advance); show the detected box on the results page.
- **The score graphic updates a few seconds after the ball.** Mitigation: timing comes from camera shots and audio; OCR only says what happened.
- **Replays from behind the bowler could be counted as new deliveries.** Mitigation: graphic-visibility check, overs-counter cross-check.
- **Commentary dominates the audio.** Mitigation: use PANNs crowd/cheer classes plus loudness compared with the last few minutes, not raw loudness.
- **CPU processing time (est. 40–60 min per match).** Mitigation: develop on 10–20 min segments; process at low resolution; process the demo match before presenting.
- **Large uploads (2–4 GB).** Mitigation: chunked upload to disk, plus a "use a local file" option.

## Open questions (for the PRD)
- Exact reel modes: target length (3 / 5 / 10 min) and "all wickets and boundaries" — anything else, e.g. wickets only?
- Should near-miss moments (dropped catches, big appeals) be in v1, or only boundaries and wickets?
- Caption design on clips (event, over.ball, score), and whether to add title/end cards.
- Which 3–5 matches to use, split into development and test.
- Success thresholds, e.g. ≥90% of boundaries and wickets found, ≥85% of clips containing the moment, under 60 min processing per match on a laptop.

---

**Exit check, the problem in 2–3 sentences:** Producing a highlight reel from a 3.5-hour T20 broadcast is manual, slow work, and the AI tools that automate it are proprietary products for large broadcasters. Reel is a locally-run, CPU-only system that splits a T20 broadcast into deliveries, reads each ball's result from the on-screen score, rates its excitement from crowd audio and replays, and assembles an explained, captioned highlight reel. It is evaluated against open ball-by-ball data.
