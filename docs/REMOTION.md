# Remotion With Resolve AI Bridge

Remotion is a separate Node.js and React workflow for producing designed video clips. It does not extend Resolve's Python API. It is heavily recommended because coding agents can express precise timing, layout, typography, and animation more reliably in a Remotion project than through a limited set of timeline scripting calls.

## 1. Install Node.js

Install the current Node.js LTS release from https://nodejs.org/ and open a new terminal.

```bash
node --version
npm --version
```

Both commands must print versions.

## 2. Install Official Agent Skills

```bash
npx -y skills@latest add remotion-dev/skills -g -y
```

This installs the maintained Remotion skill for supported coding agents. It provides instructions about compositions, sequencing, animation, audio, and rendering.

## 3. Create a Video Project

```bash
npx create-video@latest --yes --blank my-video
cd my-video
npm install
npx remotion skills add
npm run dev
```

Keep `npm run dev` open while reviewing the composition in Remotion Studio.

## 4. Open Your Coding Agent in `my-video`

Give the agent a production brief with:

- Composition name
- Width, height, and aspect ratio
- Frame rate and total duration
- Exact text and brand spelling
- Visual reference and palette
- Required media and audio paths
- Safe margins
- Output format

Ask for a plan first, then request one revision at a time.

## 5. Verify Before Rendering

Ask the agent to:

1. Run the project's typecheck or lint script.
2. Render one representative still.
3. Open Remotion Studio.
4. Confirm the composition id, dimensions, frame rate, and duration.

## 6. Render

```bash
npx remotion render <CompositionId> out/video.mp4
```

Use the composition id registered in the project's root composition file.

## 7. Import Into Resolve

Give Resolve AI Bridge an absolute path:

```text
Import /absolute/path/to/my-video/out/video.mp4 into the current Media Pool. Inspect the timeline, tell me its frame rate and current contents, and ask where to place the rendered clip before appending it.
```

## Quality Prompt

```text
Use the official Remotion skill. Plan a concise video before coding. Use a restrained visual system, strong hierarchy, and intentional pacing. Avoid generic card grids, excessive glow, random icons, and constant motion. Keep text readable at playback size. Build reusable scene components, preview the result, and verify a still before rendering.
```

## What Skills Can and Cannot Do

The official skill improves framework knowledge and reduces guessed APIs. It does not provide footage, make creative decisions automatically, or guarantee that every generated design is good. Give clear references and review the result.