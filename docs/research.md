# Research — Reel: Automatic Football Highlight Generator

> Project #227 from the BTech AI project compendium ("AI-Powered Highlight Reel Generator from Sports Broadcasts"). First narrowed to T20 cricket, re-scoped to **football** in November 2026. The cricket research is in git at tag `cricket-final`.

## The problem
A football broadcast runs about two hours, but only a few minutes of it matter to a fan catching up. Turning a full match into a 3–10 minute package is still mostly manual work: an editor scrubs the footage, marks in/out points around each goal and chance, and exports clips. Large broadcasters automate this with proprietary systems. Everyone else either pays for a commercial tool or edits by hand, so highlights arrive late or never.

## Who has this problem
- **Digital/social team at a small club, regional league or streaming platform:** they have the full broadcast but no editor free to produce highlights quickly. This is the user we design for.
- **Independent football content creators** who spend hours per match finding and trimming moments.
- **Fans** who missed a match and want the goals or "the best 5 minutes".

## Why now
- **Pretrained models run on a laptop CPU.** CLIP recognises broadcast camera shots, PANNs recognises crowd cheering, PaddleOCR reads on-screen graphics, and faster-whisper transcribes short commentary windows.
- **Ground truth and footage exist.** SoccerNet provides full broadcasts and timestamped labels, so we can measure accuracy without labelling matches ourselves.

## What exists already

### Research
| Work | Approach | What we take / where we differ |
|---|---|---|
| **Giancola et al., CVPRW 2018** — *SoccerNet* | 500 European broadcasts; spotting goals, cards and substitutions | Dataset and benchmark. Their task is to spot actions with trained models; ours is to produce a watchable, explained reel on a CPU |
| **Deliège et al., CVPRW 2021** — *SoccerNet-v2* ([paper](https://openaccess.thecvf.com/content/CVPR2021W/CVSports/papers/Deliege_SoccerNet-v2_A_Dataset_and_Benchmarks_for_Holistic_Understanding_of_Broadcast_CVPRW_2021_paper.pdf)) | 110k action labels across 17 classes, camera-shot and replay labels | **Our ground truth** |
| **Giancola et al. 2024** — *Deep learning for action spotting in association football videos* ([arXiv 2410.01304](https://arxiv.org/abs/2410.01304)) | Survey of action spotting | Confirms how crowded the field is: our contribution cannot be "detecting football events" |
| **SoccerNet-Echoes, 2024** ([arXiv 2405.07354](https://arxiv.org/abs/2405.07354)) | Whisper transcripts of SoccerNet commentary; about 48% of halves are not in English | Shows commentary is a usable signal, and that test matches must be filtered by language |
| **Raventós et al.** — *Automatic Summarization of Soccer Highlights Using Audio-visual Descriptors* ([arXiv 1411.6496](https://arxiv.org/pdf/1411.6496)) | Audio and video descriptors select shots for a summary | Closest "excitement" prior work; we use modern pretrained models and add score reading and explanations |
| **Guntuboina et al., ELCVIA 2021** — *Deep Learning Based Automated Sports Video Summarization Using YOLO* ([ELCVIA](https://raco.cat/index.php/ELCVIA/article/view/v20-n1-guntuboina)) | Finds the scoreboard with YOLO, reads it with OCR, uses rules; soccer, cricket, kabaddi | Score OCR is a strong event signal, but only for events that change the score |
| **PlayerTV, 2024** ([arXiv 2407.16076](https://arxiv.org/html/2407.16076v1)) | Open-source player-specific clips using tracking and OCR on shirt numbers | Different goal; needs tracking, which is out of our scope |

### Datasets
- **SoccerNet** ([data](https://www.soccer-net.org/data)): 500 + 50 broadcast games, six European competitions, 2014–2017, one file per half at 720p / 25 fps. Labels are public; **videos need an approved request and an NDA, per person** ([details](https://huggingface.co/datasets/SoccerNet/SoccerNet_raw_HQ)).
- **StatsBomb Open Data** ([repo](https://github.com/statsbomb/open-data)): free event data with attribution. Not used for now because SoccerNet labels are aligned to the video.

### What existing work leaves out
1. The strong systems are proprietary, with no published method or accuracy.
2. Research prototypes stop at the paper and report spotting metrics, not whether the resulting reel is any good.
3. State-of-the-art action spotting uses trained deep models and GPUs.
4. Highlights are not explained: no tool shows why a clip was chosen.

## What we are doing differently
None of the individual components is new, and football highlights are a well-studied problem. What's distinctive is the combination:
1. **CPU-only, with no training needed to run.** Pretrained models plus rules.
2. **The clock-anchored score graphic.** A running clock is an unusually strong signal for finding the graphic with no input, and gives match minutes for captions.
3. **Certain events plus ranked candidates.** Goals come from the score. Everything else is ranked from crowd audio, replays and commentary.
4. **Explainable selection.** Each clip carries its reasons, shown in the UI.
5. **Evaluated as a reel.** Beyond detection, we measure whether reel clips contain real key actions compared with a random baseline, and what each signal contributes.
6. **A usable product.** Upload a match in a web app, wait, and get the reel and event list.

## Rough shape of the solution
A local web app where the user uploads a match video and waits. A CPU pipeline finds the score graphic automatically, reads goals from it, finds other candidate moments from crowd audio and replays, types them from commentary keywords, and cuts the top moments into a captioned reel shown beside a clickable event list.

## Locked decisions
| Decision | Choice |
|---|---|
| Sport | Football, English commentary for keyword typing |
| ML approach | Pretrained models + rules; light training only for the camera-shot classifier |
| Compute | Laptop CPU, no GPU, no cloud processing of SoccerNet footage |
| Interface | Local web app. No user input beyond the file |
| Score graphic | Found automatically; audio/video-only fallback; manual box is a should-have |
| Commentary | Core signal, transcribed only around candidates |
| Footage | SoccerNet for evaluation under NDA; separate footage needed for any demo or survey |

## Key risks
- **The score graphic may not hide during replays.** Mitigation: check in slice 38 against SoccerNet's replay labels; replay detection can move to transition detection if needed.
- **Football crowds are loud all the time, so crowd probability may saturate.** Mitigation: compare with a rolling baseline, and tune on development matches.
- **Commentary keywords can mislead** ("that should have been a penalty"). Mitigation: keywords only type a moment already backed by excitement or replays.
- **The score graphic differs between broadcasters.** Mitigation: SoccerNet covers six competitions, so this is measured rather than assumed.
- **Goals are rare, so goal metrics are coarse.** Mitigation: 10 test matches rather than 2–3.
- **NDA limits on showing footage.** Mitigation: separate demo footage or written permission, tracked as a human task.
- **NDA approval time is outside our control.** Mitigation: label tooling, models and synthetic fixtures don't need footage.
- **CPU time.** Mitigation: a two-hour broadcast is shorter than a T20, and OCR ignores the clock area.

---

**Exit check, the problem in 2–3 sentences:** Producing a highlight reel from a two-hour football broadcast is manual, slow work, and the tools that automate it are proprietary products for large broadcasters. Reel is a locally-run, CPU-only system that reads goals from the on-screen score, finds other key moments from crowd audio, replays and commentary, and assembles an explained, captioned reel. It is evaluated against SoccerNet labels, including how much better its reel is than random clips.
