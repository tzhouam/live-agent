# Codex review round 4: lip sync (fixes for round lipsync3)

Your round-3 findings and what was done:
1. (major) end evidence stale after a backward move: taken as your second option -- the first chunk_end is a snapshot;
   paints after it (the slider taking the picture back into an ended chunk) are not reported, so `painted` stays
   conservative and the server's E is a lower bound in that case. Commented at the chunk_end send; recorded in the
   decision. (Re-sending evidence would change the server's ack protocol for a slider-drag corner case.)
2. (major) fallback could wait forever while renderFrame throws: the fallback now looks at `lastGoodRender` (set only
   after renderFrame returns without an error), not `lastRaf`.
3. (minor) the check did not force re-entry into an ended chunk or check the board: the page itself waits (rAF) for a
   boundary between requests, switches the offset right after it, and the check asserts the first paint after a
   backward switch is the chunk that just ended with its chunk_end already sent, and that every paint shows its own
   chunk's caption and board (trace records `board`, `shown`). Live result during a lesson: backward switches crossed
   request boundaries where both the line and the board differ; re-entered the ended chunk; caption/board correct on
   every paint; longest pause 17.9-21.3 ms.

Inlined: the page diff against HEAD, scripts/lipsync_page_check.py, the live results. Confirm the fixes, say which
earlier findings are still open (absolute zero stays open as reported), and find anything new, most severe first.
Skip style.
