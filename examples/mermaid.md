---
type: doc
title: Mermaid diagrams in mdlout
author: mdlout examples
font: Times Base 11p
page: Letter
para-indent: 0f
para-gap: 0.9v
page-headers: None
---

# Mermaid diagrams

The new `@Mermaid` passthrough macro routes ```` ```mermaid ```` fenced
code blocks through the SVG back-end's `foreignObject`, where the
browser's mermaid.js engine engraves them at view-time. Three of the
most common shapes are below; the PDF route renders each as a
placeholder.

## 1. Top-down flowchart

A four-node flowchart with a diamond decision branching to two
outcomes:

```mermaid
flowchart TD
    A[Start] --> B{Ready?}
    B -->|Yes| C[Run task]
    B -->|No| D[Wait]
    C --> E([Done])
    D --> B
```

## 2. Sequence diagram

Three actors exchanging three round-trip messages -- the canonical
"client / server / database" walk-through:

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant DB as Database
    C->>S: GET /resource
    S->>DB: SELECT row
    DB-->>S: row data
    S-->>C: 200 OK + body
```

## 3. Class diagram

A two-class relationship with one method on each side:

```mermaid
classDiagram
    class Animal {
        +String name
        +makeSound()
    }
    class Dog {
        +bark()
    }
    Animal <|-- Dog
```

In HTML mode (the default `./mdlout.py examples/mermaid.md`), each
fence engraves into vector geometry alongside the surrounding prose.
In PDF mode (`--format=pdf`), each fence renders as `[Mermaid diagram
omitted in non-SVG back-end]` -- pre-render with the `mmdc` CLI and
`![](diagram.svg)` if you need the diagrams in print.
