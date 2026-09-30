# Codex review round 3: lip sync (fixes for round lipsync2)

Your round-2 findings and what was done:
1. (blocking) retention covered 0 -> +300 only: chunks now stay drawable until `t >= end + 2 * 0.3 + 0.05 s` (the whole
   slider swing); the page check now also moves -300 -> +300 and +300 -> -300 mid-playback (no stall, right frames).
2. (major) acknowledgment / caption state on backward moves: caption and board now follow the chunk on screen in either
   direction (`onScreen`; each queued chunk carries the board view in effect, chunk 0's header board inherited by later
   chunks; `showBoard` only when the view differs), checked per paint (caption = the line of the chunk drawn).
   `painted` evidence after chunk_end is NOT re-sent: the server uses it conservatively (QC frames restricted to painted
   ones; E = last painted frame), so frames revisited after a slider drag being absent never claims an unseen frame;
   frames skipped by a forward move are correctly absent. Say if you disagree with this disposition.
3. (major) onended fallback firing before a healthy render loop: the fallback now acks only when the tab is hidden or no
   animation frame ran for 0.5 s, re-checking every 250 ms otherwise (render sends chunk_end at the picture's end).
4. (major) absolute zero: unchanged and reported as open: no independently synchronised reference is available here; the
   decision is not to shift the server audio because the model's offset lies inside the spread of real speech measured
   the same way, and the page offers per-viewer correction.
5. (minor) wire test bypassed the transport: a new test runs WSTransport.send_chunk against a fake socket and decodes
   the header, H.264 segment and PCM with PyAV.

Inlined: the page diff against HEAD (all lip-sync hunks), scripts/lipsync_page_check.py, tests/test_av_alignment.py,
the results. Check that each fix is correct and complete and find anything new, most severe first (file:line or
function, concrete failure scenario, severity, fix). Say explicitly which earlier findings are still open. Skip style.
