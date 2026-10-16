# Google Go Style Best Practices — Strings

Building strings: `+`, `fmt.Sprintf` and `fmt.Fprintf`, `strings.Builder`, templates, and
multi-line constant strings.

### google-practices:string-concat-simple — Prefer "+" for simple cases
- **meta:** severity=consider · scope=body · check=lint+llm · lint=perfsprint~can be replaced with string concatenation,gocritic:stringConcatSimplify
- **rule:** Concatenate a few strings with `+`: it is syntactically the simplest and needs
  no import.
- **look for:** `fmt.Sprintf("%s/%s", a, b)` with several operands and no other formatting;
  a `strings.Builder` used to join two or three plain strings.
- **skip:** single-operand `fmt.Sprintf("prefix%s", s)` (perfsprint) and short
  `strings.Join([]string{a, b}, sep)` (gocritic) — linters report them; strings that need
  verbs or conversions (string-concat-fmt).
- **example:** `key := fmt.Sprintf("projectid: %s", p)` -> `key := "projectid: " + p`

### google-practices:string-concat-fmt — Prefer fmt.Sprintf when formatting
- **meta:** severity=consider · scope=body · check=lint+llm · lint=gocritic:preferFprint · custom=long-concat-chain
- **rule:** Build a complex formatted string with `fmt.Sprintf`: many `+` operators obscure
  the result. When the output goes to an `io.Writer`, write it with `fmt.Fprintf` instead of
  building a temporary string first. For even more complex formatting use `text/template` or
  `safehtml/template` as appropriate.
- **look for:** `+` chains mixing literals with `strconv.Itoa`, `.String()` or other
  conversions; `s := fmt.Sprintf(...)` used only for `w.Write([]byte(s))`; large documents
  (HTML, reports) assembled by hand that a template would express.
- **skip:** `w.Write([]byte(fmt.Sprintf(...)))`, `io.WriteString(w, fmt.Sprintf(...))` and
  `w.WriteString(fmt.Sprintf(...))` in one expression — gocritic (preferFprint) reports them.
- **example:** `src.String() + " [" + qos.String() + ":" + strconv.Itoa(mtu) + "]-> " + dst.String()` -> `fmt.Sprintf("%s [%s:%d]-> %s", src, qos, mtu, dst)`

### google-practices:string-concat-piecemeal — Prefer strings.Builder for constructing a string piecemeal
- **meta:** severity=consider · scope=body · check=lint+llm · lint=perfsprint~concatenation in a loop
- **rule:** Build a string bit by bit with `strings.Builder`: it takes amortized linear
  time, whereas `+` and `fmt.Sprintf` called repeatedly to grow a string take quadratic time.
- **look for:** `s = fmt.Sprintf("%s...", s, x)` accumulating in a loop; `+=` growth the
  linters miss (the string also read inside the loop, struct fields, globals, recursion).
- **skip:** `s += x` and `s = s + x` loops over a local string — perfsprint reports them; a
  fixed handful of concatenations.
- **example:** `for i, d := range digits { s += fmt.Sprintf("%d: %d\n", i, d) }` -> `b := new(strings.Builder); for ... { fmt.Fprintf(b, "%d: %d\n", i, d) }; s := b.String()`

### google-practices:string-constants — Constant strings
- **meta:** severity=consider · scope=body · check=llm · custom=multiline-concat-literal
- **rule:** Write constant multi-line string literals as raw strings in backticks rather
  than as concatenated quoted lines ending in `\n`.
- **look for:** chains like `"" + "Usage:\n" + "\n" + "custom_tool [args]"`; one long quoted
  literal full of `\n` holding fixed multi-line text.
- **skip:** text that contains backticks or depends on characters a raw string cannot show
  clearly (trailing spaces, tabs, `\r`); strings built from non-constant parts.
- **example:** `usage := "Usage:\n" + "\n" + "custom_tool [args]"` -> one backtick raw string spanning those lines
