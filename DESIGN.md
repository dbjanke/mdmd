# mdmd Design Document

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
| Footnote marker | The small clickable label in the text that stands for a footnote or citation, drawn as a pill. |
| Citation | A bracketed number such as [3] in the text that refers to item 3 of a numbered source list at the end of the document. |
| Footnote popup | The floating panel showing a footnote's text when its marker is clicked. |
| Working settings | The set of style values currently in effect. |
| Theme | A named, complete copy of the style values. |
| Default theme | The built-in theme holding the initial settings. It cannot be edited, overwritten, or deleted. |
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
| Table | font family (optional), size, color, header background color, cell background color, border color, space before, space after |
| Horizontal rule | color, space before, space after |
| Footnote marker | color, background color, size |
| Footnote popup | font family, size, color, background color |

Sizes are in points (6 to 96). Spaces are in points (0 to 200). Line spacing is a multiple of the font size (0.8 to 3.0). Alignment is left, center, right, or justify. Colors are #rrggbb. Font family is any installed family name. The table's font family may be left unset, in which case table cells use the body text font. Paragraphs nested inside a list or block quote take that container's font, size, color, line spacing, and alignment; the innermost container wins. A block quote has no font or size of its own, so those come from whatever encloses it. Headings and code blocks keep their own style wherever they appear. The gap between two adjacent elements is the first element's space after plus the second element's space before.

### Themes

The working settings apply globally to every window. A theme is a name plus a complete copy of all element values. Theme names are non-empty, at most 64 characters, contain no control characters, are unique ignoring case, and cannot be "Default" (ignoring case). Leading and trailing spaces are removed. The Default theme is always available and is a plain light theme: dark gray text on white, a system sans-serif body at 11 pt with line spacing 1.4, bold headings sized at 2.0, 1.6, 1.3, 1.15, 1.0, and 0.9 times the body size, and a monospace font for code. The settings also record which theme is active. When the working settings differ from the active theme's values, the active theme is shown as modified.

### Stored state

Settings, themes, recent files, and window size persist across launches. The working settings, active theme, window size, and recent files are stored together. Each user theme is stored separately, one per theme. The logical structure is shown below with most elements abbreviated.

```json
{
  "workingSettings": {
    "page": { "background": "#ffffff" },
    "body": { "fontFamily": "Ubuntu", "size": 11, "color": "#222222", "lineSpacing": 1.4, "alignment": "left", "spaceBefore": 0, "spaceAfter": 8 },
    "h1": { "fontFamily": "Ubuntu", "size": 28, "color": "#111111", "lineSpacing": 1.2, "alignment": "left", "spaceBefore": 24, "spaceAfter": 10 }
  },
  "activeTheme": "Evening",
  "windowSize": [900, 700],
  "recentFiles": ["/home/me/notes/comps.md", "/home/me/notes/todo.md"]
}
```

A stored theme holds its name and a complete set of element values:

```json
{ "name": "Evening", "settings": { "page": { "background": "#1e1e1e" }, "body": {}, "h1": {} } }
```

Any property or element that is missing takes its Default value. In this degraded example the only stored value for H1 is its size, so every other H1 property is the Default value:

```json
{ "workingSettings": { "h1": { "size": 30 } }, "activeTheme": null, "recentFiles": [] }
```

A null active theme means the working settings are not tied to any theme. An active theme that names a theme that no longer exists is treated the same way.

### Recent files

The list holds up to 10 absolute paths, most recent first, without duplicates. A file is added, or moved to the top, each time it is opened successfully, including when it is already open and its window is brought to the front instead.

### Supported Markdown

The renderer supports CommonMark plus these GitHub-style extensions: tables with column alignment, strikethrough, task lists, autolinks, and footnotes. This covers headings (ATX and setext), paragraphs, hard line breaks, emphasis, strong text, inline code, fenced and indented code blocks, nested block quotes, nested ordered and unordered lists, horizontal rules, links, and images. Code blocks are monospace with no syntax highlighting. Task list boxes display checked or unchecked and cannot be toggled. Raw HTML is not interpreted and appears as literal text. YAML front matter at the top of a file is not displayed. Emphasis, strong text, strikethrough, and links nested more than 32 levels inside one another keep their text, but the levels past 32 lose their formatting.

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

### Citations

Some documents, such as research write-ups, cite sources with bracketed numbers instead of footnotes. When a document ends with a heading named Sources, References, Citations, or Notes (ignoring case) followed directly by a numbered list, every `[N]` in the text whose N is a number in that list, written with the digits 0 to 9, is drawn as a footnote marker showing N. Clicking it opens a popup showing list item N. The source list itself stays visible where it is. The brackets may be escaped in the source (`\[3\]`), which displays the same way.

```markdown
Reviewers praise its voice.\[1\]\[2\]

## Sources

1. [A Man Named Doll](https://example.com/doll)
2. [Help Wanted](https://example.com/help)
```

The text shows markers 1 and 2. Degraded cases: a number outside the list (`[7]` with a two-item list), a number of more than nine digits, or one written with other digits (such as Arabic-Indic or full-width digits) stays literal text. `[N]` inside inline code or link text stays literal. Without a matching heading directly before a closing numbered list, no citations are recognized. A document may use both footnotes and citations.

## UI Description

### Startup

Running `mdmd` with no argument shows the launcher window. Running `mdmd <path>` opens a document window on that file with no launcher. Several paths open one window each. Every launch starts a separate instance of the application; launches never hand files to an instance that is already running. All instances share the stored settings, themes, recent files, and window size: a change saved by one instance is never lost to another saving at the same time, and it reaches the windows of every running instance without a restart. An instance exits when its last launcher or document window closes; an open Settings dialog closes with it and does not keep it running.

### Launcher window

The window lists recent files, newest first, each showing the file name and its folder. Double-clicking an entry or pressing Enter on it opens that file. An Open File button opens a file chooser, filtered to Markdown files (.md, .markdown, .mdown) with an All files alternative. With no recent files the list is replaced by the text "No recent files", and the Open File button remains. A recent file that no longer exists is shown marked as missing. Activating it shows an error and removes the entry. When a file is opened from the launcher, that window becomes the document window. The menu bar is the same as in a document window, with items that need a document disabled.

### Document window

The window title is the file name. The content is the rendered file, scrolled to the top, read-only, with a vertical scrollbar. The user can select text with the mouse and copy it with Ctrl+C or the context menu. Copying is plain text; a footnote marker in the selection is copied as its number in brackets, such as [1], and images are left out. Ctrl+A selects all text. Menus:

| Menu | Items |
| --- | --- |
| File | Open... (Ctrl+O), Open Recent, Reload (F5), Close Window (Ctrl+W), Quit (Ctrl+Q) |
| Edit | Copy (Ctrl+C), Select All (Ctrl+A), Find... (Ctrl+F), Find Next (F3), Find Previous (Shift+F3), Settings... (Ctrl+,) |
| View | Zoom In (Ctrl++), Zoom Out (Ctrl+-), Reset Zoom (Ctrl+0) |
| Help | About mdmd |

Open... from a document window opens the chosen file in a new window. If the chosen file is already open in a window of the same instance, that window is brought to the front instead. Another instance may have the same file open in its own window. Reload re-reads the file and keeps the scroll position as closely as the new content allows. Each window remembers its size on close, and new windows open at the most recently stored size.

### Links and images

Links never open anything outside the window: no browser, no other application, and no new window, whatever the address. Links are drawn in the link style. Hovering a link shows its address, and the context menu over a link offers Copy Link Address. The one link that acts is a link to a heading in the same file, such as `[see](#key-findings)`, which scrolls to that heading. A heading's anchor is its text lowercased, with punctuation removed and spaces replaced by hyphens; a heading whose anchor repeats an earlier one gets `-1`, `-2`, and so on, in document order. The fragment in the link is matched ignoring case. A link to a heading that does not exist does nothing. The pointer shows a hand over footnote markers and over heading links that lead somewhere, and nowhere else.

A relative image path is resolved against the folder of the file being displayed. Absolute paths are used as given. Images wider than the text column are scaled down to fit, keeping their proportions, and are never scaled up. Animated images show their first frame. Images with any address other than a local file path, such as http, https, or data addresses, are not fetched and are shown as their alt text.

### Footnote popup

Clicking a footnote marker opens the popup beside the marker, showing the footnote's text with all its formatting, in the footnote popup style. Nothing inside the popup is clickable. A footnote marker or citation inside a footnote is shown as plain text in brackets, such as [2]. Links inside the popup do nothing, including heading links; each shows its address in parentheses after the link text, unless the text already is the address, so the address can be selected and copied. The popup closes on Esc, on a click anywhere outside it, or when another marker is clicked, in which case the popup for that marker opens instead. The popup stays within the screen. Long footnotes scroll inside the popup. Popup text can be selected and copied.

### Find

Ctrl+F or Edit > Find... shows a find bar at the bottom of the document window with a text field, Previous and Next buttons, a Match case checkbox, a match count such as "3 of 12", and a close button. Typing highlights every match in the document and scrolls to the first match at or after the current position. The current match is highlighted differently from the others. Enter or F3 moves to the next match and Shift+Enter or Shift+F3 to the previous, both wrapping around. With no matches the field is marked as failed and the count reads "0 of 0". Esc or the close button hides the bar and clears the highlights. Footnote text is not searched.

### Settings dialog

Settings... opens one dialog at a time per instance, from any of its windows. A theme saved or deleted in another instance appears in, or disappears from, an open dialog's drop-down right away. It has four areas.

Theme controls at the top: a drop-down listing Default and the saved themes, a Save as Theme button, and a Delete Theme button. The drop-down shows the active theme, with "(modified)" appended when the working values differ from it. When no theme is active it shows "No theme".

An element list on the left, containing the elements from the Data section. Selecting one shows its properties on the right.

Property controls on the right: a font family chooser (for the table, with a "Same as body text" option that leaves the table font unset; a stored family that is not installed is listed and marked as not installed), a numeric field for each size or spacing, a color picker with a hex field, an alignment chooser, and a checkbox for link underline. Values outside their allowed range are rejected, and the field keeps its previous value.

A live preview pane, showing a built-in sample document that contains every element: all six heading levels, body text, a link, inline code, a code block, a block quote, ordered, unordered, and task lists, a table, a horizontal rule, and a footnote marker with a sample popup. The preview updates as each control changes. The open document windows change only when Apply or OK is pressed.

Buttons: Apply saves the working values and updates every open window, in every running instance. OK does the same and closes the dialog. Cancel, or closing the dialog, discards changes made since the last Apply.

Selecting a theme in the drop-down loads all its values into the dialog; selecting Default returns to the initial values. This does not take effect in the windows until Apply or OK. Save as Theme asks for a name. A name matching an existing theme, ignoring case, asks whether to overwrite it, and an invalid name is refused with a message. The theme is saved immediately and becomes the active theme. Delete Theme, after a confirmation, removes the active user theme immediately. The dialog's values are unchanged and the active theme becomes none. Delete Theme is unavailable for the Default theme and when no theme is active. The Default theme cannot be deleted or overwritten. Saving or deleting a theme that cannot be written shows an error and changes nothing.

### Automatic reload and zoom

Automatic reload: when the displayed file changes on disk, including when an editor saves by replacing the file, the window reloads as Reload does, keeping the scroll position. If the changed file cannot be read, nothing is shown and the current content stays; an explicit Reload still reports the error.

Zoom: View > Zoom scales all text and spacing in that window by steps of 10 percent from 50 to 300 percent. Images keep their size. Zoom applies to one window and is not saved.

## Error Handling

A file given on the command line that does not exist, is a directory, or cannot be read shows an error message naming the path. If no other document window is open, the launcher window appears afterward so the application is never left without a window. When several paths are given, the failures are reported and the readable files still open.

A file larger than 20 MB is refused with an error naming the path. A file whose content cannot be displayed for any reason is refused the same way ("could not be displayed"); no window is left half-opened, and the application keeps running. A file that is not valid UTF-8 is displayed with undecodable bytes replaced by a replacement character. The file extension is not checked, so any readable file opens as Markdown.

Reload on a file that has been deleted or become unreadable shows an error and leaves the displayed content in place. Opening a recent file that no longer exists or is now a folder shows an error and removes it from the recent files.

A missing or unreadable image shows its alt text in place of the image and does not interrupt rendering. A footnote reference with no definition shows as literal text.

If the stored settings cannot be parsed, mdmd starts with Default settings. The same applies while running: if the stored settings become unreadable, every open window switches to the Default settings. The unreadable file is left untouched until the next save, when it is first renamed with a .bak suffix. Stored themes are unaffected. A stored theme that cannot be parsed, or whose name is invalid, is skipped and left untouched. An invalid value for a single property, such as an unparseable color or an out-of-range size, falls back to the Default value for that property only, and the rest of the file is honored. A stored font family that is not installed renders with the Default font for that element, and the stored value is kept. A stored recent files list that cannot be parsed is treated as empty. An invalid stored window size falls back to 900 by 700.

If settings cannot be written when Apply or OK is pressed, the dialog stays open and shows an error. The windows keep their previous appearance. If recent files or the window size cannot be written, no error is shown; the change applies until the application exits and is not stored.

Text that comes from outside the application, such as file names and paths, link addresses, image alt text, and theme names, is always shown literally in messages, tooltips, menus, and lists. It is never interpreted as formatting, links, or keyboard shortcuts, whatever characters it contains.

## Version and Scope

Version 1.0. Out of scope: editing of any kind, drag-and-drop, tabs or multiple files per window, an outline or table of contents, syntax highlighting, printing and PDF export, import and export of settings or themes, fetching remote images, and packaging or distribution.

Defaults chosen without explicit direction, to be overruled as needed: Open... from a document window opens a new window. Footnote definitions are not shown at the end of the document. Raw HTML appears as literal text and YAML front matter is hidden. Spacing between adjacent elements is additive. Remote images are not fetched. Window size is the only window state remembered; there is one stored size, set by whichever window closed last. Files over 20 MB are refused.
