# Codex review round 2: lip sync (fixes for round lipsync1)

Same change as round lipsync1 (instructions and your findings are summarised here), revised. Your round-1 findings and
what was done:
1. chunk_end sent from audio `onended` with incomplete `painted`: onended now only covers a stalled render loop (sent
   at once in a hidden tab, else after 1 s + the offset); render sends chunk_end when the picture reaches the end.
2. high-pass edge spikes: each run's mean is removed and its ends mirrored before the 1 s moving average; remeasured.
3. CI / absolute zero: unrestricted bootstrap interval and main-lobe share are reported; long runs are split into 10 s
   pieces; five real speakers (Wikitongues, CC BY/BY-SA) measured with the same method as the reference for the
   method's zero (results file). The "no server-side shift" conclusion now rests on the model offset lying inside that
   reference spread.
4. offset change stranding a frame: chunks are kept until `t >= end + 0.35 s` (largest positive offset + margin); the
   draw test now requires `t >= start` (moving back produced a negative index, drawImage(undefined) threw and, since
   the loop re-armed rAF at its end, stopped the picture: found by the new check); render errors can no longer stop the
   loop (try/catch around the frame body).
5. one-refresh display term: labelled as an estimate (no page API gives photon time); the calibration covers the chain.
6. fallback clock: baseLatency + outputLatency.
7. self-referential page check: added injected-latency checks against AudioContext.currentTime (getOutputTimestamp
   reporting 250 ms, and the fallback), offset change 0 -> +300 mid-playback (no stall), stop on a new comment (nothing
   from before the stop drawn), reconnect (one render loop); tests use the 34/34/34/17 shape.
8. calibration: a second click cancels the first; beeps go straight to the destination (push-to-talk ducking only
   affects outGain); help text says to test when the teacher is quiet and after changing headsets; a devicechange
   notice when an offset is set.

Inlined: the page diff against HEAD (all lip-sync hunks), tools/av_sync.py, scripts/lipsync_page_check.py,
tests/test_av_alignment.py, the results file. Check that each fix is correct and complete, and find anything new, most
severe first: file:line or function, concrete failure scenario, severity, fix. Say explicitly if a round-1 finding is
still open. Skip style.
