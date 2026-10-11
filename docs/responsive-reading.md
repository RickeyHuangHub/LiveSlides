# Responsive reading V1

Mode: `left-cover-spread`. Existing modes retain their behavior.

Every source slide is split along its vertical midpoint, including the last slide. Slide 1 left is the standalone cover, without a duplicate page or permanent white padding.

Width <= 768 CSS px or portrait orientation selects single-page reading. Desktop starts with a centered cover and opens the complete first source slide before advancing by paired spreads. Mobile reads S1_L, S1_R, S2_L, S2_R. Native image proportions are preserved. The mobile background crossfades two blurred image layers. Reading position survives viewport changes, including a remembered right half.

Default dwell is 3 seconds after the renderer returns to read state. Final dwell is 2.5 seconds without an additional regular dwell. Explicit pause persists. Manual navigation suspends autoplay for 12 seconds. Hidden tabs and publication panels suspend advance. QR export remains exclusive to the publication panel.

Verified: production build; 1280x800 cover and first spread; 390x844 single-page advance; responsive round trip preserving S1_R. Physical phone pinch zoom, safe areas and touch gesture feel require device acceptance.

Demo: `/?album=album-responsive-demo`, using a copy of existing split assets. New uploads should select the new mode. Old padded cover assets require reconversion.
