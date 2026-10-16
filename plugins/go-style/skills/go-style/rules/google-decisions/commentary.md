# Google Style Decisions — Commentary

Comments for readers of Godoc: formatting and wrapping, doc comments and their sentences,
runnable examples, named result parameters, and package comments.

### google-decisions:commentary — Commentary: Godoc formatting
- **meta:** severity=consider · scope=body · check=llm
- **rule:** Comments exist for readers of the API documentation. Godoc has little special
  formatting: indent lists and code snippets so they are not rewrapped, and otherwise avoid
  decoration. Previewing the rendered docs during development and review is recommended.
- **look for:** banner or box comments (`// ======`, `/*****`); Markdown emphasis that Godoc
  shows literally (`**bold**`); code samples in doc comments that are not indented and get
  reflowed into a paragraph.
- **skip:** doc-comment syntax Godoc renders (`# Heading`, `[Name]` links, indented lists and
  code blocks).

### google-decisions:comment-line-length — Comment line length
- **meta:** severity=should · scope=body · check=llm
- **rule:** Comments have no fixed line length, but long lines should be wrapped so the source
  reads well in tools that do not wrap; 80 or 100 columns are common, not a hard limit. Do not
  break text where breaking hurts (long URLs, literal text). Be consistent within a file.
- **look for:** a whole paragraph on one line far beyond ~100 columns; a file that mixes very
  different wrap widths.
- **skip:** long URLs or literal text on their own line; lines slightly past 80 or 100.
- **example:** a 300-character comment line -> the same paragraph wrapped at about 80 columns

### google-decisions:doc-comments/exported — Doc comments: exported names
- **meta:** severity=must · scope=decl · check=lint+llm · lint=revive:exported~^(?!.*(stutters|is repetitive)),gocritic:docStub
- **rule:** Every top-level exported name must have a doc comment, written for users of the
  package: full sentences that begin with the name, optionally preceded by an article
  ("A Request represents …").
- **look for:** comments that begin with the name but tell a user nothing (restate the name,
  describe internals instead of behavior); undocumented exported names in `package main`,
  which revive skips.
- **skip:** missing or misnamed doc comments revive reports; stub comments gocritic reports;
  an article before a function or variable name — the guide allows it, revive flags it.
- **example:** `// encode the request` -> `// Encode writes the JSON encoding of req to w.`

### google-decisions:doc-comments/unexported — Doc comments: unobvious unexported code
- **meta:** severity=should · scope=body · check=llm
- **rule:** Unexported types and functions with unobvious behavior or meaning should also have
  doc comments, written like exported ones: full sentences starting with the unexported name,
  so the symbol can later be exported by renaming it in code and comment alike.
- **look for:** undocumented unexported functions or types with non-trivial contracts (side
  effects, locking or ownership expectations, surprising results); doc comments on unexported
  symbols that do not start with the symbol's name.
- **skip:** small helpers whose name and signature say everything.

### google-decisions:comment-sentences — Comment sentences
- **meta:** severity=should · scope=decl · check=lint+llm · lint=godot
- **rule:** Comments that are complete sentences are capitalized and punctuated like English
  sentences (a sentence may begin with an uncapitalized identifier, best only at the start of a
  paragraph). Doc comments are always complete sentences. Sentence fragments, such as
  end-of-line struct field comments, need neither capitals nor punctuation.
- **look for:** doc comments that are fragments or start with a lowercase ordinary word
  (`// returns the user`); multi-sentence comments missing capitals or punctuation.
- **skip:** a missing final period on declaration comments (godot reports it); end-of-line
  and field phrases (`// optional; default: 20`); sentences starting with an identifier.
- **example:** `// returns the user` -> `// User returns the user with the given ID.`

### google-decisions:examples — Examples
- **meta:** severity=consider · scope=repo · check=llm · custom=example-outside-test
- **rule:** Packages should clearly document their intended usage; try to provide runnable
  examples (`func ExampleX` in a `_test.go` file), which show up in Godoc and run as tests. If a
  runnable example is not feasible, example code in comments is fine and should follow standard
  formatting.
- **look for:** library packages with a non-obvious API and no `Example` functions; `Example`
  functions in non-test files (neither run nor shown as examples); unformatted code in comments.
- **skip:** `main` packages.

### google-decisions:named-result-parameters/clarity — Named results: when names help
- **meta:** severity=consider · scope=decl · check=lint+llm · lint=revive:confusing-results
- **rule:** Judge result names by how the signature reads in Godoc; the function name and the
  result types are often clear enough. Names help when several results share a type
  (`(left, right *Node, err error)`) or when the caller must act on a result
  (`(ctx Context, cancel func())`); a named type such as `CancelFunc` can be clearer still.
- **look for:** unnamed, undocumented results the caller must call, close or check
  (`(Context, func())`).
- **skip:** unnamed results of the same type — revive reports them.

### google-decisions:named-result-parameters/unnecessary — Named results: no needless names
- **meta:** severity=should · scope=decl · check=llm · custom=result-names-repeat-types
- **rule:** Do not name results when the names only repeat the type (`(node *Node)`), merely to
  avoid declaring a local variable, or just to enable naked returns; that buys minor
  implementation brevity with API verbosity. Naming a result that a deferred closure must change
  is always fine.
- **look for:** signatures like `(user *User, err error)` where no name adds meaning; named
  results used only as pre-declared locals or for a bare `return`.
- **skip:** results assigned in a `defer` closure; names forced because another result needs a
  name (`ctx` in `(ctx Context, cancel func())`).
- **example:** `func (n *Node) Parent() (node *Node)` -> `func (n *Node) Parent() *Node`

### google-decisions:named-result-parameters/naked-returns — Named results: naked returns
- **meta:** severity=should · scope=body · check=lint · lint=nakedret
- **rule:** Naked returns are acceptable only in small functions; once a function is
  medium-sized, return the values explicitly. Clarity beats saving a few lines.
- **skip:** functions of a handful of lines (nakedret is configured at 8 lines).
- **example:** a bare `return` closing a 30-line function -> `return n, err`

### google-decisions:package-comments — Package comments
- **meta:** severity=must · scope=repo · check=lint+llm · lint=revive:package-comments,godoclint~more than one godoc
- **rule:** A package has exactly one package comment, directly above the `package` clause with
  no blank line; in a multi-file package only one file carries it (a `doc.go` holding just the
  comment and the clause is fine). A `main` package's comment names the binary instead of the
  package ("The seed_generator command …", "Binary seed_generator …"), capitalized when the name
  is the first word.
- **look for:** `main` package comments that say "Package main …" or do not name the binary;
  file-level maintainer notes placed directly above `package`, where they become package docs
  (they belong after the imports).
- **skip:** missing or detached comments and the "Package x …" form in non-main packages
  (revive reports them); several package comments (godoclint reports them).
- **example:** `// Package main runs the server.` -> `// The apiserver command serves the API.`
