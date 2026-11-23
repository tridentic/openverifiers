// The Masterbook's page template and helper functions. The build script
// (scripts/build_masterbook.py) writes build/meta.json and expands every
// {{marker}} in the chapter sources into calls of the functions below.

#let META = json("/build/meta.json")

#let c-impl = rgb("#1b7f3b")
#let c-part = rgb("#b36b00")
#let c-plan = rgb("#5b4bb7")
#let c-ev = rgb("#5a5a5a")
#let c-num = rgb("#0b4f8a")

#let badge(s) = {
  let c = if s == "IMPLEMENTED" { c-impl } else if s == "PARTIAL" { c-part } else { c-plan }
  box(fill: c, inset: (x: 2.5pt, y: 1.2pt), outset: (y: 1pt), radius: 2pt,
    text(fill: white, size: 6.5pt, weight: "bold", font: "DejaVu Sans Mono", s))
}

// An evidence marker: where a claim can be checked.
#let ev(kind, body) = text(size: 7pt, fill: c-ev, font: "DejaVu Sans Mono",
  "[" + kind + ": " + body.replace("/", "/\u{200b}").replace("_", "_\u{200b}").replace(",", ",\u{200b}") + "]")

// A number read from reproduce.sh's output at the stamped commit.
#let num(x) = text(fill: c-num, weight: "bold", x)

#let listing(title, lang, body) = block(width: 100%, breakable: true,
  stroke: 0.5pt + luma(175), radius: 2pt, clip: false, inset: 0pt, above: 0.8em, below: 0.9em, {
  block(fill: luma(232), width: 100%, inset: (x: 5pt, y: 3pt), below: 0pt,
    text(size: 7pt, font: "DejaVu Sans Mono", fill: luma(60), "file  " + title))
  block(inset: (x: 5pt, y: 4pt), above: 0pt, width: 100%,
    text(size: 7.2pt, raw(block: true, lang: lang, body)))
})

#let runbox(cmd, code, body, note) = block(width: 100%, breakable: true,
  stroke: 0.5pt + rgb("#3d6d99"), radius: 2pt, inset: 0pt, above: 0.8em, below: 0.9em, {
  block(fill: rgb("#e3edf7"), width: 100%, inset: (x: 5pt, y: 3pt), below: 0pt,
    text(size: 7pt, font: "DejaVu Sans Mono", fill: rgb("#1d3f60"),
      "$ " + cmd + "    (exit " + str(code) + "; captured by the build)"))
  block(inset: (x: 5pt, y: 4pt), above: 0pt, width: 100%,
    text(size: 7pt, raw(block: true, body)))
  if note != "" { block(inset: (x: 5pt, bottom: 3pt), above: 0pt,
    text(size: 6.5pt, fill: luma(90), style: "italic", note)) }
})

#let figcap(caption, kind, planned, name) = [#caption #text(size: 7pt, fill: c-ev)[(#kind; figure `#name`)] #if planned { badge("PLANNED") }]

#let fig(path, caption, kind, width, planned, name) = figure(
  image(path, width: width), caption: figcap(caption, kind, planned, name), kind: image)

#let figbox(content, caption, kind, planned, name) = figure(content,
  caption: figcap(caption, kind, planned, name), kind: image)

#let side(left-title, left, right-title, right) = grid(columns: (1fr, 1fr), gutter: 6pt,
  listing(left-title, "ov", left), listing(right-title, "rawov", right))

#let note(body) = block(fill: rgb("#fff7e0"), stroke: (left: 2pt + rgb("#d9a400")),
  inset: 6pt, width: 100%, body)

#let honest(body) = block(fill: rgb("#fdecea"), stroke: (left: 2pt + rgb("#c0392b")),
  inset: 6pt, width: 100%, body)

#let book(body) = {
  set document(title: "The OpenVerifiers Masterbook", author: "OpenVerifiers (Author agent)")
  set page(paper: "a4", margin: (x: 2.1cm, top: 2.2cm, bottom: 2.4cm),
    header: context {
      if counter(page).get().first() > 1 {
        let hs = query(selector(heading.where(level: 1)).before(here()))
        let t = if hs.len() > 0 { hs.last().body } else { [] }
        set text(size: 7.5pt, fill: luma(110))
        [The OpenVerifiers Masterbook #h(1fr) #t]
        line(length: 100%, stroke: 0.3pt + luma(180))
      }
    },
    footer: context {
      set text(size: 7pt, fill: luma(90), font: "DejaVu Sans Mono")
      line(length: 100%, stroke: 0.3pt + luma(180))
      [code #META.code_commit · built from #META.head · #META.date #h(1fr) page #counter(page).display()]
    })
  set text(font: "Libertinus Serif", size: 10pt, lang: "en")
  set par(justify: true, leading: 0.58em, spacing: 0.9em)
  show raw: set text(font: "DejaVu Sans Mono")
  show raw.where(block: false): box.with(fill: luma(240), inset: (x: 1.5pt), outset: (y: 1.5pt), radius: 1pt)
  set heading(numbering: "1.1")
  show heading.where(level: 1): it => { pagebreak(weak: true); v(1em); text(size: 20pt, it); v(0.6em) }
  show heading.where(level: 2): set text(size: 13pt)
  show heading.where(level: 3): set text(size: 11pt)
  set table(stroke: 0.4pt + luma(170), inset: 4pt)
  show table: set text(size: 8pt)
  show table: set par(justify: false)
  show figure: set block(breakable: false)
  set figure(gap: 0.5em)
  show figure.caption: set text(size: 8.5pt)
  set list(indent: 0.6em)
  set enum(indent: 0.6em)
  body
}
