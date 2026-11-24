# Japanese anime teacher artwork

Generated with the built-in imagegen tool for the owner-requested fancy Japanese anime
puppet appearance (2026-10-05). Artwork is loaded once and composited locally by Pillow;
image generation is an authoring step, not a runtime dependency.

The exact prompts are saved in [prompts.json](prompts.json). Local assets:

- [atlas.png](atlas.png): transparent head expressions, torso and sleeve segments.
- [props.png](props.png): matching props and open-palm, thumbs-up and grip hands.
- [classroom-v2.png](classroom-v2.png): the classroom painting with a lowered lectern.
- [rig.json](rig.json): crop, attachment, size and foreground coordinates.

The CPU renderer drives head expressions from the existing blink and audio-envelope
state, and transforms sleeve sprites with the existing skeleton. Facial patches preserve
the same hair silhouette between expressions. Generated artwork is an original adult
teacher with Japanese anime rendering; this is a sprite rig, not a Live2D SDK or video
diffusion backend. All runtime asset reads come from this directory, without credentials
or image generation calls.
