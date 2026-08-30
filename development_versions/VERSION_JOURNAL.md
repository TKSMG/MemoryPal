# MemoryPal Version Journal

Each version gets two short sentences. This is meant to read like a simple development journal, not a formal changelog.

## v01 Alpha - Initial Runnable PC App

This version made MemoryPal real as a runnable desktop program. It set up the first memory trainer structure with capture, review, quiz, associations, puzzles, and library ideas.

## v02 Alpha - Scaled UI Resolution

This version made the app larger and easier to read. It also added early DPI handling so the UI would look better on Windows display scaling.

## v03 Alpha - Multiple Study Bits

This version stopped treating pasted notes as one big block. It split `/n`, newlines, numbered lists, and separators into separate study bits.

## v04 Alpha - Multimedia Capture

This version moved media cues into the wider capture flow. Image and audio imports became part of study material instead of only flashcard attachments.

## v05 Beta - Modern UI Pass

This version moved the app away from a plain form layout. The dashboard cards, color, and spacing made it feel more like a modern study tool.

## v06 Beta - Removed Animation

This version removed the distracting top-right animation. The app became calmer and more suitable for learners and elderly users.

## v07 Beta - Structured Revision

This version changed shuffle into an intentional practice order. The user could revise recent items while pulling older items back into memory.

## v08 Beta - Notes And Design

This version added project notes for the memory techniques. It also started recording the design direction alongside the code.

## v09 Test - Button Scaling

This version fixed the awkward dashboard button clipping. The buttons now behave more predictably when the window is not fullscreen.

## v10 Test - Repetition And Smart Check

This version introduced start/range repetition and close-enough answer checking. The app could begin suggesting how much repetition a user might need.

## v11 Test - Native Multimedia

This version made text, image, audio, and video part of the study system. Media cues could travel with the material through different modes.

## v12 Test - Chunk Cards

This version changed capture into a study-set builder. Each study bit could become its own separate practice card.

## v13 Test - Scrollable Forms

This version made long screens scrollable. It fixed the problem where buttons could get pushed under the window.

## v14 Test - Walk-Back Repetition

This version matched the requested repetition example exactly. Start 5 and range 3 gives 5, 5-4, 5-4-3, then 3-2-1.

## v15 Beta - Polished Dashboard

This version made the dashboard and shell feel more intentional. The app became easier to scan and less like a generated interface.

## v16 Test - Prompt Answer Modes

This version changed practice around prompts, answers, reveal, and Smart Check. Repetition became open-ended instead of tied to fixed rounds.

## v17 Test - Import And Record Inputs

This version added import and recording paths for text, audio, and video. It also marks the point where a future mobile version became important for native microphone and camera recording.

## v18 Beta - Study App Polish

This version compared MemoryPal against the everyday workflow of a typical study app. It added a Focus queue, next-step dashboard guidance, direct Q/A card creation, and library filters so the app feels more useful in daily practice.

## v19 Beta - Interaction And Capture Polish

This version made the prompt-answer workflow feel more like a real app by separating question and answer entry. It also cleaned up answer panels and added a small transition when moving between sections.

## v20 Beta - Review Testing And Q/A Polish

This version made question cards more flexible by allowing optional saved answers. It also added a separate Test Lab page, visual Smart Check bucket highlights, and automatic mini-story generation.

## v21 Test - Pointer-Aware Page Scrolling

This version made scrolling feel more natural. The mouse wheel now follows the section under the pointer instead of expecting the user to hover over the scrollbar.

## v22 Beta - Test Lab Review Flow

This version made Test Lab the main place for focused review. Review and self-check quiz cards now use the separate test page instead of placing all answer controls below the prompt.

## v23 Beta - Learning App Polish

This version made MemoryPal feel closer to a complete study product. The dashboard now shows the next best action, mastery progress, daily practice guidance, hover hints, and a gentler Test Lab guide while keeping the requested feature set intact.

## v24 Beta - Accessible Repetition And Media Polish

This version made Repetition Path match the clearer Set Builder pattern by separating question/title and answer entry. It also cleaned up audio/video capture, added more practice hints, and made page changes feel smoother.

## v25 Test - Final Scroll And UX Polish

This version fixed the Repetition screen scaling problem by making it one continuous scrollable page. It also stacked the prompt and answer fields and added keyboard scrolling so the interface feels more forgiving on smaller windows.

## v26 Beta - Puzzles And Cue Menus

This version made Puzzles feel more like a real practice area by adding pair recall and missing-item recall. It also made Set Builder calmer by turning media cues into compact menu buttons instead of separate audio/video chooser dialogs.

## v27 Beta - Cue Previews, Associations, And Skeleton Loading

This version made media cues visible during testing instead of leaving them as plain file links. It also expanded Associations into a fuller memory-toolbox and replaced the page wipe with a calmer skeleton loader.

## v28 Beta - App Feel Visual Polish

This version focused on making MemoryPal feel more like a real desktop app without slowing it down. It softened the palette, improved the header, restyled controls, and added subtle hover feedback to important cards.

## v29 Beta - Page Draft Preservation

This version fixed the problem where switching pages could wipe unsaved work. It keeps page drafts in memory for capture, repetition, testing, quiz, associations, and puzzles.

## v30 Beta - Profiles, Planning, And Stats

This version made MemoryPal feel more complete as a study app instead of one local deck. It added separate profiles, study planning, progress stats, streaks, and stronger daily guidance.

## v31 Beta - Repetition Player Polish

This version made Repetition Path calmer by replacing the long generated stack with a round-by-round player. It keeps the requested 5, 5-4, 5-4-3, 3-2-1 pattern while adding progress, navigation, reveal, and Smart Check in one focused exercise.

## v32 Beta - Collapsible Navigation And Document Notes

This version made the interface easier to focus on by adding a collapsible left navigation rail and stronger scaling behavior. It also added document-note imports so PDFs, Word files, and text notes can become study bits and stay accessible as resources across study pages.

## v33 Release Candidate - Testing, Build, And Mobile Start

This version moved MemoryPal closer to something that can be tested like a real app. It added release notes, a testing checklist, Windows build files, a mobile prototype, and a few useful comments in the main desktop code.

## v34 Beta - Modern Dialogs

This version removed the remaining old-looking prompt and warning boxes from the desktop app. Profile names, recording lengths, confirmations, errors, mobile capture feedback, and applicable milestone notices now use a MemoryPal-styled modal surface.

## v35 Test - Speech-To-Text Capture

This version added a desktop speech-to-text prototype for spoken study capture. It lets dictated or transcribed text become editable question and answer cards while keeping the speech packages optional.
