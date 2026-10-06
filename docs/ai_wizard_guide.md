# AI Fixture Reverse-Engineering Guide

The controller solves the challenge of generic, unbranded, or poorly documented stage lights using two AI-assisted paths:

## Path A: Documentation & Manual Lookup
If you have a manual, dipswitch sheet, or product listing:
1. Open **Fixtures & Patch** -> click **✨ Configure with AI Wizard**.
2. Select **Path A: Documentation / Spec Lookup**.
3. Paste the text into the box (e.g. `CH1: Dimmer, CH2: Red, CH3: Green, CH4: Blue`).
4. Gemini extracts the channel mapping, checks boundaries, and commits the fixture to SQLite.

## Path B: Interactive Hardware Probing (For Unknown Fixtures)
For generic unbranded fixtures with unknown channel orders:
1. Set the fixture's physical DMX dipswitch or digital display to a known start address (e.g. Address 10).
2. Enter the start channel and estimated footprint (e.g., 4 or 7 channels) in the wizard.
3. Click **Begin Interactive Probing**:
   - The wizard zeros the fixture's DMX block.
   - It raises individual or paired channels (e.g. Channel 10 to 255 to test for a Master Dimmer).
   - It prompts you with a diagnostic question: *"Did the light turn on, display a color, or move?"*
4. Type your observation (e.g., *"Turned Red"*, *"Strobe flashed"*, *"Head panned left"*).
5. The wizard continues probing until all channels are mapped.
6. Gemini synthesizes the transcript, confirms the profile, and commits it directly to your patch map.
