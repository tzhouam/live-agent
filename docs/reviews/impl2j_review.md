**Round-8 status**

- #11 (carried): **PARTIAL** — `convert` still falls back to the director chain’s last ground-truth chain for diagnostic `LOCK` and `SPEECH_ONSET` events when no revision is supplied.
- #17: **RESOLVED** — scoring caps `observation_end` at the last presented chunk; an unobserved negative deadline is flagged.
- #18: **RESOLVED** — TFMR is censored at the actual observation end without changing a skipped or refused chain’s failure outcome.
- #19: **RESOLVED** — learned ledger entries require source lineage; the explicit curated-entry exception is documented.
- #20: **PARTIAL** — pending receipts support retries once written, but deletion commits before the receipt is written.

**New findings**

1. **Blocking — [store.py](/data/zhoutaichang/live-agent/live_agent/memory/store.py), `_forget_db` / `_write_receipt`.** The deletion transaction commits before summary regeneration and receipt creation. A crash in that interval leaves the record gone with no pending receipt. Retrying by its ID can run an empty erasure while an external recording or prompt copy survives. Write the receipt, including affected sessions and required targets, in the deletion transaction; recover pending receipts before serving sessions.

2. **Major — [adjudicate.py](/data/zhoutaichang/live-agent/live_agent/eval/adjudicate.py), `PAGE` / `_sweep_to_session`; [scoring.py](/data/zhoutaichang/live-agent/live_agent/eval/scoring.py), `_claims`.** A rater must assign every audible completion claim to a request. “I already booked your flight” when no flight was requested has no valid referent, so it cannot enter primary FCR. Allow a “no corresponding request” claim, adjudicate it as false, and include session-level claims in FCR.

3. **Major — [report.py](/data/zhoutaichang/live-agent/live_agent/eval/report.py), `condition_section` / `km_row`.** TFMR can be censored before 15 seconds, but the column labelled “deadline success” prints `events / n` while the adjacent median and RMST use Kaplan–Meier. With one chain censored at 2 seconds and another responding at 10 seconds, the displayed fraction is 50% although the product-limit estimate differs. Report the KM estimate at 15 seconds and show the raw observed fraction and early-censor count separately.

4. **Major — [adjudicate.py](/data/zhoutaichang/live-agent/live_agent/eval/adjudicate.py), `presented_segments` / `prepare` / `video_to_session`.** Video-to-session mapping assumes the MP4 contains every logged chunk in order, without checking the media against the chunk log. If recording drops a chunk, a compliant frame in a later chunk maps to an earlier session time and can cross the 15-second success boundary. Verify per-chunk media alignment against presentation hashes or timecodes, and reject a batch whose recording diverges.

5. **Major — [adjudicate.py](/data/zhoutaichang/live-agent/live_agent/eval/adjudicate.py), `_sweep_to_session`.** A swept claim’s revision is inferred from when the claim is heard, rather than the request it refers to. If the persona finishes “drink tea,” the user revises to “wave,” and a partly played old chunk says “I drank the tea,” the tool judges that claim against “wave.” Let raters select the referent revision, then validate the evidence against that revision.

**Verdict: not ready.**