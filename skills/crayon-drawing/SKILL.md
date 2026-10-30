---
name: crayon-drawing
description: Crayon drawings, hand-drawn kid-style pictures or storyboards shown inline in bb chat. Use when asked for a crayon drawing or a hand-drawn picture of how something works.
---

# Crayon drawing

The drawing library, page styles, build and check already exist in this skill. Write only the scene: each panel's words and one drawing function per picture. `<skill>` below is this skill's directory.

## Steps

1. **Facts.** Readers take a drawing as settled. Base each panel on what the code, spec or thread says, and mark anything undecided on the drawing itself, for example with a sticky note.
2. **Scene.** Write `$BB_THREAD_STORAGE/reports/<name>.scene.html` in the format below. [assets/example.scene.html](assets/example.scene.html) is a complete scene to start from.
3. **Build.** `python3 <skill>/scripts/build.py $BB_THREAD_STORAGE/reports/<name>.scene.html` writes `<name>.html` beside the scene: one self-contained page.
4. **Check.** `python3 <skill>/scripts/check.py $BB_THREAD_STORAGE/reports/<name>.html` lists problems (failed drawings, text outside its picture or overlapping other text) and prints screenshot paths. Fix every listed problem. Then open every screenshot and fix whatever reads wrong: a label covered by a shape, a cramped or half-empty picture, a step that doesn't follow from the one before. Rebuild and check until the list is empty and the screenshots read right.
5. **Show.** Put `::inline-vis{source="thread-storage" file="reports/<name>.html"}` in the reply.

**Revisions** go in a new file: copy the scene to `<name>-v2.scene.html` and change the copy. The directive shows a file's current contents, so overwriting a page also changes the drawing in earlier messages.

## Scene format

A scene is an HTML fragment: a `.board` of panels, then one `crayon.draw` call.

```html
<div class="board">
  <section class="panel">
    <svg class="new" viewBox="0 0 64 30" data-draw="new" aria-hidden="true"></svg>
    <h3><b>1</b> The GC records the onsite</h3>
    <svg class="pic" viewBox="0 0 320 180" data-draw="record" role="img" aria-label="What the picture shows"></svg>
    <p>One or two plain sentences.</p>
    <span class="sticky">A caveat or open question.</span>
  </section>
  <section class="panel later">
    <h3>Still to come</h3>
    <ul><li><svg viewBox="0 0 90 56" data-draw="later-phone" aria-hidden="true"></svg>The GC gets the scorecard<small>PR 5</small></li></ul>
  </section>
</div>
<script>
crayon.draw({
  record(P) { P.house(241, 164); P.person(76, 164, { hat: YELLOW }); },
  "later-phone"(P) { P.dash = "5 4"; P.rect(30, 3, 30, 50, GRAY, 2.2); P.dash = null; },
});
</script>
```

- Every `data-draw` name needs a function in `crayon.draw`, except the built-in `new`: the NEW! badge for a panel showing something new.
- Panel numbers colour themselves. `.sticky` is a yellow note. `.later` is a dashed strip of what isn't built yet, with small 90×56 icons.
- For one big picture, use `<section class="panel wide">` and a wider viewBox such as `0 0 640 260`.

## The pen

Each drawing function gets a pen `P` that draws in the picture's viewBox units. Below, `c` is a colour, `w` a stroke width, `o` an opacity and `gap` the scribble spacing; all are optional. The colours are globals: `INK RED ORANGE YELLOW GREEN BLUE SKY PURPLE PINK BROWN GRAY PAPER TERM`.

| Kind | Calls |
| --- | --- |
| Lines | `line(x1, y1, x2, y2, c, w)`, `arrow(x1, y1, x2, y2, c, w, bend)`, `rect(x, y, width, height, c, w)`, `poly(points, c, w, closed)`, `curve(points, c, w)`, `ring(cx, cy, rx, ry, c, w)`, `stroke(svgPath, c, w, o)`. Set `P.dash = "5 4"` for dashed lines and `null` to stop. |
| Colouring in | `fill(x, y, width, height, c, o, gap)`, `blob(cx, cy, rx, ry, c, o, gap)`, `fillPoly(points, c, o, gap)`: one scribble across a convex shape. Colour in first, then draw the outline. |
| Solid | `dot(cx, cy, r, c)`, `paper(x, y, width, height, c)`: a solid card under the crayon, so text on it stays readable. |
| Text | `text(x, y, "words", size, c, { anchor: "middle" or "end", bold, wax })`. `\n` starts a new line. `wax` runs big letters through the crayon too. |
| Marks | `tick(x, y, scale, c)`, `cross(x, y, scale, c)` |
| People and things | `person(x, feetY, { hat: c, arms: [[x, y], [x, y]], sleep })`, about 80 tall. `robot(x, feetY, { arms, sleep, switch: "on" or "off", color })`, about 140 tall. `house(x, groundY, { wall, roof })`, 114 wide and 118 tall. `sun(cx, cy, r)`, `cloud(cx, cy, width, height, c)`, `clock(cx, cy, r, { hour, minute })`. `laptop(x, y, width, height, { screen })`: the screen is that rectangle. `phone(x, y, width, height, { screen })`: the screen is (x+4, y+10, width−8, height−22). `doc(x, y, width, height, { lines })`. `drum(cx, top, bottom, rx, ry, c)`: a database. |
| Speech | `bubble(cx, cy, "words", { size, to: [x, y] })` sizes itself to the words; `to` points the tail at the speaker. |
| Placing | `at("translate(x y) scale(s) rotate(deg)", () => { ... })` draws whatever the function draws, moved, scaled or turned. |
| Points | `arc(cx, cy, rx, ry, a0, a1, n)` and `pill(cx, cy, width, height)` return point lists for `fillPoly`, `curve` and `poly`. `jit(a)` is a repeatable random offset within ±a. |

## Style

- One step per panel, usually 3–6 panels, so a reader can follow without knowing the code.
- Words inside a picture are short labels at size 11–15; the caption carries the detail.
- Put `paper` behind any text that sits on top of a drawing.
