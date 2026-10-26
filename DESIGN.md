# mdmd Design Document

Oct 26, 2026

## Overview

mdmd is a local, single-user desktop application for Ubuntu that displays Markdown files as formatted, read-only text, like the preview pane of a Markdown editor. It has no editing capability and does not render through a web browser or an embedded browser engine. Each window shows one file. Appearance is controlled by global settings edited in a settings dialog with a live preview.

## Critical Use Case

The primary workflow is opening a Markdown file and reading it, including its footnotes.

1. The user starts mdmd with no arguments. The launcher window appears with a list of recently opened files and an Open File control.
2. The user double-clicks a recent file, or chooses Open File and picks a file in the file chooser. The launcher window becomes a document window showing the rendered file from the top.
3. The user scrolls, selects text with the mouse, and copies it with Ctrl+C.
4. The user clicks a footnote marker in the text. A popup appears next to the marker showing the footnote's text with its formatting. The user clicks elsewhere or presses Esc and the popup closes.
5. The user presses Ctrl+F, types a search term, and steps through the highlighted matches.
6. The user opens Settings, changes the H1 size and the body font, watches the live preview update, and saves the result as a named theme. All open document windows adopt the new appearance.
7. The user later runs `mdmd path/to/file.md`. A document window opens directly on that file, with no launcher.

## Glossary

| Term | Meaning |
| --- | --- |
| Document window | A window showing exactly one rendered Markdown file. |
| Launcher window | The window shown when mdmd starts without a file. It lists recent files and offers Open File. It turns into a document window when a file is opened in it. |
| Element | A kind of content that has its own style settings, such as H1, block quote, or table. The full list is in the Data section. |
| Space before / space after | Vertical space added above or below an element, in points. |
| Line spacing | The line height inside a multi-line element, as a multiple of the font size. |
| Footnote marker | The small clickable label in the text that stands for a footnote, drawn as a pill. |
| Footnote popup | The floating panel showing a footnote's text when its marker is clicked. |
| Working settings | The set of style values currently in effect. |
| Theme | A named, complete copy of the style values. |
| Factory theme | The built-in theme holding the factory settings. It cannot be edited or deleted. |
| Recent file | A file that was successfully opened before, remembered by absolute path. |

## Data

### Style settings

Style values are grouped by element. The elements and their properties are:

| Element | Properties |
| --- | --- |
| Page | background color |
| Body text | font family, size, color, line spacing, alignment, space before, space after |
| Headings H1 to H6 (six separate elements) | font family, size, color, line spacing, alignment, space before, space after |
| Links | color, underline on or off |
| Inline code | font family, size, color, background color |
| Code block | font family, size, color, background color, line spacing, space before, space after |
| Block quote | color, background color, line spacing, alignment, space before, space after |
| Lists (ordered, unordered, task) | font family, size, color, line spacing, alignment, space before, space after |
| Table | font family, size, color, header background color, cell background color, border color, space before, space after |
| Horizontal rule | color, space before, space after |
| Footnote marker | color, background color, size |
| Footnote popup | font family, size, color, background color |

Sizes are in points (6 to 96). Spaces are in points (0 to 200). Line spacing is a multiple of the font size (0.8 to 3.0). Alignment is left, center, right, or justify. Colors are #rrggbb. Font family is any installed family name. Content nested inside a list or block quote takes that container's font, size, color, line spacing, and alignment. The gap between two adjacent elements is the first element's space after plus the second element's space before.

### Themes

The working settings apply globally to every window. A theme is a name plus a complete copy of all element values. Theme names are non-empty, unique ignoring case, and cannot be "Factory". The Factory theme is a plain light theme: dark gray text on white, a system sans-serif body at 11 pt with line spacing 1.4, bold headings sized at 2.0, 1.6, 1.3, 1.15, 1.0, and 0.9 times the body size, and a monospace font for code. The settings also record which theme is active. When the working settings differ from the active theme's values, the active theme is shown as modified.

### Stored state

Settings, themes, recent files, and window size persist across launches. The logical structure is shown below with most elements abbreviated.

```json
{
  "workingSettings": {
    "page": { "background": "#ffffff" },
    "body": { "fontFamily": "Ubuntu", "size": 11, "color": "#222222", "lineSpacing": 1.4, "alignment": "left", "spaceBefore": 0, "spaceAfter": 8 },
    "h1": { "fontFamily": "Ubuntu", "size": 28, "color": "#111111", "lineSpacing": 1.2, "alignment": "left", "spaceBefore": 24, "spaceAfter": 10 }
  },
  "activeTheme": "Evening",
  "themes": { "Evening": { "page": {}, "body": {}, "h1": {} } },
  "windowSize": [900, 700],
  "recentFiles": ["/home/me/notes/comps.md", "/home/me/notes/todo.md"]
}
```

Any property or element that is missing takes its Factory value. In this degraded example the only stored value for H1 is its size, so every other H1 property is the Factory value:

```json
{ "workingSettings": { "h1": { "size": 30 } }, "activeTheme": null, "themes": {}, "recentFiles": [] }
```

A null active theme means the working settings are not tied to any theme.

### Recent files

The list holds up to 10 absolute paths, most recent first, without duplicates. A file is added, or moved to the top, each time it is opened successfully.

### Supported Markdown

The renderer supports CommonMark plus these GitHub-style extensions: tables with column alignment, strikethrough, task lists, autolinks, and footnotes. This covers headings (ATX and setext), paragraphs, hard line breaks, emphasis, strong text, inline code, fenced and indented code blocks, nested block quotes, nested ordered and unordered lists, horizontal rules, links, and images. Code blocks are monospace with no syntax highlighting. Task list boxes display checked or unchecked and cannot be toggled. Raw HTML is not interpreted and appears as literal text. YAML front matter at the top of a file is not displayed.

### Footnotes

A footnote reference in the text is drawn as a footnote marker showing a number. Numbers are assigned in order of first reference, regardless of the label used in the source. Several references to the same footnote all show the same number, and each opens that footnote's popup. Footnote definitions are not displayed at the end of the document. They are reachable only through their markers. A footnote may contain multiple paragraphs, emphasis, code, and links.

Complete example:

```markdown
The strongest pairing is Ames plus Waldman.[^1] A second note follows.[^note]

[^1]: *A Man Named Doll* (Mulholland Books, 2021), reviewed in the [Literary Review](https://example.com/review).

[^note]: First paragraph of a longer note.

    Second paragraph, indented four spaces.
```

The text shows markers 1 and 2. Clicking marker 1 shows the title in italics and the review name as a link. Clicking marker 2 shows both paragraphs.

Degraded cases:

```markdown
A claim with no definition.[^missing]

[^unused]: A definition nobody references.
```

The first line shows the literal text `[^missing]` with no marker. The unused definition appears nowhere.

## UI Description

### Startup

Running `mdmd` with no argument shows the launcher window. Running `mdmd <path>` opens a document window on that file with no launcher. Several paths open one window each. Launching mdmd while it is already running opens the new window in the running instance. The application exits when its last window closes.

### Launcher window

The window lists recent files, newest first, each showing the file name and its folder. Double-clicking an entry or pressing Enter on it opens that file. An Open File button opens a file chooser, filtered to Markdown files (.md, .markdown, .mdown) with an All files alternative. With no recent files the list is replaced by the text "No recent files", and the Open File button remains. A recent file that no longer exists is shown marked as missing. Activating it shows an error and removes the entry. When a file is opened from the launcher, that window becomes the document window. The menu bar is the same as in a document window, with items that need a document disabled.

### Document window

The window title is the file name. The content is the rendered file, scrolled to the top, read-only, with a vertical scrollbar. The user can select text with the mouse and copy it with Ctrl+C or the context menu. Ctrl+A selects all text. Menus:

| Menu | Items |
| --- | --- |
| File | Open... (Ctrl+O), Open Recent, Reload (F5), Close Window (Ctrl+W), Quit (Ctrl+Q) |
| Edit | Copy (Ctrl+C), Select All (Ctrl+A), Find... (Ctrl+F), Find Next (F3), Find Previous (Shift+F3), Settings... (Ctrl+,) |
| View | Zoom In (Ctrl++), Zoom Out (Ctrl+-), Reset Zoom (Ctrl+0) |
| Help | About mdmd |

Open... from a document window opens the chosen file in a new window. If the chosen file is already open in a window, that window is brought to the front instead. Reload re-reads the file and keeps the scroll position as closely as the new content allows. Each window remembers its size on close, and new windows open at the most recently stored size.

### Links and images

Links to http, https, and mailto addresses open in the default browser. A link to a heading within the same file scrolls to that heading. A relative link to a Markdown file opens that file in a new document window, resolved against the current file's folder. Any other relative file link opens in the system's default application for that file type. The pointer shows a hand over links and markers.

A relative image path is resolved against the folder of the file being displayed. Absolute paths are used as given. Images wider than the window are scaled down to fit and are never scaled up. Animated images show their first frame. Images with http or https addresses are not fetched and are shown as their alt text.

### Footnote popup

Clicking a footnote marker opens the popup beside the marker, showing the footnote's text with all its formatting. Links inside the popup open in the default browser. The popup closes on Esc, on a click anywhere outside it, or when another marker is clicked, in which case the popup for that marker opens instead. The popup stays within the screen. Long footnotes scroll inside the popup. Popup text can be selected and copied.

### Find

Ctrl+F or Edit > Find... shows a find bar at the bottom of the document window with a text field, Previous and Next buttons, a Match case checkbox, a match count such as "3 of 12", and a close button. Typing highlights every match in the document and scrolls to the first match at or after the current position. Enter or F3 moves to the next match and Shift+Enter or Shift+F3 to the previous, both wrapping around. With no matches the field is marked as failed and the count reads "0 of 0". Esc or the close button hides the bar and clears the highlights. Footnote text is not searched.

### Settings dialog

Settings... opens one dialog at a time, from any window. It has four areas.

Theme controls at the top: a drop-down listing Factory and the saved themes, a Save as Theme button, a Delete Theme button, and a Reset to Factory Settings button. The drop-down shows the active theme, with "(modified)" appended when the working values differ from it.

An element list on the left, containing the elements from the Data section. Selecting one shows its properties on the right.

Property controls on the right: a font family chooser, a numeric field for each size or spacing, a color picker with a hex field, an alignment chooser, and a checkbox for link underline. Values outside their allowed range are rejected, and the field keeps its previous value.

A live preview pane, showing a built-in sample document that contains every element: all six heading levels, body text, a link, inline code, a code block, a block quote, ordered, unordered, and task lists, a table, a horizontal rule, and a footnote marker with a sample popup. The preview updates as each control changes. The open document windows change only when Apply or OK is pressed.

Buttons: Apply saves the working values and updates every open window. OK does the same and closes the dialog. Cancel, or closing the dialog, discards changes made since the last Apply.

Selecting a theme in the drop-down loads all its values into the dialog. Reset to Factory Settings, after a confirmation, loads all Factory values into the dialog and makes Factory the active theme. Neither takes effect in the windows until Apply or OK. Save as Theme asks for a name. A name matching an existing theme asks whether to overwrite it, and an invalid name is refused with a message. The saved theme becomes the active theme. Delete Theme, after a confirmation, removes the selected user theme. The dialog's values are unchanged and the active theme becomes none. The Factory theme cannot be deleted or overwritten.

### Optional behaviors

Built only if the effort is low. Automatic reload: when the displayed file changes on disk, the window reloads as Reload does. Zoom: View > Zoom scales all text in that window by steps of 10 percent from 50 to 300 percent. Zoom applies to one window and is not saved.

## Error Handling

A file given on the command line that does not exist, is a directory, or cannot be read shows an error message naming the path. If no other document window is open, the launcher window appears afterward so the application is never left without a window. When several paths are given, the failures are reported and the readable files still open.

A file that is not valid UTF-8 is displayed with undecodable bytes replaced by a replacement character. The file extension is not checked, so any readable file opens as Markdown.

Reload on a file that has been deleted or become unreadable shows an error and leaves the displayed content in place.

A missing or unreadable image shows its alt text in place of the image and does not interrupt rendering. A footnote reference with no definition shows as literal text.

If the stored settings cannot be parsed, mdmd starts with Factory settings and no themes. The unreadable file is left untouched until the next save, when it is first renamed with a .bak suffix. An invalid value for a single property, such as an unparseable color or an out-of-range size, falls back to the Factory value for that property only, and the rest of the file is honored. A stored font family that is not installed renders with the Factory font for that element, and the stored value is kept. A stored recent files list that cannot be parsed is treated as empty.

If settings cannot be written when Apply or OK is pressed, the dialog stays open and shows an error. The windows keep their previous appearance.

## Version and Scope

Version 1.0. Out of scope: editing of any kind, drag-and-drop, tabs or multiple files per window, an outline or table of contents, syntax highlighting, printing and PDF export, import and export of settings or themes, fetching remote images, and packaging or distribution.

Defaults chosen without explicit direction, to be overruled as needed: Open... from a document window opens a new window. Footnote definitions are not shown at the end of the document. Raw HTML appears as literal text and YAML front matter is hidden. Spacing between adjacent elements is additive. Remote images are not fetched. Relative links to other Markdown files open in a new window. Window size is the only window state remembered.
